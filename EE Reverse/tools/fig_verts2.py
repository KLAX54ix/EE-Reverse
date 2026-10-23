"""Refine the Hough peak lines of a clean textbook figure with total least
squares, then report the vertices as intersections (sub-pixel).

usage: fig_verts2.py <png> <theta1,rho1> <theta2,rho2> ... [--tol 6]
Each theta is in degrees, rho in pixels, using rho = x*cos(t) + y*sin(t).
Prints every line's refined (theta, rho) and every pairwise intersection that
lies inside the ink bounding box.
"""
import sys
import math
import numpy as np
from PIL import Image


def refine(pts, theta_deg, rho, tol):
    t = math.radians(theta_deg)
    nx, ny = math.cos(t), math.sin(t)
    d = pts[:, 0] * nx + pts[:, 1] * ny - rho
    sel = pts[np.abs(d) <= tol]
    if len(sel) < 20:
        return None, 0
    c = sel.mean(axis=0)
    u, s, vt = np.linalg.svd(sel - c, full_matrices=False)
    dirv = vt[0]
    n = np.array([-dirv[1], dirv[0]])
    # keep the normal pointing the same way as the initial one
    if n[0] * nx + n[1] * ny < 0:
        n = -n
    rho2 = float(n @ c)
    return (float(math.degrees(math.atan2(n[1], n[0]))), rho2), len(sel)


def inter(l1, l2):
    t1, r1 = l1
    t2, r2 = l2
    a1, b1 = math.cos(math.radians(t1)), math.sin(math.radians(t1))
    a2, b2 = math.cos(math.radians(t2)), math.sin(math.radians(t2))
    det = a1 * b2 - a2 * b1
    if abs(det) < 1e-9:
        return None
    x = (r1 * b2 - r2 * b1) / det
    y = (a1 * r2 - a2 * r1) / det
    return (round(x, 1), round(y, 1))


def main():
    path = sys.argv[1]
    tol = 6.0
    args = []
    i = 2
    while i < len(sys.argv):
        if sys.argv[i] == '--tol':
            tol = float(sys.argv[i + 1]); i += 2; continue
        args.append(sys.argv[i]); i += 1
    a = np.array(Image.open(path).convert('L'))
    ys, xs = np.nonzero(a < 128)
    pts = np.stack([xs, ys], axis=1).astype(np.float64)
    print("image %s  ink px %d  bbox x[%d..%d] y[%d..%d]"
          % (path, len(pts), xs.min(), xs.max(), ys.min(), ys.max()))
    lines = []
    for spec in args:
        t, r = spec.split(',')
        ref, n = refine(pts, float(t), float(r), tol)
        if ref is None:
            print("  line %-14s -> too few px" % spec)
            continue
        print("  line %-14s -> theta=%7.2f rho=%8.2f  (%d px)" % (spec, ref[0], ref[1], n))
        lines.append((spec, ref))
    print("intersections (in-bbox only):")
    for i in range(len(lines)):
        for j in range(i + 1, len(lines)):
            p = inter(lines[i][1], lines[j][1])
            if p is None:
                continue
            if not (xs.min() - 12 <= p[0] <= xs.max() + 12 and
                    ys.min() - 12 <= p[1] <= ys.max() + 12):
                continue
            print("  %-10s x %-10s = (%6.1f, %6.1f)"
                  % (lines[i][0], lines[j][0], p[0], p[1]))


main()
