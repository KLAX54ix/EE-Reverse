#!/usr/bin/env python3
"""Q3 (九下期中 选择压轴): 百变魔尺 24 段 = 24 个等腰直角三角形.

Stem: "如图是用24段魔尺(24个等腰直角三角形，把等腰直角三角形最长边看作1)
       围成的长为4、宽为3的长方形．用该魔尺能围出不全等的长方形个数为 ( )"

Constraint extraction (all derived; only the colouring is copied from the photo)
-------------------------------------------------------------------------------
The printed photo is a hollow rectangular RING (a magic-ruler strip closed into
a frame), not a solid rectangle.  Let the hypotenuse of every isosceles right
triangle be 1 (the stem's unit).  Then:

  * each triangle's altitude onto its hypotenuse is 1/2;
  * the 24 triangles lie flat, each with its hypotenuse on either the OUTER or
    the INNER boundary of the ring, its right-angle apex touching the other
    boundary.  Hence the ring has constant width 1/2 and
        inner rectangle = (W-1) x (H-1).
  * the 24 hypotenuses tile the two boundaries, so
        outer perimeter + inner perimeter = 2(W+H) + 2(W-1+H-1) = 24
    For W=4, H=3: 14 + 10 = 24  -- exactly the 24 segments.  (This is also the
    counting rule behind the answer: 4(W+H)-4 = 24  ->  W+H = 7.)
  * area check: outer 4x3 = 12, inner 3x2 = 6, band = 6 = 24 * (1/4).

So the figure is FULLY CONSTRAINED by the stem (W=4, H=3 literal in units of the
unit hypotenuse) -- no free geometric parameter.  The only thing taken from the
photo is the red/white alternation of the 24 segments along the ruler chain
(physical fact of the toy: consecutive segments alternate colour).

Colouring: the 24 triangles form one closed zig-zag chain (each triangle shares
its two legs with its two neighbours).  Colour alternates along that chain;
the "red" set is emitted with fill="dark", the "white" set stays unfilled
(grey/white two-tone, which is how the figure reads in print).

Output: analysis/specs/nb/q03.model.json   (model units, y UP)
"""
import json
import math
import os

# ---------------------------------------------------------------- constraints
W, H = 4.0, 3.0            # outer rectangle, unit = hypotenuse of one triangle
HYP = 1.0                  # stem: longest side of the isosceles right triangle
BAND = HYP / 2.0           # altitude to the hypotenuse -> ring width
W2, H2 = W - HYP, H - HYP  # inner rectangle = 3 x 2

# ---------------------------------------------------------------- construction
# Outer boundary lattice points (unit steps along each side of the 4x3 rect).
outer = {
    "ob0": (0.0, 0.0), "ob1": (1.0, 0.0), "ob2": (2.0, 0.0),
    "ob3": (3.0, 0.0), "ob4": (4.0, 0.0),
    "or1": (4.0, 1.0), "or2": (4.0, 2.0), "or3": (4.0, 3.0),
    "ot3": (3.0, 3.0), "ot2": (2.0, 3.0), "ot1": (1.0, 3.0), "ot0": (0.0, 3.0),
    "ol2": (0.0, 2.0), "ol1": (0.0, 1.0),
}
# Inner boundary lattice points (inner rect is BAND inside the outer one).
inner = {
    "ib0": (0.5, 0.5), "ib1": (1.5, 0.5), "ib2": (2.5, 0.5), "ib3": (3.5, 0.5),
    "ir1": (3.5, 1.5), "ir2": (3.5, 2.5),
    "it2": (2.5, 2.5), "it1": (1.5, 2.5), "it0": (0.5, 2.5),
    "il1": (0.5, 1.5),
}
pts = dict(outer)
pts.update(inner)

