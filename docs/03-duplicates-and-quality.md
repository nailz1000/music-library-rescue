# 3 — Duplicates and quality: keeping the right copy

## Disposition rules

For each candidate track compared against the library's copy:

| situation | action |
|---|---|
| library has no copy | **ADD**, into `Artist/Album` — never loose at the artist root |
| candidate is higher quality | **REPLACE** that track; the loser goes to recycle/quarantine |
| candidate is equal or worse | **DISCARD** the candidate |
| library has tracks the candidate lacks | **LEAVE THEM** — never lose a track |

- **Operate on TRACKS, not directories.** A hi-res copy missing two tracks
  upgrades the ten it has; the album stays complete. Replacing whole
  directories loses content.
- **Never hard-delete.** Every removal is a move to a recycle or quarantine
  folder. One review cycle of reversibility is the whole point — several
  judgment calls in the source rescue were reversed days later.
- **Dry-run first, always.** Every tool defaults to a printed plan; `--apply`
  is a separate decision made after reading it.
- **Every withheld decision goes in the output with its reason**
  (`SKIP-LIVE`, `SKIP-UNOFFICIAL`, `SKIP-LENGTH`), not just a count — a
  withheld decision you can't inspect is a decision nobody reviewed.

## The quality ladder — and how it is miscomputed

Correct ordering: **lossless beats lossy**; within lossless, higher
`(sample_rate, bit_depth)`; within lossy, higher bitrate *by a real margin*
(~48 kbps) so a re-encode doesn't read as a gain.

Three measured failure modes:

- **Never rank lossless by bitrate.** A less-compressed FLAC has a higher
  bitrate and *identical* audio. Ranking by it reported ~39 phantom "upgrades"
  in one pass.
- **`bits_per_raw_sample` is often absent for FLAC** in ffprobe output; it
  coerces to 0 and a 16-bit library track then ranks *below* a 16-bit staged
  one. Fall back to `bits_per_sample`, then `sample_fmt` (s16→16, s32/flt→24).
  This alone produced 28 false upgrades.
- **Compare against the library's BEST copy of a track**, not the first found.
  Mid-dedup, an album holds both a FLAC and an MP3 of the same track;
  comparing against the MP3 calls a staged FLAC an "upgrade" the library
  already has.

## Verify a claimed upgrade is real

Numbers in headers lie. Before trusting an upgrade:

- **Fake hi-res**: 96/24 upsampled from CD has no energy above ~22 kHz.
- **Fake lossless**: FLAC transcoded from MP3 cuts off hard at ~16–20 kHz.
- **Transcoded MP3**: 128k re-encoded to 320k still cuts at ~16 kHz.

The measurement:

    ffmpeg -hide_banner -nostats -i FILE -af "highpass=f=24000,volumedetect" -f null -

Read `max_volume`: near-silence (below about −70 dB) means the content isn't
there. Two traps in the measurement itself:

- **Don't highpass above the file's Nyquist** — testing 24 kHz on a 44.1 kHz
  file measures nothing and reads as "suspect".
- Use `-hide_banner -nostats`, **not** `-v error` — the quieter loglevel also
  suppresses volumedetect's report, and an empty result can get scored as a
  pass.

## "Same recording?" is decided by sound

Filename matching fails in documented ways: two rips spell titles differently
(one +1-track album reported "9 new tracks"); the same track differs by ~5
seconds between masters, so a tight duration guard rejects real matches;
stripping `(live)`/`(demo)`/`(instrumental)` from title keys matched a studio
take to a live take. Byte hashing doesn't substitute: library copies carry
embedded art, so identical audio is never byte-identical.

[`tools/fingerprint.py`](../tools/fingerprint.py) — Chromaprint via the muxer
already inside ffmpeg, no extra dependency. Fingerprints are compared over a
**sliding alignment offset**, which is not optional: index-aligned, a known
same-recording pair scored 0.75; with the offset search, 0.93.

