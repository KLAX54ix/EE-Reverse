"""Least-squares fit the traced curve of fig24's right panel to a parabola,
using ONLY clearly-curve pixels (excluding axes and the N(a,b,..) label), then
report the fit quality and the implied vertex.
"""
import numpy as np
from PIL import Image

PATH = r"D:\EE Reverse\captures\beilun-figs\fig24.png"
X0, X1, Y0, Y1 = 560, 760, 0, 258       # region containing the curve, above the x axis
AX_ROW, AX_COL = 260, 570               # x-axis row, y-axis col (global)


def main():
    ink = np.asarray(Image.open(PATH).convert("L")) < 128
    pts = []
    for c in range(X0, X1 + 1):
        rows = np.where(ink[Y0:Y1 + 1, c])[0] + Y0
        if len(rows) == 0:
            continue
        # split into runs
        runs, start, prev = [], rows[0], rows[0]
        for r in rows[1:]:
            if r != prev + 1:
                runs.append((start, prev))
                start = r
            prev = r
        runs.append((start, prev))
        # The curve is the run closest to the previous column's curve row
        # (continuity tracking); start from the origin side.
        pts.append((c, [(a + b) / 2.0 for a, b in runs], runs))

    # seed: first column right of the y axis whose only run is below row 255
    cur = None
    traced = []
    for c, centres, runs in pts:
        if cur is None:
            near = [m for m in centres if m > 200]
            if not near:
                continue
            cur = max(near)
            traced.append((c, cur))
            continue
        cand = sorted(centres, key=lambda m: abs(m - cur))
        best = cand[0]
        if abs(best - cur) > 22:      # jump -> label or axis, skip
            continue
        cur = best
        traced.append((c, cur))

    X = np.array([c for c, _ in traced], float)
    Y = np.array([r for _, r in traced], float)
    print("traced %d columns, x %d..%d" % (len(X), X.min(), X.max()))

    # Fit two models and compare.
    models = {}
    coef_o = np.polyfit(X, Y, 2)
    models["plain quadratic"] = (coef_o, np.polyval(coef_o, X))
    Z = (X - AX_COL)
    A = np.vstack([Z, Z ** 2]).T
    coef_o2, *_ = np.linalg.lstsq(A, Y, rcond=None)
    models["through origin"] = (coef_o2, A @ coef_o2)

    for name, (coef, pred) in models.items():
        res = pred - Y
        print("\n%-18s rms=%.2f px  max=%.2f px" %
              (name, float(np.sqrt((res ** 2).mean())), float(np.abs(res).max())))
        if name == "plain quadratic":
            a, b, c = coef
            print("   y = %.6f x^2 + %.6f x + %.6f   vertex x=%.2f y=%.2f"
                  % (a, b, c, -b / (2 * a), np.polyval(coef, -b / (2 * a))))
            print("   vertex column = %.2f  (row %.2f)" % (-b / (2 * a), np.polyval(coef, -b / (2 * a))))

    print("\nresiduals of the plain quadratic (col, traced, model, delta):")
    coef = models["plain quadratic"][0]
    for (c, r), m in zip(traced, np.polyval(coef, X)):
        if c % 8 == 0:
            print("%5d %7.1f %8.1f %7.1f" % (c, r, m, m - r))


if __name__ == "__main__":
    main()
