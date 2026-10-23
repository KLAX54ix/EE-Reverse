"""Validate carved PNGs, index them by real dimensions, and match against a
reference set (e.g. captures/beilun-figs) by exact byte digest.

Carved files may have bogus dimensions in their names (the bridge read the IHDR
fields big-endian), so every real property is re-read here with Pillow.
"""
import hashlib
import os
import sys


def digest_set(d):
    out = {}
    if not os.path.isdir(d):
        return out
    for f in sorted(os.listdir(d)):
        p = os.path.join(d, f)
        if not os.path.isfile(p) or not f.lower().endswith(".png"):
            continue
        b = open(p, "rb").read()
        out.setdefault(hashlib.sha256(b).hexdigest(), []).append(f)
    return out


def main():
    carve_dir = sys.argv[1]
    ref_dirs = sys.argv[2:]
    refs = {}
    for r in ref_dirs:
        for k, v in digest_set(r).items():
            refs.setdefault(k, []).extend([os.path.basename(r) + "/" + x for x in v])
    print("reference unique digests: %d" % len(refs))

    rows = []
    for f in sorted(os.listdir(carve_dir)):
        p = os.path.join(carve_dir, f)
        if not os.path.isfile(p) or not f.lower().endswith(".png"):
            continue
        b = open(p, "rb").read()
        d = hashlib.sha256(b).hexdigest()
        try:
            from PIL import Image
            import io
            im = Image.open(io.BytesIO(b))
            w, h = im.size
            mode = im.mode
        except Exception as e:
            rows.append((f, None, None, len(b), d, "BAD:" + str(e)[:40]))
            continue
        rows.append((f, w, h, len(b), d, ",".join(refs.get(d, []))))

    rows.sort(key=lambda r: (r[1] is None, -(r[1] or 0) * (r[2] or 0)))
    print("%-46s %6s %6s %9s  %s" % ("file", "w", "h", "bytes", "matches"))
    for f, w, h, n, d, m in rows:
        print("%-46s %6s %6s %9d  %s" % (f, w, h, n, m))


if __name__ == "__main__":
    main()
