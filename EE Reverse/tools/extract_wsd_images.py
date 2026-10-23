"""Carve every embedded PNG out of an EE .wsd document, in file order.

The document stores each pasted picture as a plain PNG stream, so the byte
order here matches the order the pictures appear in the paper.
"""
import re
import os
import sys

PATH = sys.argv[1] if len(sys.argv) > 1 else \
    r"D:\EE Reverse\2025-2026学年浙江省宁波市镇海区九年级（上）期末数学试卷.wsd"
OUTDIR = sys.argv[2] if len(sys.argv) > 2 else r"D:\EE Reverse\captures\paper-figs"

SIG = b"\x89PNG\r\n\x1a\n"
END = b"IEND\xaeB`\x82"


def main():
    b = open(PATH, "rb").read()
    os.makedirs(OUTDIR, exist_ok=True)
    n = 0
    i = 0
    rows = []
    while True:
        s = b.find(SIG, i)
        if s < 0:
            break
        e = b.find(END, s)
        if e < 0:
            break
        e += len(END)
        blob = b[s:e]
        n += 1
        p = os.path.join(OUTDIR, "fig%02d.png" % n)
        with open(p, "wb") as f:
            f.write(blob)
        # read the PNG header for the size
        w = int.from_bytes(blob[16:20], "big")
        h = int.from_bytes(blob[20:24], "big")
        rows.append((n, s, len(blob), w, h))
        i = e
    with open(os.path.join(OUTDIR, "index.txt"), "w", encoding="utf-8") as f:
        for n, s, ln, w, h in rows:
            f.write("fig%02d.png  offset=0x%07X  bytes=%7d  %dx%d\n" % (n, s, ln, w, h))
    print("extracted", n, "images ->", OUTDIR)
    for n, s, ln, w, h in rows[:40]:
        print("  fig%02d  @0x%07X  %7d bytes  %dx%d" % (n, s, ln, w, h))


main()
