#!/usr/bin/env python3
r"""Losslessly split a cue-referenced single-file album image (one file per
vinyl side, or a whole album as one file) into per-track FLACs, using the
`.cue` sheet's INDEX offsets.

This is the "long file, no track boundaries" shape a rip can arrive in: one
audio file per side plus a `.cue` that says where each track starts — the
common vinyl-transfer case. The cue is the discriminator: cue present ->
splittable. A long lone file with NO cue could be a legitimate continuous
mix or DJ set — that goes to manual review, never an automatic split (see
docs/03-duplicates-and-quality.md).

HOW IT STAYS BIT-PERFECT
  Cue `INDEX MM:SS:FF` times use CD frames (`FF`, 1/75 second). For every
  standard sample rate (44100, 48000, 88200, 96000, 176400, 192000 Hz),
  dividing by 75 gives a whole number, so every track boundary lands on an
  exact sample — no rounding, no drift. Cutting with ffmpeg's
  `atrim=start_sample=..:end_sample=..` is sample-accurate (not
  time-approximate); the split then re-encodes to FLAC, which is lossless.
  Track N ends exactly where track N+1 begins; the final track in a file
  runs to end-of-file. Concatenating the split tracks therefore reproduces
  the original PCM byte-for-byte — which `--verify` proves by decoding the
  splits and the source to raw PCM and comparing MD5s, rather than trusting
  that the cut "looked right".

  Each source FILE is decoded ONCE (ffmpeg's `asplit` filter fans one decode
  out to every `atrim` it feeds), so an N-track side costs one decode pass,
  not N.

TWO SILENT NO-OP TRAPS (PLAYBOOK L30)
  1. A scene-release folder name often carries brackets, e.g.
     `[001+114] Artist - Album`. Listing that directory with `glob` treats
     `[...]` as a character class, not a literal — it matches nothing and
     looks exactly like an empty folder. This script lists directories with
     `os.listdir` + a suffix filter, never a glob built from the folder name.
  2. The cue's `FILE` lines can name files that don't match what's actually
     on disk (a stray prefix tacked on by whoever built the rip). This
     script resolves each FILE reference defensively — exact match, then a
     stripped bracket/brace prefix, then position-order mapping against the
     folder's audio files when the counts agree — and REFUSES outright
     rather than silently skipping a track it couldn't resolve.

SAFETY
  Writes only into `<cue dir>/split` (or `--outdir`); the source files are
  never modified. Dry run by default — it prints the plan; `--apply`
  performs the split, `--verify` additionally proves it bit-perfect.

Dependencies: `ffmpeg` on PATH, `mutagen` (`pip install mutagen`).

    python3 cue_split.py --cue "Side A.cue"                  # dry run
    python3 cue_split.py --folder "path/to/rip"              # auto-picks the cue
    python3 cue_split.py --cue "Side A.cue" --apply --verify
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from collections import OrderedDict

try:
    from mutagen.flac import FLAC
    import mutagen
except ImportError:
    sys.exit("cue_split.py needs mutagen: pip install mutagen")

# A header probe (not a decode) normally finishes in well under a second;
# bounded anyway so a pathological file can't hang the script forever.
PROBE_TIMEOUT_S = 60
# Decode-verify timeout: a floor plus a multiple of the audio's own length,
# since a full-album decode legitimately takes longer than a quick probe.
VERIFY_TIMEOUT_FLOOR_S = 120
VERIFY_TIMEOUT_PER_SECOND = 4


def strip_kw(line, kw):
    return line[len(kw):].strip().strip('"').strip()


def parse_cue(cue_path):
    """Return (album_dict, [track_dict, ...]) parsed from a .cue sheet."""
    album = {"performer": "", "title": "", "date": "", "genre": ""}
    tracks, cur_file, cur, seen_track = [], None, None, False
    with open(cue_path, encoding="utf-8", errors="replace") as fh:
        for raw in fh:
            line = raw.strip()
            if line.startswith("REM GENRE"):
                album["genre"] = strip_kw(line, "REM GENRE")
            elif line.startswith("REM DATE"):
                album["date"] = strip_kw(line, "REM DATE")
            elif line.startswith("FILE "):
                m = re.match(r'FILE\s+"(.+)"\s+\w+\s*$', line) or re.match(r"FILE\s+(\S+)\s+\w+\s*$", line)
                cur_file = m.group(1) if m else line[5:].strip().strip('"')
            elif line.startswith("TRACK ") and line.rstrip().endswith("AUDIO"):
                m = re.match(r"TRACK\s+(\d+)\s+AUDIO", line)
                cur = {"num": int(m.group(1)), "title": "", "performer": "", "file": cur_file, "frames": None}
                tracks.append(cur)
                seen_track = True
            elif line.startswith("TITLE "):
                val = strip_kw(line, "TITLE")
                (cur if (seen_track and cur is not None) else album)["title"] = val
            elif line.startswith("PERFORMER "):
                val = strip_kw(line, "PERFORMER")
                (cur if (seen_track and cur is not None) else album)["performer"] = val
            elif line.startswith("INDEX 01"):
                m = re.search(r"INDEX\s+01\s+(\d+):(\d+):(\d+)", line)
                if m and cur is not None:
                    mm, ss, ff = map(int, m.groups())
                    cur["frames"] = (mm * 60 + ss) * 75 + ff
    return album, tracks


def sanitize(s):
    s = s.replace(":", " -").replace("/", "-").replace("\\", "-")
    s = re.sub(r'[<>"|?*]', "", s)
    s = re.sub(r"\s+", " ", s).strip().rstrip(". ")
    return s or "Untitled"


def hms(sec):
    return "%d:%05.2f" % (int(sec) // 60, sec - 60 * (int(sec) // 60))


def pcm_codec(bps):
    return {16: "pcm_s16le", 24: "pcm_s24le", 32: "pcm_s32le"}.get(bps, "pcm_s24le")


# Scene release folders often encode artist/album/year when the cue itself
# does not, e.g. "[001+114] Some_Band-Some_Album-2LP-24BIT-FLAC-1985-GROUP".
# Tokens after the album are format/quality tags, then the year, then the
# release-group name.
_REL_TAG = re.compile(
    r"^(?:\d*(?:LP|CD|DVD|SACD)|WEB|FLAC|WAVPACK|APE|MP3|VINYL|\d+BIT|\d+KHZ|"
    r"REMASTER(?:ED)?|DELUXE|PROPER|REPACK|LIMITED|EDITION|BOXSET|EP|SINGLE|"
    r"ADVANCE|PROMO|REISSUE|ANNIVERSARY|EXPANDED|HDTRACKS|QOBUZ|BANDCAMP)$",
    re.IGNORECASE)


def derive_from_folder(folder):
    """(artist, album, year) parsed from a scene-style release folder name.

    A cue is not required to carry album-level PERFORMER/TITLE/REM DATE, and
    plenty don't — some cues start straight at FILE with no header at all.
    Tracks split from such a cue come out with a title and nothing else,
    which nothing downstream can file with any confidence. The folder name
    is evidence that IS present, so it becomes the fallback.

    Returns empty strings for anything it can't parse confidently. It never
    overrides a value the cue actually supplied.
    """
    name = os.path.basename(os.path.normpath(folder))
    name = re.sub(r"^\[[^\]]*\]\s*", "", name)                 # leading [scene] tag
    name = re.sub(r"\.part\d+\.rar(\.\d+)?$|\.rar(\.\d+)?$", "", name, flags=re.I)
    parts = name.split("-")
    if len(parts) < 2:
        return "", "", ""
    artist = parts[0].replace("_", " ").strip()
    album_bits, year = [], ""
    for seg in parts[1:]:
        if re.fullmatch(r"(19|20)\d{2}", seg):
            year = seg
            break
        if _REL_TAG.match(seg):
            break
        album_bits.append(seg)
    if not year:                      # year may sit after the format tags
        m = re.search(r"-((?:19|20)\d{2})-", name)
        year = m.group(1) if m else ""
    album = " ".join(b.replace("_", " ").strip() for b in album_bits).strip()
    return artist, album, year


def _run(cmd, timeout_s, **kw):
    """subprocess.run with a wall-clock ceiling. Returns (status, result):
    status is "ok", "error", or "timeout" — a timeout is a claim about the
    INVOCATION, never about the file, and callers must not read it as proof
    the source or the split is bad."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s, **kw)
        return ("ok" if r.returncode == 0 else "error"), r
    except subprocess.TimeoutExpired:
        return "timeout", None


