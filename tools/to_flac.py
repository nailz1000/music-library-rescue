#!/usr/bin/env python3
r"""Transcode WavPack / WAV / APE / AIFF rips to FLAC, capping at 96 kHz / 24-bit.

Policy (DECISIONS D13): when converting a WavPack/WAV/APE rip, drop to
**96 kHz / 24-bit FLAC** if the source is higher, and treat that as
"lossless". For a vinyl or other analog-sourced rip the discarded rate
(> 48 kHz) and bits (below 24) are noise and empty ultrasonic spectrum, not
music — vinyl holds on the order of 12-14 bits of dynamic range and nothing
above ~30 kHz. The motivating case: a 384 kHz / 32-bit WavPack vinyl rip is
roughly 84% noise by data volume; 96/24 keeps 100% of the real audio at
about 1/6 the size.

Rules:
  * sample rate: keep native if <= 96000, else resample to 96000.
  * bit depth: keep 16-bit sources at 16-bit (never inflate); anything
    deeper -> 24-bit.
  * metadata carried over (`-map_metadata 0`); FLAC compression level 8.
  * every output is verified (valid FLAC, right rate/depth, duration matches).

This also serves as a pre-step for cue-image splitting (`cue_split.py`),
which only reads FLAC/WAV/APE/WavPack sources by name: convert a WavPack or
APE image to FLAC first, then split it.

Dependency: `ffmpeg` on PATH. No sample-rate-conversion library is required
— ffmpeg's default resampler is used, which is fine here because the band
being discarded in the downsample is noise, not signal.

    python3 to_flac.py --folder "path/to/rip"            # dry run
    python3 to_flac.py --folder "path/to/rip" --apply    # writes <folder>/flac/
"""
import argparse
import os
import re
import subprocess

SRC_EXT = (".wv", ".wav", ".ape", ".aiff", ".aif")
CAP_SR = 96000
CAP_BITS = 24


def probe(path):
    """(sample_rate, bits, seconds) via ffmpeg -- reliable across WavPack/
    FLAC/etc. (a general metadata library can report zero for these exotic
    high-rate WavPack files instead of the real value)."""
    err = subprocess.run(["ffmpeg", "-hide_banner", "-i", path],
                          capture_output=True, text=True, errors="replace").stderr
    m = re.search(r"(\d+) Hz", err)
    sr = int(m.group(1)) if m else 0
    dm = re.search(r"Duration:\s*(\d+):(\d+):([\d.]+)", err)
    dur = int(dm.group(1)) * 3600 + int(dm.group(2)) * 60 + float(dm.group(3)) if dm else 0.0
    bm = re.search(r"\((\d+) bit\)", err)                       # e.g. "s32 (24 bit)"
    if bm:
        bits = int(bm.group(1))
    else:
        sm = re.search(r"Audio:\s*[^,]+,\s*\d+ Hz,\s*[^,]+,\s*(\w+)", err)
        sf = sm.group(1) if sm else ""
        bits = 16 if sf.startswith("s16") else (32 if sf.startswith(("s32", "flt", "dbl")) else 24)
    return sr, bits, dur


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--folder", required=True)
    ap.add_argument("--outdir", default=None, help="default: <folder>/flac")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    base = os.path.abspath(args.folder)
    outroot = os.path.abspath(args.outdir) if args.outdir else os.path.join(base, "flac")
    if not os.path.isdir(base):
        print("no such folder: %s" % base)
        return 1

    srcs = []
    for dp, _d, fs in os.walk(base):
        if os.path.abspath(dp).startswith(outroot):
            continue                                   # never re-process our own output
        for f in sorted(fs):
            if f.lower().endswith(SRC_EXT):
                srcs.append(os.path.join(dp, f))
    if not srcs:
        print("no convertible audio (%s) under %s" % ("/".join(SRC_EXT), base))
        return 1

    print("%d source file(s); cap %d Hz / %d-bit FLAC; out=%s\n" % (len(srcs), CAP_SR, CAP_BITS, outroot))
    done = ok = 0
    for s in srcs:
        sr, bits, dur = probe(s)
        tsr = CAP_SR if sr and sr > CAP_SR else (sr or 44100)
        sfmt = "s16" if 0 < bits <= 16 else "s32"       # s32 => 24-bit FLAC in this ffmpeg
        tbits = 16 if sfmt == "s16" else 24
        rel = os.path.relpath(s, base)
        outp = os.path.join(outroot, os.path.splitext(rel)[0] + ".flac")
        print("  %-50s %s/%s %ds -> %d/%d" % (rel[:50], sr or "?", bits or "?", round(dur), tsr, tbits))
        if not args.apply:
            continue
        os.makedirs(os.path.dirname(outp), exist_ok=True)
        cmd = ["ffmpeg", "-hide_banner", "-nostdin", "-v", "error", "-y", "-i", s, "-map_metadata", "0"]
        if tsr != sr:
            cmd += ["-af", "aresample=%d" % tsr]
        cmd += ["-sample_fmt", sfmt, "-c:a", "flac", "-compression_level", "8", outp]
        try:
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as e:
            print("       FFMPEG FAILED: %s" % e)
            continue
        done += 1
        osr, obits, odur = probe(outp)
        good = osr == tsr and 0 < obits <= CAP_BITS and abs(odur - dur) < 0.05
        ok += 1 if good else 0
        print("       -> %s/%s %ds  %s" % (osr, obits, round(odur), "OK" if good else "*** DURATION/FORMAT MISMATCH ***"))

    print("\n%s: %d/%d file(s)%s%s"
          % ("APPLIED" if args.apply else "DRY RUN", ok if args.apply else len(srcs), len(srcs),
             " verified OK" if args.apply else "",
             "" if args.apply else "  (re-run with --apply)"))
    return 0 if (not args.apply or ok == done) else 2


if __name__ == "__main__":
    raise SystemExit(main())