Thresholds, measured: **≥ 0.85 same recording**; 0.65–0.85 related edit/mix
(a human decides); **< 0.65 different**. Validation points: MP3-vs-FLAC of one
recording 0.93–0.97; same song, different mix 0.68; different songs 0.52–0.54.

## The three guards — the fingerprint alone is not sufficient

For propagating quality across copies (every copy of a recording raised to the
best owned, different *versions* never touched), apply three independent
guards, cheapest first. Each catches what the others cannot:

**1. Duration, first.** Same recording ⇒ same length within `max(3s, 3%)`. The
fingerprinter samples only the first ~120 seconds, so a radio edit and the
album version can score **1.000** and differ by 40 seconds:

| pair | similarity | lengths |
|---|---|---|
| album vs album (same) | 1.000 | 244s / 236s — caught by duration |
| radio edit vs album | 0.936 | 180s / 258s — caught by duration |

On one artist this guard caught 33 pairs, 21 of which had already cleared the
similarity bar. One probe field, decisive. It should be the first guard built,
not the last.

**2. Release type — measured from the audio, never read off the folder name.**
Names are wrong in both directions: *One Night in Japan* and *Tokyo '87* are
concert recordings matching no keyword, while *Tour Souvenir CD Single* sounds
live and is a studio compilation. MusicBrainz doesn't rescue this — the albums
it marks Live are rarely the unmatched folders at risk. The measurement:
applause is continuous, so a live track is loud at **both edges**, while a
studio track begins from silence. Tail-only measurement misfires on genres that
end songs on a hard cut. Require both edges loud on ≥50% of tracks:

| album | head dB | tail dB | both-loud tracks | verdict |
|---|---|---|---|---|
| studio control | −33.5 | −61.1 | 0/14 | studio |
| live control | −17.2 | −21.5 | 16/17 | live |
| unlabeled concert | −20.0 | −24.0 | 12/17 | LIVE |
| disco studio album | −19.7 | −51.5 | 9/19 | studio |

Live files are never replaced **and never used as a source**, in either
direction. Record verdicts in a per-artist flags file that every tool reads —
and let measurement only ever *add* flags, never clobber a hand-set one,
because the flags file is also where human judgments no measurement can make
(e.g. soundboard recordings with the crowd mixed out) live.

**3. Name markers — for what audio cannot reveal.** An *Instrumental Version
Collection* shares the entire backing track: it fingerprints high AND matches
duration, and would silently replace a song with its karaoke version. Only the
name shows it. Same for `karaoke`, `a cappella`, `tribute`, `demo`, and
unofficial releases (`fan edition`, `bootleg`) whose provenance can't be
verified at all.

Compare mastering markers as **sets, not presence**: `bool(a) != bool(b)` lets
`mono` and `remaster` cancel out and waves the pair through — the opposite of
what two different mastering signals should mean. And `deluxe` / `special
edition` are **not** mastering markers — they usually mean "album plus bonus
tracks, same mastering"; treating them as hazards blocked one of the best FLAC
sources in the library.

## Small findings that recur

- **Punctuation variants are real duplicates**: `Grails Mysteries` vs
  `Grail's Mysteries` (straight vs typographic apostrophe) — fingerprint 0.981,
  same bitrate, same size. Keep the typographic form (matches MusicBrainz
  style). Unlike case-aliases on SMB (chapter 6), these differ by more than
  case, so both files are real and one really is redundant.
- **Remaster vs distinct release**: a remaster of the same album keeps the
  original year and is a *quality* question; an edition with a different
  tracklist is a *different album* and shows the year it came out. The test is
  the tracklist, not the pressing date.
- **Duplicate-vs-quality deadlock**: when two copies are the same format and
  the same audio, decide on metadata completeness (release MBID, full date) —
  the quality ladder has no opinion and shouldn't be forced to invent one.