def probe_source(path):
    """(path, sample_rate, total_samples, bps, embedded_md5, is_float).

    FLAC is read exactly via mutagen (and carries a real STREAMINFO MD5 of
    the decoded audio for free). Everything else (.wv/.ape/...) is read via
    mutagen for duration/rate, plus an `ffmpeg -i` header probe for the
    sample format — mutagen can report 0 for exotic containers it can't
    fully parse, which is "couldn't read", not "no properties" (see
    docs/03-duplicates-and-quality.md on trusting a zero).

    Float sources report bps=24 and is_float=True: FLAC can't represent
    float, so 24-bit int is the write/verify convention — ffmpeg's
    float->s32->24-bit-FLAC conversion is deterministic (no dither by
    default), which is what makes an equal-representation MD5 check valid.
    """
    if path.lower().endswith(".flac"):
        fl = FLAC(path)
        return (path, fl.info.sample_rate, fl.info.total_samples,
                fl.info.bits_per_sample, "%032x" % fl.info.md5_signature, False)
    mf = mutagen.File(path)
    if mf is None:
        raise SystemExit("cannot read audio geometry of %s" % path)
    sr = mf.info.sample_rate
    total = int(round(mf.info.length * sr))
    status, r = _run(["ffmpeg", "-nostdin", "-i", path], PROBE_TIMEOUT_S)
    if status == "timeout":
        raise SystemExit("header probe of %s exceeded %ss; nothing concluded "
                          "about the file" % (path, PROBE_TIMEOUT_S))
    m = re.search(r"Audio:.*?,\s*\d+\s*Hz,[^,]*,\s*(\w+)", (r.stderr if r else "") or "")
    fmt = (m.group(1) if m else "").lower()
    is_float = fmt.startswith("flt") or fmt.startswith("dbl")
    bps = 16 if fmt.startswith("s16") else 24
    # no embedded md5 outside FLAC: verify always re-decodes the original
    return (path, sr, total, bps, "0" * 32, is_float)


