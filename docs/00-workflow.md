# 0 — Workflow: where to start for *your* setup

This repo's chapters go deep; this page routes you. Everything here works on
**four setups** — files only, files + Plex, files + Lidarr, or the full stack —
and the *order of operations* differs between them, which is most of what people
get wrong.

Two rules first, true for every setup:

- **The files on disk are the source of truth.** Plex and Lidarr both derive
  their view *from* the files. So you fix the disk first, then let the apps
  re-read it. Never fix an app's display by fighting the app.
- **Reversibility before judgment.** Every delete is a move to a recycle/quarantine
  folder; every tool runs dry-run first. You will change your mind about an
  obscure track three days later — make that cost a restore, not a loss.

---

## Step 0 (everyone, always): take a manifest

Before touching anything, inventory what you have. It's your baseline for
detecting loss and the input to the triage.

```
pip install mutagen          # + ffmpeg on PATH
python tools/library_manifest.py --root /path/to/Music --out manifest-$(date +%F).jsonl
```

Keep the dated file. Re-run after any bulk change and
`python tools/library_triage.py --diff old.jsonl new.jsonl` — "removed and not
a move" is your loss alarm. Details: [chapter 4](04-triage-at-scale.md).

---

## Pick your path

| you run… | go to |
|---|---|
| **Just files** (no Plex, no Lidarr) | [Path A](#path-a--files-only) |
| **Files + Plex** | [Path B](#path-b--files--plex) |
| **Files + Lidarr** | [Path C](#path-c--files--lidarr) |
| **Files + Plex + Lidarr** | [Path D](#path-d--the-full-stack) |

---

## Path A — files only

The foundation. Everything else is this plus an app on top.

1. **Manifest** (step 0).
2. **Triage** — find the ~10% that needs work without touching the 90%:
   ```
   python tools/library_triage.py --manifest manifest.jsonl --triage --csv worklist.csv
   ```
   Flags stacked releases (multiple release IDs / disagreeing track totals in
   one folder) and completeness gaps. [Chapter 4](04-triage-at-scale.md).
3. **Fix stacked folders** — one folder = one release. Split the folders the
   triage flagged; confirm shapes against MusicBrainz by release ID (Tier 2).
   [Chapter 2](02-diagnosing-a-messy-artist.md) has the merge-vs-split logic.
4. **Normalize format before de-duplicating.** A single file with a `.cue`
   sidecar is one release wearing the wrong shape — split it into per-track
   files first (`tools/cue_split.py`), or the next step's duration/
   fingerprint guards have nothing comparable to work with. Down-convert
   absurd-rate rips to a sane ceiling at the same time (`tools/to_flac.py`) —
   comparing a 384 kHz file against a 96 kHz library copy by quality ladder
   alone reports a fake "upgrade". [Chapter 3](03-duplicates-and-quality.md)
   has both procedures.
5. **De-duplicate** — where two files are the same recording, keep the better
   one. Decide "same recording?" by sound, not filename:
   ```
   python tools/fingerprint.py match <staged_dir> <library_dir>
   ```
   Then the quality ladder + the three guards (duration first!) decide the
   keeper. Two distinct masters of the same album (e.g. a CD remaster and a
   vinyl rip) are NOT duplicates — keep both, marked in the name.
   [Chapter 3](03-duplicates-and-quality.md).
6. **Re-manifest and diff** to prove you lost nothing.

That's a clean library on disk. Stop here, or add an app below.

---

## Path B — files + Plex

Do **Path A first** (a clean disk), then make Plex render it correctly. The
whole game is Plex's four embedded identity signals — read
[chapter 1](01-how-plex-groups-music.md) before the first scan.

1. **Set "Prefer local metadata"** (`respectTags`) on the music library **before
   the first scan.** A new library defaults it OFF, and that switch is what makes
   your folders matter.
2. **Fix tags before the scan builds albums.** Correcting tags does *not* fix
   albums Plex already built (chapter 1) — so get `musicbrainz_albumid`, `date`,
   `originalyear`, and embedded art right *first*, then scan. A library scanned
   before its tags were fixed needs a rebuild, not a refresh.
3. **Scan, then diagnose by layer** — a mess in Plex usually isn't a mess on
   disk. Work down: still broken? → disk → tags → Plex's own objects. Stop at the
   broken layer. [Chapter 2](02-diagnosing-a-messy-artist.md).
4. **Repair Plex objects** with the ladder — merge (stale duplicates of one
   folder) / unmatch+refresh (stale identity) / split / move-out-rebuild (track
   membership). Never the DELETE API — it removes files. [Chapter 1](01-how-plex-groups-music.md).

You do **not** need Lidarr for any of this. Plex + good tags is a complete setup.

---

## Path C — files + Lidarr

Do **Path A first**, then bring Lidarr onto the clean library.
[Chapter 5](05-lidarr.md) is the whole story; the essentials:

1. **Protect the config.** If Lidarr's `/config` is an anonymous Docker volume,
   fix that first — a container update silently wipes it (chapter 5). Bind-mount
   it to a real folder.
2. **Choose the metadata profile deliberately.** A restrictive profile (studio
   albums only) never creates compilation/soundtrack/single/live albums, so
   those files can never match — *by design*. Permissive is expensive (a huge
   "missing" wanted-list). Default restrictive, opt in per artist.
3. **Adopt the existing library.** This is the step everyone misses: **a rescan
   does not import files already on disk** — it only imports new arrivals.
   Adopting pre-existing files is a *Manual Import* / *Library Import*, not a
   rescan (chapter 5). If Lidarr shows `1/N` on every album with the files
   clearly present, they're recorded-but-unmatched ("orphans") and need Manual
   Import to link them.
4. **Mind the SQLite lock.** On some setups (Docker, btrfs, heavy concurrency)
   Lidarr throws `database is locked` and bulk imports fail. Do bulk imports on
   a *quiet* queue — stop rescans from spawning, one operation at a time.
   Chapter 5 has the recovery pattern.
5. **Reconcile before importing anything new.** Before importing a freshly
   downloaded or freshly converted rip, check whether the library already
   holds it — equal or better — rather than assuming a gap; a "partly
   matched" existing album is usually an orphaned-link problem, not a hole
   to fill with a second copy.
   [Chapter 5](05-lidarr.md#reconcile-before-importing--read-first-then-write).

Lidarr manages downloads/upgrades and metadata; it does **not** render your
library to you. If you only want a clean, browsable library, you may not need it.

---

## Path D — the full stack

Files + Lidarr + Plex. The extra difficulty is purely **ordering** — three
systems each want to own something:

> **Lidarr owns filenames and folder structure. Your tagger owns tag *content*.
> Plex groups by the tags.** Set `writeAudioTags=no` in Lidarr so it doesn't
> fight the tagger, and run taggers *after* Lidarr imports.

The sequence:

1. **Disk** — Path A. One folder = one release, deduped.
2. **Lidarr** — Path C. Adopt the library (Manual Import), let it own
   filenames/folders. Fix the config volume and profile first.
3. **Tags** — run your tagger to get the four Plex signals right (chapter 1),
   *after* Lidarr has placed the files.
4. **Plex** — Path B. `respectTags` on, scan, repair objects by layer.

### Doing it at scale (hundreds of artists)

Walk the library **per artist, in batches**. Within a batch, the disk + Plex
work (steps 1, 3, 4) parallelises fine. **The Lidarr step (2) must be serial on
a quiet queue** — concurrent Lidarr writers collide on the SQLite lock and all
fail. So: parallel-walk a batch of artists, *then* run the Lidarr adopt/re-link
for that batch one artist at a time, then start the next batch. Never fan the
Lidarr step out wide.

---

## The through-line

Whatever your setup: **fix the disk, then let each app re-read it, in the order
disk → Lidarr → tags → Plex.** Every painful failure in this repo's field notes
came from doing it in a different order — fixing an app's display while the disk
was still wrong, or letting an app import before the files were right.

*Keep this page current as the tools and chapters evolve — it's the front door.*
