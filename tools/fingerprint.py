#!/usr/bin/env python3
"""Acoustic fingerprinting — decide "is this the same recording?" by how a
track SOUNDS, not by what its filename says.

Every hard call in the 2026-07-23 staging reconciliation came down to this
question, and filename matching kept getting it wrong:
  - Persuader reported "9 new tracks" on a +1 album because the two copies
    spell their track titles differently.
  - LĪVE's "White, Discussion" was nearly added as a duplicate because the
    two masters differ by 5 seconds.
  - Tarot's studio "Back in the Fire" matched the LIVE take because both
    normalise to the same title string.
Content hashing does not help either: the library's copies carry embedded art,
so byte-identical never happens even for the same audio.

No new dependency: ffmpeg already ships the Chromaprint muxer (verified on this
box). Fingerprints are compared over a sliding offset, because the same track
mastered twice rarely starts at the same sample.

Measured on a known pair (MJ "Bad", library FLAC vs the quarantined MP3):
    same recording, MP3 vs FLAC   0.933
    same song, different mix      0.683
    different song entirely       0.541
So SAME_RECORDING = 0.85 separates cleanly, and a "different mix" is correctly
NOT treated as the same recording.

CLI:
    python fingerprint.py compare A.flac B.mp3
    python fingerprint.py match <staged_dir> <library_dir>
"""
from __future__ import annotations

import argparse
import json
import os
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SAME_RECORDING = 0.85     # >= this means the same performance
LIKELY_RELATED = 0.65     # alt mix / edit of the same song
SAMPLE_SECONDS = 120      # first N seconds is plenty to identify a track
MAX_OFFSET = 90           # alignment search, in fingerprint frames
CACHE = Path(__file__).with_name("fingerprint_cache.json")
AUD = (".flac", ".mp3", ".m4a", ".ogg", ".wma", ".wav", ".aac", ".alac")
_POP = bytes(bin(i).count("1") for i in range(256))


def _load_cache() -> dict:
    try:
        return json.loads(CACHE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _key(p: Path) -> str:
    try:
        st = p.stat()
        return f"{p}|{st.st_size}|{int(st.st_mtime)}"
    except OSError:
        return str(p)


def fingerprint(path, seconds: int = SAMPLE_SECONDS, cache: dict | None = None):
    """Chromaprint fingerprint as a list of uint32, or None if unreadable.

    Fingerprinting is CPU-heavy, so results are cached on (path, size, mtime).
    """
    p = Path(path)
    k = _key(p)
    if cache is not None and k in cache:
        return cache[k]
    tmp = Path(tempfile.gettempdir()) / f"fp_{abs(hash(k))}.bin"
    try:
        subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
             "-t", str(seconds), "-i", str(p),
             "-ac", "1", "-ar", "11025",              # mono/11k: what chromaprint wants
             "-f", "chromaprint", "-fp_format", "raw", str(tmp)],
            capture_output=True, timeout=180)
        if not tmp.exists() or tmp.stat().st_size == 0:
            return None
        raw = tmp.read_bytes()
        n = len(raw) // 4
        fp = list(struct.unpack(">%dI" % n, raw[:n * 4]))
    except (OSError, subprocess.SubprocessError, struct.error):
        return None
    finally:
        try:
            tmp.unlink()
        except OSError:
            pass
    if cache is not None:
        cache[k] = fp
    return fp


def _score(a, b, off: int) -> float:
    if off >= 0:
        a2, b2 = a[off:], b
    else:
        a2, b2 = a, b[-off:]
    n = min(len(a2), len(b2))
    if n < 80:                      # too little overlap to trust
        return 0.0
    bits = 0
    for i in range(n):
        x = a2[i] ^ b2[i]
        bits += _POP[x & 255] + _POP[(x >> 8) & 255] + _POP[(x >> 16) & 255] + _POP[(x >> 24) & 255]
    return 1 - bits / (n * 32)


def similarity(a, b, max_offset: int = MAX_OFFSET):
    """Best similarity over an alignment search, 0..1. None if either is bad.

    The alignment matters: index-aligned, a genuine same-recording pair scored
    0.75; searching offsets took it to 0.93.
    """
    if not a or not b:
        return None
    return max(_score(a, b, o) for o in range(-max_offset, max_offset + 1))


def same_recording(a, b) -> bool:
    s = similarity(a, b)
    return s is not None and s >= SAME_RECORDING


def _audio(d: Path):
    return sorted(f for f in d.rglob("*") if f.is_file() and f.suffix.lower() in AUD)


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("compare"); c.add_argument("a"); c.add_argument("b")
    m = sub.add_parser("match"); m.add_argument("staged"); m.add_argument("library")
    args = ap.parse_args()
    cache = _load_cache()

    try:
        if args.cmd == "compare":
            s = similarity(fingerprint(args.a, cache=cache), fingerprint(args.b, cache=cache))
            if s is None:
                print("could not fingerprint one of the inputs")
                return 1
            verdict = ("SAME RECORDING" if s >= SAME_RECORDING else
                       "related (alt mix/edit)" if s >= LIKELY_RELATED else "different")
            print(f"similarity {s:.4f} -> {verdict}")
            return 0

        staged, lib = Path(args.staged), Path(args.library)
        lib_fps = [(f, fingerprint(f, cache=cache)) for f in _audio(lib)]
        print(f"library: {len(lib_fps)} tracks fingerprinted\n")
        for sf in _audio(staged):
            sfp = fingerprint(sf, cache=cache)
            best, score = None, 0.0
            for lf, lfp in lib_fps:
                s = similarity(sfp, lfp) or 0.0
                if s > score:
                    best, score = lf, s
            tag = ("SAME" if score >= SAME_RECORDING else
                   "related" if score >= LIKELY_RELATED else "NO MATCH")
            print(f"  {sf.name[:44]:<44} {tag:<9} {score:.3f}"
                  + (f"  <- {best.name[:40]}" if best and score >= LIKELY_RELATED else ""))
        return 0
    finally:
        try:
            CACHE.write_text(json.dumps(cache), encoding="utf-8")
        except OSError:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
