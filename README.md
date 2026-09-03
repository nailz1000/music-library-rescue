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
   which checks *verify* and which merely *fail to find evidence*. The
   corollary is the most expensive lesson here (L49): a check that **cannot do
   its job** must never return what a check that **found nothing** returns.
   Silence is indistinguishable from success, and every tool in this guide that
   ever produced a confidently wrong answer failed in that direction.

## Start here

**[Workflow — where to start for your setup](docs/00-workflow.md)** routes you by
what you run (files only / + Plex / + Lidarr / the full stack) and gives the
ordered steps for each. Read it first; it points into the chapters below.

## The guide

| chapter | what it covers |
|---|---|
| [0 — Workflow](docs/00-workflow.md) | The front door: pick your setup, get the ordered steps, disk → Lidarr → tags → Plex |
| [1 — How Plex groups music](docs/01-how-plex-groups-music.md) | The four embedded identity signals plus `album_artist` (the compilation-shatter bug), why fixing tags doesn't fix built albums, CD-vs-vinyl same-tile rendering, the merge/unmatch/rebuild repair ladder, API traps |
| [2 — Diagnosing a messy artist](docs/02-diagnosing-a-messy-artist.md) | The layer model, the merge-vs-split decision table, stacked folders, box sets that only look broken, a shattered compilation masquerading as several artists |
| [3 — Duplicates and quality](docs/03-duplicates-and-quality.md) | The quality ladder and how it's miscomputed, fake hi-res/lossless detection, fingerprinting thresholds, the three guards, splitting a cue-referenced album image, down-converting hi-res rips |
| [4 — Triage at scale](docs/04-triage-at-scale.md) | Manifest-first workflow, the three-tier triage that avoids 90% of network calls, MusicBrainz by release ID |
| [5 — Lidarr](docs/05-lidarr.md) | Metadata profile economics, what "unmatched" really means, the rescan-flood/SQLite-lock failure, config-volume trap, which copy of two masters the manager tracks, reconciling before importing a new rip |
| [6 — Field notes](docs/06-field-notes.md) | SMB case aliases, orphan shells, running server-side, liveness checks, log-reading discipline |

## The tools

Small, dependency-light Python (`mutagen` for tags; `ffmpeg` on PATH for audio).
Each is standalone and dry-run-first. See [tools/README.md](tools/README.md).

| tool | question it answers |
|---|---|
| [`fingerprint.py`](tools/fingerprint.py) | "Are these two files the same recording?" — by sound |
| [`library_manifest.py`](tools/library_manifest.py) | "What exactly do I have?" — streaming, resumable, lock-guarded walk of every file's audio properties and tags |
| [`library_triage.py`](tools/library_triage.py) | "Where is the work?" — stacked-release and completeness triage off the manifest, zero network |
| [`flac_integrity.py`](tools/flac_integrity.py) | "Does the audio underneath actually decode?" — header arithmetic catches corrupt files with no decoding at all |
| [`cue_split.py`](tools/cue_split.py) | "This is one file with a `.cue` — how do I get real tracks?" — sample-accurate split, verified bit-perfect |
| [`to_flac.py`](tools/to_flac.py) | "This rip is 384kHz/32-bit — do I really need to keep that?" — down-converts to a 96kHz/24-bit lossless ceiling |

## The method itself

The guide is what was learned; this is **how it was learned** — the two
registers that kept mistakes from repeating, plus full transparency about the
apparatus. Every entry below links to its full write-up.

