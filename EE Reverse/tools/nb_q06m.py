#!/usr/bin/env python3
"""多选 6 (九下期中选择压轴, 5 分): 半圆 O, 直径 AB; C 在半圆上; 延长 BC 至 D
使 BC=CD; CE 是过 C 的切线, 交 AD 于 E; BE 交圆 O 于 F; AF 延长交 CE 于 G;
若 BE=AG, 则 ( )

Stem constraints
----------------
1. AB 是半圆 O 的直径  -> O 是 AB 中点, 半径 R = AB/2, 半圆在 AB 上方.
2. C 在半圆上          -> |OC| = R, C 在上半圆 (sin>0).
3. D 在 BC 的延长线上, BC = CD  -> D = 2C - B.
4. CE 是过 C 的切线    -> CE ⟂ OC.
5. E = CE ∩ AD.
6. F = BE ∩ 圆的第二个交点 (B 也在圆上).
7. G = 直线 AF ∩ 直线 CE.
8. BE = AG             <- 强约束, 唯一确定 C 的位置.

Free parameters
---------------
Only the global scale/orientation; the printed figure (captures/jxqz-figs/fig10.png)
fixes AB horizontal and the semicircle above it, so we take A=(-1,0), B=(1,0),
R=1.  Nothing else is measured: C is SOLVED from the BE=AG equation.

Derivation (all in the script, numerically constructed)
-------------------------------------------------------
Put c = cos θ, s = sin θ > 0, C=(c,s):
  D = 2C - B = (2c-1, 2s)
  AD ∥ 2C  =>  AD ∥ OC, hence CE ⟂ AD also holds identically.
  E = AD ∩ CE = C + s·(-s, c)              (|CE| = s)
  F = B + λ(E-B),  λ = -2(B·(E-B))/|E-B|²  (second circle intersection)
  G = AF ∩ CE,  and one finds CG = CE/2 identically.
The script solves BE(c) = AG(c) by bisection on c∈(0,1):
  |BE| = sqrt((1-c)(5+3c)),  |AG| = ½·sqrt((1+c)(5+3c))
  => (1-c)(5+3c) = ¼(1+c)(5+3c)  =>  c = 3/5,  θ = arccos(3/5) ≈ 53.130°
The closed forms are printed only as a cross-check of the constructed points.

Consequences (multi-select options):
  AD = AB (= 2R)                 always, and in particular at this C.
  CE ⟂ AD                        always (AD ∥ OC), true.
  AE / DE = (1+c)/(1-c) = 4      exactly when c = 3/5  -> C is true.
  G is the midpoint of CE        identically true      -> D is true.
"""
import json
import math
import os

# ------------------------------------------------------------------ helpers
def sub(p, q):
    return (p[0] - q[0], p[1] - q[1])


def add(p, q):
    return (p[0] + q[0], p[1] + q[1])


def mul(k, p):
    return (k * p[0], k * p[1])


def norm(p):
    return math.hypot(p[0], p[1])


def dist(p, q):
    return norm(sub(p, q))


def line_intersection(p1, d1, p2, d2):
    """solve p1 + u*d1 = p2 + v*d2 for u (returns the point)."""
    det = d1[0] * (-d2[1]) - d1[1] * (-d2[0])
    if abs(det) < 1e-15:
        raise ZeroDivisionError("parallel lines")
    rx, ry = p2[0] - p1[0], p2[1] - p1[1]
    u = (rx * (-d2[1]) + d2[0] * ry) / det
    return (p1[0] + u * d1[0], p1[1] + u * d1[1])


A = (-1.0, 0.0)
B = (1.0, 0.0)
O = (0.0, 0.0)
R = 1.0


def construct(c):
    """Build every point of the figure for a given cos(theta) = c (y up)."""
    s = math.sqrt(max(0.0, 1.0 - c * c))
    C = (c, s)
    D = (2.0 * c - 1.0, 2.0 * s)                 # B + 2(C-B)
    ad_dir = sub(D, A)                           # = 2C
    tang = (-s, c)                               # unit tangent at C
    E = line_intersection(A, ad_dir, C, tang)    # E = AD ∩ CE
    e_from_ap = sub(E, A)
    if not (0.0 < (e_from_ap[0] * ad_dir[0] + e_from_ap[1] * ad_dir[1]) /
            (norm(ad_dir) ** 2) < 1.0):
        raise ValueError("E outside segment AD")
    # F: second intersection of line B-E with the unit circle
    d = sub(E, B)
    lam = -2.0 * (B[0] * d[0] + B[1] * d[1]) / (d[0] ** 2 + d[1] ** 2)
    F = add(B, mul(lam, d))
    G = line_intersection(A, sub(F, A), C, tang)  # G = AF ∩ CE
    return dict(C=C, D=D, E=E, F=F, G=G, s=s,
                BE=dist(B, E), AG=dist(A, G))


