# Playbook — lessons with receipts

How this project avoided repeating its mistakes: every incident that produced a
**confidently wrong answer** became a numbered entry in this file, written the
same way each time —

- **What happened** — the concrete failure, with the real numbers;
- **Lesson** — the general rule it proves, stated so it transfers;
- **Scope** — where the rule applies, so it can't be over- or under-applied.

Two disciplines make a file like this work. *Write the entry while it stings* —
a lesson harvested a week later loses the detail that makes it recognizable.
And *cite entries by number* in code comments, tickets and reviews — an
uncited playbook is a diary; a cited one is a checklist that grows itself.

Everything below was earned during the rescue of one ~31,000-file library.
The entries are ordered as they happened, which is also roughly
cheapest-mistake to most-expensive.

---

### L1 — A degraded system-of-record's COUNTS are poison for destructive decisions
**What happened:** Asked to delete "albums that show one track", we found 436 of
them — but the music manager's scan was stalled, having matched one file of
each album's real tracklist. By the system's OWN declared `totalTrackCount`,
exactly ONE album was genuinely single-track. Deleting on the observed count
would have destroyed 436 real albums.
**Lesson:** When a source-of-truth is mid-failure (stalled scan, partial
import, rate-limited sync), its aggregate counts are artifacts of the failure,
not facts about the world — and they are most dangerous as the trigger for a
DELETE. Separate "what the system asserts this item IS" (declared track total)
from "what its broken process happened to observe so far" (files matched). Act
on the former; treat a surprising count from a degraded source as evidence
your *view* is broken, and surface it instead of executing.
**Scope:** any destructive batch gated on a queryable system's metrics

### L2 — Validate a reproduction against the target's OWN output, never the corpus it lives in
**What happened:** A renderer was built to name files "as the music manager
would" without running it. Graded against the whole library it scored 66% —
meaningless, because the manager had named only ~810 of ~30,000 files; the
rest carried other tools' conventions from years past. Graded against the
manager's own managed files, the format matched exactly; the residual gap
(preferring MusicBrainz metadata over file tags) was inherent and got
documented, not "fixed".
**Lesson:** When you reimplement another tool's behavior, the only valid
ground truth is output that tool actually produced. The ambient corpus is full
of other tools' history and will score a faithful reproduction as broken.
Isolate the target's own artifacts, validate there, and record inherent gaps
as known limitations.
**Scope:** any reimplementation / port / renderer graded for fidelity

