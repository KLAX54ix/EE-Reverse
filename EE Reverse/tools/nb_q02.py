#!/usr/bin/env python3
"""Q2 (九下期中选择压轴): A(1,0), B(0,2); square ABCD in the first quadrant;
line CD meets the y-axis at G; square DEFG built on side DG; the hyperbola
y = k/x passes through E.

Everything is determined by the stem:
  AB = (-1,2) -> BC = rot90(AB) = (2,1)  => C = (2,3), D = (3,1)
  line C-D extended to x = 0              => G = (0,7)
  DG = G-D = (-3,6) -> DE = rot-90(DG) = (6,3) => E = (9,4), F = (6,10)
  k = x_E * y_E = 36, so the drawn hyperbola is y = 36/x.
"""
import json
import math
import os

A = (1.0, 0.0)
B = (0.0, 2.0)
C = (2.0, 3.0)
D = (3.0, 1.0)
G = (0.0, 7.0)
E = (9.0, 4.0)
F = (6.0, 10.0)
O = (0.0, 0.0)

# hyperbola y = 36 / x, the part the printed figure shows
K = 36.0
hyper = []
for i in range(81):
    x = 3.35 + (11.0 - 3.35) * i / 80.0
    hyper.append([x, K / x])

pts = {"A": list(A), "B": list(B), "C": list(C), "D": list(D), "G": list(G),
       "E": list(E), "F": list(F), "O": list(O)}

spec = {
    "q": 2,
    "title": "A(1,0), B(0,2), squares ABCD & DEFG, hyperbola y=36/x through E",
    "png": "captures/jxqz-figs/fig03.png",
    "points": pts,
    "checks": [
        {"type": "distance", "label": "AB=sqrt5", "a": "A", "b": "B",
         "value": math.sqrt(5), "tol_pct": 1e-9},
        {"type": "perpendicular", "label": "AB perp BC",
         "a": ["A", "B"], "b": ["B", "C"], "tol_deg": 1e-9},
        {"type": "equal", "label": "BC=AB", "a": ["B", "C"], "b": ["A", "B"],
         "tol_pct": 1e-9},
        {"type": "equal", "label": "CD=AB", "a": ["C", "D"], "b": ["A", "B"],
         "tol_pct": 1e-9},
        {"type": "equal", "label": "DA=AB", "a": ["D", "A"], "b": ["A", "B"],
         "tol_pct": 1e-9},
        {"type": "collinear", "label": "C,D,G collinear",
         "points": ["C", "D", "G"], "tol": 1e-9},
        {"type": "distance", "label": "G on y-axis (OG=7)", "a": "O", "b": "G",
         "value": 7.0, "tol_pct": 1e-9},
        {"type": "perpendicular", "label": "DG perp DE",
         "a": ["D", "G"], "b": ["D", "E"], "tol_deg": 1e-9},
        {"type": "equal", "label": "DE=DG", "a": ["D", "E"], "b": ["D", "G"],
         "tol_pct": 1e-9},
        {"type": "equal", "label": "EF=DG", "a": ["E", "F"], "b": ["D", "G"],
         "tol_pct": 1e-9},
        {"type": "equal", "label": "FG=DG", "a": ["F", "G"], "b": ["D", "G"],
         "tol_pct": 1e-9},
    ],
    "paths": [
        # square ABCD
        {"points": ["A", "B"]}, {"points": ["B", "C"]},
        {"points": ["C", "D"]}, {"points": ["D", "A"]},
        # square DEFG
        {"points": ["D", "E"]}, {"points": ["E", "F"]},
        {"points": ["F", "G"]}, {"points": ["G", "D"]},
    ],
    "polylines": [{"points": hyper}],
    "labels": [
        {"text": "A", "anchor": "A", "ox": 0.18, "oy": -0.55},
        {"text": "B", "anchor": "B", "ox": -0.62, "oy": -0.10},
        {"text": "C", "anchor": "C", "ox": -0.55, "oy": 0.30},
        {"text": "D", "anchor": "D", "ox": 0.35, "oy": -0.55},
        {"text": "G", "anchor": "G", "ox": -0.62, "oy": 0.10},
        {"text": "E", "anchor": "E", "ox": 0.28, "oy": -0.60},
        {"text": "F", "anchor": "F", "ox": -0.10, "oy": 0.62},
    ],
    "axis": {"rect": [-0.85, -0.85, 11.35, 11.9], "origin": [0.0, 0.0]},
}

os.makedirs("analysis/specs/nb", exist_ok=True)
out = "analysis/specs/nb/q02.model.json"
json.dump(spec, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("wrote", out)
