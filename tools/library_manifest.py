#!/usr/bin/env python3
r"""Walk a music library once and record everything downstream work needs.

One streaming pass producing a JSONL manifest: per file — path, size, mtime,
duration, sample rate, bit depth, channels, codec, and the identity tags
(artist, albumartist, album, title, date, originaldate/year, MusicBrainz
release id, disc, track, tracktotal, disctotal). The manifest is both a
**baseline ledger** (diff two manifests to make loss detectable, not just
reversible) and the input to `library_triage.py`.

Design notes, each paid for in the source project:

* **Streams JSONL, one line per file, flushed as it goes.** A first version
  printed its summary at the end, died ~20 minutes in, and left an empty file
  -- no partial results and no clue where it stopped.
* **Resumable.** Re-running skips paths already in the manifest, so a death
  costs only the files since the last flush.
* **No ffprobe / no decoding.** mutagen reads duration, sample rate, bit depth
  and channels straight from the header for free; decoding tens of thousands
  of files to hash them costs hours.
* **FLAC carries its own decoded-audio MD5** in STREAMINFO (`md5_signature`),
  so lossless files get a true content hash at zero cost -- that field is what
  lets a later diff tell a MOVED file from a LOST one. MP3 has no equivalent;
  those rely on (size, mtime, duration). Stated rather than papered over.
* **Case-alias safe.** SMB shares backed by case-sensitive filesystems can
  present ONE physical file under two names differing only by case; a tool
  that trusts the listing counts it twice (or deletes "the duplicate", i.e.
  the only copy). Files are de-duplicated by stat identity (st_dev, st_ino).
* **Takes an exclusive lock.** Two copies were once started against one
  manifest -- because a broken liveness check (`ps w`, which hides processes
  with no controlling terminal) said the first had died -- and wrote 1,265
  duplicate records. A second run now refuses to start.

Run it ON the machine that owns the disks (over SSH), not across a network
mount -- measured ~20x faster server-side. Detach so a dropped session can't
kill a long walk:

    nohup python3 library_manifest.py --root /path/to/Music \
        --out manifest-$(date +%F).jsonl > scan.log 2>&1 &

**Check liveness with `ps -ef` or `pgrep`, never `ps w`** -- `ps w` lists only
processes with a controlling terminal, so it reports a detached scan dead
while it runs perfectly.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import mutagen

AUDIO = (".flac", ".mp3", ".m4a", ".wav", ".ogg", ".wma", ".aac", ".opus", ".ape", ".wv")

# one tag name per concept; mutagen's easy interface already normalises most of
# the format differences, and the rest are handled by trying each in order
TAGS = {
    "artist": ("artist",),
    "albumartist": ("albumartist", "album artist"),
    "album": ("album",),
    "title": ("title",),
    "date": ("date",),
    "originaldate": ("originaldate",),
    "originalyear": ("originalyear",),
    "mbid": ("musicbrainz_albumid",),
    "disc": ("discnumber",),
    "track": ("tracknumber",),
    "tracktotal": ("tracktotal", "totaltracks"),
    "disctotal": ("disctotal", "totaldiscs"),
}


def first(tags, names):
    for n in names:
        v = tags.get(n)
        if v:
            return str(v[0])
    return ""


def probe(path):
    """Everything about one file, from its header. No decode, no subprocess."""
    st = os.stat(path)
    rec = {"size": st.st_size, "mtime": int(st.st_mtime)}
    try:
        m = mutagen.File(path, easy=True)
    except Exception as e:
        rec["error"] = "%s: %s" % (type(e).__name__, e)
        return rec
    if m is None:
        rec["error"] = "unreadable by mutagen"
        return rec
    info = getattr(m, "info", None)
    if info is not None:
        rec["dur"] = round(getattr(info, "length", 0) or 0, 3)
        for src, dst in (("sample_rate", "sr"), ("bits_per_sample", "bits"),
                         ("channels", "ch"), ("bitrate", "br")):
            v = getattr(info, src, None)
            if v:
                rec[dst] = v
        rec["codec"] = type(info).__module__.rsplit(".", 1)[-1]
    tags = m.tags or {}
    for key, names in TAGS.items():
        v = first(tags, names)
        if v:
            rec[key] = v
    # FLAC stores the MD5 of the UNENCODED audio in its header -- a real content
    # hash for free. Zero means the encoder did not write one.
    sig = getattr(getattr(m, "info", None), "md5_signature", 0)
    if sig:
        rec["pcm_md5"] = "%032x" % sig
    return rec


def take_lock(path, force):
    """Refuse to run twice against one manifest.

    Two concurrent scans append interleaved records to the same file, and the
    resume logic then can't tell a duplicate from a fresh record. Created with
    O_EXCL so the check and the claim are one atomic step."""
    lock = path + ".lock"
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        try:
            with open(lock) as fh:
                pid = int((fh.read().split() or ["0"])[0])
        except Exception:
            pid = 0
        alive = False
        if pid:
            try:
                os.kill(pid, 0)          # signal 0 = "does this pid exist?"
                alive = True
            except OSError:
                alive = False
        if alive and not force:
            print("REFUSING: pid %d is already scanning into %s\n"
                  "  (verify with: ps -ef | grep '[l]ibrary_manifest.py')\n"
                  "  use --force only if you are certain that process is gone"
                  % (pid, path), file=sys.stderr)
            return None
        print("stale lock from pid %s -- taking over" % (pid or "?"), flush=True)
        os.unlink(lock)
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    os.write(fd, ("%d\n" % os.getpid()).encode())
    os.close(fd)
    return lock


def load_done(path):
    """Paths already recorded. Keeps only the LAST record per path, so a
    manifest polluted by an earlier concurrent run still resumes correctly."""
    done = {}
    if not os.path.exists(path):
        return done
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            try:
                rec = json.loads(line)
                done[rec["path"]] = rec
            except Exception:
                pass
    return done


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True, help="library root to walk")
    ap.add_argument("--out", required=True, help="JSONL manifest path (append/resume)")
    ap.add_argument("--every", type=int, default=500, help="progress + flush interval")
    ap.add_argument("--force", action="store_true", help="override a lock believed stale")
    ap.add_argument("--dedupe", action="store_true",
                    help="rewrite the manifest keeping one record per path, then exit")
    args = ap.parse_args()

    if args.dedupe:
        recs = load_done(args.out)
        tmp = args.out + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            for p in sorted(recs):
                fh.write(json.dumps(recs[p], ensure_ascii=False) + "\n")
        before = sum(1 for _ in open(args.out, encoding="utf-8"))
        os.replace(tmp, args.out)
        print("deduped %d line(s) -> %d unique path(s)" % (before, len(recs)))
        return 0

    lock = take_lock(args.out, args.force)
    if lock is None:
        return 2

    done = set(load_done(args.out))
    if done:
        print("resuming: %d file(s) already recorded" % len(done), flush=True)

    seen_ids = set()
    n = skipped = aliased = errors = 0
    t0 = time.time()
    out = open(args.out, "a", encoding="utf-8")
    for dirpath, dirnames, filenames in os.walk(args.root):
        dirnames.sort()
        for fn in sorted(filenames):
            if not fn.lower().endswith(AUDIO):
                continue
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, args.root)
            if rel in done:
                skipped += 1
                continue
            try:
                st = os.stat(full)
            except OSError as e:
                out.write(json.dumps({"path": rel, "error": str(e)}) + "\n")
                errors += 1
                continue
            # two names, one physical file (SMB case alias): count it once
            ident = (st.st_dev, st.st_ino)
            if ident in seen_ids:
                aliased += 1
                out.write(json.dumps({"path": rel, "alias_of_inode": st.st_ino,
                                      "skipped": "case-alias"}) + "\n")
                continue
            seen_ids.add(ident)
            rec = probe(full)
            rec["path"] = rel
            if "error" in rec:
                errors += 1
            out.write(json.dumps(rec, ensure_ascii=False) + "\n")
            n += 1
            if n % args.every == 0:
                out.flush()
                os.fsync(out.fileno())
                el = time.time() - t0
                print("  %6d files  %5.1f/s  %5.1f min elapsed  (%s)"
                      % (n, n / max(el, 1e-9), el / 60, rel[:60]), flush=True)
    out.flush()
    os.fsync(out.fileno())
    out.close()
    try:
        os.unlink(lock)
    except OSError:
        pass
    el = time.time() - t0
    print("DONE %d file(s) in %.1f min (%.1f/s); %d resumed-skip, %d case-alias, %d error"
          % (n, el / 60, n / max(el, 1e-9), skipped, aliased, errors), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
