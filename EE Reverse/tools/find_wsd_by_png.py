"""Find which .wsd file on disk contains a PNG image at a given file offset.

The paper's images are carved by signature, so a known (offset, size, dims) triple
from an earlier extraction is a fingerprint for the source file.
"""
import os
import struct
import sys


def png_info(path):
    """Yield (offset, width, height, byte_len) for every PNG signature in path."""
    data = open(path, "rb").read()
    sig = b"\x89PNG\r\n\x1a\n"
    out = []
    start = 0
    while True:
        i = data.find(sig, start)
        if i < 0:
            break
        w = h = None
        if data[i + 12:i + 16] == b"IHDR":
            w, h = struct.unpack(">II", data[i + 16:i + 24])
        end = data.find(b"IEND", i)
        out.append((i, w, h, (end + 8 - i) if end > 0 else None))
        start = i + 8
    return out, len(data)


def main():
    want_off = int(sys.argv[1], 0)
    want_len = int(sys.argv[2])
    roots = sys.argv[3:]
    targets = []
    for r in roots:
        if os.path.isfile(r):
            targets.append(r)
            continue
        for dirpath, _dirs, files in os.walk(r):
            if "ghidra_12" in dirpath:
                continue
            for f in files:
                if f.lower().endswith(".wsd"):
                    targets.append(os.path.join(dirpath, f))
    print("scanning %d .wsd files" % len(targets))
    for t in targets:
        try:
            infos, size = png_info(t)
        except Exception as e:
            print("  ERR %s: %s" % (t, e))
            continue
        hits = [x for x in infos if x[0] == want_off]
        exact = [x for x in hits if x[3] == want_len]
        flag = "MATCH" if exact else ("offset-only" if hits else "")
        if hits or size > 1_000_000:
            print("%-9s %-70s file=%d pngs=%d %s" % (
                flag, os.path.basename(t), size, len(infos),
                ("off=0x%X len=%s dims=%sx%s" % (hits[0][0], hits[0][3], hits[0][1], hits[0][2])) if hits else ""))


if __name__ == "__main__":
    main()
