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

## Start here

**[Workflow — where to start for your setup](docs/00-workflow.md)** routes you by
what you run (files only / + Plex / + Lidarr / the full stack) and gives the
ordered steps for each. Read it first; it points into the chapters below.

## The guide

| chapter | what it covers |
|---|---|
| [0 — Workflow](docs/00-workflow.md) | The front door: pick your setup, get the ordered steps, disk → Lidarr → tags → Plex |
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

## The method itself

The guide is what was learned; this is **how it was learned** — the two
registers that kept mistakes from repeating, plus full transparency about the
apparatus. Every entry below links to its full write-up.

### The playbook — 28 lessons with receipts

Each entry in [PLAYBOOK.md](PLAYBOOK.md) records a real incident: what
happened (with the numbers), the transferable rule, and its scope. Written
while the mistake stung; cited by number ever since.

| # | lesson |
|---|---|
| [L1](PLAYBOOK.md#l1--a-degraded-system-of-records-counts-are-poison-for-destructive-decisions) | A degraded system-of-record's COUNTS are poison for destructive decisions |
| [L2](PLAYBOOK.md#l2--validate-a-reproduction-against-the-targets-own-output-never-the-corpus-it-lives-in) | Validate a reproduction against the target's OWN output, never the corpus it lives in |
| [L3](PLAYBOOK.md#l3--windows-enumeration-silently-drops-paths-over-maxpath) | Windows enumeration silently drops paths over MAX_PATH |
| [L4](PLAYBOOK.md#l4--a-dry-run-that-probes-the-live-filesystem-lies-about-a-not-yet-created-target) | A dry-run that probes the live filesystem lies about a not-yet-created target |
| [L5](PLAYBOOK.md#l5--correcting-source-data-doesnt-refresh-a-cached-view-never-force-it-with-a-destructive-api) | Correcting source data doesn't refresh a cached view; never force it with a destructive API |
| [L6](PLAYBOOK.md#l6--deletions-go-through-the-stores-native-recycletrash-not-hard-delete-or-bespoke-quarantine) | Deletions go through the store's NATIVE recycle/trash, not hard-delete or bespoke quarantine |
| [L7](PLAYBOOK.md#l7--a-guard-must-be-at-least-as-deep-as-the-action-it-authorizes) | A guard must be at least as DEEP as the action it authorizes |
| [L8](PLAYBOOK.md#l8--a-new-measuring-instrument-gets-a-known-answer-control-positive-and-negative-before-its-output-is-trusted) | A new measuring instrument gets a known-answer control, positive AND negative, before its output is trusted |
| [L9](PLAYBOOK.md#l9--print-samples-next-to-aggregates-so-they-can-contradict-each-other) | Print samples next to aggregates so they can contradict each other |
| [L10](PLAYBOOK.md#l10--complete-from-a-sampled-heuristic-is-a-claim-about-the-sample) | "Complete" from a sampled heuristic is a claim about the sample |
| [L11](PLAYBOOK.md#l11--inventory-what-already-running-systems-expose-before-adding-a-dependency) | Inventory what already-running systems expose before adding a dependency |
| [L12](PLAYBOOK.md#l12--before-acting-on-a-cause-look-for-the-observation-that-would-disprove-it) | Before acting on a cause, look for the observation that would DISPROVE it |
| [L13](PLAYBOOK.md#l13--a-cacheindex-built-over-time-will-not-self-correct-when-the-data-is-fixed) | A cache/index built over time will not self-correct when the data is fixed |
| [L14](PLAYBOOK.md#l14--controls-prove-your-instrument-separates-the-controls--not-that-its-right-elsewhere) | Controls prove your instrument separates the controls — not that it's right elsewhere |
| [L15](PLAYBOOK.md#l15--a-similarity-score-computed-over-a-sample-is-silent-about-everything-outside-the-sample) | A similarity score computed over a sample is silent about everything outside the sample |
| [L16](PLAYBOOK.md#l16--size-the-parallel-unit-to-the-work-not-to-the-loop-you-happened-to-write) | Size the parallel unit to the work, not to the loop you happened to write |
| [L17](PLAYBOOK.md#l17--a-paginated-api-returns-a-page-treating-it-as-the-whole-set-invents-a-crisis) | A paginated API returns a PAGE; treating it as the whole set invents a crisis |
| [L18](PLAYBOOK.md#l18--diagnostics-must-not-destabilize-the-system-being-diagnosed) | Diagnostics must not destabilize the system being diagnosed |
| [L19](PLAYBOOK.md#l19--delete-then-recreate-is-not-atomic-a-crash-in-the-gap-leaves-nothing) | Delete-then-recreate is not atomic; a crash in the gap leaves nothing |
| [L20](PLAYBOOK.md#l20--it-picked-the-wrong-one-is-often-the-system-obeying-a-setting-you-chose) | "It picked the wrong one" is often the system obeying a setting you chose |
| [L21](PLAYBOOK.md#l21--a-filter-that-runs-before-your-expensive-check-decides-what-the-check-never-sees) | A filter that runs BEFORE your expensive check decides what the check never sees |
| [L22](PLAYBOOK.md#l22--a-guard-placed-on-the-wrong-branch-can-skip-the-exact-case-it-was-written-for) | A guard placed on the wrong branch can skip the exact case it was written for |
| [L23](PLAYBOOK.md#l23--shell-heredocs-mangle-backslash-escapes-write-code-with-a-file-tool) | Shell heredocs mangle backslash escapes; write code with a file tool |
| [L24](PLAYBOOK.md#l24--before-merging-n-things-into-one-predict-the-resulting-count-and-check-it) | Before merging N things into one, predict the resulting count and check it |
| [L25](PLAYBOOK.md#l25--a-report-that-always-flags-healthy-items-trains-you-to-skim-it) | A report that always flags healthy items trains you to skim it |
| [L26](PLAYBOOK.md#l26--hunt-failures-by-severity-not-recency-the-tail-of-a-busy-log-is-all-chatter) | Hunt failures by SEVERITY, not recency; the tail of a busy log is all chatter |
| [L27](PLAYBOOK.md#l27--validate-a-liveness-check-against-something-known-alive-before-acting-on-it-died) | Validate a liveness check against something known-alive before acting on "it died" |
| [L28](PLAYBOOK.md#l28--diagnose-from-a-fresh-measurement-not-from-the-last-thing-you-wrote) | Diagnose from a fresh measurement, not from the last thing you wrote |

### The decision register

Each entry in [DECISIONS.md](DECISIONS.md) is an intentional choice with its
reasoning, the measured cost of the alternative, a narrow scope, and a
**"revisit if"** trigger — so odd-looking choices don't get "fixed" back into
bugs, and no decision silently hardens into dogma.

| # | decision |
|---|---|
| [D1](DECISIONS.md#d1--on-disk-naming-follows-the-file-tags-not-the-managers-metadata-source) | On-disk naming follows the FILE TAGS, not the manager's metadata source |
| [D2](DECISIONS.md#d2--unknown-album-clutter-is-fixed-by-writing-tags-never-by-deleting) | "Unknown Album" clutter is fixed by WRITING tags, never by deleting |
| [D3](DECISIONS.md#d3--cleanup-trash-is-reversible-native-recycle-bin-or-a-quarantine-folder) | Cleanup "trash" is reversible: native recycle bin, or a quarantine folder |
| [D4](DECISIONS.md#d4--same-recording-is-decided-by-sound-not-filename-tags-or-bytes) | "Same recording?" is decided by SOUND, not filename, tags, or bytes |
| [D5](DECISIONS.md#d5--official-release-data-comes-from-whats-already-running-before-any-new-tool) | Official release data comes from what's ALREADY RUNNING before any new tool |
| [D6](DECISIONS.md#d6--the-restrictive-metadata-profile-is-the-default-permissive-is-opt-in-per-artist) | The restrictive metadata profile is the DEFAULT; permissive is opt-in per artist |
| [D7](DECISIONS.md#d7--upgrade-propagation-requires-three-independent-guards-the-fingerprint-alone-is-insufficient) | Upgrade propagation requires three independent guards; the fingerprint alone is insufficient |
| [D8](DECISIONS.md#d8--release-type-livestudio-is-measured-from-the-audio-not-inferred-from-names) | Release type (live/studio) is MEASURED from the audio, not inferred from names |
| [D9](DECISIONS.md#d9--the-media-server-groups-by-identity-embedded-in-files-that-identity-is-inherited-from-wherever-a-track-was-ripped) | The media server groups by identity EMBEDDED IN FILES — inherited from wherever a track was ripped |
| [D10](DECISIONS.md#d10--tags-are-fixed-before-the-scan-that-builds-album-objects) | Tags are fixed BEFORE the scan that builds album objects |
| [D11](DECISIONS.md#d11--a-distinct-release-shows-the-year-it-came-out-never-its-parents) | A distinct release shows the year IT came out, never its parent's |

### The apparatus — what all of this runs on

Full details, data-source etiquette, and the working method in
[METHOD.md](METHOD.md). The stack:

| layer | software | role |
|---|---|---|
| media server | **Plex** (`tv.plex.agents.music`, Prefer local metadata ON) | renders the library; chapter 1 |
| collection manager | **Lidarr** | download/upgrade automation; chapter 5 |
| metadata authority | **MusicBrainz** (`ws/2`, by release ID) | official release shapes |
| tag I/O | **mutagen** | all tag reads/writes, header-level audio properties |
| audio analysis | **ffmpeg** | Chromaprint fingerprints (built-in muxer), `volumedetect` measurements |

No paid services, no proprietary APIs.

**Transparency:** this project — the rescue and this repo — was a
collaboration between the library's owner (goals, disposition rules, every
judgment call, review of every dry-run plan) and **Claude (Anthropic), running
in Claude Code** (the tools, the analyses, the bulk work, most of this
prose). The AI's own mistakes are documented in the playbook rather than
sanded off — L7, L27 and L28 were all its. Commits carry
`Co-Authored-By: Claude` accordingly. [METHOD.md](METHOD.md) has the full
picture, including the per-project rules-file pattern that made the
collaboration compound instead of repeating itself.

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
