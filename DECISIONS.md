# Decisions — the register

The second half of the method (the [playbook](PLAYBOOK.md) is the first).
Where the playbook records *lessons from incidents*, this file records
*intentional choices* — especially the odd-looking ones that a future reader
(or a future you) would otherwise "fix" back into a bug.

The format, which is most of the value:

- each decision is **numbered** so code comments and tickets can cite it;
- each states **the reasoning and the measured cost of the alternative**, not
  just the verdict;
- each is **scoped narrowly**, so it can't be wielded to dismiss an adjacent
  request it was never about;
- each ends with a **Revisit if** trigger — the condition under which the
  decision should be reopened. A decision without a revisit trigger silently
  hardens into dogma.

These are the decisions from the source rescue, generalized. Adopt the ones
that fit; the register format is the part meant to be copied.

**Scoping discipline (playbook P78/P81; see claude-tools/DECISIONS.md D4):**
Scope each entry NARROWLY — the ONE thing decided and its tradeoff, not a vague "we simplified X" —
so it can't be stretched to dismiss an adjacent request (P81). A decision is NOT a shield; don't cite one
to reject a request unless the request is literally what the entry decided against. When an entry keeps
getting invoked in things that aren't working out, it's OVER-BROAD — re-scope it (P78), never overrule
the owner's judgment. **Revisiting what a decision covers = tightening it in the same change (P78):**
when you revisit what a decision entry describes, or act outside it, update the entry in the same sitting
— add the nuance you learned, cite the concrete case, sharpen the "Revisit if" trigger.

---

### D1 — On-disk naming follows the FILE TAGS, not the manager's metadata source (2026-07-24)
When the library manager's scan was wedged, files still had to be named and
filed. The manager names from MusicBrainz (original-release year, MB casing) —
which an offline tool cannot reproduce, because that data isn't in the files.
The renderer was validated to match the manager's *format* exactly (against
the manager's own managed files — playbook L2); the only divergence is the
metadata *source*, and file tags are also how the existing ~30k files were
named, so tag-naming is the consistent choice.

**Revisit if:** the manager's scan is healthy and the goal becomes canonical
MusicBrainz naming — then a manager-driven rename pass supersedes this (the
format already matches, so files won't move; some years/casings change).

See sibling entry: Plex DECISIONS.md D1

### D2 — "Unknown Album" clutter is fixed by WRITING tags, never by deleting (2026-07-24)
Tracks land in a media server's "Various Artists / [Unknown Album]" bucket
because their `album_artist` tag is EMPTY — not because they are junk. They
are real, catalogued music with stripped tags. A literal "delete the one-track
albums" request would have destroyed real songs; the fix is writing
`album_artist`/`artist`/`album`/`title` derived from folder + filename so the
server refiles them. Only items verified uncatalogued get trashed.

**Revisit if:** an entry is *verified* junk — then it's a recycle-bin move,
still never a blanket delete of everything that merely looks one-track.

See sibling entry: Plex DECISIONS.md D2

### D3 — Cleanup "trash" is reversible: native recycle bin, or a quarantine folder (2026-07-24)
Disposition rules (uncatalogued → trash, duplicate → keep higher quality,
verified demo → `Demo/`, live bootleg → `Live Bootleg/`) decide WHAT goes;
reversibility decides HOW. "Trash" always means a move to the store's native
recycle bin (PLAYBOOK.md P120), never an immediate hard delete — bulk judgment
calls about obscure tracks are exactly the decisions that get revisited.

**Revisit if:** the owner asks for immediate hard deletion of a specific,
provably-worthless set — the reversible default is a safety net, not a mandate.

See sibling entry: Plex DECISIONS.md D3

### D4 — "Same recording?" is decided by SOUND, not filename, tags, or bytes (2026-07-24)
Settled by Chromaprint fingerprinting over a sliding alignment offset
(`tools/fingerprint.py`). Measured thresholds: ≥ 0.85 same recording,
0.65–0.85 related edit (human decides), < 0.65 different. Everything cheaper
was tried first and failed in documented ways: filenames (spelling variants
invented "9 new tracks"; stripping `(live)` matched a studio take to a live
take), duration alone (masters differ ~5s), byte hashes (embedded art means
identical audio is never byte-identical). The alignment search is not
optional: 0.75 index-aligned vs 0.93 with the search, on a known-same pair.

**Revisit if:** the library is ever normalized to one tagger + one encoding,
making cheap checks sufficient for most pairs — fingerprinting stays the
arbiter for edits vs duplicates.

See sibling entry: Plex DECISIONS.md D4

### D5 — Official release data comes from what's ALREADY RUNNING before any new tool (2026-07-24)
Deciding whether an extra track is legitimate bonus content needs release
data. The already-running manager's API had 17 releases of the album in
question, including the exact edition that settled it (playbook L11). No new
tool was installed; a second metadata source that can drift from the first is
a cost, not a feature. When the running service can't answer (filtered
metadata profile), query MusicBrainz directly by release ID — scoped to the
gap, not a wholesale replacement.