# Each triangle = (hyp_a, hyp_b, apex); hyp_a-hyp_b is the hypotenuse (length 1,
# lying on one boundary), apex is the right-angle vertex on the other boundary.
TRIAS = [
    # --- 14 triangles whose hypotenuse lies on the OUTER boundary -----------
    ("ob0", "ob1", "ib0"), ("ob1", "ob2", "ib1"),
    ("ob2", "ob3", "ib2"), ("ob3", "ob4", "ib3"),
    ("ob4", "or1", "ib3"), ("or1", "or2", "ir1"), ("or2", "or3", "ir2"),
    ("or3", "ot3", "ir2"), ("ot3", "ot2", "it2"), ("ot2", "ot1", "it1"),
    ("ot1", "ot0", "it0"),
    ("ot0", "ol2", "it0"), ("ol2", "ol1", "il1"), ("ol1", "ob0", "ib0"),
    # --- 10 triangles whose hypotenuse lies on the INNER boundary ----------
    ("ib0", "ib1", "ob1"), ("ib1", "ib2", "ob2"), ("ib2", "ib3", "ob3"),
    ("ib3", "ir1", "or1"), ("ir1", "ir2", "or2"),
    ("ir2", "it2", "ot3"), ("it2", "it1", "ot2"), ("it1", "it0", "ot1"),
    ("it0", "il1", "ol2"), ("il1", "ib0", "ol1"),
]


def vec(a, b):
    return (pts[b][0] - pts[a][0], pts[b][1] - pts[a][1])


def dist(a, b):
    return math.hypot(*vec(a, b))


def tri_adjacency():
    """adj[i] = the (at most two) triangles that share a LEG with triangle i."""
    adj = {i: set() for i in range(len(TRIAS))}
    for i, (h1, h2, ap) in enumerate(TRIAS):
        for a, b in ((h1, ap), (h2, ap)):
            key = tuple(sorted((a, b)))
            for j, t2 in enumerate(TRIAS):
                if j == i:
                    continue
                if key in {tuple(sorted((t2[0], t2[2]))),
                           tuple(sorted((t2[1], t2[2])))}:
                    adj[i].add(j)
    return adj


# ---------------------------------------------------------------- self checks
def assert_geometry():
    n = len(TRIAS)
    assert n == 24, n
    used = set()
    for t in TRIAS:
        used.update(t)
    assert len(used) == 24, len(used)      # exactly 24 vertices
    for i, (h1, h2, ap) in enumerate(TRIAS):
        lh, l1, l2 = dist(h1, h2), dist(h1, ap), dist(h2, ap)
        assert abs(lh - HYP) < 1e-12, (i, lh)
        assert abs(l1 - l2) < 1e-12, (i, l1, l2)
        u, v = vec(ap, h1), vec(ap, h2)
        c = (u[0] * v[0] + u[1] * v[1]) / (l1 * l2)
        assert abs(c) < 1e-12, (i, c)
        # apex must be the altitude foot -> distance to hyp midpoint is HYP/2
        foot = ((pts[h1][0] + pts[h2][0]) / 2, (pts[h1][1] + pts[h2][1]) / 2)
        hgt = math.hypot(pts[ap][0] - foot[0], pts[ap][1] - foot[1])
        assert abs(hgt - BAND) < 1e-12, (i, "apex height", hgt)
    adj = tri_adjacency()
    assert all(len(v) == 2 for v in adj.values()), \
        "chain adjacency broken: %r" % [len(v) for v in adj.values()]
    order, cur, prev = [0], 0, None
    while True:
        nxt = [x for x in adj[cur] if x != prev]
        if not nxt or nxt[0] == 0:
            break
        order.append(nxt[0])
        prev, cur = cur, nxt[0]
    assert len(order) == 24, len(order)
    return order


