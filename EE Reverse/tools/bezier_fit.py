"""Fit a sampled curve with as FEW cubic bezier segments as possible.

Why this exists
---------------
EE's own "函数图象" graph is an ``esShapePath`` + ``esSegBezier`` (type 0x4703)
whose control polygon has only a handful of knots: the user-made y=x^2 sample
on the canvas carries **7 control points = 2 cubic segments**.  Feeding the
engine a densely Catmull-Rom'd chain instead still LOOKS like a polyline to the
user ("这次你只用了更多的折线", 2026-10-19) because the object then carries
hundreds of knots.

So: sample the function densely, fit it with Schneider's classic
"algorithm for automatically fitting digitized curves" (least squares +
error-driven split), and hand the engine the resulting SHORT control polygon.
Tolerance is in canvas units (1 unit = 1/400 mm); 1.5 units = 0.00375 mm.

Public API
----------
fit_bezier(points, tol=1.5, max_segments=24) -> list[(x, y)]
    ``points`` are on-curve samples in canvas coordinates.
    Returns the flattened control polygon [P0, C1, C2, P1, C3, C4, P2, ...]
    (length 1 + 3*segments), ready for
    ``esShapePath::CreateFromPathData`` with types [0,3,3,...,0x80].
"""

from __future__ import annotations

import math
from typing import List, Sequence, Tuple

Point = Tuple[float, float]


def _bez(p0: Point, c1: Point, c2: Point, p1: Point, t: float) -> Point:
    mt = 1.0 - t
    a = mt * mt * mt
    b = 3.0 * mt * mt * t
    c = 3.0 * mt * t * t
    d = t * t * t
    return (a * p0[0] + b * c1[0] + c * c2[0] + d * p1[0],
            a * p0[1] + b * c1[1] + c * c2[1] + d * p1[1])


def _dist(a: Point, b: Point) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _unit(v: Point) -> Point:
    n = math.hypot(v[0], v[1])
    if n < 1e-12:
        return (0.0, 0.0)
    return (v[0] / n, v[1] / n)


def _chord_params(pts: Sequence[Point]) -> List[float]:
    u = [0.0]
    for i in range(1, len(pts)):
        u.append(u[-1] + _dist(pts[i], pts[i - 1]))
    total = u[-1]
    if total <= 1e-12:
        n = len(pts) - 1
        return [i / n for i in range(len(pts))]
    return [v / total for v in u]


def _solve_alpha_beta(pts: Sequence[Point], u: Sequence[float],
                      t1: Point, t2: Point) -> Tuple[float, float]:
    """Least squares for C1 = P0 + a*t1, C2 = P3 - b*t2."""
    p0, p3 = pts[0], pts[-1]
    a11 = a12 = a22 = b1 = b2 = 0.0
    for i, q in enumerate(pts):
        ui = u[i]
        m = 1.0 - ui
        bb1 = 3.0 * ui * m * m
        bb2 = 3.0 * ui * ui * m
        ax = t1[0] * bb1
        ay = t1[1] * bb1
        bx = t2[0] * bb2
        by = t2[1] * bb2
        # residual after the fixed endpoints
        base_x = p0[0] * (m * m * m + bb1) + p3[0] * (bb2 + ui * ui * ui)
        base_y = p0[1] * (m * m * m + bb1) + p3[1] * (bb2 + ui * ui * ui)
        rx = q[0] - base_x
        ry = q[1] - base_y
        a11 += ax * ax + ay * ay
        a12 += ax * bx + ay * by
        a22 += bx * bx + by * by
        b1 += ax * rx + ay * ry
        b2 += bx * rx + by * ry
    det = a11 * a22 - a12 * a12
    if abs(det) < 1e-9:
        # fall back to chord/3 tangents
        d = _dist(p0, p3) / 3.0
        return d, d
    alpha = (b1 * a22 - b2 * a12) / det
    beta = (a11 * b2 - a12 * b1) / det
    # guard against pathological solutions
    d = _dist(p0, p3)
    lo, hi = 0.05 * d, 4.0 * d + 1e-9
    if not (lo <= alpha <= hi):
        alpha = max(lo, min(hi, d / 3.0))
    if not (lo <= beta <= hi):
        beta = max(lo, min(hi, d / 3.0))
    return alpha, beta