**Revisit if:** the gaps become the common case rather than the exception.

### D6 — The restrictive metadata profile is the DEFAULT; permissive is opt-in per artist (2026-07-24)
A restrictive profile (Album+Studio only) means the manager never creates
compilation/soundtrack/single/live/remix albums — files belonging to them can
never match, *by design*. The permissive alternative was measured: four
opted-in artists produced 208 monitored albums expecting 1,955 tracks against
146 on disk — an 1,809-track "missing" list of bootlegs and repackagings.
That's acceptable when chosen deliberately per artist; it is not acceptable as
a silent default across 300+.

**Consequence, easy to misread:** on the restrictive profile a nonzero
unmatched-file count is EXPECTED and is not a health signal. The health signal
is per-album disk-vs-release-tracklist comparison.

**Revisit if:** per-artist opt-in becomes the common case.

### D7 — Upgrade propagation requires three independent guards; the fingerprint alone is insufficient (2026-07-24)
Rule: every copy of a recording is raised to the best quality owned;
different *versions* (remaster, remix, edit, live) are never touched. The
fingerprint samples ~120s, so a radio edit scores 1.000 against the album
version (playbook L15). Guards, cheapest first: **duration** within
`max(3s, 3%)` — caught 33 pairs, 21 of which had cleared the similarity bar;
**release type measured from audio** (D8) — live files are never replaced and
never used as a source; **name markers** for what audio can't reveal — an
instrumental collection shares the whole backing track and would replace a
song with its karaoke version. Mastering markers compare as SETS (`mono` vs
`remaster` must not cancel out); `deluxe`/`special edition` are NOT hazards
(same mastering, bonus tracks).

**Revisit if:** never wholesale — but individual markers earn or lose hazard
status by evidence, as `deluxe` did.

### D8 — Release type (live/studio) is MEASURED from the audio, not inferred from names (2026-07-24)
Names are wrong in both directions: real concert recordings match no keyword,
while a "Tour Souvenir Single" is studio. Metadata doesn't rescue it — the
albums marked Live in MusicBrainz are rarely the unmatched folders at risk.
The measurement: applause is continuous, so a live track is loud at BOTH edges
(head ≥ ~−30 dB and tail loud on ≥50% of tracks); a studio track begins from
silence. Tail-only misfires on genres that end on a hard cut. Verdicts live in
a per-artist flags file that every tool reads; measurement only ever ADDS
flags and never clobbers a hand-set one, because the file is also where human
judgments no measurement can make (soundboard recordings) live.

**Revisit if:** an artist's live material is soundboard-sourced with the crowd
mixed out — no audio measurement saves that; it needs a human flag.

### D9 — The media server groups by identity EMBEDDED IN FILES; that identity is inherited from wherever a track was ripped (2026-07-24)
The four signals (release MBID, whole-string date, originaldate/year, embedded
art) and their failure modes are chapter 1 of the [guide](docs/01-how-plex-groups-music.md).
Registered as a decision because it drives a rule: **fix tags to describe the
folder the file lives in now**, not the album it was ripped from — a
compilation track claiming its source album's identity is wrong *here* even
though the claim is historically true.

**Revisit if:** the server changes what its prefer-local setting governs.