def assert_tiling(rng_seed=7, nsample=200000):
    """Random points: every interior point of the frame covered exactly once,
    no point of the hole / outside covered."""
    import random
    rnd = random.Random(rng_seed)
    tol = 1e-12

    def in_tri(P, T):
        (x1, y1), (x2, y2), (x3, y3) = T
        d1 = (x2 - x1) * (P[1] - y1) - (y2 - y1) * (P[0] - x1)
        d2 = (x3 - x2) * (P[1] - y2) - (y3 - y2) * (P[0] - x2)
        d3 = (x1 - x3) * (P[1] - y3) - (y1 - y3) * (P[0] - x3)
        neg = (d1 < -tol) or (d2 < -tol) or (d3 < -tol)
        pos = (d1 > tol) or (d2 > tol) or (d3 > tol)
        return not (neg and pos)

    tri_pts = [[pts[a], pts[b], pts[c]] for a, b, c in TRIAS]
    bad = 0
    for _ in range(nsample):
        P = (rnd.random() * W, rnd.random() * H)
        inside_frame = not (BAND < P[0] < W - BAND and BAND < P[1] < H - BAND)
        cnt = sum(1 for T in tri_pts if in_tri(P, T))
        if inside_frame != (cnt == 1):
            bad += 1
    assert bad == 0, "tiling coverage failures: %d / %d" % (bad, nsample)


CHAIN = assert_geometry()
assert_tiling()
ADJ = tri_adjacency()

# ------------------------------------------------- alternate colouring (chain)
color = {0: 0}
stack = [0]
while stack:
    u = stack.pop()
    for v in ADJ[u]:
        if v not in color:
            color[v] = 1 - color[u]
            stack.append(v)
assert len(color) == 24 and sum(color.values()) == 12, color

# ---------------------------------------------------------------- model spec
checks = []


def C(**kw):
    checks.append(kw)


# --- outer rectangle 4 x 3 ---------------------------------------------------
C(type="distance", label="outer AB = 4", a="ob0", b="ob4", value=W, tol_pct=0.001)
C(type="distance", label="outer BC = 3", a="ob4", b="or3", value=H, tol_pct=0.001)
C(type="distance", label="outer CD = 4", a="or3", b="ot0", value=W, tol_pct=0.001)
C(type="distance", label="outer DA = 3", a="ot0", b="ob0", value=H, tol_pct=0.001)
C(type="perpendicular", label="outer corner A", a=["ob0", "ob1"], b=["ob0", "ol1"])
C(type="perpendicular", label="outer corner B", a=["ob4", "or1"], b=["ob4", "ob3"])
C(type="perpendicular", label="outer corner C", a=["or3", "ot3"], b=["or3", "or2"])
C(type="perpendicular", label="outer corner D", a=["ot0", "ol2"], b=["ot0", "ot1"])
C(type="collinear", label="outer side AB straight", points=["ob0", "ob2", "ob4"])
C(type="collinear", label="outer side BC straight", points=["ob4", "or2", "or3"])
C(type="collinear", label="outer side CD straight", points=["or3", "ot2", "ot0"])
C(type="collinear", label="outer side DA straight", points=["ot0", "ol1", "ob0"])

# --- inner rectangle 3 x 2 (band width = 1/2) --------------------------------
C(type="distance", label="inner A'B' = 3", a="ib0", b="ib3", value=W2, tol_pct=0.001)
C(type="distance", label="inner B'C' = 2", a="ib3", b="ir2", value=H2, tol_pct=0.001)
C(type="distance", label="inner C'D' = 3", a="ir2", b="it0", value=W2, tol_pct=0.001)
C(type="distance", label="inner D'A' = 2", a="it0", b="ib0", value=H2, tol_pct=0.001)
C(type="perpendicular", label="inner corner A'", a=["ib0", "ib1"], b=["ib0", "il1"])
C(type="perpendicular", label="inner corner C'", a=["ir2", "it2"], b=["ir2", "ir1"])
C(type="parallel", label="inner A'B' // outer AB",
  a=["ib0", "ib3"], b=["ob0", "ob4"])
