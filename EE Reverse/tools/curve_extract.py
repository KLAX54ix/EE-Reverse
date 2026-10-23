"""Extract the traced curve of a function-graph panel as exact pixel coordinates.

Separates the curve from the straight axes by walking columns and rejecting
pixels that belong to a near-solid horizontal or vertical line, then reports the
curve skeleton and a least-squares fit against a quadratic through the origin.
"""
import sys

import numpy as np
from PIL import Image


def main():
    path = sys.argv[1]
    x0, x1, y0, y1 = (int(v) for v in sys.argv[2:6])
    ink = np.asarray(Image.open(path).convert("L")) < 128
    sub = ink[y0:y1 + 1, x0:x1 + 1].copy()
    h, w = sub.shape

    # --- locate axes: rows/cols whose ink coverage is nearly solid -------------
    row_frac = sub.sum(axis=1) / float(w)
    col_frac = sub.sum(axis=0) / float(h)
    ax_row = int(np.argmax(row_frac))          # x axis
    ax_col = int(np.argmax(col_frac))          # y axis
    print("x-axis row=%d (%.2f solid)   y-axis col=%d (%.2f solid)" %
          (y0 + ax_row, row_frac[ax_row], x0 + ax_col, col_frac[ax_col]))

    # --- remove the axes (and their arrowheads) from the mask -----------------
    clean = sub.copy()
    clean[max(0, ax_row - 3):ax_row + 4, :] = False
    clean[:, max(0, ax_col - 3):ax_col + 4] = False

    # --- curve skeleton -------------------------------------------------------
    pts = []
    for c in range(w):
        rows = np.where(clean[:, c])[0]
        if len(rows) == 0:
            continue
        # the curve is thin; take the run whose centre is most "curve-like"
        pts.append((c, int(rows.min()), int(rows.max()), len(rows)))
    # The printed label N(a,b,...) sits above the curve -- drop column clusters
    # that are vertically thick or that jump far above the smooth trend.
    print("\n-- raw skeleton (global coords) --")
    print("  x    ytop  ybot   n")
    for c, rt, rb, n in pts:
        print("%5d %5d %5d %4d" % (x0 + c, y0 + rt, y0 + rb, n))

    # --- fit y = A*x*(2h - x) style quadratic through the origin -------------
    # Use only columns clearly to the right of the y axis and below the label.
    sel = [(c, rt) for c, rt, rb, n in pts if (x0 + c) > x0 + ax_col + 4 and n <= 6]
    if len(sel) >= 8:
        X = np.array([c for c, _ in sel], dtype=float)
        Y = np.array([r for _, r in sel], dtype=float)
        # quadratic through (0,0):  y = p*x + q*x^2   (x measured from origin col)
        xo = X - ax_col
        A = np.vstack([xo, xo ** 2]).T
        coef, *_ = np.linalg.lstsq(A, Y, rcond=None)
        print("\nquadratic fit through origin: y = %.6f*x + %.6f*x^2  (x in px from col %d)"
              % (coef[0], coef[1], x0 + ax_col))
        xv = -coef[0] / (2 * coef[1]) if coef[1] != 0 else float('nan')
        print("vertex x = %.2f px from y-axis  (global col %.1f), y = %.2f"
              % (xv, x0 + ax_col + xv, coef[0] * xv + coef[1] * xv * xv))
        # residuals
        pred = A @ coef
        print("residual rms = %.2f px, max = %.2f px" %
              (float(np.sqrt(((pred - Y) ** 2).mean())), float(np.abs(pred - Y).max())))


if __name__ == "__main__":
    main()
