# 4 — Triage at scale: find the 10% that needs work without touching the 90%

Per-artist spelunking doesn't scale to hundreds of artists, and the mistakes it
invites (fixing healthy folders) get worse with fatigue. The scalable shape is
**manifest first, then tiers of increasingly expensive checks** — designed so
each tier clears most of what reaches it.

Measured on the source library (31,580 files, 2,539 album folders, 338
artists): Tier 0 flagged 3.7% of folders, Tier 1 another 9.1%, and **87.3% had
no evidence of any problem** — so only ~13% ever needed a network call, and
none of the triage touched the files.

## Step 0: the manifest

One streaming walk of the library recording, per file: path, size, mtime,
duration, sample rate, bit depth, codec, and the full identity tags (artist,
albumartist, album, date, originaldate/year, release MBID, disc, track,
tracktotal, disctotal). [`tools/library_manifest.py`](../tools/library_manifest.py).

Design points that were each paid for:

- **Stream JSONL and flush as you go.** A first version printed a summary at
  the end, died 20 minutes in, and left an empty file — no partial results, no
  clue where it stopped.
- **Resume by re-reading the manifest** — a death costs only the files since
  the last flush.
- **Take an exclusive lock (O_EXCL pidfile).** Two copies once ran against one
  manifest — because a broken liveness check said the first had died — and
  wrote 1,265 duplicate records. A second run must refuse to start.
- **Read headers, not decodes.** mutagen reads duration/rate/depth from file
  headers for free; a decode-based hash of 31k files costs hours.
- **FLAC gives you a real content hash for free**: STREAMINFO carries the MD5
  of the *decoded audio* (`pcm_md5`). Record it — it's what lets a later diff
  distinguish a *moved* file from a *lost* one. MP3 has no equivalent; say so
  rather than papering over it.
- The manifest is a **ledger, not a backup**: it makes loss *detectable and
  attributable* (recycle folders make it *reversible* — different property).
  Re-run after any bulk operation and diff; "removed and not in recycle" is a
  red alert, "removed here + added there with the same pcm_md5" is a move.
- **Calibrate against a slice you've verified by hand** before trusting
  library-wide numbers (the source run checked its A-artists total against an
  independently verified count).

## Tier 0 — stacked releases (free, no network)

Per album folder, off the manifest alone:

- **more than one distinct release MBID** — with a substantial minority
  (≥3 files or ≥25%); a lone foreign ID is one contaminated file, not a second
  release;
- files on the **same disc** disagreeing about the declared track total;
- disagreeing `album` names.

This fires **even when Plex happens to render the folder as one album** — a
per-artist visual pass only catches the stacks Plex chose to split, which is a
sampling bias you won't notice from inside it.

## Tier 1 — completeness (free, no network)

Files on disk vs the track total the files themselves declare. Three reader
traps produced wildly wrong numbers before the logic was right:

1. **`tracktotal` is per-DISC, not per-album.** A 2-disc set declaring 15 and
   10 is consistent, not conflicted. Compared folder-wide, every multi-disc
   album reads as stacked (42 flagged; 30 were fine).
2. **The disc number is often missing from tags.** One 17-file 2-disc release
   had no `discnumber` anywhere; totals of "10" and "7" then look like a
   conflict. Fall back to the numbered subfolder (`CD 02`,
   `Digital Media 02`, `12 Vinyl 02` all end in the disc number).
3. **ID3 stores the total inside the track field** (`5/12`). Reading only a
   `tracktotal` tag reported a third of folders as "declares nothing"; the
   real figure was under 5%.

**Tier 1 agreement is a prioritizer, not a verifier.** The total is a claim
written by whoever ripped the folder; a folder missing tracks whose tag was
written from that same incomplete rip agrees with itself and looks clean.
Report agreement as *no evidence of a problem* — never as *verified correct*.

## Tier 2 — authoritative, MusicBrainz by release ID (~10% of folders)

Your files already carry `musicbrainz_albumid`, so skip name-search entirely
and fetch releases **by ID**:

    GET https://musicbrainz.org/ws/2/release/<mbid>?fmt=json&inc=media+release-groups

That returns title, per-medium track counts and formats, and the
release-group's primary type (album/single/soundtrack/live) — everything needed
to say "this folder matches an official release shape" or "this folder is
stacked/incomplete", including for release types a Lidarr metadata profile
filters out.

Operational reality, measured: ~0.4 requests/sec sustained, with 503s even at
1.1s spacing. Pace ~1 req/sec, retry with backoff, and **cache by release ID on
disk** so re-runs are free. A few hundred flagged folders is minutes; verifying
everything is a one-time couple of hours.

Report a folder with no confident release match as **UNKNOWN, never as a
defect** — "nobody has looked" and "the library is wrong" must stay
distinguishable, or the worklist fills with false accusations that erode trust
in the real ones.

## Running long scans without lying to yourself

- Run bulk file work **on the machine that owns the disks** (SSH into the NAS,
  not across SMB): a tag sweep measured 27 seconds server-side vs ~10 minutes
  over the mount; 4,200 file moves took seconds vs ~30 minutes.
- Detach with `nohup`/`setsid`, and check liveness with `ps -ef` / `pgrep` —
  **`ps w` lists only processes with a controlling terminal**, so it reports
  every detached scan as dead. Acting on that false verdict is how the
  double-writer incident above happened. Validate a liveness probe against a
  process you *know* is running before believing "it died".
- Parallelize with **one flat worker pool over all files**, never a pool per
  album — a nested pool idles most workers on a 12-track album and pays setup
  per album. Measure the plateau (the source library saturated SMB at ~8.5
  ffmpeg calls/sec; more workers bought nothing).
- Long enumerations on Windows must handle **paths over 260 chars** (`\\?\`
  prefix) — the default APIs silently drop them, and "silently" means your
  "complete" plan is quietly missing files.
