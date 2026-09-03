# Tools

Six standalone Python scripts. Requirements: Python 3.8+, `mutagen`
(`pip install mutagen`), and `ffmpeg` on PATH (used for fingerprinting via
its built-in Chromaprint muxer — no separate fpcalc/acoustid dependency —
and for the split/transcode tools' actual audio work).

Everything is read-only except `cue_split.py` and `to_flac.py`, which write
new files but never touch a source file — both are dry-run by default and
only write under `--apply`.

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

## `cue_split.py` — split a single-file album image into per-track FLACs

    python cue_split.py --folder "path/to/rip"                 # dry run, auto-picks the cue
    python cue_split.py --cue "Side A.cue" --apply --verify

For the "one file per vinyl side + a `.cue`" shape. Cuts at sample-accurate
boundaries derived from the cue's `INDEX MM:SS:FF` frames, re-encodes to
FLAC, and (`--verify`) proves the split bit-perfect by comparing decoded-PCM
MD5s of the concatenated output against the original. Writes only under
`<cue dir>/split` (or `--outdir`); the source is never modified. Full method
and the two silent-no-op traps it guards against:
[chapter 3](../docs/03-duplicates-and-quality.md) and PLAYBOOK L30.

## `to_flac.py` — down-convert hi-res/lossless-container rips to a sane ceiling

    python to_flac.py --folder "path/to/rip"            # dry run
    python to_flac.py --folder "path/to/rip" --apply    # writes <folder>/flac/

Transcodes WavPack/WAV/APE/AIFF sources to FLAC, capping at 96 kHz / 24-bit
(never inflating a 16-bit source). The discarded band above that ceiling is
noise for an analog-sourced rip, not music — see
[chapter 3](../docs/03-duplicates-and-quality.md) and DECISIONS D13. Every
output is verified for rate/depth/duration before being counted as done.
Also useful as a pre-step for `cue_split.py`, which reads FLAC/WAV/APE/
WavPack sources by name.
