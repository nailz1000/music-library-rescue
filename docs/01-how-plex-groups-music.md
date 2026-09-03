# 1 — How Plex groups music (and why fixing tags doesn't fix Plex)

Everything in this chapter assumes the music library is set to **Prefer local
metadata** (`respectTags=true` in the section settings). That switch is what
makes a folder-organized library work at all — without it Plex ignores your
folders and groups by online match. **A newly created library defaults it to
OFF.** Set it immediately after creating the library, *before* the first scan
builds albums.

## The four identity signals

With prefer-local on, Plex builds albums from four signals **embedded in the
files**. All four travel with a track from wherever it was originally ripped —
so a compilation disc or box-set track arrives still claiming to *be* the
studio album it came from.

| signal | failure it causes | real case |
|---|---|---|
| `musicbrainz_albumid` | folders shatter into several albums, or two folders fuse into one | a "Collection" compilation became **5 albums with 5 different covers**; 26 release IDs were each claimed by more than one folder |
| `date` — compared as a **whole string** | same-year splits | `2008` and `2008-09-29` are *two different albums* to Plex |
| `originaldate` / `originalyear` | wrong displayed year | junk values `0001`, `1`, or a year *later* than the release |
| embedded cover art | wrong poster | one 14-track compilation carried **six different covers**, two belonging to another album |

Working rules that fall out of this:

- **One folder is one release**, so a `musicbrainz_albumid` that disagrees
  *within* a folder, or is claimed by *more than one* folder, is wrong — clear
  it. Plex then falls back to album-name + artist, which is the folder-driven
  grouping you wanted.
- Every track in a folder must carry the **identical** `date` string.
- `YYYY-01-01` is a placeholder written by taggers that only knew the year — not
  a New Year's Day release. Demote it when choosing a folder's canonical date.
- The wrong-poster case looks like a Plex bug and is not: prefer-local means
  *prefer the artwork inside the files*. The fix is a folder-level `cover.jpg`,
  which outranks embedded art — not an agent setting.
- `originalyear` (not `date`) drives the displayed year. A reissue split out of
  a parent folder usually inherits the parent's `originalyear` and files itself
  under the wrong year until you fix that field specifically.
- Writing `originalyear` to MP3 requires a `TXXX(desc="originalyear")` frame
  (plus `TDOR`); mutagen's EasyID3 has no such key and raises — and if your
  loop writes FLACs first, half the album is saved before the crash.

## Built albums are sticky — the part nobody expects

**Correcting tags does not fix albums Plex has already built.** The scanner
reconciles files against existing album objects; it does not re-derive
grouping. Demonstrated, not assumed: after a full tag fix, a forced deep rescan
left *all five* known grouping defects untouched; deleting and re-adding the
library cleared three immediately.

So the order of operations is: **fix tags first, then let a scan build the
objects.** A library scanned before its tags were corrected needs a rebuild,
not a refresh.

Two distinct kinds of stickiness, with different repairs:

1. **Album identity** (title/year/match) — repaired by `unmatch` + `refresh`.
   A matched album takes its title and year from the *online release it
   matched*, not from your files; a rescan after a tag fix changes nothing, and
   even re-`match`ing to the right release can leave stale fields. `unmatch`
   drops the online identity so prefer-local rebuilds it from tags. Afterwards
   the album's guid reads `tv.plex.agents.none://…` — locally derived, which is
   the intended end state, not an error.
2. **Track membership** — *much* stickier. Plex assigns a track to an album at
   import and never reconsiders. After splitting a vinyl release into its own
   folder with its own tags, Plex still showed 7 vinyl tracks inside the CD
   album and 1 CD track inside the vinyl one — and **none of** a targeted
   rescan, `unmatch`, per-album refresh, Empty Trash, or tag edits moved a
   single track. What works, scoped to one artist:

   1. move the affected album folders OUT of the library root (same volume →
      instant rename);
   2. scan the artist path — Plex sees the files gone;
   3. Empty Trash on the section — the stale album objects disappear;
   4. move the folders back;
   5. scan again — fresh import builds objects from the *current* tags.

   Count the artist's total tracks before and after (e.g. 196 → 196). A
   same-volume move copies nothing, so nothing can be lost — count anyway.

## A fifth failure: `album_artist` decides WHICH ARTIST owns the folder

The four signals above decide how tracks group into an album once you're
under the right artist. A separate field — `album_artist` — decides which
artist bucket the whole folder lands in, and it fails in its own
recognizable way.

