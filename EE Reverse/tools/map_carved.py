"""Carved PNGs can be located inside the composite .wsd (which concatenates every
embedded image in document order), giving each 北仑 image its correct figNN name.

p_blcheck_<fileoffset>_<size>.png files are carved straight out of that file, so
their names already carry (fileoffset, size).  For each other carved blob we find
those bytes inside the .wsd and reuse the offset -> figNN mapping.
"""
import hashlib
import os
import sys

WSD = r"D:\EE Reverse\宁波2024-2025中考模拟卷选择压轴题.wsd"
CARVE = r"D:\EE Reverse\captures\bl-live"


def main():
    data = open(WSD, "rb").read()
    # offset -> name, from the carved straight-from-file blobs
    off2name = {}
    for f in os.listdir(CARVE):
        if not f.startswith("p_blcheck_"):
            continue
        parts = f.split("_")
        off = int(parts[2], 16)
        off2name[off] = f

    rows = []
    for f in sorted(os.listdir(CARVE)):
        p = os.path.join(CARVE, f)
        if not os.path.isfile(p) or not f.lower().endswith(".png"):
            continue
        b = open(p, "rb").read()
        i = data.find(b)
        kind = "unique" if i >= 0 else "?"
        rows.append((f, len(b), i, off2name.get(i, "")))

    for f, n, i, origin in sorted(rows, key=lambda r: (r[2] < 0, r[2])):
        print("%-50s %8d  off=%s  origin=%s" % (f, n, hex(i) if i >= 0 else "-", origin))


if __name__ == "__main__":
    main()
