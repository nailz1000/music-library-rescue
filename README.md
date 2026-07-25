# Music Library Rescue

A field guide — with tools — for reconciling a large, messy, decades-old music
library across the four places its truth lives: **the files on disk, the tags
inside them, Plex, and Lidarr/MusicBrainz**.

This is not theory. It was distilled from the rescue of a real ~31,000-file
library accumulated over 20 years from every source imaginable: rips, downloads,
staging folders, duplicate drives, three generations of taggers. Every rule in
here was paid for by a mistake that produced a **confidently wrong answer** —
including one that destroyed 56 files before the guards existed. The numbers
(fingerprint thresholds, detection cutoffs, failure rates) are measured, not
guessed.

## The five theses

1. **Diagnose the layer before touching anything.** A mess in Plex usually is
   *not* a mess on disk. Work down: is it still broken → disk → tags → Plex's
   own objects — and stop at the layer that's actually broken. Most artists
   need *nothing* (measured: 87% of 2,539 album folders had no evidence of any
   problem).
2. **One folder = one release.** Half of everything that looks like "duplicates"
   or "corruption" in Plex is two releases stacked in one folder, or one release
   split across two.
3. **Identity is decided by sound, not names.** Filenames, tags, and byte hashes
   all lie in documented ways. Acoustic fingerprinting with the right guards is
   the arbiter of "same recording?".
4. **Never lose a track.** Every deletion is a move to a recycle/quarantine
   folder; every merge is preceded by an arithmetic check; every claim of "safe
   to delete" is proven, not pattern-matched.
5. **A claim isn't a measurement.** Track totals written by a ripper, folder
   names, release dates in tags — all are claims. The guide is explicit about
   which checks *verify* and which merely *fail to find evidence*.

## The guide

| chapter | what it covers |
|---|---|
| [1 — How Plex groups music](docs/01-how-plex-groups-music.md) | The four embedded identity signals, why fixing tags doesn't fix built albums, the merge/unmatch/rebuild repair ladder, API traps |
| [2 — Diagnosing a messy artist](docs/02-diagnosing-a-messy-artist.md) | The layer model, the merge-vs-split decision table, stacked folders, box sets that only look broken |
| [3 — Duplicates and quality](docs/03-duplicates-and-quality.md) | The quality ladder and how it's miscomputed, fake hi-res/lossless detection, fingerprinting thresholds, the three guards |
| [4 — Triage at scale](docs/04-triage-at-scale.md) | Manifest-first workflow, the three-tier triage that avoids 90% of network calls, MusicBrainz by release ID |
| [5 — Lidarr](docs/05-lidarr.md) | Metadata profile economics, what "unmatched" really means, the rescan-flood/SQLite-lock failure, config-volume trap |
| [6 — Field notes](docs/06-field-notes.md) | SMB case aliases, orphan shells, running server-side, liveness checks, log-reading discipline |

## The tools

Small, dependency-light Python (`mutagen` for tags; `ffmpeg` on PATH for audio).
Each is standalone and dry-run-first. See [tools/README.md](tools/README.md).

| tool | question it answers |
|---|---|
| [`fingerprint.py`](tools/fingerprint.py) | "Are these two files the same recording?" — by sound |
| [`library_manifest.py`](tools/library_manifest.py) | "What exactly do I have?" — streaming, resumable, lock-guarded walk of every file's audio properties and tags |
| [`library_triage.py`](tools/library_triage.py) | "Where is the work?" — stacked-release and completeness triage off the manifest, zero network |

## Who this is for

Anyone with a music library big enough that "just re-rip it" isn't an answer and
"let Plex/Lidarr sort it out" has already failed. You'll get the most out of it
if you run Plex with **Prefer local metadata** and want your folder structure to
be the source of truth.

## Origin and honesty

Extracted from a live library-reconciliation project. Case studies name real
albums (AC/DC's two *High Voltage*s, Queen's *The Miracle* box, a 70-file a‑ha
anniversary set) because the specifics are what make the traps recognizable.
Where a technique failed, the failure is documented next to the fix — the
worst mistakes came from tools that were *almost* right.

## License

MIT — see [LICENSE](LICENSE).