class VerifyTimeout(RuntimeError):
    """A decode-verify ffmpeg call hit its wall-clock ceiling. This is a
    claim about the invocation, not the file — report it as its own outcome,
    never folded into a pass or a real mismatch."""


def _duration_s(path):
    try:
        m = mutagen.File(path)
        d = getattr(getattr(m, "info", None), "length", None)
        return float(d) if d else None
    except Exception:
        return None


def _verify_timeout_for(paths):
    durs = [d for d in (_duration_s(p) for p in paths) if d]
    dur = sum(durs) if durs else None
    return VERIFY_TIMEOUT_FLOOR_S + int((dur or 0) * VERIFY_TIMEOUT_PER_SECOND)


def ffmpeg_pcm_md5(inputs, bps, timeout_s=None):
    """MD5 of decoded interleaved PCM for one file or a concat list of files."""
    if len(inputs) == 1:
        cmd = ["ffmpeg", "-nostdin", "-v", "error", "-i", inputs[0]]
    else:
        lst = inputs[0] + ".concat.txt"
        with open(lst, "w", encoding="utf-8") as fh:
            for p in inputs:
                fh.write("file '%s'\n" % p.replace("'", "'\\''"))
        cmd = ["ffmpeg", "-nostdin", "-v", "error", "-f", "concat", "-safe", "0", "-i", lst]
    cmd += ["-map", "0:a", "-c:a", pcm_codec(bps), "-f", "md5", "-"]
    status, r = _run(cmd, timeout_s or _verify_timeout_for(inputs))
    if status == "timeout":
        raise VerifyTimeout("decode-verify exceeded its wall-clock ceiling on %r" % (inputs,))
    if status != "ok":
        raise subprocess.CalledProcessError(
            r.returncode if r is not None else 1, cmd,
            output=r.stdout if r is not None else "", stderr=r.stderr if r is not None else "")
    return (r.stdout or "").strip().split("=")[-1].lower()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cue", help="explicit .cue path")
    ap.add_argument("--folder", help="rip folder; auto-selects the .cue that references the MOST "
                                      "FILE entries whose files actually resolve on disk (the real "
                                      "image cue, not a single-track decoy)")
    ap.add_argument("--outdir", default=None)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--artist", default="",
                     help="override album artist when neither the cue nor the folder name yields one")
    ap.add_argument("--album", default="",
                     help="override album title, same rationale as --artist")
    ap.add_argument("--compression", default="8")
    args = ap.parse_args()

    cue_path = args.cue
    if not cue_path and args.folder:
        # os.listdir, NOT glob: scene folders contain [..] which glob would treat
        # as a character class and fail to match the literal directory name.
        if not os.path.isdir(args.folder):
            print("not a folder: %s" % args.folder)
            return 1
        cues = [os.path.join(args.folder, f) for f in os.listdir(args.folder)
                if f.lower().endswith(".cue")]
        if not cues:
            print("no .cue found in %s" % args.folder)
            return 1

        def _file_names(c):
            names = []
            try:
                for ln in open(c, encoding="utf-8", errors="replace"):
                    s = ln.strip()
                    if not s.upper().startswith("FILE"):
                        continue
                    m = re.match(r'FILE\s+"([^"]+)"', s, re.I) or re.match(r"FILE\s+(\S+)", s, re.I)
                    if m:
                        names.append(m.group(1))
            except Exception:
                pass
            return names

        def file_refs(c):
            return len(_file_names(c))

        def resolved_refs(c):
            """FILE refs that name a file actually present next to the cue.

            A rip can ship BOTH an older-era cue and a FLAC-era cue for the
            same disc, tied on FILE-ref count — ranking by count alone would
            let ties resolve arbitrarily (whichever the directory listing
            happened to yield first), possibly the one whose paths don't
            exist. Prefer the cue whose references actually RESOLVE.
            """
            d = os.path.dirname(os.path.abspath(c))
            have = {f.lower() for f in os.listdir(d)} if os.path.isdir(d) else set()
            return sum(1 for n in _file_names(c)
                       if os.path.basename(n).lower() in have)

        # Resolvable first, then richest. Ties inside that are broken by name so
        # the choice is at least deterministic across runs.
        cue_path = max(cues, key=lambda c: (resolved_refs(c), file_refs(c),
                                             os.path.basename(c).lower()))
        print("auto-selected cue (%d FILE refs, %d resolve on disk): %s"
              % (file_refs(cue_path), resolved_refs(cue_path), os.path.basename(cue_path)))
    if not cue_path:
        print("need --cue or --folder")
        return 1
    base_dir = os.path.dirname(os.path.abspath(cue_path))
    outdir = args.outdir or os.path.join(base_dir, "split")
    album, tracks = parse_cue(cue_path)
    if not tracks:
        print("no AUDIO tracks parsed from cue")
        return 1

    # A cue need not carry album-level PERFORMER/TITLE/DATE, and when it
    # doesn't the split tracks come out with a title and nothing else. Fall
    # back to the release folder name, which encodes exactly these three
    # fields for scene-style rips. Never overrides the cue.
    f_artist, f_album, f_year = derive_from_folder(base_dir)
    # Explicit overrides win over the folder guess but still never override
    # the cue: only supply these when you have better evidence than a
    # filename parse (e.g. metadata from wherever the album was catalogued).
    if args.artist:
        f_artist = args.artist
    if args.album:
        f_album = args.album
    borrowed = []
    if not album["performer"] and f_artist:
        album["performer"] = f_artist
        borrowed.append("artist=%r" % f_artist)
    if not album["title"] and f_album:
        album["title"] = f_album
        borrowed.append("album=%r" % f_album)
    if not album["date"] and f_year:
        album["date"] = f_year
        borrowed.append("date=%r" % f_year)
    if borrowed:
        print("cue lacks album metadata; borrowed from folder name: %s" % ", ".join(borrowed))
    if not album["performer"] or not album["title"]:
        print("REFUSING: no artist/album from the cue OR the folder name -- "
              "split output would be untagged and unfileable.")
        return 1

    # Reconcile cue FILE names against what's actually on disk. Some rips
    # carry a junk prefix in the cue (e.g. "{xxxx} some_file.flac") or
    # otherwise mismatch. Try: exact -> strip a leading {..}/[..] token ->
    # map FILE refs to the folder's audio files in cue order when the counts
    # match.
    AUDIO_EXT = (".flac", ".wav", ".ape", ".wv", ".aiff", ".aif")
    disk_audio = sorted(f for f in os.listdir(base_dir) if f.lower().endswith(AUDIO_EXT))
    cue_files = []
    for t in tracks:
        if t["file"] not in cue_files:
            cue_files.append(t["file"])

    def resolve_one(fn):
        if os.path.exists(os.path.join(base_dir, fn)):
            return fn
        stripped = re.sub(r"^\s*[\{\[][^\}\]]*[\}\]]\s*", "", fn)
        if stripped != fn and os.path.exists(os.path.join(base_dir, stripped)):
            return stripped
        return None

    resolved = {fn: resolve_one(fn) for fn in cue_files}
    if any(v is None for v in resolved.values()):
        if len(cue_files) == len(disk_audio):
            resolved = {fn: disk_audio[i] for i, fn in enumerate(cue_files)}
            print("NOTE: cue FILE names do not match disk; mapped %d FILE ref(s) to the %d "
                  "audio file(s) in order:" % (len(cue_files), len(disk_audio)))
            for fn in cue_files:
                print("   %r -> %s" % (fn, resolved[fn]))
        else:
            missing = [fn for fn, v in resolved.items() if v is None]
            print("MISSING source file(s) referenced by cue (%d FILE ref(s) vs %d audio on disk): %s"
                  % (len(cue_files), len(disk_audio), missing))
            return 1
    for t in tracks:
        t["file"] = resolved[t["file"]]

    # resolve each FILE, attach sample geometry
    finfo = {}
    for t in tracks:
        fn = t["file"]
        if fn not in finfo:
            p = os.path.join(base_dir, fn)
            if not os.path.exists(p):
                print("MISSING source file referenced by cue: %s" % p)
                return 1
            finfo[fn] = probe_source(p)
        p, sr, total, bps, _, is_float = finfo[fn]
        t.update(path=p, sr=sr, total=total, bps=bps)
        t["start"] = int(round(t["frames"] * sr / 75.0))
    if any(v[5] for v in finfo.values()):
        print("NOTE: FLOAT source detected (e.g. 32-bit float WavPack). FLAC cannot")
        print("      represent float, so tracks are written as 24-bit FLAC -- a")
        print("      deliberate depth conversion, inaudible for any vinyl/ADC source.")
        print("      Verification compares source and output at the SAME s24 PCM")
        print("      representation, which is what proves the cut+encode exact.")
    # end = next track's start within same file, else EOF
    for i, t in enumerate(tracks):
        if i + 1 < len(tracks) and tracks[i + 1]["file"] == t["file"]:
            t["end"] = tracks[i + 1]["start"]
        else:
            t["end"] = t["total"]
        t["outname"] = "%02d - %s.flac" % (t["num"], sanitize(t["title"]))

    print("Album : %s -- %s (%s)  genre=%s" % (album["performer"], album["title"], album["date"], album["genre"]))
    print("Source: %s" % base_dir)
    print("Files : %s" % ", ".join("%s [%d Hz / %d-bit / %d samples]" % (k, v[1], v[3], v[2]) for k, v in finfo.items()))
    print("Output: %s\n" % outdir)
    print("  #  start->end (samples)      dur       output")
    for t in tracks:
        print("  %02d %10d->%-10d  %8s  %s"
              % (t["num"], t["start"], t["end"], hms((t["end"] - t["start"]) / t["sr"]), t["outname"]))
    bad = [t for t in tracks if not (0 <= t["start"] < t["end"] <= t["total"])]
    if bad:
        print("\nREFUSING: %d track(s) have an out-of-range sample window." % len(bad))
        return 1

    if not args.apply:
        print("\nDRY RUN -- re-run with --apply (add --verify to prove bit-perfect).")
        return 0

    os.makedirs(outdir, exist_ok=True)
    files = OrderedDict()
    for t in tracks:
        files.setdefault(t["file"], []).append(t)

    # split: one ffmpeg pass per source FILE (asplit -> per-track atrim)
    for fn, ftr in files.items():
        src = ftr[0]["path"]
        n = len(ftr)
        parts = ["[0:a]asplit=%d%s" % (n, "".join("[a%d]" % k for k in range(n)))]
        cmd = ["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", src]
        for k, t in enumerate(ftr):
            parts.append("[a%d]atrim=start_sample=%d:end_sample=%d,asetpts=PTS-STARTPTS[o%d]"
                          % (k, t["start"], t["end"], k))
        cmd += ["-filter_complex", ";".join(parts)]
        for k, t in enumerate(ftr):
            t["tmp"] = os.path.join(outdir, "_tmp_%02d.flac" % t["num"])
            cmd += ["-map", "[o%d]" % k, "-c:a", "flac", "-compression_level", args.compression, t["tmp"]]
        print("\nsplitting %s -> %d track(s) (one decode pass)..." % (fn, n))
        status, r = _run(cmd, _verify_timeout_for([src]))
        if status == "timeout":
            for t in ftr:
                try:
                    os.unlink(t["tmp"])
                except OSError:
                    pass
            print("  %-40s SPLIT-TIMEOUT -- wall-clock ceiling hit; partial "
                  "outputs removed; nothing concluded about the file" % fn)
            return 3
        if status != "ok":
            raise subprocess.CalledProcessError(r.returncode, cmd, output=r.stdout, stderr=r.stderr)

    # tag + final names
    for t in tracks:
        fl = FLAC(t["tmp"])
        fl.delete()
        fl["title"] = t["title"] or ("Track %02d" % t["num"])
        fl["artist"] = t["performer"] or album["performer"]
        fl["albumartist"] = album["performer"] or t["performer"]
        fl["album"] = album["title"]
        if album["date"]:
            fl["date"] = album["date"]
        if album["genre"]:
            fl["genre"] = album["genre"]
        fl["tracknumber"] = str(t["num"])
        fl["tracktotal"] = str(len(tracks))
        fl.save()
        final = os.path.join(outdir, t["outname"])
        if os.path.abspath(t["tmp"]) != os.path.abspath(final):
            os.replace(t["tmp"], final)
        t["final"] = final
    print("\nwrote %d track(s) to %s" % (len(tracks), outdir))

    if args.verify:
        print("\n=== VERIFY (decoded-PCM MD5 of split tracks vs original) ===")
        all_ok = True
        any_timeout = False
        for fn, ftr in files.items():
            bps = ftr[0]["bps"]
            embedded = finfo[fn][4]
            try:
                split_md5 = ffmpeg_pcm_md5([t["final"] for t in ftr], bps)
            except VerifyTimeout as e:
                print("  %-40s VERIFY-TIMEOUT  %s" % (fn, e))
                any_timeout = True
                continue
            ref = embedded
            note = "embedded STREAMINFO md5"
            if embedded == "0" * 32 or embedded != split_md5:
                try:
                    ref = ffmpeg_pcm_md5([ftr[0]["path"]], bps)  # decode original, same convention
                except VerifyTimeout as e:
                    print("  %-40s VERIFY-TIMEOUT (re-decoding original)  %s" % (fn, e))
                    any_timeout = True
                    continue
                note = "re-decoded original"
            ok = split_md5 == ref
            all_ok &= ok
            print("  %-40s %s  (vs %s)\n      split=%s\n      orig =%s"
                  % (fn, "BIT-PERFECT" if ok else "*** MISMATCH ***", note, split_md5, ref))
        if any_timeout:
            # A VERIFY-TIMEOUT is a claim about the invocation, not the file
            # -- report it as its own outcome, never folded into ALL FILES
            # BIT-PERFECT or *** MISMATCH ***.
            print("\n*** at least one file hit VERIFY-TIMEOUT -- re-run with a longer "
                  "timeout, or verify that file by hand ***")
            return 3
        print("\n%s" % ("ALL FILES BIT-PERFECT -- lossless split confirmed." if all_ok
                         else "*** verification FAILED on at least one file ***"))
        return 0 if all_ok else 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
