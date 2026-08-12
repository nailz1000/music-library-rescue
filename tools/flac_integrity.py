#!/usr/bin/env python3
"""Find FLAC files that are broken, truncated, or not what they claim to be.

Read-only. Nothing here moves, retags, or deletes anything.

    python flac_integrity.py /path/to/music
    python flac_integrity.py /path/to/music --json findings.jsonl

Most library checks ask whether the METADATA is right and assume the audio
underneath is fine. This asks the other question, and the first thing it found
in a real 31,000-file library was a track that had been sitting there unplayable
for years:

    Billie Jean.flac   declares 16bit/44.1kHz stereo, 294.3s = 51.9 MB
                       contains 117.5 MB of audio
                       ffmpeg: "switching bps mid-stream is not supported"

A FLAC stream cannot be larger than the audio it decodes to. That is
arithmetic, not a judgement, and it needs no decoding to detect -- so it is
affordable across a whole library. The file was invisible to every other check
because it LOOKS healthy: right title, right track number, right album,
plausible duration, and a size that reads as "high quality" rather than
"impossible".

Verdicts, worst first:

  IMPOSSIBLE        audio payload exceeds the uncompressed size the header
                    implies. The file is corrupt. Stated as fact.
  UNREADABLE        no STREAMINFO, or the header does not parse.
  SUSPICIOUSLY SMALL  under 5% of the expected size -- probably truncated,
                    though a genuine very short track looks the same.
  ID3-PREFIXED      an ID3v2 block sits in front of the FLAC magic. The audio
                    is INTACT and players read it; strict parsers do not.
                    Cosmetic. An earlier version of this script called these
                    "not a FLAC", which is exactly the sort of alarming-but-
                    wrong verdict that gets a good file deleted.
  NO PCM CHECKSUM   the header's MD5 of the unencoded audio is all zeroes, so
                    a standard encoder did not write this file. Informational
                    only -- it says nothing about whether the audio is right,
                    and it is COMMON (152 files in one artist), so it is
                    counted by folder rather than listed per file.

`--decode` additionally runs every flagged file through ffmpeg. Note the two
traps that cost real time when this was written: bound each decode with a
timeout, or one hung decode outlives the run and pins a CPU for hours; and give
ffmpeg `-nostdin` plus `< /dev/null`, or it consumes the rest of a piped
script (see PLAYBOOK L50, L60).
"""
from __future__ import annotations

import argparse
import json
import os
import struct
import subprocess
import sys
from collections import Counter