C(type="parallel", label="inner B'C' // outer BC",
  a=["ib3", "ir2"], b=["ob4", "or3"])
C(type="parallel", label="inner C'D' // outer CD",
  a=["ir2", "it0"], b=["or3", "ot0"])
C(type="parallel", label="inner D'A' // outer DA",
  a=["it0", "ib0"], b=["ot0", "ob0"])
C(type="collinear", label="inner side A'B' straight", points=["ib0", "ib2", "ib3"])
C(type="collinear", label="inner side C'D' straight", points=["ir2", "it1", "it0"])

# --- all 24 triangles: hypotenuse 1, equal legs, right angle ----------------
for i, (h1, h2, ap) in enumerate(TRIAS):
    tag = "T%02d" % (i + 1)
    C(type="distance", label=tag + " hypotenuse = 1",
      a=h1, b=h2, value=HYP, tol_pct=0.0001)
    C(type="equal", label=tag + " legs equal",
      a=[h1, ap], b=[h2, ap], tol_pct=0.0001)
    C(type="angle", label=tag + " right angle at apex",
      vertex=ap, a=h1, b=h2, deg=90, tol_deg=0.0001)

# ---------------------------------------------------------------- paths
paths = []
# fills first (the outlines drawn later stay on top)
for i, (h1, h2, ap) in enumerate(TRIAS):
    if color[i] == 0:
        paths.append({"points": [h1, h2, ap], "close": True, "fill": "dark"})
for i, (h1, h2, ap) in enumerate(TRIAS):
    if color[i] == 1:
        paths.append({"points": [h1, h2, ap], "close": True})
# frame outlines last
paths.append({"points": ["ob0", "ob4", "or3", "ot0"], "close": True})
paths.append({"points": ["ib0", "ib3", "ir2", "it0"], "close": True})

spec = {
    "q": 3,
    "title": "magic ruler: 24 congruent isosceles right triangles (hyp=1) "
             "closed into a 4x3 rectangular ring (inner 3x2)",
    "png": "captures/jxqz-figs/fig05.png",
    "unit": "hypotenuse of one isosceles right triangle = 1 (stem's unit)",
    "assumptions": [
        "the photo is a closed ring of the 24-segment ruler, so the triangles "
        "carry their hypotenuses on the outer boundary (14) and on the inner "
        "boundary (10): 14+10 = 24; the ring has constant width 1/2",
        "outer rectangle 4x3 is literal in the stem's unit (hyp=1); the inner "
        "hole is 3x2; 4x3 is not a solid 12-square grid -- the solid reading "
        "would make the 24 triangles cover only half of it",
        "the 24 triangles form one closed chain; segment colours alternate "
        "along that chain (red -> fill=dark, white -> unfilled)",
    ],
    "points": {k: [v[0], v[1]] for k, v in pts.items()},
    "checks": checks,
    "paths": paths,
    "labels": [],
    "dots": [],
}

out = "analysis/specs/nb/q03.model.json"
os.makedirs(os.path.dirname(out), exist_ok=True)
with open(out, "w", encoding="utf-8") as fh:
    json.dump(spec, fh, ensure_ascii=False, indent=1)
print("wrote", out)
print("triangles =", len(TRIAS), " vertices =", len(pts), " checks =", len(checks))
print("outer %.1fx%.1f  inner %.1fx%.1f  band=%.2f"
      % (W, H, W2, H2, BAND))
print("hypotenuse count: outer %d + inner %d = %d"
      % (2 * (W + H), 2 * (W2 + H2), 2 * (W + H) + 2 * (W2 + H2)))
print("area: outer %.2f - inner %.2f = %.2f = 24 * hyp^2/4 = %.2f"
      % (W * H, W2 * H2, W * H - W2 * H2, 24 * HYP * HYP / 4.0))
print("chain order:",
      " ".join("T%d(%s)" % (i + 1, "dark" if color[i] == 0 else "light")
               for i in CHAIN))
