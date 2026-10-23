"""List the unique image blobs the live process holds for ONE paper.

Fingerprint = byte length.  A blob counts as belonging to the paper when its
length matches an entry of that paper's carve index; duplicates are collapsed so
the document-order figure list stays readable.
"""
import hashlib
import io
import os
import re
import sys

from PIL import Image


def load_index(idx_path):
    """Parse '<name>  offset=0x...  bytes=N  WxH' lines -> {bytes: (name, w, h)}."""
    out = {}
    for line in open(idx_path, encoding="utf-8", errors="replace"):
        m = re.match(r"(\S+\.png)\s+offset=(\S+)\s+bytes=\s*(\d+)\s+(\d+)x(\d+)", line.strip())
        if not m:
            continue
        out[int(m.group(3))] = (m.group(1), int(m.group(4)), int(m.group(5)))
    return out


def main():
    carve_dir = sys.argv[1]
    idx = load_index(sys.argv[2])
    print("index entries: %d" % len(idx))
    seen = {}
    rows = []
    for f in sorted(os.listdir(carve_dir)):
        p = os.path.join(carve_dir, f)
        if not os.path.isfile(p) or not f.lower().endswith(".png"):
            continue
        b = open(p, "rb").read()
        d = hashlib.sha256(b).hexdigest()
        if d in seen:
            continue
        seen[d] = 1
        if len(b) not in idx:
            continue
        name, w, h = idx[len(b)]
        rows.append((name, f, w, h, len(b)))
    rows.sort(key=lambda r: r[0])
    print("%-12s %-46s %6s %6s %9s" % ("figure", "carved file", "w", "h", "bytes"))
    for name, f, w, h, n in rows:
        print("%-12s %-46s %6d %6d %9d" % (name, f, w, h, n))
    print("total matched figures: %d" % len(rows))


if __name__ == "__main__":
    main()
