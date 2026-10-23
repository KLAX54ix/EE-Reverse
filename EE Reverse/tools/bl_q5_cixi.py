#!/usr/bin/env python3
"""Q5 (Cixi paper) figure: recover the geometry of fig05.png.

The problem says: coordinate axes, O at the origin; triangle ABC and triangle
A1B1C1 are homothetic with centre O; B(-3,-2) -> B1(6,4); A(-2,1) -> A1(?).
So the scale factor is -2 (B1 = -2*B).  The 4 known vertices are therefore
exact constraints; the only unconstrained vertex is C (its image C1 = -2*C).

This script:
  1. finds the two axes (longest ink row / column) -> origin in pixels
  2. finds the SOLID edges of the two triangles (continuous ink lines, unlike
     the dashed homothety lines)
  3. labels each triangle's 3 corners (topmost = A / bottom = A1 ...)
  4. least-squares fits  x_px = s*x + tx,  y_px = -s*y + ty  on the 4 known
     vertices, reports the residual, then emits C and C1 in data coordinates
  5. verifies the homothety (C1 == -2*C, collinearity with O)

Run: python tools/bl_q5_cixi.py captures/cixi-figs/fig05.png
"""
import sys
import math
import numpy as np
from PIL import Image


def load_ink(path):
    a = np.array(Image.open(path).convert('L'), dtype=np.uint8)
    return (a < 128)


def find_axes(ink):
    """Longest horizontal ink run row / longest vertical run column."""
    h, w = ink.shape
    rows = ink.sum(axis=1)
    cols = ink.sum(axis=0)
    y0 = int(np.argmax(rows))
    x0 = int(np.argmax(cols))
    return x0, y0


def hough(ink, theta_step=0.5, rho_step=2, min_votes=80):
    ys, xs = np.nonzero(ink)
    diag = int(math.hypot(*ink.shape))
    thetas = np.arange(0.0, 180.0, theta_step)
    tr = np.deg2rad(thetas)
    cos, sin = np.cos(tr), np.sin(tr)
    nrho = (2 * diag) // rho_step + 1
    center = diag // rho_step
    acc = np.zeros((nrho, len(thetas)), dtype=np.int32)
    rhos = np.outer(xs, cos) + np.outer(ys, sin)
    idx = (rhos / rho_step).astype(np.int32) + center
    good = (idx >= 0) & (idx < nrho)
    for t in range(len(thetas)):
        g = good[:, t]
        np.add.at(acc[:, t], idx[g, t], 1)
    peaks = []
    for t in range(len(thetas)):
        col = acc[:, t]
        for r in range(1, nrho - 1):
            v = col[r]
            if v >= min_votes and v >= col[r - 1] and v >= col[r + 1]:
                rho = (r - center) * rho_step
                peaks.append((v, thetas[t], rho))
    peaks.sort(reverse=True)
    # dedupe
    kept = []
    for v, th, rho in peaks:
        if any(abs(th - k[1]) < 1.5 and abs(rho - k[2]) < 8 for k in kept):
            continue
        kept.append((v, th, rho))
    return kept


def refine(pts, theta_deg, rho, tol=4.0):
    t = math.radians(theta_deg)
    nx, ny = math.cos(t), math.sin(t)
    d = pts[:, 0] * nx + pts[:, 1] * ny - rho
    sel = pts[np.abs(d) <= tol]
    if len(sel) < 30:
        return None
    c = sel.mean(axis=0)
    _, _, vt = np.linalg.svd(sel - c, full_matrices=False)
    dirv = vt[0]
    n = np.array([-dirv[1], dirv[0]])
    if n[0] * nx + n[1] * ny < 0:
        n = -n
    rho2 = float(n @ c)
    return {'theta': math.degrees(math.atan2(n[1], n[0])) % 180.0,
            'rho': rho2, 'c': c, 'dir': dirv / np.linalg.norm(dirv),
            'n': n, 'npx': len(sel)}


def coverage(ink, line):
    """Ink runs along the line.

    Returns (extent, longest_run, ratio).  A SOLID edge is one contiguous ink
    run, so longest_run/extent ~ 1.  A DASHED line has many short runs, so the
    ratio is small even though it has plenty of ink.
    """
    h, w = ink.shape
    c = line['c']; d = line['dir']
    half = int(max(h, w))
    ts = np.arange(-half, half + 1, 1.0)
    pts = c[None, :] + ts[:, None] * d[None, :]
    xs = np.round(pts[:, 0]).astype(int)
    ys = np.round(pts[:, 1]).astype(int)
    inside = (xs >= 1) & (xs < w - 1) & (ys >= 1) & (ys < h - 1)
    hit = np.zeros(len(ts), dtype=bool)
    for oy in (-1, 0, 1):
        for ox in (-1, 0, 1):
            yy = np.clip(ys + oy, 0, h - 1); xx = np.clip(xs + ox, 0, w - 1)
            hit |= ink[yy, xx]
    hit &= inside
    if not hit.any():
        return 0, 0, 0.0
    idx = np.nonzero(hit)[0]
    extent = int(idx[-1] - idx[0] + 1)
    best = cur = 0
    for v in hit[idx[0]:idx[-1] + 1]:
        cur = cur + 1 if v else 0
        best = max(best, cur)
    return extent, best, best / max(extent, 1)