### L3 — Windows enumeration silently drops paths over MAX_PATH
**What happened:** A dry-run AND its apply both reported "no failures" while
silently omitting 8 tracks whose nested scene-release folders pushed paths past
260 characters — `os.walk`/`rglob` don't raise on an over-long path, they skip
it. The gap surfaced only because a reconcile compared files-in against
files-accounted-for.
**Lesson:** Any Windows sweep that must be exhaustive has to enumerate via the
extended-length `\\?\` form, and pair it with a reconcile that fails LOUDLY
when input count ≠ disposed-of count. "The plan looked complete" is exactly how
silent omission disguises itself.
**Scope:** any Windows file-tree sweep that must be complete

### L4 — A dry-run that probes the live filesystem lies about a not-yet-created target
**What happened:** A folder-merge dry-run tested `dest.exists()` on disk — but
when merging several folders into a BRAND-NEW target, nothing exists mid-plan,
so every colliding file read as a clean move: 22 "moves" that were really 11
moves + 11 collisions. The apply path was correct; the preview lied.
**Lesson:** A dry-run is trustworthy only if it simulates the same state
transitions apply performs. Model the operation against an in-memory picture of
claimed slots, updated identically with or without `--apply`, so the preview's
numbers EQUAL the real run's. A dry-run you can't trust is worse than none: it
launders a bad plan as reviewed.
**Scope:** any move / merge / dedupe planner with a dry-run

### L5 — Correcting source data doesn't refresh a cached view; never force it with a destructive API
**What happened:** Fixing misgrouped tracks meant writing their missing
`album_artist` tags — the true fix. The media server re-read the files (titles
updated) but kept them bonded to the stale album object; full scan, metadata
refresh, empty-trash, clean-bundles all changed nothing. The lever that works
is "unmatch" (drop the cached match, re-derive from tags). The lever that must
never be used is the server's DELETE endpoint — it removes the actual files.
**Lesson:** Many systems hold a derived, cached view that does not rebuild just
because you corrected the source and the system re-read it. Making the cache
reflect the fix is a SEPARATE step with its own non-destructive mechanism
(re-index, unmatch, rebuild). Never reach for a delete/remove action to force a
cosmetic refresh.
**Scope:** any store with a cached/derived grouping over editable source data

### L6 — Deletions go through the store's NATIVE recycle/trash, not hard-delete or bespoke quarantine
**What happened:** Cleanup scripts had been inventing ad-hoc quarantine folders
per job while the NAS already exposed a recycle bin per share with its own
retention and auto-purge. Standing rule since: deletions route through the
native bin, mirroring the origin subpath.
**Lesson:** When the store already has a native trash with a retention window,
route deletions THROUGH it — you inherit recoverability, one consistent
location, and automatic cleanup for free, and a same-volume move is instant.
Reserve hard delete for what provably never mattered, and say so.
**Scope:** any deletion from a store that has a native trash / recycle

### L7 — A guard must be at least as DEEP as the action it authorizes
**What happened:** A mover split stacked album folders, then retired each
emptied source. It tested emptiness with `os.listdir` — ONE level — and deleted
with a recursive walk — ALL levels. Two folders held disc subfolders; the
shallow test said "empty", and the deep delete took 56 files (a box set and two
vinyl rips), unrecoverable. The same run had explicitly deferred those folders
as multi-disc hazards — then deleted them in cleanup.
**Lesson:** When a cheap predicate authorizes an irreversible action, the
predicate's scope must cover everything the action can touch. A one-level check
before a recursive delete, a HEAD before a full sync — same bug, and it fails
silently because the guard honestly reports on the narrow thing it looked at.
Write the check against the action's blast radius. And pair it with L6: a
deletion path with no recoverable step converts every guard bug into permanent
loss.
**Scope:** any guarded destructive operation, especially recursive ones

### L8 — A new measuring instrument gets a known-answer control, positive AND negative, before its output is trusted
**What happened:** Five instruments returned plausible, well-formed, WRONG
answers in one session. ffprobe omits `bits_per_raw_sample` for many FLACs → 0
→ 28 files "upgrades" over themselves. Ranking lossless by bitrate → 39 phantom
upgrades. A fake-hi-res test highpassed at 24 kHz on 44.1 kHz files — above
Nyquist — and reported everything "suspect". A browse API resolved missing
directories to their nearest existing parent, so wrong paths returned plausible
listings. A field read `None` for every record because the real field was named
differently. None of these threw an error. The one instrument right on first
use — the fingerprinter — was the one validated against a known-same and a
known-different pair before use.
**Lesson:** An instrument that returns a number is not an instrument that
returns the RIGHT number, and at the call site they look identical. Before a
measurement drives a decision, run it against a case whose answer you know —
and one whose answer you know is the opposite (a positive control alone passes
for anything that returns a constant). Treat "field is missing/None/0" as a
third outcome, never as a low value.
**Scope:** any probe, API field, scoring function, or heuristic whose output authorizes an action

### L9 — Print samples next to aggregates so they can contradict each other
**What happened:** A scan reported "21 upgrades" while the three example rows
printed beneath showed the staged file LOSING. That one-screen contradiction
exposed the bit-depth bug. It recurred twice more — each time the aggregate
looked authoritative and the samples refuted it.
**Lesson:** An aggregate is a claim; a sample is evidence. Emit both from the
SAME data structure so a reader can check one against the other at a glance.
When they disagree, believe the samples — they carry raw values, while the
count has already passed through the logic under suspicion.
**Scope:** any script reporting counts over a collection

### L10 — "Complete" from a sampled heuristic is a claim about the sample
**What happened:** A staging folder was declared reconciled on the strength of
an album-level, one-file-per-album sampling pass. Asked directly whether it was
really done, the honest answer was no: a per-track pass over all 4,326 files
found 29 genuine upgrades in MIXED albums the sampling could not see.
**Lesson:** Coverage is part of a result, not a footnote. State the basis in
the same breath as the finding — "sampled one file per album" vs "every file".
When the cost gap forces sampling, make the exhaustive pass feasible instead of
skipping it (here, a size pre-filter turned ~3 hours of probing into minutes —
a real upgrade is always much larger on disk).
**Scope:** any audit, sweep, or migration reporting completeness

### L11 — Inventory what already-running systems expose before adding a dependency
**What happened:** "Is this extra track official bonus content?" needs release
data; the obvious answer was installing a library manager for its MusicBrainz
plugin. One query against the ALREADY-RUNNING manager showed it knew 17
releases of the album, including the exact 26-track edition that settled the
case.
**Lesson:** Services already in the stack expose far more than the feature they
were installed for. Before adding a tool for data, spend one query asking
whether something already running has it — this also avoids a second source of
truth that can drift from the first. When the existing service genuinely can't
answer, that limitation is the recorded justification for the dependency.
**Scope:** any "we should install X to get Y" decision

### L12 — Before acting on a cause, look for the observation that would DISPROVE it
**What happened:** A folder showed as four albums; inspection found genuinely
messy date tags — a real defect and a plausible cause. 78 files were retagged
and a 600-second full rescan run. Nothing changed. The refutation had been
sitting in the FIRST listing taken: all four album objects already displayed
the SAME year, so dates could not be what split them. The real cause was stale
accumulated objects (L13); one merge call fixed it instantly.
**Lesson:** "I found a defect near the symptom" is not "I found the cause."
Before an expensive write, ask the cheap question: *what would I see if this
theory were false — and do I already have that observation?* Corollary: when a
fix runs clean and the symptom is unchanged, that is the theory being
falsified — stop and re-diagnose, don't escalate. Fix the unrelated defect
anyway; just don't bill it as the cure.
**Scope:** any causal claim that authorizes a write, especially against a live system

### L13 — A cache/index built over time will not self-correct when the data is fixed
**What happened:** A media server had, across many past scans, created several
album objects for what is now one clean folder. Correcting the files and
re-scanning did nothing — the scanner reconciles files against EXISTING
objects; it does not re-derive grouping. Only an explicit merge collapsed them.
**Lesson:** Derived stores record decisions made when each row was created.
Fixing the source changes what NEW rows would look like; it does not revisit
old ones. Look for the operation that rebuilds or merges the entity itself, and
prefer the reversible one (a merge that can be split beats delete-and-rescan).
Verify by re-reading the store afterwards.
**Scope:** any derived index, cache, or library database downstream of files you just fixed

### L14 — Controls prove your instrument separates the controls — not that it's right elsewhere
**What happened:** A live-album detector was calibrated exactly as L8 asks —
known-studio and known-live albums confirmed on opposite sides of the
threshold. It then flagged a famous *studio* album as live, because its
measurement ("tracks end loud") is genuinely true of that album's arrangements.
The controls were never sensitive to the confound.
**Lesson:** Passing controls proves the instrument is not inert; it does not
prove it measures the thing you care about. After calibrating, run it over
cases whose answers you know independently and read the *verdicts*, not the
summary count. When a false positive appears, prefer a measurement with a
different confound (applause is continuous → a live track is loud at the START
too, while studio tracks begin from silence) over nudging the threshold, which
only moves the error around.
**Scope:** any classifier, heuristic, or detector you calibrate before trusting

### L15 — A similarity score computed over a sample is silent about everything outside the sample
**What happened:** The fingerprinter compares the first ~120 seconds. Two files
scored a perfect **1.000** — at 244s and 236s: different edits sharing an
identical opening. A radio edit vs the album version scored 0.936. Twenty-one
such pairs had cleared the confidence bar and were queued to overwrite each
other.
**Lesson:** A sampled comparison's score is evidence about the sampled region
only. Check a cheap whole-object invariant alongside it — length, record
count, byte size. Here duration cost one probe field, was decisive, and should
have been the FIRST guard, not the last one added.
**Scope:** fingerprints, embeddings, head/tail diffs, any "similar enough" threshold

### L16 — Size the parallel unit to the work, not to the loop you happened to write
**What happened:** A measurement pass over 104 album folders ran a fresh
16-worker pool *inside each album*. Most albums hold ~13 tracks, so the pool
was never full and its setup was paid 104 times. Flattening to one pool over
all 1,399 files fixed it without changing the worker count.
**Lesson:** "Am I using workers?" is the wrong question — ask what the pool is
spread across. A pool nested in a loop is throttled by the smallest iteration.
Collect the full work-list first, then parallelize once. Report throughput
against the believed bottleneck so "8.5 calls/sec over SMB" can be recognized
as saturated rather than starved.
**Scope:** any fan-out over a nested collection

### L17 — A paginated API returns a PAGE; treating it as the whole set invents a crisis
**What happened:** An audit walked a parent→children endpoint and reported "104
folders on disk but only 60 albums; 214 tracks missing across 45 folders." All
false. The endpoint paginates at 60; querying the item type directly returned
all 104 albums and every track. An hour went into diagnosing data that was
never absent.
**Lesson:** Any list endpoint may be a page. Before reporting a shortfall,
prove the reader is complete: check the total field, re-query with an explicit
page size, cross-check the count a second way. The tell is a suspiciously
round ceiling (60, 100, 1000) — treat "N equals the default page size" as a
reader bug until proven otherwise.
**Scope:** REST collections, SDK list calls, DB cursors, any parent→children walk

### L18 — Diagnostics must not destabilize the system being diagnosed
**What happened:** A watcher polled a media server every 15 seconds, each time
pulling the ENTIRE track list with a 20,000-item page size — during a full
library scan. The server crashed. Twice, because the first crash was written
off as coincidence.
**Lesson:** Monitoring competes with the work it monitors. Poll the cheapest
signal that answers the question (a status flag, a count) and pull the payload
once the flag says done. Scale the interval to the operation's real duration.
When the system falls over right after you start hammering it, you are the
prime suspect; a second identical crash is confirmation, not bad luck.
**Scope:** any polling/monitoring against a system under load

### L19 — Delete-then-recreate is not atomic; a crash in the gap leaves nothing
**What happened:** Rebuilding a library meant deleting it and immediately
re-creating it. The server crashed between the calls. The delete had
committed; the create had not; the library did not exist — and the user
noticed first.
**Lesson:** A destroy/rebuild pair is a window where the resource is absent.
Verify the recreate succeeded; prefer create-then-swap where the API allows.
Where it doesn't, confirm the underlying DATA survives the delete (here: audio
files counted either side, 1408 → 1408) and re-check existence at the end
instead of trusting the last status code.
**Scope:** library/index rebuilds, drop-and-recreate migrations, blue/green swaps

### L20 — "It picked the wrong one" is often the system obeying a setting you chose
**What happened:** The server showed an obviously wrong album cover while two
correct ones sat unused in its picker. Not a ranking bug: the library was set
to *prefer local metadata*, and the tracks carried embedded art inherited from
the album they were ripped from. The server was obeying instructions.
**Lesson:** When a configured system makes a choice that looks stupid, first
ask which of your settings makes that choice CORRECT. Preference settings reach
far beyond the field you were thinking about when you set them. The fix lives
at the level the setting actually reads (a folder-level cover file that
outranks embedded art), not in fighting the symptom.
**Scope:** any "prefer X" / precedence setting

### L21 — A filter that runs BEFORE your expensive check decides what the check never sees
**What happened:** Tracks were bucketed by normalized title before
fingerprinting (the all-pairs comparison is quadratic). `dance extended mix`
and `extended dance mix` bucketed apart, so the duplicate pair was never
compared at all — while hours went into tuning a similarity threshold it never
reached.
**Lesson:** The cheap pre-filter, not the expensive comparison, sets the
ceiling on what can be found. When something that should match doesn't, first
check whether the candidates ever MET. Loosening a pre-filter is usually safe
precisely because the real checks still run downstream — measure the cost
instead of assuming it explodes.
**Scope:** blocking/bucketing before fuzzy match, candidate generation before ranking, any prefilter→scorer pipeline

### L22 — A guard placed on the wrong branch can skip the exact case it was written for
**What happened:** A near-miss rescue pass (for pairs scoring just under the
same-recording bar) was nested inside the branch handling singleton clusters.
The file it was written for always clustered WITH its low-quality copy, so the
rescue never ran on it — while demoing fine on 28 other pairs.
**Lesson:** Placing a check inside an existing conditional inherits that
conditional's assumptions. Ask what the guard conceptually ranges over ("every
pair") and put it at that level. Then test it against the specific input that
motivated it — plausible aggregate output is not evidence the new path
executed for that case.
**Scope:** rescue/fallback passes, retry logic, special-cases added into existing control flow

### L23 — Shell heredocs mangle backslash escapes; write code with a file tool
**What happened:** A function written into a Python file via shell heredoc had
its regex `\b` become a literal backspace byte (0x08). The regex matched
nothing, and the failure looked like a logic error — the code READ correctly
in every excerpt, because control bytes don't render.
**Lesson:** Any escape sequence written through a shell heredoc is suspect;
use a real file-write tool for source. When output contradicts code that looks
right, stop re-reading and print what the interpreter actually loaded (`repr`,
hex dump).
**Scope:** generating source via shell, config files with regexes/paths

### L24 — Before merging N things into one, predict the resulting count and check it
**What happened:** Duplicate album objects needed merging, and merging the
wrong pair silently fuses two different records — the damage is invisible
because the result looks plausible either way. The free check: each pair's
track counts had to sum to the folder's file count (4+5=9, 9+1=10, 7+1=8,
11+1=12, 13+1=14). All five predicted, all five landed.
**Lesson:** A consolidation is a claim about arithmetic — *these parts are the
whole*. State the expected post-merge number BEFORE the call and assert it
after; if the parts don't sum, they were never the same thing and the merge is
hiding data. Any operation that reduces N records to 1 should have a
conservation law you can write down and test.
**Scope:** dedupe/merge passes, record consolidation, "collapse duplicates" tooling

### L25 — A report that always flags healthy items trains you to skim it
**What happened:** A triage compared artist names to folder names and flagged
three artists *every run* — all three were correct-by-construction (illegal
path characters force `AC/DC` → `AC+DC`; a trailing dot is dropped). The
summary line stopped carrying information.
**Lesson:** Known-benign findings are worse than none: they teach you the alert
list is noise, so the run where it says 4 gets the same glance as the run where
it says 3. Encode the benign transformation as an expectation so the check
still runs but only speaks when reality departs from the rules. "I know about
those three" does not survive into next month or someone else's head.
**Scope:** linters, audit/triage reports, monitoring alerts, CI warnings

### L26 — Hunt failures by SEVERITY, not recency; the tail of a busy log is all chatter
**What happened:** To check whether a known failure was recurring, the last 40
log records were read — all `info`, so the failure was declared absent and the
diagnosis went to an innocent subsystem. Querying the same log at error level
returned 200 records of exactly that failure, continuous for hours.
**Lesson:** "Recent logs look clean" is only evidence if the sample could have
contained the failure. Filter by severity (or grep the signature) over a real
time window before declaring an all-clear — and state the filter you used when
a conclusion rests on a log sample.
**Scope:** any "is it still happening?" check against logs

### L27 — Validate a liveness check against something known-alive before acting on "it died"
**What happened:** A detached scan was polled with `ps w`, which lists only
processes with a controlling terminal — so it reported the scan dead while it
ran perfectly. Acting on the false verdict launched a second copy against the
same output file: 1,265 duplicate records.
**Lesson:** A liveness probe is code that can be wrong, and its failure mode —
"everything is dead" — invites destructive reactions. Point the probe at a
process you KNOW is running first. Prefer `ps -ef`/`pgrep`, and give the tool
an O_EXCL pidfile lock so a lying probe *cannot* create a second writer.
**Scope:** daemon/watchdog scripts, restart-on-dead automation

### L28 — Diagnose from a fresh measurement, not from the last thing you wrote
**What happened:** One root cause was diagnosed three times. First call:
correct. Then a bad log sample (L26) said the evidence was absent, so a
confident written "correction" shipped blaming another subsystem. Only when the
system was down and directly measurable did the correction collapse — the
original call had been right all along. Each re-diagnosis had anchored on the
previous written conclusion instead of new primary evidence.
**Lesson:** When you revise a root cause, re-derive it from evidence measured
NOW — your own prior write-up reads as authority even where it was a guess.
Name the specific measurement that forces the new diagnosis; if you can't, you
are pattern-matching your own prose. A correction deserves MORE evidence than
the original claim, not less.
**Scope:** any multi-round diagnosis, incident write-ups, RCA

### L29 — A compilation shatters into one album PER performer when album_artist is the TRACK artist
**What happened:** A 14-track hits compilation credited to one headline artist
carried, on three tracks, the `album_artist` of the track's ACTUAL performer
(two by a sibling band, one by a guest). The server groups albums by
`album_artist`, so ONE folder rendered as THREE identical "same title / same
year" albums under three artists — the smallest fragment (a single guest track)
read as a mystery album by an artist with nothing else in the library.
**Lesson:** On a compilation the `album_artist` must be the album's CREDITED
artist — uniform across every track (or `Various Artists` for a true VA comp) —
while the per-track `artist` still carries the real performer for the credit.
This is the wrong-VALUE cousin of the empty-`album_artist` bug (L5 / decision
D2): there the tag was blank, here it is set to the track artist. Fixing the tag
is not enough — the server won't re-group existing objects (L13); rebuild
(unmatch, or move-out → empty-trash → move-back).
**Scope:** any multi-performer album (hits comp, soundtrack, tribute, split) on a server grouping by album_artist

### L30 — Splitting a cue-image rip has two silent-no-op traps
**What happened:** Converting one-file-per-side vinyl images to per-track files
via a `.cue`, two bugs each made the splitter find "nothing" while looking like
it succeeded. (1) The rip folder was a scene name in brackets — `[001+114] …` —
and the code listed cues with `glob`, where `[…]` is a CHARACTER CLASS, not a
literal, so it matched no directory. (2) The cue's `FILE` lines named files with
a junk prefix (`{xxxx} Artist … .flac`) absent on disk, so every source read as
missing.
**Lesson:** List a known folder's contents with `os.listdir` + a suffix filter,
never `glob` with the directory path embedded (a scene `[..]` folder IS a glob
pattern). Resolve each cue `FILE` against disk defensively: exact → strip a
leading `{..}`/`[..]` token → map the cue's FILE refs to the folder's audio
files in order when the counts match. And prove the split lossless the only way
that counts — decode the concatenated output to PCM and compare its MD5 to the
original side, not "it looked right".
**Scope:** cue-sheet / single-file-image splitting; any glob over release folders

### L31 — Before importing a rip, check the library already holds it — equal or better
**What happened:** A freshly-converted 17-track vinyl rip was queued to import
as a new album. The library ALREADY had that album — same 96 kHz/24-bit quality,
and MORE complete (a bonus track the new rip lacked). Importing would have made
a duplicate, or overwritten an equal-or-better copy with a worse one. The real
defect was elsewhere: the existing copy showed as partly-matched only because
the manager had ORPHANED 5 of its on-disk tracks — a re-link, not an import.
**Lesson:** "Import this download" is a create; do the read first. Compare the
candidate to the destination's existing copy by the disposition rules
(add-missing / replace-if-better / discard-if-equal-or-worse / never-lose-a-
track) BEFORE writing. A partly-matched existing album is usually an orphaned-
link problem (re-link the on-disk files), not a gap to fill with a second copy.
**Scope:** importing any downloaded release into a library that may already hold it

### L32 — A format/quality claim — in a tag, a release name, or an encoder's silence — is not the audio
**What happened:** Three claims lied in one session. A file tagged `media: 12"
Vinyl` was 16-bit/44.1 kHz and an incomplete subset — CD-spec audio wearing a
vinyl label. A metadata library reported sample-rate and bit-depth of ZERO for a
32-bit/384 kHz file it couldn't parse (a different tool read it fine). An encoder
that caps at 24-bit silently TRUNCATED a 32-bit source and produced a valid file
whose decoded PCM no longer matched the input.
**Lesson:** Decide source and quality from the AUDIO, measured — not from a name
or tag (L8, extended to provenance claims). Probe with a tool that actually
parses the format; a library's `0`/`None` is "couldn't read", a third outcome
(L8), never a real value — cross-check a suspicious zero against a second tool.
After any transform that could hit a capability boundary (bit depth, sample
rate, channels), verify the output preserved what you claim (decoded-PCM MD5, or
a format probe of the result) rather than trusting the command "worked".
**Scope:** provenance/quality decisions, format probes, lossless transforms

### L33 — A media-server album count that looks half-right is a VIEW artifact; count TRACKS vs files before re-scanning
**What happened:** After rebuilding an artist's grouping, the media server's
artist page showed **45 album objects for 94 disk folders**. A long, wasteful
chase followed — folder move-out/move-back, forced re-scans, touching every
mtime, reading scanner logs — before the definitive check: **996 of 1008 tracks
were present, in 92 distinct parent albums.** The server buckets releases by type
(Albums / Singles / EPs / Live / Compilations), and the default album view counts
only the "album" type — so ~47 singles and EPs were invisible and a COMPLETE
rebuild read as half-failed.
**Lesson:** Album-object count is a grouped, type-FILTERED view; track count is
the data. When an album count looks wrong — especially ~half the folder count —
verify with the cheap ground truth FIRST: the distinct-parent count over the
artist's TRACKS, against the files on disk. If they match, nothing is missing and
no re-scan will help — the gap is category grouping. Re-scanning off an unverified
album shortfall burns time and changes nothing. And prefer the smallest fix —
merge the few duplicate objects — over a full-artist rebuild.
**Scope:** any media-library audit where "album objects" ≠ folders; verifying a "missing releases" claim

### L34 — A blocklist that also triggers a re-search is a closed loop when the rejection is a MATCHING verdict
**What happened:** A nightly janitor cleared stuck imports with "blocklist and
remove", leaving the manager's re-download flag at its default — which means
"blocklist this, then go find another copy right now". Every reason it acted on
was a MATCHING verdict: *has fewer tracks than existing release*, *album match is
not close enough: 75.8 % vs 80 %*, *worst track match: 55.0 % vs 60 %*. None
describe a corrupt file; they describe how the release lines up against the
metadata release the manager chose. A different copy of the same album earns the
same verdict. Caught in the act inside ONE 20-minute run: the same release
blocklisted at 10:00:21 and again at 10:00:51. Over days the download folder
reached **663 GB / 593 folders, 185 of them `.1` duplicates**, and the constant
re-downloads kept the downloader busy — which deferred the cleanup pass that was
supposed to empty it. The mechanism filling the folder was starving the one
draining it.
**Lesson:** Separate "this release is BAD" from "this release does not MATCH".
Only the first justifies fetching another copy, and it never arrives on the
failed-import path anyway — a genuine download failure surfaces as its own
event. Any automated blocklist should skip the re-search. Note also that
blocklists match on release TITLE, so the same release re-published with
different punctuation walks straight back in: `Artist.Name-Album-CDS-FLAC` was
blocklisted and `Artist Name-Album-CDS-FLAC` was queued twelve minutes later.
**Scope:** any library manager with automated queue cleanup

### L35 — "Has a cue" is not "needs splitting"
**What happened:** A sweep selected every folder holding a `.cue`, audio, and no
split output — 204 candidates. **141 were ordinary per-track rips** that simply
ship a cue alongside one file per track. The difference is visible at a glance:

    image rip      4 files, 378-624 MB, named "Side A.flac"
    per-track rip  9 files,  24- 29 MB, named "07. Track Title.flac"

Sixty-nine percent of the planned work was pointless, and that was most of the
runtime problem it was blamed on.
**Lesson:** A rip needs cutting exactly when one `FILE` holds more than one
`TRACK` — **and** the cue must describe MORE tracks than there are audio files
present. The second half is not optional: a per-track rip can carry a LEFTOVER
single-image cue describing audio that is no longer there (14 per-track files
beside a cue with one FILE ref and 14 TRACKs), which cue-internally is
indistinguishable from a genuine image rip.
**Scope:** any bulk cue-splitting sweep

### L36 — A rip can ship SEVERAL cues; take the one whose FILE refs exist on disk
**What happened:** A two-disc rip carried four cues — a `.wav`-era pair and a
`.flac` pair, one of each per disc. The splitter selected "the cue with the most
FILE refs"; all four had exactly one, so the tie resolved to directory order and
it picked a `.wav` cue naming a file that never existed. The run died with
`MISSING source file(s) referenced by cue`, which reads exactly like an
incomplete download — and the folder was put on a delete-and-blocklist list on
that basis. Both disc images (439 MB + 444 MB) were present and perfect. Pointed
at the `.flac` cues it split **bit-perfect**, 14 tracks recovered.
**Lesson:** Rank candidate cues by how many of their `FILE` references actually
RESOLVE on disk, then by count, then by name so the choice is deterministic
rather than dependent on listing order. A tie-break that can select an
unresolvable cue will eventually condemn a perfect rip.
**Scope:** cue selection wherever more than one cue can exist in a folder

### L37 — A per-track GUEST credit in album-artist mints a phantom artist
**What happened:** A famous album's one duet track carried the GUEST as its
album-artist (and no separate album-artist tag at all — only `artist`). The
importer filed that single track under her name, and the server then rendered
the whole album under her. The same shape produced **seven** phantom artists
from one electronic album ("X & Collaborator A", "X & Collaborator B", …) and
five from a DJ compilation — 26 in a single pass, each an artist page holding
one or two orphaned songs.
**Lesson:** The fix is NOT to stop trusting album-artist — that tag is what
routes a MISLABELLED folder correctly (a folder named for one album containing
another lands right *because* the tags are believed over the folder name). The
evidence is in the FOLDER: 29 of 30 tracks say one thing and one disagrees. Take
the source folder's MODAL album-artist when the outlier claims the SAME album,
on either signal — the mode is a PREFIX of the outlier under a credit separator
(`&`, `feat.`, `+`), or the mode covers ≥80 % of the folder's tagged tracks (which
catches a guest credited without naming the lead). A true various-artists
compilation has no dominant value and passes through untouched. Careful: a name
that merely STARTS with the dominant one is a DIFFERENT act: a band called
`Kissing The Pink` on a folder dominated by `Kiss` is not a Kiss track, and a
prefix test without the separator check will claim it.
**Scope:** importing any release with featured artists or duets

### L38 — One artist can exist TWICE, split by a diacritic
**What happened:** The library held one artist under two folders — the same
name with and without its diaeresis. The manager tracked only the accented
spelling, so 43 tracks were invisible to it, and the server rendered two
artists. A sweep found **four** such pairs across ~350 artists, and one of them
split on a straight apostrophe versus an acute accent (`'` vs `´`) rather than
an accented letter at all.
**Lesson:** Normalise names by FOLDING diacritics (NFKD, then drop only the
combining marks), never by stripping non-alphanumerics — stripping turns a
name containing `ë` into `nme` rather than `name`, a different key entirely, so
an artist stops matching its own credit variants. Merge to the spelling the
manager points at. Leave albums that exist by the same name on BOTH sides in
place for a human: folding two
same-titled album folders together is a release-identity decision, not a rename.
**Scope:** any name matching across a library — dedupe, credit resolution, merges

### L39 — A wrong diagnosis that ends in DELETION is worse than a crash
**What happened:** In one pass, four folders were queued for
delete-and-blocklist as "incomplete downloads". **All four held good audio.** A
complete 11-track album carrying a cue for a different edition; two complete
per-track rips sitting beside a leftover image cue; and a folder dismissed as
"78 GB of junk poster scans" that was a 59-album discography of roughly 950
tracks.
**Lesson:** Before any delete driven by a tool's OWN error text, verify the
CLAIM independently — count the files, read the cue, compare the size sets
against the copy you already hold. The error tells you what the tool could not
do; it never tells you what is on disk. A crash announces itself. A confident
misreading removes data and leaves nothing looking broken afterwards, which is
why this one deserves a hard rule rather than care.
**Scope:** any automated cleanup with a delete or blocklist branch
