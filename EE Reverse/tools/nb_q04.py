#!/usr/bin/env python3
"""Q4 (九下期中 选择压轴): 半圆 O 半径 1, ∠AOC = 45°, D 是弧 BC 上一动点.

Stem (the text layer of the .wsd lost a couple of glyphs; the printed figure is
authoritative):  AB is the diameter of the semicircle with centre O, radius 1;
C is on the arc with ∠AOC = 45°; D is a moving point on arc BC;
AODC is the quadrilateral A-O-D-C (edges AO, OD, DC, CA).

Constraints extracted from the stem/figure
------------------------------------------
  * OA = OB = OC = OD = 1                       (radii; AB is a diameter)
  * A, O, B collinear, O = midpoint of AB       (semicircle)
  * ∠AOC = 45°  ->  with A at 180°, C sits at 135° on the unit circle
  * the drawn segments are AO (part of AB), OC, OD, DC, CA, plus the arc AB
  * no perpendicular relation is drawn in the problem figure (fig06); the
    perpendiculars CF⊥AB and OE⊥CD only belong to the ANSWER figure (fig07)
    and are therefore NOT reproduced.

Free parameter (only one)
-------------------------
  θ_D = 69.0°  -- where D sits on arc BC.  Measured from fig06:
      * OD radius-line fit ∩ circle  -> 68.5°
      * chord CD line fit ∩ circle   -> 69.8°
      * the two fitted lines' actual intersection -> 68.5°
    (the 173x100 px raster gives ±0.7°; nothing in the stem fixes D)

Model units: radius R = 1, y UP, O at the origin, AB horizontal.

Output: analysis/specs/nb/q04.model.json
"""
import json
import math
import os

R = 1.0                     # stem: 半径为 1
THETA_A = 180.0             # A at the left end of the diameter
THETA_C = 135.0             # ∠AOC = 45° measured from A's radius
THETA_D = 69.0              # FREE parameter: D on arc BC (measured from fig06)

A = (R * math.cos(math.radians(THETA_A)), R * math.sin(math.radians(THETA_A)))
B = (R * math.cos(0.0), R * math.sin(0.0))
C = (R * math.cos(math.radians(THETA_C)), R * math.sin(math.radians(THETA_C)))
D = (R * math.cos(math.radians(THETA_D)), R * math.sin(math.radians(THETA_D)))
O = (0.0, 0.0)


def dist(P, Q):
    return math.hypot(P[0] - Q[0], P[1] - Q[1])


# ---------------------------------------------------------------- self checks
assert abs(dist(A, O) - R) < 1e-15
assert abs(dist(B, O) - R) < 1e-15
assert abs(dist(C, O) - R) < 1e-15
assert abs(dist(D, O) - R) < 1e-15
assert abs(math.degrees(math.acos(
    ((A[0] - O[0]) * (C[0] - O[0]) + (A[1] - O[1]) * (C[1] - O[1]))
    / (dist(A, O) * dist(C, O)))) - 45.0) < 1e-12
# D is on arc BC: 0 < theta_D < 135
assert 0.0 < THETA_D < THETA_C
assert abs((A[0] + B[0]) / 2 - O[0]) < 1e-15
assert abs((A[1] + B[1]) / 2 - O[1]) < 1e-15