def inter(l1, l2):
    n1, r1 = l1['n'], l1['rho']
    n2, r2 = l2['n'], l2['rho']
    A = np.array([n1, n2]); b = np.array([r1, r2])
    det = np.linalg.det(A)
    if abs(det) < 1e-9:
        return None
    return np.linalg.solve(A, b)


def tls(pts):
    c = pts.mean(axis=0)
    _, _, vt = np.linalg.svd(pts - c, full_matrices=False)
    d = vt[0] / np.linalg.norm(vt[0])
    n = np.array([-d[1], d[0]])
    return {'c': c, 'dir': d, 'n': n, 'rho': float(n @ c),
            'theta': math.degrees(math.atan2(n[1], n[0])) % 180.0}


def main(path):
    ink = load_ink(path)
    h, w = ink.shape
    ys, xs = np.nonzero(ink)
    pts = np.stack([xs, ys], axis=1).astype(np.float64)
    x0, y0 = find_axes(ink)
    print(f"image {w}x{h}  ink={len(pts)}  y-axis col x0={x0}  x-axis row y0={y0}")

    peaks = hough(ink, min_votes=60)
    print(f"hough peaks: {len(peaks)}")

    solids = []
    for v, th, rho in peaks:
        r = refine(pts, th, rho)
        if r is None:
            continue
        extent, run, ratio = coverage(ink, r)
        if ratio > 0.80 and extent > 60:
            solids.append((r, ratio, extent, run, v))
    # dedupe refined
    solids.sort(key=lambda t: -t[4])
    keep = []
    for r, ratio, extent, run, v in solids:
        if any(abs(r['theta'] - k[0]['theta']) < 2.0 and abs(r['rho'] - k[0]['rho']) < 8
               for k in keep):
            continue
        keep.append((r, ratio, extent, run, v))
    print(f"\nsolid lines ({len(keep)}):")
    for r, ratio, extent, run, v in keep:
        print(f"  votes={v:4d} theta={r['theta']:7.2f} rho={r['rho']:8.2f} "
              f"run/extent={ratio:.3f} extent={extent} run={run}")

    # drop the two axes from the edge set
    edges = []
    for r, ratio, extent, run, v in keep:
        t = r['theta']
        is_v = min(t, 180 - t) < 2.0 and abs(abs(r['rho']) - x0) < 8
        is_h = abs(t - 90.0) < 2.0 and abs(r['rho'] - y0) < 8
        if is_v or is_h:
            continue
        edges.append((r, v))
    print(f"\nedge candidates (axes removed): {len(edges)}")
    for r, v in edges:
        print(f"  votes={v:4d} theta={r['theta']:7.2f} rho={r['rho']:8.2f}")

    # all pairwise intersections
    print("\npairwise intersections:")
    inter_pts = {}
    for i in range(len(edges)):
        for j in range(i + 1, len(edges)):
            p = inter(edges[i][0], edges[j][0])
            if p is None:
                continue
            if -20 <= p[0] <= w + 20 and -20 <= p[1] <= h + 20:
                print(f"  E{i} x E{j} = ({p[0]:7.2f},{p[1]:7.2f})")
                inter_pts[(i, j)] = p

    # --- build the two triangles from 3 lines each (combinatorial search) ---
    # A triangle = 3 lines pairwise intersecting at 3 points; require the three
    # points to be inside the ink bbox and to span a reasonable area.
    allk = list(range(len(edges)))
    tris = []
    for a_i in range(len(allk)):
        for b_i in range(a_i + 1, len(allk)):
            for c_i in range(b_i + 1, len(allk)):
                ls = [edges[allk[a_i]][0], edges[allk[b_i]][0], edges[allk[c_i]][0]]
                ps = []
                ok = True
                for u in range(3):
                    for vv in range(u + 1, 3):
                        p = inter(ls[u], ls[vv])
                        if p is None or not (-5 <= p[0] <= w + 5 and -5 <= p[1] <= h + 5):
                            ok = False
                        else:
                            ps.append(p)
                if not ok or len(ps) != 3:
                    continue
                area = abs((ps[1][0] - ps[0][0]) * (ps[2][1] - ps[0][1]) -
                           (ps[1][1] - ps[0][1]) * (ps[2][0] - ps[0][0])) / 2
                if area < 2000:
                    continue
                # each side must be a real drawn segment: the 3 vertices must
                # sit where the line actually has ink, and between two vertices
                # the line must not run way beyond
                tris.append({'lines': ls, 'pts': ps, 'area': area})
    tris.sort(key=lambda t: -t['area'])
    uniq = []
    for t in tris:
        sig = tuple(sorted((round(p[0] / 6), round(p[1] / 6)) for p in t['pts']))
        if any(sig == u['sig'] for u in uniq):
            continue
        t['sig'] = sig
        uniq.append(t)
    print(f"\ntriangle candidates: {len(uniq)}")
    for t in uniq:
        print(f"  area={t['area']:8.0f} pts=" +
              " ".join(f"({p[0]:.1f},{p[1]:.1f})" for p in t['pts']))

    if len(uniq) < 2:
        print("!! need two triangles, aborting")
        return 1

    # Two largest disjoint-in-vertex candidates are the two triangles:
    triL, triR = uniq[0], None
    for t in uniq[1:]:
        if all(min(math.hypot(p[0] - q[0], p[1] - q[1]) for q in triL['pts']) > 15
               for p in t['pts']):
            triR = t
            break
    if triR is None:
        print("!! no second triangle found")
        return 1

    def label_tri(t, kind):
        ps = t['pts']
        # topmost (min pixel y) = A/A1?  We label after the figure's own layout:
        #   left triangle:  A = topmost, B = leftmost of the rest, C = last
        #   right triangle: A1 = bottommost, B1 = rightmost of the rest, C1 = last
        idx = sorted(range(3), key=lambda i: ps[i][1])
        if kind == 'L':
            A = ps[idx[0]]
            rest = [ps[idx[1]], ps[idx[2]]]
            B = min(rest, key=lambda p: p[0])
            C = max(rest, key=lambda p: p[0])
            return {'A': A, 'B': B, 'C': C}
        else:
            A1 = ps[idx[2]]
            rest = [ps[idx[0]], ps[idx[1]]]
            B1 = max(rest, key=lambda p: p[0])
            C1 = min(rest, key=lambda p: p[0])
            return {'A1': A1, 'B1': B1, 'C1': C1}

    L = label_tri(triL, 'L')
    R = label_tri(triR, 'R')
    print("\nlabelled pixels:")
    for k, v in list(L.items()) + list(R.items()):
        print(f"  {k}: ({v[0]:7.2f},{v[1]:7.2f})")

    # least squares: x_px = s*x + tx ;  y_px = -s*y + ty
    known = {
        'A': (L['A'], (-2.0, 1.0)),
        'B': (L['B'], (-3.0, -2.0)),
        'A1': (R['A1'], (4.0, -2.0)),
        'B1': (R['B1'], (6.0, 4.0)),
    }
    # solve separately for (s, tx) from x and (s, ty) from y but force one s:
    # least squares over both coordinate equations -> parameters (s, tx, ty)
    Amat, bvec = [], []
    for px, (X, Y) in known.values():
        Amat.append([X, 1.0, 0.0]); bvec.append(px[0])
        Amat.append([-Y, 0.0, 1.0]); bvec.append(px[1])
    sol, res, *_ = np.linalg.lstsq(np.array(Amat), np.array(bvec), rcond=None)
    s, tx, ty = sol
    print(f"\nfitted transform: s={s:.4f} px/unit  tx={tx:.2f}  ty={ty:.2f}")
    resid = []
    for k, (px, (X, Y)) in known.items():
        ex = s * X + tx - px[0]
        ey = -s * Y + ty - px[1]
        resid.append(math.hypot(ex, ey))
        print(f"  {k:3s} data=({X:5.2f},{Y:5.2f}) px=({px[0]:7.2f},{px[1]:7.2f}) "
              f"err=({ex:+.2f},{ey:+.2f})")
    print(f"  max |resid| = {max(resid):.2f} px")

    def to_data(px):
        return ((px[0] - tx) / s, -(px[1] - ty) / s)

    C = to_data(L['C'])
    C1 = to_data(R['C1'])
    print(f"\nC  = ({C[0]:.3f}, {C[1]:.3f})")
    print(f"C1 = ({C1[0]:.3f}, {C1[1]:.3f})")
    print(f"homothety check  C1 vs -2*C: "
          f"({C1[0]:+.3f},{C1[1]:+.3f}) vs ({-2*C[0]:+.3f},{-2*C[1]:+.3f})")

    # collinearity of O-A-A1, O-B-B1, O-C-C1 in pixels
    def line_dist(p, q, o=(x0, y0)):
        # distance of o from line pq
        v = np.array(p) - np.array(q)
        w2 = np.array(o) - np.array(q)
        cr = abs(v[0] * w2[1] - v[1] * w2[0]) / (np.linalg.norm(v) + 1e-12)
        return cr
    print("\ncollinearity with the origin (pixel distance, should be small):")
    for nm, p, q in (('A A1', L['A'], R['A1']), ('B B1', L['B'], R['B1']),
                     ('C C1', L['C'], R['C1'])):
        print(f"  {nm}: {line_dist(p, q):.2f} px")

    # aspect ratio check: is the figure isotropic (same s in x and y)?
    print("\n--- suggested exact drawing spec (constrained) ---")
    print(f"  origin O = (0,0); units: 1 data unit = {s:.2f} px in the scan")
    print(f"  A = (-2, 1)   B = (-3, -2)   C = ({C[0]:.3f}, {C[1]:.3f})")
    print(f"  A1 = (4, -2)  B1 = (6, 4)   C1 = (-2*Cx, -2*Cy)")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else 'captures/cixi-figs/fig05.png'))
