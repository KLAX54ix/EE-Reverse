#!/usr/bin/env python3
"""Byte-level reconnaissance helper for the EE (.wsd) investigation.

Subcommands:
  strings <file> [--min N] [--filter a,b,c] [--utf16]
  hexdump <file> <offset> <length>
  zlibscan <file> [--limit N]
  hist <file>
"""
import sys
import re
import zlib
import struct
import argparse
from collections import Counter

ASCII_RE = re.compile(rb"[\x20-\x7e]{4,}")
UTF16_RE = re.compile(rb"(?:[\x20-\x7e]\x00){4,}")


def cmd_strings(args):
    data = open(args.file, "rb").read()
    filters = [f.lower() for f in args.filter.split(",")] if args.filter else None
    out = []
    for m in ASCII_RE.finditer(data):
        s = m.group().decode("ascii", "replace")
        if len(s) >= args.min:
            out.append((m.start(), "ascii", s))
    for m in UTF16_RE.finditer(data):
        s = m.group().decode("utf-16-le", "replace")
        if len(s) >= args.min:
            out.append((m.start(), "utf16", s))
    out.sort()
    shown = 0
    for off, enc, s in out:
        if filters and not any(f in s.lower() for f in filters):
            continue
        print(f"{off:#010x} [{enc}] {s}")
        shown += 1
        if args.limit and shown >= args.limit:
            print(f"... (limit {args.limit} reached)")
            break
    print(f"# total strings={len(out)} shown={shown}", file=sys.stderr)


def cmd_hexdump(args):
    data = open(args.file, "rb").read()
    start, length = args.offset, args.length
    chunk = data[start:start + length]
    for i in range(0, len(chunk), 16):
        row = chunk[i:i + 16]
        hexs = " ".join(f"{b:02X}" for b in row)
        asc = "".join(chr(b) if 32 <= b < 127 else "." for b in row)
        print(f"{start + i:08X}  {hexs:<47}  {asc}")


def cmd_zlibscan(args):
    data = open(args.file, "rb").read()
    found = 0
    for i in range(len(data) - 2):
        if data[i] == 0x78 and data[i + 1] in (0x01, 0x5E, 0x9C, 0xDA):
            try:
                d = zlib.decompressobj()
                out = d.decompress(data[i:], 1 << 20)
                if len(out) > 64:
                    print(f"{i:#010x} zlib ok: inflated>={len(out)}B "
                          f"head={out[:48]!r}")
                    found += 1
                    if args.limit and found >= args.limit:
                        break
            except Exception:
                continue
    print(f"# zlib candidates accepted={found}", file=sys.stderr)


def cmd_hist(args):
    data = open(args.file, "rb").read()
    c = Counter(data)
    print(f"size={len(data)} distinct={len(c)}")
    for b, n in c.most_common(24):
        print(f"  {b:02X} {b:3d}  {n:10d}  {n / len(data) * 100:6.2f}%")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("strings")
    p.add_argument("file")
    p.add_argument("--min", type=int, default=6)
    p.add_argument("--filter", default=None)
    p.add_argument("--limit", type=int, default=400)
    p.set_defaults(func=cmd_strings)

    p = sub.add_parser("hexdump")
    p.add_argument("file")
    p.add_argument("offset", type=lambda s: int(s, 0))
    p.add_argument("length", type=lambda s: int(s, 0), default=256, nargs="?")
    p.set_defaults(func=cmd_hexdump)

    p = sub.add_parser("zlibscan")
    p.add_argument("file")
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(func=cmd_zlibscan)

    p = sub.add_parser("hist")
    p.add_argument("file")
    p.set_defaults(func=cmd_hist)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