def _bez_d1(p0: Point, c1: Point, c2: Point, p1: Point, t: float) -> Point:
    mt = 1.0 - t
    return (3.0 * (mt * mt * (c1[0] - p0[0]) + 2.0 * mt * t * (c2[0] - c1[0])
                   + t * t * (p1[0] - c2[0])),
            3.0 * (mt * mt * (c1[1] - p0[1]) + 2.0 * mt * t * (c2[1] - c1[1])
                   + t * t * (p1[1] - c2[1])))


def _bez_d2(p0: Point, c1: Point, c2: Point, p1: Point, t: float) -> Point:
    mt = 1.0 - t
    return (6.0 * (mt * (c2[0] - 2.0 * c1[0] + p0[0]) + t * (p1[0] - 2.0 * c2[0] + c1[0])),
            6.0 * (mt * (c2[1] - 2.0 * c1[1] + p0[1]) + t * (p1[1] - 2.0 * c2[1] + c1[1])))


def _reparameterize(pts: Sequence[Point], u: Sequence[float], p0: Point,
                    c1: Point, c2: Point, p1: Point) -> List[float]:
    """One Newton-Raphson step toward the closest parameter for each sample.

    Without this the chord-length parameters are biased, the least-squares fit
    is worse than it could be, and the recursive splitter creates far more
    segments than needed (Schneider's paper relies on exactly this step).
    """
    out = []
    for i, q in enumerate(pts):
        t = u[i]
        b = _bez(p0, c1, c2, p1, t)
        d1 = _bez_d1(p0, c1, c2, p1, t)
        d2 = _bez_d2(p0, c1, c2, p1, t)
        dx, dy = b[0] - q[0], b[1] - q[1]
        num = dx * d1[0] + dy * d1[1]
        den = d1[0] * d1[0] + d1[1] * d1[1] + dx * d2[0] + dy * d2[1]
        if abs(den) < 1e-12:
            out.append(t)
        else:
            nt = t - num / den
            out.append(min(1.0, max(0.0, nt)))
    return out


def _max_error(pts: Sequence[Point], u: Sequence[float], p0: Point, c1: Point,
               c2: Point, p1: Point) -> Tuple[float, int]:
    """Max distance between the samples and the fitted cubic AT THE SAME
    chord parameter.

    Sampling the bezier at a fixed 25 points over-estimates the error badly for
    long segments (the sample spacing is hundreds of units, so "distance to the
    nearest sampled curve point" is dominated by the spacing, not the actual
    deviation) -- the first version of this fitter therefore produced 21
    segments for a quarter circle that 2 segments can do.  Evaluating the curve
    at each sample's own chord parameter u_i is the standard cheap proxy.
    """
    worst = -1.0
    worst_i = 0
    for idx, q in enumerate(pts):
        cc = _bez(p0, c1, c2, p1, u[idx])
        d = _dist(q, cc)
        if d > worst:
            worst = d
            worst_i = idx
    return worst, worst_i