def be_minus_ag(c):
    return construct(c)["BE"] - construct(c)["AG"]


# --------------------------------------------------- solve the strong constraint
LO, HI = 0.01, 0.99
assert be_minus_ag(LO) > 0.0, "no sign change at low end"
assert be_minus_ag(HI) < 0.0, "no sign change at high end"
lo, hi = LO, HI
for _ in range(200):
    mid = 0.5 * (lo + hi)
    if be_minus_ag(mid) > 0.0:
        lo = mid
    else:
        hi = mid
c_sol = 0.5 * (lo + hi)
g = construct(c_sol)
C, D, E, F, G = g["C"], g["D"], g["E"], g["F"], g["G"]
s_sol = g["s"]
theta_deg = math.degrees(math.atan2(s_sol, c_sol))

# closed-form cross-check (the equation admits the exact root c = 3/5)
assert abs(c_sol - 0.6) < 1e-12, c_sol

# ------------------------------------------------------- derived quantities
AD = dist(A, D)
AB = dist(A, B)
BC = dist(B, C)
CD = dist(C, D)
CE = dist(C, E)
CG = dist(C, G)
AE = dist(A, E)
DE = dist(D, E)
BE = g["BE"]
AG = g["AG"]

# angle between CE and AD
u, v = sub(E, C), sub(D, A)
angle_ce_ad = math.degrees(math.acos(max(-1.0, min(1.0,
    (u[0] * v[0] + u[1] * v[1]) / (norm(u) * norm(v))))))
u2 = sub(C, O)
angle_ce_oc = math.degrees(math.acos(max(-1.0, min(1.0,
    (u[0] * u2[0] + u[1] * u2[1]) / (norm(u) * norm(u2))))))

# identifications enforced by the construction / the solution
assert abs(BC - CD) < 1e-12, (BC, CD)                 # BC = CD
assert abs(angle_ce_oc - 90.0) < 1e-9, angle_ce_oc    # CE ⟂ OC
assert abs(angle_ce_ad - 90.0) < 1e-9, angle_ce_ad    # CE ⟂ AD (derived)
assert abs(norm(F) - 1.0) < 1e-12, norm(F)            # F on circle
assert abs(AE / DE - 4.0) < 1e-9, AE / DE             # AE = 4 DE (option C)
assert abs(CG - CE / 2.0) < 1e-12, (CG, CE)           # G midpoint of CE (option D)
assert abs(AD - AB) < 1e-12, (AD, AB)                 # AD = AB (option A)
assert abs(BE - AG) < 1e-12, (BE, AG)                 # the strong constraint

# ------------------------------------------------------------------ model json
points = {
    "A": list(A), "B": list(B), "O": list(O),
    "C": list(C), "D": list(D), "E": list(E),
    "F": list(F), "G": list(G),
}

TOL = 1e-9
PCT = 1e-6
DEG = 1e-6
checks = [
    # ---- circle / diameter --------------------------------------------
    {"type": "midpoint", "label": "O midpoint AB", "point": "O",
     "a": "A", "b": "B", "tol": TOL},
    {"type": "collinear", "label": "B,O,A collinear", "points": ["B", "O", "A"],
     "tol": TOL},
    {"type": "distance", "label": "O A = R", "a": "O", "b": "A",
     "value": R, "tol_pct": PCT},
    {"type": "distance", "label": "O B = R", "a": "O", "b": "B",
     "value": R, "tol_pct": PCT},
    {"type": "distance", "label": "C on circle (OC=R)", "a": "O", "b": "C",
     "value": R, "tol_pct": PCT},
    {"type": "distance", "label": "F on circle (OF=R)", "a": "O", "b": "F",
     "value": R, "tol_pct": PCT},
    # ---- D on ray BC with BC = CD --------------------------------------
    {"type": "collinear", "label": "B,C,D collinear", "points": ["B", "C", "D"],
     "tol": TOL},
    {"type": "on_segment", "label": "C between B and D", "point": "C",
     "segment": ["B", "D"], "tol": TOL},
    {"type": "equal", "label": "BC = CD", "a": ["B", "C"], "b": ["C", "D"],
     "tol_pct": PCT},
    # ---- tangent at C --------------------------------------------------
    {"type": "perpendicular", "label": "CE perp OC (tangent)", "a": ["C", "E"],
     "b": ["O", "C"], "tol_deg": DEG},
    # ---- E on AD -------------------------------------------------------
    {"type": "on_segment", "label": "E on AD", "point": "E",
     "segment": ["A", "D"], "tol": TOL},
    # ---- F on BE -------------------------------------------------------
    {"type": "on_segment", "label": "F on BE", "point": "F",
     "segment": ["B", "E"], "tol": TOL},
    # ---- G on CE, A-F-G collinear --------------------------------------
    {"type": "on_segment", "label": "G on CE", "point": "G",
     "segment": ["C", "E"], "tol": TOL},
    {"type": "collinear", "label": "A,F,G collinear", "points": ["A", "F", "G"],
     "tol": TOL},
    {"type": "on_segment", "label": "F between A and G", "point": "F",
     "segment": ["A", "G"], "tol": TOL},
    # ---- the strong constraint -----------------------------------------
    {"type": "equal", "label": "BE = AG (given)", "a": ["B", "E"], "b": ["A", "G"],
     "tol_pct": PCT},
    # ---- derived facts = the four options ------------------------------
    {"type": "equal", "label": "option A: AD = AB", "a": ["A", "D"], "b": ["A", "B"],
     "tol_pct": PCT},
    {"type": "perpendicular", "label": "option B: CE perp AD", "a": ["C", "E"],
     "b": ["A", "D"], "tol_deg": DEG},
    {"type": "distance", "label": "option C: AE = 4 DE", "a": "A", "b": "E",
     "value": 4.0 * DE, "tol_pct": PCT},
    {"type": "midpoint", "label": "option D: G midpoint CE", "point": "G",
     "a": "C", "b": "E", "tol": TOL},
]