**A compilation shatters into one album per performer when `album_artist`
is set to the track's performer instead of the album's credited artist.**
A multi-track hits compilation credited to one headline act, with a few
tracks' `album_artist` left as *that track's own performer* (a feature
artist, a guest spot), doesn't render as one messy album — it renders as
**several separate albums**, one per artist named in `album_artist`, all
sharing the same title and year. The smallest fragment (a single guest
track) shows up as a whole "mystery album" under an artist who otherwise has
nothing in the library.

The fix: on a compilation, soundtrack, tribute, or split release,
`album_artist` must be **uniform across every track** — the album's
credited artist (or `Various Artists` for a true various-artists release) —
while the per-track `artist` field still carries each song's real performer.
This is the wrong-*value* cousin of an empty `album_artist`: there the field
is blank, here it's set, just to the wrong thing.

**Fixing the tag alone does nothing.** Plex already built the separate album
objects and won't re-derive the grouping from a corrected tag — see "Built
albums are sticky" above. Rebuild with `unmatch` + refresh, or the
move-out → Empty Trash → move-back sequence, exactly as for any other sticky
grouping defect. (PLAYBOOK L29)

## Two masters, one tile: CD vs vinyl

Keeping two distinct masters of the same album (say, a CD remaster and a
vinyl rip) as separate releases on disk is a disposition choice made
upstream of Plex ([chapter 3](03-duplicates-and-quality.md)) — but Plex
renders the consequence in a way worth knowing about. The two releases'
`date` values are what let Plex tell them apart at all; make them differ
(even just in precision), or Plex draws **one identical "title / year"
tile** for both, indistinguishable to a human browsing the library.

Mark the source in **both** places: the album-title tag (e.g.
`Album Name [CD]` / `Album Name [24-192 Vinyl]`) and the folder name — the
tag alone isn't enough, because **Plex does not re-read a folder's title tag
on a plain rescan unless the folder path itself changed.** Rename the folder
(or force a per-album metadata refresh) to make a tag correction visible.

Which copy your collection manager actually tracks is a separate question —
see [chapter 5](05-lidarr.md#cd-vs-vinyl-the-manager-tracks-only-one-copy).

## The repair ladder

Cheapest first. Escalate only when the level below is proven insufficient.

| repair | fixes | doesn't fix |
|---|---|---|
| `PUT …/merge?ids=` | several album objects backed by ONE folder (stale duplicates) | anything backed by two folders — merging those fuses two releases |
| `unmatch` + `refresh` | stale identity: wrong title/year from an old online match | track membership |
| `split` | an artist or album wrongly fused from a bad merge/match | grouping driven by tags |
| move-out → scan → Empty Trash → move-back → scan | track membership | tag defects (fix those first or it rebuilds the same mess) |
| delete + re-add the library | everything built from stale state | nothing if tags are still wrong; **does not delete media files** (verified by counting both sides) — but delete/re-create is not atomic, so confirm the new library exists and has `respectTags` on |

**Never use the Plex DELETE metadata API to "clean up" music entries — it
deletes the underlying files.**

## Reading the Plex API without inventing a crisis

Each of these produced a confident false alarm at least once:

- **`/children` paginates at 60** and can *silently omit* an album that the
  type query returns. One page read as "the whole set" produced a false report
  of 214 missing tracks. Query types directly —
  `/library/sections/<key>/all?type=8|9|10` (artist/album/track) — and send
  `X-Plex-Container-Size`. Any count that exactly equals a default page size is
  a reader bug until proven otherwise.
- The album listing (`type=9`) **carries no usable `leafCount`** in JSON or
  XML. Count tracks with `type=10&artist.id=<ratingKey>`.
- **Windows Plex returns backslash paths.** Splitting on `/` finds nothing and
  reports every folder missing.
- The JSON metadata endpoint may omit `Media`; the XML form reliably carries
  `Media.Part.file` when you need to know which folder backs an album.
- **`refreshing="1"` means every read is the OLD state.** Poll the flag and
  `/activities` until quiet — and require several consecutive idle reads,
  because the flag clears while background metadata work continues.
- Don't hammer a scanning server: a 15-second poll that pulled the full track
  list crashed the server twice. Poll the cheap flag, fetch the payload once.
- `browse`-style endpoints resolve a missing directory to its nearest existing
  parent, so a wrong path returns a *plausible* listing. Control-test with a
  path you know doesn't exist.

## Verifying any Plex fix

Count all three — albums, duplicate titles, total tracks — from Plex after the
scan settles, then compare the track total against disk. A gap means Plex has
not indexed everything and any album-level conclusion is premature.
