# 2 — Diagnosing a messy artist (before touching a single file)

The expensive mistakes in a library rescue don't come from the mess — they come
from "fixing" files to chase a Plex display problem. Of 2,539 album folders
triaged in the source library, **87% had no evidence of any problem**, and of
the artists that *looked* broken in Plex, most had perfect files.

## The layer model

Work down, cheapest first, and stop at the layer that is actually broken:

1. **Is it still broken?** Libraries change under you — another session, a
   worker, Lidarr, a scheduled scan. Re-read current state before acting on a
   screenshot or memory.
2. **Disk** — do the folders and per-album file counts look right?
3. **Tags** — do `album` / `albumartist` / `date` / `musicbrainz_albumid` agree
   *within* each folder?
4. **Plex's own objects** — several album objects for one folder (chapter 1).

Layer 4 is the most common and the least obvious: Plex accumulates album
objects over time and never merges them when their metadata later agrees. Real
case: an artist showed 20 albums with quadruplicate titles; files were clean,
tags were mostly clean, and retagging 78 files plus a 600-second full rescan
changed **nothing**. One merge call took it to 15 albums, zero duplicates, no
tracks lost.

**Do not conclude "the messy date tags split it" just because the date tags are
messy.** Check whether the duplicate album objects already *agree* on the field
you want to blame — if they do, that theory is dead before you write anything.
Fix messy tags anyway as hygiene; just don't call it the cure. The reverse also
holds: **a split does not prove a tag defect exists.** One artist had two
same-title splits — one with a genuine two-release-ID conflict, one with
perfectly identical tags and a purely stale Plex object. The merge fixes both;
only one needed a file written.

## The merge-vs-split decision, on two fields

Given several album objects sharing a title, **backing folder** and **guid**
decide the verdict — and getting it backwards is destructive in both
directions:

| same folder? | same guid? | verdict |
|---|---|---|
| yes | yes | stale Plex object → **merge** |
| no | either | two releases → **never merge** (fusing them loses the distinction permanently) |
| yes | no | two releases stacked in one folder → **split the folder** |

Resolve the backing folder *per duplicate* before choosing. One artist showed
three "duplicates" needing three different answers: two same-folder/same-guid
pairs (merge, one call each) and one where each object drew tracks from BOTH
folders — merging that would have fused a CD release with its vinyl remaster;
it needed the move-out/move-back rebuild from chapter 1.

**The conservation check costs nothing and catches wrong merges before they
happen:** a stale split's objects must sum to the folder's file count. In one
batch, five merges were predicted exactly (4+5=9, 9+1=10, 7+1=8, 11+1=12,
13+1=14) and all five landed on the prediction. If the parts don't sum to the
whole, they were never the same thing — merging will hide tracks, not reunite
them. State the expected number *before* the call; assert it after.

A **one-track splinter album** is the signature of a single file carrying a
foreign `musicbrainz_albumid` (a stray remaster track, a hidden bonus track).
Fix the tag, then merge the object it already created.

## Stacked folders — the headline defect

More than one release living in one folder. Signals, all checkable without any
network call:

- more than one distinct `musicbrainz_albumid` in the folder (with a
  *substantial* second group — a lone foreign ID is one contaminated file);
- files on the same disc disagreeing about their declared track total;
- files disagreeing about the `album` name;
- **repeated track titles inside one folder.** Two stacked releases can share
  tracks — a 1975 LP and its 1976 international counterpart shared two songs.
  Repeated titles are a *stacking* signal, not a duplicate-file signal;
  "de-duplicating" them deletes the only copy a release has.

Two stacked releases sharing a *name* need disambiguating in the `album` tag
(`High Voltage (Australian version)`), not just the folder name — otherwise the
split leaves Plex rendering two identically-titled albums, which is exactly
what you were trying to cure.

**A disc number above 1 is a claim that disc 1 lives somewhere else.** The
hardest fuse in the source library — a 13-track album and its 47-track
collectors box that kept building as ONE 60-track album through distinct album
tags, distinct release IDs, a full rebuild, `unmatch`, AND `split` — was caused
by the box's tracks being numbered discs 2–5 while the album was disc 1. The
tagger had modelled them as one five-disc release, and Plex faithfully
assembled it. Renumbering the box 1–4 and rebuilding split them instantly.
Corollary: when no lever separates two folders, stop pulling levers and go read
the tags Plex is grouping on — something in them genuinely says "same release".

## When "several artists" is really one compilation, shattered

A compilation, soundtrack, or tribute album can present as a diagnosis
problem at the wrong layer entirely: instead of one messy artist, you see
**several otherwise-unrelated artists**, each holding a one- or two-track
"album" with the identical title and year. That's not several artists
sharing a coincidence — it's one folder whose `album_artist` tag varies
per track instead of naming the album's credited artist. The tell is the
duplicated title/year across artists who otherwise share nothing in the
library. [Chapter 1](01-how-plex-groups-music.md#a-fifth-failure-album_artist-decides-which-artist-owns-the-folder)
has the full mechanism and the fix (PLAYBOOK L29).

## Things that look stacked and are not

- **Box sets.** A 70-file folder with `CD 01–04` has the exact shape of the
  stacking bug — and was a genuine 60-track/4-disc 30th-anniversary release
  matching the disk file-for-file (10+25+15+10). **Before splitting any
  multi-disc folder, check whether an official release with that disc/track
  shape exists** (MusicBrainz, or Lidarr's `album.releases[]` —
  `trackCount`/`mediumCount`/`media[]`). This is not hypothetical caution: a
  56-file data loss happened precisely in folders a run had *deferred as
  box-set hazards* before deleting them anyway.
- **Odd disc numbering.** `CD 03`/`CD 04` with no CD 01/02 looked broken; the
  monitored release was literally `media=['3:CD','4:CD']` — discs 1–2 were
  DVDs. An `8cm CD 02` folder matched `media=['1:CD','2:8cm CD']` exactly. Read
  the release's media list before renaming or renumbering anything.
- **A release-group title in the `album` tag.** One artist's *Happy Nation*
  folder carried `album="The Sign"` on every track — with a *correct*
  `musicbrainz_albumid`. The release genuinely sits in MusicBrainz's "The Sign"
  release-group and the tagger wrote the group title into the album field. When
  an album tag disagrees with its folder, check the release-group of its own
  MBID before assuming the tag is junk.
- **Loose files beside disc folders** are usually a better-quality copy of one
  disc dropped in later (fingerprints 0.86–0.945 against the disc's MP3s in the
  observed case) — not a separate album.
- **The same release ripped twice** (e.g. as `CD 01/02` *and*
  `Digital Media 01/02`): identical filename lists across two disc sets in one
  folder is the cheap tell — check it before probing any audio. When both rips
  are the same format and the fingerprints say same audio, the quality ladder
  cannot choose; decide on **metadata completeness** (real release MBID, full
  date) and retire the other set.

## When choosing an online match, don't take the top score on faith

For the *Happy Nation* folder above, the match dialog offered the wrong edition
at score 93 and the right release at 91 — the 93 was the edition that *is* the
other album, and accepting it would have rebuilt the exact bug. Cross-reference
candidate releases against an authority (the release-group, the track count on
disk) rather than trusting the ranking.