paths = [
    {"points": ["A", "B"]},      # diameter
    {"points": ["A", "D"]},      # AD (contains E)
    {"points": ["B", "D"]},      # ray BC extended to D (contains C)
    {"points": ["C", "E"]},      # tangent CE (contains G)
    {"points": ["B", "E"]},      # BE (contains F)
    {"points": ["A", "G"]},      # AF extended to G (contains F)
]

labels = [
    # offsets out of the figure, ~6-10% of the figure scale; checked so that the
    # visible glyph never crosses a drawn line (EE label boxes are transparent)
    {"text": "A", "anchor": "A", "ox": -0.13, "oy": -0.12},
    {"text": "B", "anchor": "B", "ox": 0.13, "oy": -0.12},
    {"text": "O", "anchor": "O", "ox": 0.0, "oy": -0.12},
    {"text": "C", "anchor": "C", "ox": 0.12, "oy": 0.12},
    {"text": "D", "anchor": "D", "ox": 0.10, "oy": 0.11},
    {"text": "E", "anchor": "E", "ox": -0.184, "oy": 0.001},
    {"text": "F", "anchor": "F", "ox": -0.08, "oy": -0.18},
    {"text": "G", "anchor": "G", "ox": 0.0, "oy": 0.15},
]

spec = {
    "q": "多选6",
    "title": "半圆O直径AB, C在圆上, BC=CD, CE切线, BE交圆于F, AF延长交CE于G, BE=AG",
    "png": "captures/jxqz-figs/fig10.png",
    "unit_note": "AB = 2 model units; theta = arccos(3/5) solved from BE=AG",
    "points": points,
    "checks": checks,
    "paths": paths,
    "arcs": [{"cx": 0.0, "cy": 0.0, "r": R, "a0": 0.0, "a1": 180.0,
              "steps": 96}],
    "labels": labels,
    "dots": ["O"],
}

os.makedirs("analysis/specs/nb", exist_ok=True)
out = "analysis/specs/nb/q06m.model.json"
with open(out, "w", encoding="utf-8") as fh:
    json.dump(spec, fh, ensure_ascii=False, indent=1)

# ------------------------------------------------------------------ report
print("wrote", out)
print("solved cos(theta) = %.15f   theta = %.10f deg" % (c_sol, theta_deg))
print("cross-check closed form: cos=3/5=0.6, theta=%.10f deg"
      % math.degrees(math.acos(0.6)))
print("A=(%.15f,%.15f) B=(%.1f,%.1f) O=(%.1f,%.1f)" % (A[0], A[1], B[0], B[1], O[0], O[1]))
for name in ("C", "D", "E", "F", "G"):
    print("  %s = (%.15f, %.15f)" % (name, points[name][0], points[name][1]))
print("BC=%.15f CD=%.15f  (equal)" % (BC, CD))
print("CE=%.15f  OC=%.1f  angle(CE,OC)=%.12f deg" % (CE, 1.0, angle_ce_oc))
print("AD=%.15f AB=%.15f  angle(CE,AD)=%.12f deg" % (AD, AB, angle_ce_ad))
print("AE=%.15f DE=%.15f AE/DE=%.15f" % (AE, DE, AE / DE))
print("BE=%.15f AG=%.15f diff=%.3e" % (BE, AG, BE - AG))
print("CG=%.15f CE/2=%.15f  (G midpoint of CE)" % (CG, CE / 2.0))
print("F: |OF|=%.15f  F on BE (F between B,E); F between A and G" % norm(F))
print("answer: A,B,C,D all hold under BE=AG "
      "(A,B,D identically; C iff cos=3/5)")