### D10 — Tags are fixed BEFORE the scan that builds album objects (2026-07-24)
Correcting tags never fixes albums the server already built (playbook L13) —
demonstrated: a forced deep rescan fixed none of five known defects; a library
rebuild fixed three instantly. So on any new library: set prefer-local FIRST,
fix tags SECOND, scan LAST. A library scanned before its tags were corrected
needs a rebuild, not a refresh.

**Revisit if:** the server's scanner ever re-derives grouping on rescan.

### D11 — A distinct release shows the year IT came out, never its parent's (2026-07-24)
An anniversary edition with a different tracklist (25 tracks vs the original's
11) is a *different album* and displays its own year. The deciding field is
`originalyear` (which drives displayed year), not `date` — the edition had
inherited its parent's `originalyear` from the source rip and sorted wrongly
until that field specifically was fixed, followed by unmatch+refresh (the
album object was matched to the parent's online release and took its year
from there). The boundary: a **remaster with the same tracklist** is the same
album and keeps the original year. The test is the tracklist, not the
pressing date.

**Revisit if:** never as stated — but expect the unmatch+refresh step on
every reissue split out of a parent folder.

### D12 — CD and vinyl (any two distinct MASTERS) of one album are kept as SEPARATE releases, distinguished in the name (2026-07-26)
Where D11 is about editions/years, this is about two different SOURCES of the
same album — a CD (or CD remaster) and a vinyl rip. They are distinct releases,
not duplicates: keep both on disk in separate release folders. A library manager
that models one file per track can only track ONE, so it tracks the
higher-resolution copy; the other stays as an untracked release. Mark the source
in BOTH the album-title tag and the folder name (`… [CD]` / `… [24-192 Vinyl]`):
the server separates them by their differing date, but otherwise renders both as
the same "title / year" tile — indistinguishable to a human. Determination is
MEASURED, not read off the name (playbook L32): a "vinyl" tag on 16/44.1 audio
is a mislabeled CD copy and gets deduped by quality, not kept as a second
release.

**Gotcha:** the server won't re-read an album's title tag on rescan unless the
folder PATH changed — rename the folder, or force a per-album metadata refresh.

**Revisit if:** the manager ever tracks multiple releases of one album
natively — then track both, not only the better one.

### D13 — Hi-res / lossless-container rips are down-converted to a 96 kHz / 24-bit ceiling, and that counts as "lossless" (2026-07-26)
Rips arrive at absurd rates (384 kHz / 32-bit vinyl transfers are real). For a
vinyl or analog-sourced rip the band above ~48 kHz and the bits below 24 are
noise and empty ultrasonic spectrum — vinyl holds ~12-14 bits and nothing above
~30 kHz — so a 96/24 FLAC keeps 100% of the actual audio at a fraction of the
size (a measured 384/32 album: 6.4 GB → 1.2 GB). Rule: keep native rate if
≤ 96 kHz else resample to 96; keep 16-bit sources at 16 else 24; never inflate.
Treat the result as lossless even though it is not bit-identical, because the
discarded data carries no music. (Probe the source with a tool that parses the
format — L32.)

**Revisit if:** a genuinely > 24-bit MUSICAL source appears (studio masters, not
vinyl) — the ceiling deserves reconsideration for that source.

### D14 — An automated blocklist NEVER triggers a re-search (2026-07-29)
**Decided** after measuring the loop it caused.

A janitor that clears stuck imports acts on ONE class of failure: the manager
declined to match a download to a release. Every reason it sees is a matching
verdict — fewer tracks than the chosen release, album similarity under
threshold, worst-track-title score under threshold. A different copy of the same
album produces the same verdict, so "blocklist and immediately search for a
replacement" is a closed loop by construction (L34).

**The rule.** Automated blocklists set the manager's skip-redownload flag. The
album stays monitored, so a scheduled search or a human can still find a
genuinely better release — but nothing is fetched on the strength of a matching
failure.

**The one exception**, which must be identified positively rather than by
default: a download that is genuinely INCOMPLETE — the cue references files that
were never fetched, or the track numbering has a hole. That is a real defect in
the copy, another copy plausibly fixes it, and a re-grab is correct. Verified in
practice: an album deleted and blocklisted for a truncated second disc was
re-fetched complete and imported cleanly on the next run.

**Revisit if:** the janitor is ever extended to act on corruption verdicts,
where a fresh copy is the actual remedy.

