"""Recover the axis + curve geometry of a function-graph panel in real units.

Prints, for one panel of a composite figure:
  * the axis row (x axis) and axis column (y axis), found as the longest
    near-solid ink lines;
  * the curve skeleton (for each column, the ink extreme away from the axes);
  * the vertex, and the x-intercepts.
Everything is reported in pixels first, then as a fraction of the panel box so
the numbers can be lifted onto a canvas of any size.
"""
import sys

import numpy as np
from PIL import Image


def load(path):
    im = Image.open(path).convert("L")
    return np.asarray(im) < 128, im.width, im.height


def longest_run(mask_1d):
    """Longest consecutive True run -> (start, end, length)."""
    best = (0, -1, 0)
    start = None
    for i, v in enumerate(mask_1d):
        if v and start is None:
            start = i
        elif not v and start is not None:
            if i - start > best[2]:
                best = (start, i - 1, i - start)
            start = None
    if start is not None and len(mask_1d) - start > best[2]:
        best = (start, len(mask_1d) - 1, len(mask_1d) - start)
    return best


def main():
    path = sys.argv[1]
    x0, x1, y0, y1 = (int(v) for v in sys.argv[2:6])
    ink, W, H = load(path)
    sub = ink[y0:y1 + 1, x0:x1 + 1]
    h, w = sub.shape
    print("panel %dx%d at (%d,%d)" % (w, h, x0, y0))

    # x axis candidate: the row with the longest horizontal run
    best_row, best = None, 0
    for r in range(h):
        s, e, n = longest_run(sub[r])
        if n > best:
            best, best_row, best_seg = n, r, (s, e)
    print("x-axis row=%d (global %d) run=%d cols %s" %
          (best_row, y0 + best_row, best, (x0 + best_seg[0], x0 + best_seg[1])))

    # y axis candidate: the column with the longest vertical run
    best_col, best = None, 0
    for c in range(w):
        s, e, n = longest_run(sub[:, c])
        if n > best:
            best, best_col, best_seg = n, c, (s, e)
    print("y-axis col=%d (global %d) run=%d rows %s" %
          (best_col, x0 + best_col, best, (y0 + best_seg[0], y0 + best_seg[1])))

    print("\n-- curve skeleton: per column, ink rows away from the axes --")
    pts = []
    for c in range(w):
        col = np.where(sub[:, c])[0]
        if len(col) == 0:
            continue
        # ignore the axis row (within 2 px) and the axis column
        f = [int(y) for y in col if abs(int(y) - best_row) > 2]
        if not f:
            continue
        pts.append((c, min(f)))
    if pts:
        # vertex = lowest row value (highest on screen)
        vx, vy = min(pts, key=lambda p: p[1])
        print("vertex at local (%d,%d) global (%d,%d)" % (vx, vy, x0 + vx, y0 + vy))
        # x intercepts = curve points nearest the axis row
        near = sorted(pts, key=lambda p: abs(p[1] - best_row))[:6]
        print("curve points nearest x-axis: %s" % ([(x0 + a, y0 + b) for a, b in near],))
        print("\ncol_global row_global")
        for c, r in pts:
            print("%6d %6d" % (x0 + c, y0 + r))


if __name__ == "__main__":
    main()