### The playbook — 61 lessons with receipts

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
| [L29](PLAYBOOK.md#l29--a-compilation-shatters-into-one-album-per-performer-when-albumartist-is-the-track-artist) | A compilation shatters into one album PER performer when album_artist is the TRACK artist |
| [L30](PLAYBOOK.md#l30--splitting-a-cue-image-rip-has-two-silent-no-op-traps) | Splitting a cue-image rip has two silent-no-op traps |
| [L31](PLAYBOOK.md#l31--before-importing-a-rip-check-the-library-already-holds-it--equal-or-better) | Before importing a rip, check the library already holds it — equal or better |
| [L32](PLAYBOOK.md#l32--a-formatquality-claim--in-a-tag-a-release-name-or-an-encoders-silence--is-not-the-audio) | A format/quality claim — in a tag, a release name, or an encoder's silence — is not the audio |
| [L33](PLAYBOOK.md#l33--a-media-server-album-count-that-looks-half-right-is-a-view-artifact-count-tracks-vs-files-before-re-scanning) | A media-server album count that looks half-right is a VIEW artifact; count TRACKS vs files before re-scanning |
| [L34](PLAYBOOK.md#l34--a-blocklist-that-also-triggers-a-re-search-is-a-closed-loop-when-the-rejection-is-a-matching-verdict) | A blocklist that also triggers a re-search is a closed loop when the rejection is a MATCHING verdict |
| [L35](PLAYBOOK.md#l35--has-a-cue-is-not-needs-splitting) | "Has a cue" is not "needs splitting" |
| [L36](PLAYBOOK.md#l36--a-rip-can-ship-several-cues-take-the-one-whose-file-refs-exist-on-disk) | A rip can ship SEVERAL cues; take the one whose FILE refs exist on disk |
| [L37](PLAYBOOK.md#l37--a-per-track-guest-credit-in-album-artist-mints-a-phantom-artist) | A per-track GUEST credit in album-artist mints a phantom artist |
| [L38](PLAYBOOK.md#l38--one-artist-can-exist-twice-split-by-a-diacritic) | One artist can exist TWICE, split by a diacritic |
| [L39](PLAYBOOK.md#l39--a-wrong-diagnosis-that-ends-in-deletion-is-worse-than-a-crash) | A wrong diagnosis that ends in DELETION is worse than a crash |
| [L40](PLAYBOOK.md#l40--a-delete-guard-that-tests-characters-blocks-the-work-test-the-hazard) | A delete guard that tests CHARACTERS blocks the work; test the HAZARD |
| [L41](PLAYBOOK.md#l41--a-network-mount-listing-under-concurrent-writes-lies--including-empty) | A network-mount listing under concurrent writes lies — including "empty" |
| [L42](PLAYBOOK.md#l42--a-fix-made-only-on-disk-is-undone-by-the-next-import) | A fix made only on DISK is undone by the next import |
| [L43](PLAYBOOK.md#l43--a-whole-folder-credit-defeats-modal-evidence-file-under-the-credits-lead-only-if-that-artist-exists) | A whole-folder credit defeats modal evidence; file under the credit's LEAD, only if that artist EXISTS |
| [L44](PLAYBOOK.md#l44--a-tools-size-threshold-is-load-bearing-raising-it-turns-cleanup-into-demolition) | A tool's size threshold is load-bearing; raising it turns cleanup into demolition |
| [L45](PLAYBOOK.md#l45--a-vanished-album-may-be-an-empty-shell-search-former-names-before-concluding-loss) | A "vanished" album may be an empty SHELL; search former names before concluding loss |
| [L46](PLAYBOOK.md#l46--a-media-servers-own-am-i-busy-flag-is-an-opinion-wait-on-the-outcome-instead) | A media server's own "am I busy?" flag is an opinion; wait on the outcome instead |
| [L47](PLAYBOOK.md#l47--moving-files-does-not-make-a-media-server-re-derive-anything) | Moving files does not make a media server re-derive anything |
| [L48](PLAYBOOK.md#l48--marking-an-edition-in-the-title-fails-when-the-ui-truncates-it) | Marking an edition in the title fails when the UI truncates it |
| [L49](PLAYBOOK.md#l49--the-dangerous-failures-are-the-ones-that-look-like-good-news) | The dangerous failures are the ones that look like good news |
| [L50](PLAYBOOK.md#l50--a-subprocess-that-reads-stdin-will-eat-the-script-it-was-piped-inside) | A subprocess that reads stdin will eat the script it was piped inside |
| [L51](PLAYBOOK.md#l51--verify-a-file-operation-by-its-content-never-by-its-metadata) | Verify a file operation by its CONTENT, never by its metadata |
| [L52](PLAYBOOK.md#l52--all-n-compared-equal-is-a-red-flag-not-a-result) | "All N compared equal" is a red flag, not a result |
| [L53](PLAYBOOK.md#l53--fixing-the-files-is-not-finishing-the-job) | Fixing the files is not finishing the job |
| [L54](PLAYBOOK.md#l54--one-folder-two-spellings-of-the-album-name-two-albums-on-the-shelf) | One folder, two spellings of the album name, two albums on the shelf |
| [L55](PLAYBOOK.md#l55--a-folders-year-tracks-the-original-release-the-date-tag-tracks-the-edition) | A folder's year tracks the ORIGINAL release; the date tag tracks the edition |
| [L56](PLAYBOOK.md#l56--files-that-belong-to-no-album-are-invisible-to-checks-that-group-by-album) | Files that belong to no album are invisible to checks that group by album |
| [L57](PLAYBOOK.md#l57--duration-identifies-a-track-it-does-not-place-it-within-a-large-release) | Duration identifies a track; it does not place it within a large release |
| [L58](PLAYBOOK.md#l58--parallel-workers-sharing-one-scratch-directory-overwrite-each-other) | Parallel workers sharing one scratch directory overwrite each other |
| [L59](PLAYBOOK.md#l59--your-library-manager-tracks-one-release-per-album-keeping-both-masters-hides-one) | Your library manager tracks one release per album; keeping both masters hides one |
| [L60](PLAYBOOK.md#l60--an-unbounded-child-process-outlives-its-session-and-taxes-everything-after-it) | An unbounded child process outlives its session and taxes everything after it |
| [L61](PLAYBOOK.md#l61--a-suppression-list-not-bound-to-its-evidence-becomes-a-blindfold) | A suppression list not bound to its evidence becomes a blindfold |

### The decision register — 18 decisions

Each entry in [DECISIONS.md](DECISIONS.md) is an intentional choice with its
reasoning, the measured cost of the alternative, a narrow scope, and a
**"revisit if"** trigger — so odd-looking choices don't get "fixed" back into
bugs, and no decision silently hardens into dogma.

| # | decision |
|---|---|
| [D1](DECISIONS.md#d1--on-disk-naming-follows-the-file-tags-not-the-managers-metadata-source-2026-07-24) | On-disk naming follows the FILE TAGS, not the manager's metadata source (2026-07-24) |
| [D2](DECISIONS.md#d2--unknown-album-clutter-is-fixed-by-writing-tags-never-by-deleting-2026-07-24) | "Unknown Album" clutter is fixed by WRITING tags, never by deleting (2026-07-24) |
| [D3](DECISIONS.md#d3--cleanup-trash-is-reversible-native-recycle-bin-or-a-quarantine-folder-2026-07-24) | Cleanup "trash" is reversible: native recycle bin, or a quarantine folder (2026-07-24) |
| [D4](DECISIONS.md#d4--same-recording-is-decided-by-sound-not-filename-tags-or-bytes-2026-07-24) | "Same recording?" is decided by SOUND, not filename, tags, or bytes (2026-07-24) |
| [D5](DECISIONS.md#d5--official-release-data-comes-from-whats-already-running-before-any-new-tool-2026-07-24) | Official release data comes from what's ALREADY RUNNING before any new tool (2026-07-24) |
| [D6](DECISIONS.md#d6--the-restrictive-metadata-profile-is-the-default-permissive-is-opt-in-per-artist-2026-07-24) | The restrictive metadata profile is the DEFAULT; permissive is opt-in per artist (2026-07-24) |
| [D7](DECISIONS.md#d7--upgrade-propagation-requires-three-independent-guards-the-fingerprint-alone-is-insufficient-2026-07-24) | Upgrade propagation requires three independent guards; the fingerprint alone is insufficient (2026-07-24) |
| [D8](DECISIONS.md#d8--release-type-livestudio-is-measured-from-the-audio-not-inferred-from-names-2026-07-24) | Release type (live/studio) is MEASURED from the audio, not inferred from names (2026-07-24) |
| [D9](DECISIONS.md#d9--the-media-server-groups-by-identity-embedded-in-files-that-identity-is-inherited-from-wherever-a-track-was-ripped-2026-07-24) | The media server groups by identity EMBEDDED IN FILES; that identity is inherited from wherever a track was ripped (2026-07-24) |
| [D10](DECISIONS.md#d10--tags-are-fixed-before-the-scan-that-builds-album-objects-2026-07-24) | Tags are fixed BEFORE the scan that builds album objects (2026-07-24) |
| [D11](DECISIONS.md#d11--a-distinct-release-shows-the-year-it-came-out-never-its-parents-2026-07-24) | A distinct release shows the year IT came out, never its parent's (2026-07-24) |
| [D12](DECISIONS.md#d12--cd-and-vinyl-any-two-distinct-masters-of-one-album-are-kept-as-separate-releases-distinguished-in-the-name-2026-07-26) | CD and vinyl (any two distinct MASTERS) of one album are kept as SEPARATE releases, distinguished in the name (2026-07-26) |
| [D13](DECISIONS.md#d13--hi-res--lossless-container-rips-are-down-converted-to-a-96-khz--24-bit-ceiling-and-that-counts-as-lossless-2026-07-26) | Hi-res / lossless-container rips are down-converted to a 96 kHz / 24-bit ceiling, and that counts as "lossless" (2026-07-26) |
| [D14](DECISIONS.md#d14--an-automated-blocklist-never-triggers-a-re-search-2026-07-29) | An automated blocklist NEVER triggers a re-search (2026-07-29) |
| [D15](DECISIONS.md#d15--this-register-stands-alone-it-never-points-at-a-repo-the-reader-cant-open-2026-08-03) | This register stands ALONE; it never points at a repo the reader can't open (2026-08-03) |
| [D16](DECISIONS.md#d16--a-credited-single-is-filed-under-its-lead-artist-when-that-artist-exists-anything-larger-is-an-owner-decision-2026-08-08) | A credited SINGLE is filed under its lead artist when that artist exists; anything larger is an owner decision (2026-08-08) |
| [D17](DECISIONS.md#d17--placeholder-tags-are-worse-than-empty-ones-and-need-their-own-tool) | Placeholder tags are worse than empty ones, and need their own tool |
| [D18](DECISIONS.md#d18--identify-by-four-methods-before-discarding-anything) | Identify by four methods before discarding anything |

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