def _fit_range(pts: Sequence[Point], t1: Point, t2: Point, tol: float,
               depth: int = 0) -> List[Point]:
    if len(pts) == 2:
        d = _dist(pts[0], pts[1]) / 3.0
        return [pts[0], (pts[0][0] + t1[0] * d, pts[0][1] + t1[1] * d),
                (pts[1][0] + t2[0] * d, pts[1][1] + t2[1] * d), pts[1]]
    u = _chord_params(pts)
    alpha, beta = _solve_alpha_beta(pts, u, t1, t2)
    c1 = (pts[0][0] + t1[0] * alpha, pts[0][1] + t1[1] * alpha)
    # t2 is the BACKWARD tangent at the end point, so C2 = P3 + t2*beta.
    c2 = (pts[-1][0] + t2[0] * beta, pts[-1][1] + t2[1] * beta)
    # Newton reparameterisation + refit (twice is plenty)
    for _ in range(2):
        u2 = _reparameterize(pts, u, pts[0], c1, c2, pts[-1])
        if _dist((u2[0], 0.0), (u[-1], 0.0)) < 1e-12 and u2[-1] - u2[0] < 1e-9:
            pass
        # keep the parameter ordering monotone
        for i in range(1, len(u2)):
            if u2[i] <= u2[i - 1]:
                u2[i] = min(1.0, u2[i - 1] + 1e-9)
        u = u2
        alpha, beta = _solve_alpha_beta(pts, u, t1, t2)
        c1 = (pts[0][0] + t1[0] * alpha, pts[0][1] + t1[1] * alpha)
        c2 = (pts[-1][0] + t2[0] * beta, pts[-1][1] + t2[1] * beta)
    err, idx = _max_error(pts, u, pts[0], c1, c2, pts[-1])
    if err <= tol or depth > 12 or len(pts) <= 3:
        return [pts[0], c1, c2, pts[-1]]
    # split at the worst sample
    idx = max(1, min(len(pts) - 2, idx))
    left = list(pts[:idx + 1])
    right = list(pts[idx:])
    center = _unit((left[-1][0] - left[-2][0], left[-1][1] - left[-2][1])) if len(left) > 1 else t1
    if center == (0.0, 0.0):
        center = t1
    left_t2 = (-center[0], -center[1])
    part_a = _fit_range(left, t1, left_t2, tol, depth + 1)
    part_b = _fit_range(right, center, t2, tol, depth + 1)
    return part_a[:-1] + part_b


def fit_bezier(points: Sequence[Point], tol: float = 1.5,
               max_segments: int = 32) -> List[Point]:
    """Fit on-curve samples with piecewise cubic beziers.

    Returns the flattened CONTROL polygon [P0, C1, C2, P1, C3, C4, P2, ...].
    """
    pts = [(float(x), float(y)) for x, y in points]
    # drop repeated points (they break the parameterisation)
    clean = [pts[0]]
    for p in pts[1:]:
        if _dist(p, clean[-1]) > 1e-6:
            clean.append(p)
    if len(clean) < 2:
        raise ValueError("need at least 2 distinct points")
    pts = clean
    t1 = _unit((pts[1][0] - pts[0][0], pts[1][1] - pts[0][1]))
    t2 = _unit((pts[-2][0] - pts[-1][0], pts[-2][1] - pts[-1][1]))
    poly = _fit_range(pts, t1, t2, tol)
    segs = (len(poly) - 1) // 3
    # too many segments: coarsen the tolerance until the polygon is acceptable
    while segs > max_segments:
        tol *= 1.8
        poly = _fit_range(pts, t1, t2, tol)
        segs = (len(poly) - 1) // 3
    return poly


if __name__ == "__main__":
    # tiny self-test: fit a quarter circle and report the resulting error
    n = 400
    pts = [(5000 * math.cos(math.pi / 2 * i / n),
            5000 * math.sin(math.pi / 2 * i / n)) for i in range(n + 1)]
    poly = fit_bezier(pts, tol=1.0)
    segs = (len(poly) - 1) // 3
    # measure max deviation of the fitted curve from the circle
    worst = 0.0
    for k in range(segs):
        p0, c1, c2, p1 = poly[3 * k:3 * k + 4]
        for j in range(21):
            q = _bez(p0, c1, c2, p1, j / 20.0)
            worst = max(worst, abs(math.hypot(*q) - 5000.0))
    print("quarter circle -> %d segments, max radial error %.4f canvas units"
          % (segs, worst))