def probe(path):
    """Parse a FLAC's metadata blocks. Returns a dict, never raises."""
    try:
        with open(path, "rb") as f:
            head = f.read(4)
            id3 = False
            if head[:3] == b"ID3":
                # Some taggers write an ID3v2 block in front of a FLAC: a
                # 10-byte header then a syncsafe size (7 bits per byte).
                id3 = True
                f.seek(6)
                size = 0
                for b in f.read(4):
                    size = (size << 7) | (b & 0x7F)
                f.seek(10 + size)
                head = f.read(4)
            if head != b"fLaC":
                return {"path": path, "err": "not a FLAC (magic %s)"
                        % head.hex()}

            sr = ch = bps = total = 0
            md5 = ""
            seen = False
            while True:
                h = f.read(4)
                if len(h) < 4:
                    break
                last, typ = h[0] & 0x80, h[0] & 0x7F
                n = struct.unpack(">I", b"\x00" + h[1:4])[0]
                d = f.read(n)
                if typ == 0 and len(d) >= 34:
                    seen = True
                    bits = int.from_bytes(d[10:18], "big")
                    sr = (bits >> 44) & 0xFFFFF
                    ch = ((bits >> 41) & 0x7) + 1
                    bps = ((bits >> 36) & 0x1F) + 1
                    total = bits & ((1 << 36) - 1)
                    md5 = d[18:34].hex()
                if last:
                    break
            if not seen:
                return {"path": path, "err": "no STREAMINFO"}
            if not sr or not total:
                return {"path": path, "err": "STREAMINFO has no rate/length"}
            return {"path": path, "audio": os.path.getsize(path) - f.tell(),
                    "raw": total * ch * ((bps + 7) // 8), "sr": sr, "ch": ch,
                    "bps": bps, "dur": round(total / sr, 2), "id3": id3,
                    "zero_md5": md5 == "0" * 32}
    except Exception as exc:
        return {"path": path, "err": "%s: %s" % (type(exc).__name__, exc)}


def classify(r):
    if "err" in r:
        return "UNREADABLE", r["err"]
    if r["audio"] > r["raw"] * 1.02:
        return ("IMPOSSIBLE",
                "%.0fMB of audio declared as %dbit/%dkHz x%d (%.0fs = %.0fMB "
                "uncompressed)" % (r["audio"] / 1e6, r["bps"], r["sr"] // 1000,
                                   r["ch"], r["dur"], r["raw"] / 1e6))
    if r["audio"] < r["raw"] * 0.05:
        return ("SUSPICIOUSLY SMALL",
                "%.1fMB for %.0fs -- truncated?" % (r["audio"] / 1e6, r["dur"]))
    if r.get("id3"):
        return ("ID3-PREFIXED",
                "valid FLAC audio behind an ID3v2 block; players read it, "
                "strict parsers do not")
    if r.get("zero_md5") and r["bps"] >= 24:
        return ("NO PCM CHECKSUM",
                "%dbit/%dkHz with an all-zero STREAMINFO md5 -- not written "
                "by a standard encoder" % (r["bps"], r["sr"] // 1000))
    return None


def decode_check(paths, timeout=120):
    """ffmpeg each path to null. -nostdin and </dev/null are load-bearing."""
    errs = {}
    for p in paths:
        try:
            r = subprocess.run(
                ["ffmpeg", "-nostdin", "-v", "error", "-i", p, "-f", "null",
                 "-"], stdin=subprocess.DEVNULL, capture_output=True,
                text=True, timeout=timeout)
            msg = (r.stderr or "").strip().splitlines()
            if msg:
                errs[p] = msg[0][:160]
        except subprocess.TimeoutExpired:
            errs[p] = "decode exceeded %ds" % timeout
        except FileNotFoundError:
            print("ffmpeg not on PATH -- skipping --decode", file=sys.stderr)
            return errs
    return errs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--decode", action="store_true",
                    help="ffmpeg-verify everything the structural pass flags")
    ap.add_argument("--json", metavar="FILE", help="write findings as JSONL")
    ap.add_argument("--list-nochecksum", action="store_true")
    a = ap.parse_args()

    flacs = []
    for dirpath, _dirs, files in os.walk(a.root):
        for fn in files:
            if fn.lower().endswith(".flac"):
                flacs.append(os.path.join(dirpath, fn))
    flacs.sort()

    findings = []
    for p in flacs:
        v = classify(probe(p))
        if v:
            findings.append({"verdict": v[0], "detail": v[1], "path": p})

    if a.decode and findings:
        errs = decode_check([f["path"] for f in findings])
        for f in findings:
            if f["path"] in errs:
                f["detail"] += "; ffmpeg: " + errs[f["path"]]

    order = {"IMPOSSIBLE": 0, "UNREADABLE": 1, "SUSPICIOUSLY SMALL": 2,
             "ID3-PREFIXED": 3, "NO PCM CHECKSUM": 4}
    findings.sort(key=lambda f: (order.get(f["verdict"], 9), f["path"]))

    print("%d FLAC(s) checked, %d finding(s)" % (len(flacs), len(findings)))
    counts = Counter(f["verdict"] for f in findings)
    if counts:
        print("   " + ", ".join("%s x%d" % kv for kv in sorted(counts.items())))

    noisy = [f for f in findings if f["verdict"] == "NO PCM CHECKSUM"]
    if noisy and not a.list_nochecksum:
        by = Counter(os.path.dirname(f["path"]) for f in noisy)
        print("\n  NO PCM CHECKSUM: %d file(s) in %d folder(s) -- "
              "informational (--list-nochecksum to see them all)"
              % (len(noisy), len(by)))
        findings = [f for f in findings if f["verdict"] != "NO PCM CHECKSUM"]

    for f in findings[:80]:
        print("  [%s] %s" % (f["verdict"], f["path"]))
        print("      " + f["detail"])
    if len(findings) > 80:
        print("  ... and %d more" % (len(findings) - 80))

    if a.json:
        with open(a.json, "w", encoding="utf-8") as fh:
            for f in findings:
                fh.write(json.dumps(f) + "\n")
        print("\nwrote %d finding(s) to %s" % (len(findings), a.json))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
