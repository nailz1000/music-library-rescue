# Tools

Four standalone Python scripts. Requirements: Python 3.8+, `mutagen`
(`pip install mutagen`), and `ffmpeg` on PATH (fingerprinting only — it uses
the Chromaprint muxer already built into ffmpeg, so there is no separate
fpcalc/acoustid dependency).

Everything is read-only except where explicitly noted. Nothing here moves,
retags, or deletes music.

## `fingerprint.py` — is this the same recording?

    python fingerprint.py compare A.flac B.mp3
    python fingerprint.py match <staged_dir> <library_dir>

Acoustic comparison over a sliding alignment offset (the alignment is not
optional — a known same-recording pair scores 0.75 index-aligned and 0.93 with
the search). Measured thresholds: **≥ 0.85 same recording**, 0.65–0.85 related
edit/mix (human decides), < 0.65 different.

Caveat that matters: it samples the first ~120 seconds, so a radio edit can
score 1.000 against the full album version. **Always guard with duration
first** (`max(3s, 3%)`) — see [chapter 3](../docs/03-duplicates-and-quality.md).

Fingerprints are cached in `fingerprint_cache.json` next to the script, keyed
on (path, size, mtime), so repeat runs are cheap.

## `library_manifest.py` — what exactly do I have?

    python library_manifest.py --root /path/to/Music --out manifest-2026-07-24.jsonl

Streaming, resumable, lock-guarded walk of every audio file: header-derived
audio properties (no decoding), identity tags, and FLAC's built-in
decoded-audio MD5. One line of JSON per file, flushed as it goes.

Run it on the machine that owns the disks; check on it with `ps -ef`, not
`ps w` (which hides detached processes and will tell you it died when it
didn't). `--dedupe` repairs a manifest that ever got double-written.

The manifest doubles as a **loss ledger**: keep the dated file, re-scan after
any bulk operation, and diff (below). Reversibility (a recycle folder) and
detectability (a diff that names what vanished) are different properties; you
want both.

## `library_triage.py` — where is the work?

    python library_triage.py --manifest manifest-2026-07-24.jsonl --triage --csv worklist.csv
    python library_triage.py --diff manifest-OLD.jsonl manifest-NEW.jsonl

Off the manifest alone (no network): flags stacked releases (multiple release
IDs per folder, same-disc track-total conflicts, mixed album names) and
completeness gaps (files on disk vs the per-disc totals the files declare),
ranked worst-first. Handles the three traps that produce false worklists:
per-disc (not per-folder) totals, disc numbers recovered from subfolder names
when tags omit them, and ID3's `5/12`-style track field.

Output vocabulary is deliberate: folders with no findings are
**"no evidence of a problem"** — the declared totals it checks against are
claims by whoever ripped the folder, so agreement prioritizes, it does not
verify. Verification is a MusicBrainz release-by-ID lookup on the flagged ~10%
(see [chapter 4](../docs/04-triage-at-scale.md)).

`--diff` compares two manifests and reports added / changed / **moved**
(matched by FLAC's decoded-audio MD5) / **removed** — exit code 1 if anything
was removed without a matching move, which makes it usable as a guard in
scripts.

## `flac_integrity.py` — is the audio underneath actually intact?

    python flac_integrity.py /path/to/music
    python flac_integrity.py /path/to/music --decode --json findings.jsonl

Every other check here asks whether the metadata is right. This asks whether
the file decodes. The headline test needs no decoding at all: a FLAC's audio
payload cannot exceed the uncompressed size its own header implies, so anything
larger is corrupt by arithmetic. That is cheap enough to run across a whole
library, and it found a track that had been sitting unplayable for years behind
a correct title, correct track number and a file size that read as "high
quality".

Also reports ID3-prefixed FLACs (intact audio behind an ID3v2 block — cosmetic,
NOT corruption), suspiciously small files, and, counted by folder rather than
listed, files whose header carries no PCM checksum.

Read-only. `--decode` shells out to ffmpeg with a per-file timeout and closed
stdin, for the reasons in PLAYBOOK L50 and L60.
