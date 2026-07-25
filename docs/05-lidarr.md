# 5 — Lidarr: what it manages, what it filters, and how it fails

Lidarr is the download/upgrade automation layer. Two framing rules keep it from
fighting the rest of the stack:

- **Division of labor**: with `writeAudioTags = no`, Lidarr owns filenames and
  folder structure; a tagger owns tag content. Run taggers after imports.
- **Lidarr is a proxy for MusicBrainz**, not a source of truth about your
  disk. When you need official release shapes and Lidarr's view is filtered or
  stale, query MusicBrainz by release ID directly (chapter 4).

## Metadata profile economics

The profile decides which release *types* Lidarr will create albums for at
all. A restrictive profile (primary **Album** + secondary **Studio** only)
means compilations, soundtracks, singles, live albums and remixes are never
created — files belonging to them **can never match, by design**.

The permissive alternative is expensive in a specific, measurable way: opting
just four heavy artists into a permissive profile created 208 monitored albums
expecting 1,955 tracks against 146 on disk — a **1,809-track "missing" list**
of bootlegs, DJ mixes and repackagings that then haunts every wanted-list and
search. A sane arrangement:

- restrictive profile as the **default**;
- permissive profile **opt-in per artist**, for artists whose libraries really
  are mostly non-studio material;
- monitoring left on for opted-in artists — Lidarr only *searches* what's
  monitored, but *matches* files regardless.

**Consequence, easy to misread:** for any artist on the restrictive profile, a
nonzero unmatched-file count is *expected*. "Files Lidarr does not manage" is
not "files that are broken", and the unmatched count is not a health signal.

## Reading Lidarr's numbers without panicking

- **A low `trackFileCount` does not mean files are missing.** An artist showing
  1/N on every album usually means *Lidarr has not indexed the files yet* — the
  disk can be complete. Distinguish "the library is wrong" from "the database
  hasn't looked". The health metric that actually works is per-album **disk
  count vs release track count** (chapter 4), which doesn't involve Lidarr's
  matching state at all.
- **The matched/wanted ratio structurally cannot reach 100%** — the denominator
  includes every track of every monitored album you don't own. Chasing it is
  chasing a mirage; watch the *trend*, and alert on *freeze*, not level.
- Check `album.releases[].media[]` before "fixing" disc folders: `CD 03`/
  `CD 04` with no CD 01/02, and an `8cm CD 02`, were both exact matches for
  their releases' medium lists (discs 1–2 were DVDs; the release really has an
  8cm CD).
- When bulk-adding artists, `monitor: "existing"` is evaluated **before the
  folder is scanned** — it monitors nothing. Use `monitor: "all"` with
  `searchForMissingAlbums: false`.

## The rescan-flood failure (SQLite `database is locked`)

The worst operational failure in the source project, diagnosed wrong twice
before it was diagnosed right. The shape:

- Symptom: matching frozen for 24+ hours; the UI spinner shows real progress
  ("Reading file 9330/13686") forever; completed downloads sit unimported.
- Mechanism: `rescanAfterRefresh = always` makes **every artist refresh queue
  its own full-library rescan**. A "refresh all artists" therefore queued 200+
  identical 40-minute rescans. Meanwhile a full-library rescan is effectively
  one giant transaction — and Lidarr's scheduled tasks write every minute, so
  sooner or later one collision throws `SQLiteException: database is locked`,
  the rescan **fails at the end and commits nothing**, and the next queued one
  starts the cycle again. Real work, thrown away at the finish line, forever.
- Why it's invisible: health checks report clean; the UI shows progress; and
  the lock errors hide below a flood of info-level log lines — **query logs by
  severity, never by "the last N lines"**, when checking for a known failure.

Fixes, in the order that actually mattered:

1. **`rescanAfterRefresh: always → afterManual`** — stop refreshes from
   multiplying rescans. This was the cause; everything else is hardening.
2. **Drain the queued duplicates** (they're `queued`, so the API can DELETE
   them; a `started` command returns 409 — restart the service to kill it).
3. **Prefer many scoped rescans over one monolithic one**: per-artist
   `RescanFolders {folders:[<artist path>]}` is a seconds-long transaction that
   a transient lock costs one artist, not the library. Note Lidarr *dedupes*
   identical queued commands — a scoped rescan submitted while a full one is
   queued may return the existing command's id.
4. If on **btrfs**, mark the config dir NOCOW (`chattr +C`, then rewrite
   existing DB files so they inherit it): copy-on-write amplifies SQLite's
   fsync cost and widens every lock window. Do it while the DB is closed.
   (Check journal mode first — the DB header at bytes 18–19 reads `2 2` when
   WAL is already on, which it likely is.)

## The anonymous-volume trap (Docker)

If Lidarr's `/config` is an **anonymous Docker volume** rather than a bind
mount, the entire configuration — database, indexers, API keys — lives in a
hash-named directory invisible to file managers and covered by no backup. A
container recreate (the thing image updates do) silently orphans it: Lidarr
comes back up healthy-looking and **empty**, which reads as "it broke" when
actually it started over. The source NAS had exactly one orphaned config from a
previous instance of this failure sitting on disk, undiagnosed.

Migration that costs nothing if it goes wrong: stop the container → copy (never
move) the volume contents to a real folder → verify (db byte size, file count,
`PRAGMA quick_check` via a read-only immutable open) → rename the old container
as a rollback → recreate with `-v /path/lidarr-config:/config` → verify
indexers/clients/root-folders via the API → only then discard the rollback.
Keep the old container's restart policy set to `no` meanwhile, or a host reboot
starts both and they fight over the port.

Two bonus finds from the same migration: a `tz=America/Los Angeles` env var —
lowercase key *and* a space — meant the container had silently run on UTC
(it's `TZ=America/Los_Angeles`); and recreating a container via the docker CLI
leaves Synology's Container Manager UI showing a stale ghost entry until the
old container is removed.
