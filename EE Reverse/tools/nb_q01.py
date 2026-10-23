#!/usr/bin/env python3
"""Q1 (九下期中选择压轴): line y = -3/4 x + 3 meets the axes at A(0,3), B(4,0);
P is on segment OB, C is on AB with angle OCP = 90 deg.  Draw the boundary case
(the printed figure uses the tangent position m = 3: the circle with diameter OP
touches AB, so C = (2.4, 1.2) and the right angle is exact).

Constraints (stem): A(0,3), B(4,0) i.e. 3x+4y=12; P=(m,0) on OB;
(O-C).(P-C) = 0; C on AB.  Free: the printed figure's m = 3 (tangency), which
also fixes C = (2.4, 1.2).
"""
import json
import os

A = (0.0, 3.0)
B = (4.0, 0.0)
O = (0.0, 0.0)
P = (3.0, 0.0)
C = (2.4, 1.2)          # AB tangent point of circle diameter OP

# the printed figure draws the whole line a little past A and B
L1 = (-0.55, 3.4125)
L2 = (4.55, -0.4125)

pts = {"A": list(A), "B": list(B), "O": list(O), "P": list(P), "C": list(C),
       "L1": list(L1), "L2": list(L2)}

spec = {
    "q": 1,
    "title": "y=-3/4x+3, A on y-axis, B on x-axis, P on OB, angle OCP=90 (m=3)",
    "png": "captures/jxqz-figs/fig01.png",
    "points": pts,
    "checks": [
        {"type": "distance", "label": "OA=3", "a": "O", "b": "A", "value": 3.0,
         "tol_pct": 1e-6},
        {"type": "distance", "label": "OB=4", "a": "O", "b": "B", "value": 4.0,
         "tol_pct": 1e-6},
        {"type": "perpendicular", "label": "OA perp OB",
         "a": ["O", "A"], "b": ["O", "B"], "tol_deg": 1e-6},
        {"type": "collinear", "label": "A,C,B on the line",
         "points": ["A", "C", "B"], "tol": 1e-6},
        {"type": "angle", "label": "angle OCP=90", "vertex": "C",
         "a": "O", "b": "P", "deg": 90, "tol_deg": 1e-6},
        {"type": "on_segment", "label": "P on OB", "point": "P",
         "segment": ["O", "B"], "tol": 1e-6},
        {"type": "on_segment", "label": "C on AB", "point": "C",
         "segment": ["A", "B"], "tol": 1e-6},
    ],
    "paths": [
        {"points": ["L1", "L2"]},          # the whole line, extends past A and B
        {"points": ["O", "C"]},
        {"points": ["C", "P"]},
    ],
    "labels": [
        {"text": "A", "anchor": "A", "ox": -0.34, "oy": 0.10},
        {"text": "B", "anchor": "B", "ox": 0.12, "oy": -0.30},
        {"text": "C", "anchor": "C", "ox": 0.30, "oy": 0.24},
        {"text": "P", "anchor": "P", "ox": -0.16, "oy": -0.32},
    ],
    "axis": {"rect": [-0.85, -0.75, 5.25, 4.05], "origin": [0.0, 0.0]},
}

os.makedirs("analysis/specs/nb", exist_ok=True)
out = "analysis/specs/nb/q01.model.json"
json.dump(spec, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("wrote", out)
