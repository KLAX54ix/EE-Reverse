#!/usr/bin/env python3
"""Structural probe for EE .wsd / .WSTUDIO containers.

Reports the container header, per-block entropy to separate raw image payloads
from compressed/serialized regions, embedded raster/vector image signatures, and
deflate stream candidates.
"""
import sys
import zlib
import struct
import argparse
import math
from collections import Counter


MAGICS = [
    (b"\xff\xd8\xff", "JPEG"),
    (b"\x89PNG\r\n\x1a\n", "PNG"),
    (b"GIF87a", "GIF87a"),
    (b"GIF89a", "GIF89a"),
    (b"BM", "BMP"),
    (b"\x01\x00\x00\x00", "EMF-header?"),
    (b"\xd7\xcd\xc6\x9a", "WMF-placeable"),
    (b"PK\x03\x04", "ZIP-local"),
    (b"PK\x05\x06", "ZIP-EOCD"),
    (b"<!DOCTYPE", "HTML"),
    (b"<?xml", "XML"),
    (b"\xff\xfe", "UTF16LE-BOM"),
    (b"\x78\x9c", "zlib-default"),
    (b"\x78\x01", "zlib-fast"),
    (b"\x78\xda", "zlib-best"),
]


def entropy(buf):
    if not buf:
        return 0.0
    c = Counter(buf)
    n = len(buf)
    return -sum((v / n) * math.log2(v / n) for v in c.values())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--blocks", type=int, default=200)
    ap.add_argument("--min-image", type=int, default=64)
    a = ap.parse_args()

    data = open(a.file, "rb").read()
    print(f"file={a.file} size={len(data)} ({len(data)/1048576:.2f} MiB)")

    print(f"\n=== header (first 64 bytes) ===")
    for i in range(0, 64, 16):
        row = data[i:i + 16]
        print(f"{i:08X}  {' '.join(f'{b:02X}' for b in row):<47}  "
              f"{''.join(chr(b) if 32 <= b < 127 else '.' for b in row)}")

    # Magic tail after the ASCII container name
    print(f"\n=== container name field ===")
    z = data.find(b"\x00", 0)
    print(f"  leading NUL at {z}")
    name = data[z + 1:data.find(b"\x00", z + 1)] if z == 0 else b""
    print(f"  id = {name!r}")

    if a.blocks:
        print(f"\n=== entropy map ({a.blocks} blocks of "
              f"{len(data)//a.blocks} bytes) ===")
        blk = max(1, len(data) // a.blocks)
        for bi in range(a.blocks):
            chunk = data[bi * blk:(bi + 1) * blk]
            if not chunk:
                break
            e = entropy(chunk)
            bar = "#" * int(e * 4)
            flag = ""
            if e < 1.5:
                flag = "  <- very low (raw/uniform arrays)"
            elif e < 5.0:
                flag = "  <- low (structured/raw)"
            elif e > 7.9:
                flag = "  <- max (compressed/encrypted)"
            print(f"  blk{bi:04d} {bi*blk:#010x} H={e:5.3f} {bar}{flag}")

    print(f"\n=== embedded signatures ===")
    counts = Counter()
    for magic, label in MAGICS:
        start = 0
        hits = []
        while True:
            i = data.find(magic, start)
            if i < 0:
                break
            hits.append(i)
            start = i + 1
        counts[label] = len(hits)
        if hits and label in ("JPEG", "PNG", "GIF87a", "GIF89a", "BMP",
                              "ZIP-local", "EMF-header?", "WMF-placeable"):
            shown = ", ".join(f"{h:#x}" for h in hits[:12])
            more = f" ... (+{len(hits)-12})" if len(hits) > 12 else ""
            print(f"  {label:<14} {len(hits):6d}  {shown}{more}")
        elif hits:
            print(f"  {label:<14} {len(hits):6d}")
    print("  (counts include chance occurrences; treat as candidates)")

    print(f"\n=== deflate stream trials (find-based, first 24) ===")
    found = 0
    for marker in (b"\x78\x9c", b"\x78\x01", b"\x78\xda", b"\x78\x5e"):
        start = 0
        while found < 24:
            i = data.find(marker, start)
            if i < 0:
                break
            start = i + 1
            try:
                out = zlib.decompressobj().decompress(data[i:i + 1 << 22],
                                                      1 << 22)
            except Exception:
                continue
            if len(out) >= 256:
                head = out[:40]
                printable = sum(1 for b in head if 32 <= b < 127 or b in (9, 10, 13))
                print(f"  {i:#010x} {marker.hex()} -> {len(out)}+ bytes, "
                      f"printable={printable}/40 head={head!r}")
                found += 1
    if not found:
        print("  none inflated (payload may be a custom codec, not zlib)")


if __name__ == "__main__":
    main()
