#!/usr/bin/env python3
r"""Read a library manifest and produce a ranked worklist -- or diff two manifests.

All of this runs off `library_manifest.py`'s JSONL. No network, no Lidarr, no
Plex -- so it is instant and can be re-run freely while opinions change.

    python library_triage.py --manifest manifest-2026-07-24.jsonl --triage
    python library_triage.py --diff manifest-2026-07-24.jsonl manifest-2026-08-01.jsonl

## Tier 0 -- stacked releases
A folder is ONE release. Signals that it holds more than one:

  * a substantial second group of files carrying a different
    `musicbrainz_albumid` (`SPLIT`). A lone foreign ID is one contaminated
    file (`MINORITY-ID`), not a second release.
  * files on the SAME DISC disagreeing about how many tracks that disc has
  * files disagreeing about the `album` name

AC/DC's `1975 - High Voltage` held the 1975 Australian LP and the 1976
international LP -- different records sharing a name, and even sharing two
tracks. 3 Doors Down's `2000 - The Better Life` held the 2000 album plus a 2021
anniversary edition ripped twice. Both were caught by conflicting release IDs.

This fires even when Plex renders the folder as ONE album, which is the blind
spot of any per-artist visual pass: it only notices the stacks Plex happened
to split.

## Tier 1 -- completeness
Files on disk vs the track total the files themselves declare.

**`tracktotal` is PER DISC, so every comparison is per (album, disc).** A 2-disc
release whose discs hold 15 and 10 declares 15 and 10, never 25. An earlier
version compared totals across the whole folder and called every multi-disc
album stacked -- 42 folders flagged, of which 30 were correct all along.

**The disc number often is not in the tags.** Ayreon's `Into the Electric
Castle` is 17 files with no `discnumber` on any of them, declaring 10 and 7.
Falling back to a numbered subfolder (`CD 02`, `Digital Media 02`, `12 Vinyl
02`) recovers the real layout; without it both discs collapse into one pile and
the count check is meaningless.

**Tier 1 agreement is NOT verification.** The total is a claim written by
whoever ripped the folder; a folder missing tracks whose tag was written from
that same incomplete rip agrees with itself and looks clean. Agreement is
reported as UNVERIFIED, and only MusicBrainz (Tier 2) can promote it.

Measured on the first 46 artists: 3.3% Tier 0, 6.6% Tier 1, 90.1% no evidence of
a problem -- so ~10% of folders need a network call.
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def load(path):
    recs = {}
    bad = 0
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            try:
                r = json.loads(line)
            except Exception:
                bad += 1
                continue
            if r.get("skipped") or "path" not in r:
                continue
            recs[r["path"]] = r
    return recs, bad


def split_path(p):
    """(artist, album) from a manifest path, disc folders collapsed into album."""
    parts = p.replace("\\", "/").split("/")
    if len(parts) < 2:
        return None, None
    if len(parts) == 2:
        return parts[0], "<ROOT>"
    return parts[0], parts[1]


def as_int(v):
    try:
        return int(str(v).split("/")[0].strip())
    except Exception:
        return None


DISC_SUFFIX = __import__("re").compile(r"(\d+)\s*$")


def declared_total(rec):
    """How many tracks this file says its disc has.

    ID3 writes the track number as `5/12`, putting the TOTAL in the track field
    rather than a separate one, so reading `tracktotal` alone finds nothing for
    most MP3s -- which reported 32.8% of folders as declaring no total when the
    real figure is a fraction of that. FLAC/Vorbis uses a real `tracktotal`."""
    t = as_int(rec.get("tracktotal"))
    if t:
        return t
    raw = str(rec.get("track") or "")
    if "/" in raw:
        return as_int(raw.split("/", 1)[1])
    return None


def disc_of(rec, root_album):
    """Which disc a file belongs to.

    The `discnumber` TAG is missing often enough that trusting it alone merges a
    multi-disc release into one pile: Ayreon's `Into the Electric Castle` has 17
    files, no disc tag on any of them, and declares totals of 10 and 7. Falling
    back to the subfolder recovers the real layout -- `CD 02`, `Digital Media 02`
    and `12 Vinyl 02` all end in the disc number."""
    d = as_int(rec.get("disc"))
    if d:
        return d, "tag"
    parts = rec["path"].replace("\\", "/").split("/")
    if len(parts) > 3:                      # Artist/Album/<subfolder>/file
        m = DISC_SUFFIX.search(parts[2])
        if m:
            return int(m.group(1)), "folder"
    return None, "unknown"


def triage(recs, out_csv):
    albums = collections.defaultdict(list)
    for r in recs.values():
        a, alb = split_path(r["path"])
        if a:
            albums[(a, alb)].append(r)

    rows = []
    for (artist, album), files in sorted(albums.items()):
        flags = []
        n = len(files)

        # --- release IDs. More than one is only a SPLIT if the second group is
        # substantial; a lone foreign ID is one contaminated file (the
        # "one-track splinter" the skill describes), not two releases.
        idc = collections.Counter(f["mbid"] for f in files if f.get("mbid"))
        if len(idc) > 1:
            sizes = [c for _i, c in idc.most_common()]
            minority = sum(sizes[1:])
            if minority >= 3 or minority >= 0.25 * n:
                flags.append("SPLIT:%s-release-ids(%s)"
                             % (len(idc), "+".join(str(s) for s in sizes)))
            else:
                flags.append("MINORITY-ID:%d file(s)" % minority)
        if len({f["album"] for f in files if f.get("album")}) > 1:
            flags.append("MIXED-ALBUM-NAMES")

        # --- group by disc, using the subfolder when the tag is absent
        discs = collections.defaultdict(list)
        srcs = set()
        for f in files:
            d, src = disc_of(f, album)
            srcs.add(src)
            discs[d].append(f)

        gaps = []
        declared_any = False
        untagged = discs.pop(None, [])
        if untagged:
            # no disc tag AND no numbered subfolder. If the distinct totals these
            # files declare sum to the file count, it is a multi-disc release
            # missing its disc numbers -- a tagging defect, not a stacked folder.
            tots = sorted({declared_total(f) for f in untagged if declared_total(f)})
            if len(tots) > 1 and sum(tots) == len(untagged):
                flags.append("MISSING-DISC-TAGS:%d discs (%s)"
                             % (len(tots), "+".join(str(t) for t in tots)))
                declared_any = True
            else:
                discs[1] = discs.get(1, []) + untagged

        for dno, dfiles in sorted(discs.items()):
            counter = collections.Counter(declared_total(f) for f in dfiles
                                          if declared_total(f))
            if not counter:
                continue
            declared_any = True
            # tracktotal is PER DISC, so disagreement is only meaningful within
            # one disc. Comparing across a folder flags every multi-disc release.
            if len(counter) > 1:
                odd = sum(c for _t, c in counter.most_common()[1:])
                if odd >= 3 or odd >= 0.25 * len(dfiles):
                    flags.append("DISC%d-CONFLICT:totals %s"
                                 % (dno, ",".join(str(t) for t, _c in counter.most_common())))
                else:
                    flags.append("DISC%d:%d file(s) declare a different total" % (dno, odd))
            want = counter.most_common(1)[0][0]
            have = len(dfiles)
            if have != want:
                gaps.append((dno, have, want))
                flags.append("DISC%d:%d/%d" % (dno, have, want))
        if not declared_any:
            flags.append("NO-DECLARED-TOTAL")

        mbids = set(idc)
        totals = None  # kept out of the report; per-disc figures are what matter
        worst = max((abs(h - w) for _d, h, w in gaps), default=0)
        hard = [f for f in flags if f.startswith(("SPLIT", "MIXED-ALBUM")) or "CONFLICT" in f]
        soft = [f for f in flags if f.startswith(("MINORITY-ID", "MISSING-DISC-TAGS"))]
        sev = (2 if hard else
               1 if gaps or soft or not declared_any else 0)
        rows.append({
            "severity": sev, "gap": worst, "artist": artist, "album": album,
            "files": len(files), "release_ids": len(mbids),
            "needs_musicbrainz": "yes" if (sev or not declared_any) else "no",
            "status": "; ".join(flags) if flags else "UNVERIFIED-OK",
        })

    rows.sort(key=lambda r: (-r["severity"], -r["gap"], r["artist"], r["album"]))
    if out_csv:
        with open(out_csv, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)

    n = len(rows)
    stacked = [r for r in rows if r["severity"] == 2]
    gapped = [r for r in rows if r["severity"] == 1]
    clean = [r for r in rows if r["severity"] == 0]
    print("album folders            : %d   (%d audio files, %d artists)"
          % (n, sum(r["files"] for r in rows), len({r["artist"] for r in rows})))
    print("  TIER 0 stacked/mixed   : %-5d %5.1f%%   %d files"
          % (len(stacked), 100.0 * len(stacked) / max(n, 1), sum(r["files"] for r in stacked)))
    print("  TIER 1 count mismatch  : %-5d %5.1f%%   %d files"
          % (len(gapped), 100.0 * len(gapped) / max(n, 1), sum(r["files"] for r in gapped)))
    print("  no evidence of a problem: %-4d %5.1f%%   %d files   (UNVERIFIED, not confirmed)"
          % (len(clean), 100.0 * len(clean) / max(n, 1), sum(r["files"] for r in clean)))
    print("  need a MusicBrainz call : %d (%.1f%%)"
          % (len(stacked) + len(gapped), 100.0 * (len(stacked) + len(gapped)) / max(n, 1)))
    print("\nworst offenders:")
    for r in rows[:25]:
        print("   [%d] %-52s %3d files  %s"
              % (r["severity"], (r["artist"] + "/" + r["album"])[:50], r["files"], r["status"][:58]))
    if out_csv:
        print("\nfull worklist -> %s" % out_csv)


def diff(old_path, new_path):
    old, _ = load(old_path)
    new, _ = load(new_path)
    removed = sorted(set(old) - set(new))
    added = sorted(set(new) - set(old))
    changed = [p for p in (set(old) & set(new))
               if old[p].get("size") != new[p].get("size")
               or old[p].get("pcm_md5") != new[p].get("pcm_md5")]
    # a file that vanished from one album and appeared in another is a MOVE, not
    # a loss -- match on content where the format gives us a real audio hash
    oldsig = {old[p].get("pcm_md5"): p for p in removed if old[p].get("pcm_md5")}
    moved = []
    for p in list(added):
        sig = new[p].get("pcm_md5")
        if sig and sig in oldsig:
            moved.append((oldsig[sig], p))
    moved_from = {a for a, _b in moved}
    moved_to = {b for _a, b in moved}
    lost = [p for p in removed if p not in moved_from]

    print("old: %-44s %d files" % (old_path.rsplit("/", 1)[-1], len(old)))
    print("new: %-44s %d files" % (new_path.rsplit("/", 1)[-1], len(new)))
    print("  moved   : %d" % len(moved))
    print("  added   : %d" % len([p for p in added if p not in moved_to]))
    print("  changed : %d" % len(changed))
    print("  REMOVED : %d   <- every one of these must be accounted for" % len(lost))
    for p in lost[:40]:
        print("     %s" % p)
    if len(lost) > 40:
        print("     ... %d more" % (len(lost) - 40))
    return 1 if lost else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest")
    ap.add_argument("--triage", action="store_true")
    ap.add_argument("--csv", help="write the full ranked worklist here")
    ap.add_argument("--diff", nargs=2, metavar=("OLD", "NEW"))
    args = ap.parse_args()

    if args.diff:
        return diff(*args.diff)
    if not args.manifest:
        ap.error("--manifest is required unless --diff is used")
    recs, bad = load(args.manifest)
    if bad:
        print("WARNING: %d unparseable line(s) skipped" % bad)
    triage(recs, args.csv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