# ---------------------------------------------------------------- model spec
spec = {
    "q": 4,
    "title": "semicircle O (r=1), A(-1,0)/B(1,0) diameter, angle AOC=45, "
             "D on arc BC, quadrilateral AODC",
    "png": "captures/jxqz-figs/fig06.png",
    "unit": "radius of the circle = 1 (stem's unit)",
    "free_parameters": {
        "theta_D_deg": THETA_D,
        "source": "printed figure captures/jxqz-figs/fig06.png; "
                  "estimates 68.5 (OD line) / 69.8 (chord CD), adopted 69.0",
    },
    "points": {
        "O": [O[0], O[1]],
        "A": [A[0], A[1]],
        "B": [B[0], B[1]],
        "C": [C[0], C[1]],
        "D": [D[0], D[1]],
    },
    "checks": [
        {"type": "distance", "label": "OA = radius", "a": "O", "b": "A",
         "value": R, "tol_pct": 1e-6},
        {"type": "distance", "label": "OB = radius", "a": "O", "b": "B",
         "value": R, "tol_pct": 1e-6},
        {"type": "distance", "label": "OC = radius", "a": "O", "b": "C",
         "value": R, "tol_pct": 1e-6},
        {"type": "distance", "label": "OD = radius", "a": "O", "b": "D",
         "value": R, "tol_pct": 1e-6},
        {"type": "distance", "label": "AB = diameter = 2", "a": "A", "b": "B",
         "value": 2 * R, "tol_pct": 1e-6},
        {"type": "midpoint", "label": "O midpoint of AB", "point": "O",
         "a": "A", "b": "B", "tol": 1e-9},
        {"type": "collinear", "label": "A,O,B collinear", "points": ["A", "O", "B"],
         "tol": 1e-9},
        {"type": "angle", "label": "angle AOC = 45 (given)", "vertex": "O",
         "a": "A", "b": "C", "deg": 45.0, "tol_deg": 1e-6},
        {"type": "angle", "label": "D on arc BC: angle BOD = free parameter",
         "vertex": "O", "a": "B", "b": "D", "deg": THETA_D, "tol_deg": 1e-6},
        {"type": "angle", "label": "angle COD = 135 - free parameter",
         "vertex": "O", "a": "C", "b": "D",
         "deg": THETA_C - THETA_D, "tol_deg": 1e-6},
        {"type": "angle", "label": "quadrilateral AODC: angle AOD",
         "vertex": "O", "a": "A", "b": "D",
         "deg": 180.0 - THETA_D, "tol_deg": 1e-6},
    ],
    # quadrilateral AODC = A -> O -> D -> C -> A ; AO lies on the diameter AB
    "paths": [
        {"points": ["A", "B"]},      # diameter / side AO of the quadrilateral
        {"points": ["O", "C"]},      # radius OC
        {"points": ["O", "D"]},      # radius OD
        {"points": ["C", "D"]},      # chord DC
        {"points": ["C", "A"]},      # chord CA
    ],
    # semicircle from A (180 deg) over the top (90 deg) to B (0 deg)
    "arcs": [
        {"cx": 0.0, "cy": 0.0, "r": R, "a0": 180.0, "a1": 0.0, "steps": 128},
    ],
    "labels": [
        {"text": "A", "anchor": "A", "ox": -0.10, "oy": -0.09},
        {"text": "B", "anchor": "B", "ox": 0.09, "oy": -0.10},
        {"text": "O", "anchor": "O", "ox": 0.0, "oy": -0.13},
        {"text": "C", "anchor": "C", "ox": -0.11, "oy": 0.10},
        {"text": "D", "anchor": "D", "ox": 0.04, "oy": 0.15},
    ],
}

out = "analysis/specs/nb/q04.model.json"
os.makedirs(os.path.dirname(out), exist_ok=True)
with open(out, "w", encoding="utf-8") as fh:
    json.dump(spec, fh, ensure_ascii=False, indent=1)
print("wrote", out)
print("A=(%.6f,%.6f) B=(%.6f,%.6f) C=(%.6f,%.6f) D=(%.6f,%.6f)"
      % (A + B + C + D))
print("angles: AOC=45, BOD=%.3f, COD=%.3f, AOD=%.3f"
      % (THETA_D, THETA_C - THETA_D, 180.0 - THETA_D))
print("semicircle arc A->B via top, steps=128")
s_area = 0.5 * (R * R * math.sin(math.radians(180.0 - THETA_D)) +
                R * R * math.sin(math.radians(THETA_C - THETA_D)))
print("quadrilateral AODC area (for reference, not drawn) = %.6f" % s_area)
