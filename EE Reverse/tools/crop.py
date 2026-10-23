#!/usr/bin/env python3
"""Crop and upscale a screenshot region for visual inspection.

Usage: python crop.py <in.png> <out.png> <x0> <y0> <x1> <y1> [scale]
"""
import sys

from PIL import Image


def main():
    if len(sys.argv) < 7:
        print(__doc__)
        return 1
    src, dst = sys.argv[1], sys.argv[2]
    x0, y0, x1, y1 = (int(v) for v in sys.argv[3:7])
    scale = int(sys.argv[7]) if len(sys.argv) > 7 else 4
    im = Image.open(src)
    x0 = max(0, min(x0, im.width))
    x1 = max(x0 + 1, min(x1, im.width))
    y0 = max(0, min(y0, im.height))
    y1 = max(y0 + 1, min(y1, im.height))
    c = im.crop((x0, y0, x1, y1))
    c = c.resize((c.width * scale, c.height * scale), Image.LANCZOS)
    c.save(dst)
    print(f"{dst} {c.size} from {src} box=({x0},{y0},{x1},{y1})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
