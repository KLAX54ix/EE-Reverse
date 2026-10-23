#!/usr/bin/env python3
"""Q5 (九下期中选择压轴, 4 分): 四张边长互不相同的正方形纸片放入矩形 ABCD,
未被覆盖的部分（右上角、左下角两块阴影）用阴影表示.

Printed figure: captures/jxqz-figs/fig08.png  (A 左上, D 右上, B 左下, C 右下).

Stem constraints extracted from the wording
-------------------------------------------
* four SQUARES, pairwise DISTINCT side lengths, placed inside rectangle ABCD;
* adjacent pieces (papers AND the two shaded regions) share their boundaries:
  no overlap and no gap -> the four squares + the two shaded regions exactly
  tile the rectangle;
* shaded parts: one at the top-right corner, one at the bottom-left corner
  (in the printed figure the top-right one is L-shaped: a strip above square
  ③ merged with the strip right of ③; the bottom-left one is a rectangle).

Free parameters
---------------
The stem fixes no length: the whole figure is free up to scale, and the side
lengths may be chosen freely as long as the tiling closes.  We measure the
*printed* figure's pixel grid and use the ratios (they turn out to be integers,
so the closure is exact, not approximate).

Measured grid of fig08.png (ink runs, y down):
    rectangle x 6..133, y 14..107
    vertical divider x = 79        horizontal edges y = 87, 53, 20
    short verticals  x = 112 (y 20..53), x = 59 (y 87..107)
    grey fills: rows 15..19 x 80..132;  rows 20..52 x 113..132;
                rows 88..106 x 7..58
Converting to model units (y up, 1 px = 1 unit, origin B):
    a = ① side = 73   b = ② side = 54   c = ③ side = 33   d = ④ side = 20
    W = a + b = 127   H = a + d = 93    top strip e = H - b - c = 6
Closure identities (asserted below):
    W = a + b ,  H = a + d ,  H = b + c + e ,
    area(4 squares) + area(2 shaded) = W*H.

Derived invariant (the actual question)
---------------------------------------
perimeter(top-right shaded L) = 2H          (telescoping: H + (b+c+e))
perimeter(bottom-left shaded)  = 2a
l = 2H - 2a = 2(H - a) = 2d = 2 * side(④)
=> with l known,  perimeter(④) = 2·l  is known without measuring;
   answer: D (④).
"""
import json
import math
import os

# ---------------------------------------------------------------- measurement
# pixel boundaries of the printed figure (captures/jxqz-figs/fig08.png)
PIX = {"left": 6, "right": 133, "top": 14, "bottom": 107,
       "div": 79,          # vertical divider between ① column and ②/③ column
       "row_1": 87,        # ① bottom edge  (= ④ top edge, y-up 20)
       "row_2": 53,        # ② top edge / ③ bottom edge (y-up 54)
       "row_3": 20,        # ③ top edge (y-up 87)
       "col_3_right": 112,  # ③ right edge
       "col_4_left": 59}    # ④ left edge

a = PIX["div"] - PIX["left"]          # 73
b = PIX["right"] - PIX["div"]         # 54
c = PIX["col_3_right"] - PIX["div"]   # 33
d = PIX["bottom"] - PIX["row_1"]      # 20
e = PIX["row_3"] - PIX["top"]         # 6
Wt = PIX["right"] - PIX["left"]       # 127
Ht = PIX["bottom"] - PIX["top"]       # 93

# closure must be exact (integer geometry of the printed figure)
assert Wt == a + b, (Wt, a + b)
assert Ht == a + d, (Ht, a + d)
assert Ht == b + c + e, (Ht, b + c + e)
# the four squares must be pairwise distinct
assert len({a, b, c, d}) == 4, (a, b, c, d)
# exact tiling: area identity
area_sq = a * a + b * b + c * c + d * d
area_gray_top = b * e + (b - c) * c          # horizontal strip + vertical strip
area_gray_bot = (a - d) * d
assert area_sq + area_gray_top + area_gray_bot == Wt * Ht, (
    area_sq + area_gray_top + area_gray_bot, Wt * Ht)

# ------------------------------------------------------------- derived answer
# perimeter of the top-right L-shaped shaded region:
#   b (top) + (H-b) (right) + (b-c) (②top) + c (③right) + c (③top) + e (divider)
per_top = b + (Ht - b) + (b - c) + c + c + e
per_bot = 2 * (a - d) + 2 * d                     # bottom-left grey rectangle
assert per_top == 2 * Ht, (per_top, 2 * Ht)
assert per_bot == 2 * a, (per_bot, 2 * a)
ell = per_top - per_bot                            # the l of the problem
assert ell == 2 * d, (ell, 2 * d)                  # l = 2·side(④)
assert 4 * d == 2 * ell                            # perimeter(④) = 2l

# ------------------------------------------------------------------ points
A = (0.0, float(Ht))      # rectangle corners (y up, origin at B)
D = (float(Wt), float(Ht))
B = (0.0, 0.0)
C = (float(Wt), 0.0)

Q0 = (0.0, float(d))          # ① bottom-left      (on left edge)
Q1 = (float(a), float(d))     # ① bottom-right / ④ top-right
Q2 = (float(a), float(Ht))    # ① top-right        (on top edge, divider top)
Q3 = (float(a), 0.0)          # ② bottom-left / ④ bottom-right (on bottom edge)
Q4 = (float(Wt), float(b))    # ② top-right        (on right edge)
Q5 = (float(a), float(b))     # ② top-left / ③ bottom-left (divider)
Q6 = (float(a + c), float(b))       # ③ bottom-right
Q7 = (float(a + c), float(b + c))   # ③ top-right
Q8 = (float(a), float(b + c))       # ③ top-left (divider)
Q9 = (float(a - d), 0.0)            # ④ bottom-left (on bottom edge)
QA = (float(a - d), float(d))       # ④ top-left

# region centres for the circled-number labels
C1 = (a / 2.0, (Ht + d) / 2.0)                      # ① centre (36.5, 56.5)
C2 = ((a + Wt) / 2.0, b / 2.0)                      # ② centre (100, 27)
C3 = (a + c / 2.0, b + c / 2.0)                     # ③ centre (89.5, 70.5)
C4 = (a - d / 2.0, d / 2.0)                         # ④ centre (63, 10)

points = {"A": list(A), "B": list(B), "C": list(C), "D": list(D),
          "Q0": list(Q0), "Q1": list(Q1), "Q2": list(Q2), "Q3": list(Q3),
          "Q4": list(Q4), "Q5": list(Q5), "Q6": list(Q6), "Q7": list(Q7),
          "Q8": list(Q8), "Q9": list(Q9), "QA": list(QA),
          "C1": list(C1), "C2": list(C2), "C3": list(C3), "C4": list(C4)}

# ------------------------------------------------------------------ checks
TOL = 1e-9
PCT = 1e-6
checks = [
    # ---- rectangle ------------------------------------------------------
    {"type": "collinear", "label": "left edge B-Q0-A", "points": ["B", "Q0", "A"], "tol": TOL},
    {"type": "collinear", "label": "top edge A-Q2-D", "points": ["A", "Q2", "D"], "tol": TOL},
    {"type": "collinear", "label": "bottom B-Q9-Q3-C", "points": ["B", "Q9", "Q3", "C"], "tol": TOL},
    {"type": "collinear", "label": "right edge C-Q4-D", "points": ["C", "Q4", "D"], "tol": TOL},
    {"type": "collinear", "label": "divider Q3-Q1-Q5-Q8-Q2",
     "points": ["Q3", "Q1", "Q5", "Q8", "Q2"], "tol": TOL},
    # ---- square ① (A,Q2,Q1,Q0) ----------------------------------------
    {"type": "equal", "label": "① AQ2=Q2Q1", "a": ["A", "Q2"], "b": ["Q2", "Q1"], "tol_pct": PCT},
    {"type": "equal", "label": "① Q2Q1=Q1Q0", "a": ["Q2", "Q1"], "b": ["Q1", "Q0"], "tol_pct": PCT},
    {"type": "equal", "label": "① Q1Q0=Q0A", "a": ["Q1", "Q0"], "b": ["Q0", "A"], "tol_pct": PCT},
    {"type": "angle", "label": "① right angle at Q2", "vertex": "Q2",
     "a": "A", "b": "Q1", "deg": 90, "tol_deg": 1e-6},
    # ---- square ② (Q3,C,Q4,Q5) ----------------------------------------
    {"type": "equal", "label": "② Q3C=CQ4", "a": ["Q3", "C"], "b": ["C", "Q4"], "tol_pct": PCT},
    {"type": "equal", "label": "② CQ4=Q4Q5", "a": ["C", "Q4"], "b": ["Q4", "Q5"], "tol_pct": PCT},
    {"type": "equal", "label": "② Q4Q5=Q5Q3", "a": ["Q4", "Q5"], "b": ["Q5", "Q3"], "tol_pct": PCT},
    {"type": "angle", "label": "② right angle at C", "vertex": "C",
     "a": "Q3", "b": "Q4", "deg": 90, "tol_deg": 1e-6},
    # ---- square ③ (Q5,Q6,Q7,Q8) ---------------------------------------
    {"type": "equal", "label": "③ Q5Q6=Q6Q7", "a": ["Q5", "Q6"], "b": ["Q6", "Q7"], "tol_pct": PCT},
    {"type": "equal", "label": "③ Q6Q7=Q7Q8", "a": ["Q6", "Q7"], "b": ["Q7", "Q8"], "tol_pct": PCT},
    {"type": "equal", "label": "③ Q7Q8=Q8Q5", "a": ["Q7", "Q8"], "b": ["Q8", "Q5"], "tol_pct": PCT},
    {"type": "angle", "label": "③ right angle at Q7", "vertex": "Q7",
     "a": "Q6", "b": "Q8", "deg": 90, "tol_deg": 1e-6},
    # ---- square ④ (Q9,Q3,Q1,QA) ---------------------------------------
    {"type": "equal", "label": "④ Q9Q3=Q3Q1", "a": ["Q9", "Q3"], "b": ["Q3", "Q1"], "tol_pct": PCT},
    {"type": "equal", "label": "④ Q3Q1=Q1QA", "a": ["Q3", "Q1"], "b": ["Q1", "QA"], "tol_pct": PCT},
    {"type": "equal", "label": "④ Q1QA=QAQ9", "a": ["Q1", "QA"], "b": ["QA", "Q9"], "tol_pct": PCT},
    {"type": "angle", "label": "④ right angle at Q3", "vertex": "Q3",
     "a": "Q9", "b": "Q1", "deg": 90, "tol_deg": 1e-6},
    # ---- pieces flush: vertices on the rectangle boundary --------------
    {"type": "on_segment", "label": "Q2 on AD", "point": "Q2",
     "segment": ["A", "D"], "tol": TOL},
    {"type": "on_segment", "label": "Q0 on AB", "point": "Q0",
     "segment": ["A", "B"], "tol": TOL},
    {"type": "on_segment", "label": "Q9 on BC", "point": "Q9",
     "segment": ["B", "C"], "tol": TOL},
    {"type": "on_segment", "label": "Q3 on BC", "point": "Q3",
     "segment": ["B", "C"], "tol": TOL},
    {"type": "on_segment", "label": "Q4 on CD", "point": "Q4",
     "segment": ["C", "D"], "tol": TOL},
    # ---- pieces flush with each other ----------------------------------
    {"type": "collinear", "label": "① bottom line Q0-QA-Q1", "points": ["Q0", "QA", "Q1"], "tol": TOL},
    {"type": "on_segment", "label": "④ top QA on ① bottom",
     "point": "QA", "segment": ["Q0", "Q1"], "tol": TOL},
    {"type": "collinear", "label": "② top line Q5-Q6-Q4", "points": ["Q5", "Q6", "Q4"], "tol": TOL},
    {"type": "on_segment", "label": "③ bottom Q6 on ② top",
     "point": "Q6", "segment": ["Q5", "Q4"], "tol": TOL},
    # ---- closure identities expressed as distances ---------------------
    {"type": "distance", "label": "W = a+b = 127", "a": "A", "b": "D", "value": a + b, "tol_pct": PCT},
    {"type": "distance", "label": "H = a+d = 93", "a": "A", "b": "B", "value": a + d, "tol_pct": PCT},
    {"type": "distance", "label": "BC = W", "a": "B", "b": "C", "value": Wt, "tol_pct": PCT},
    {"type": "distance", "label": "CD = H", "a": "C", "b": "D", "value": Ht, "tol_pct": PCT},
    {"type": "distance", "label": "② side = b", "a": "C", "b": "Q4", "value": float(b), "tol_pct": PCT},
    {"type": "distance", "label": "right column above ② = c+e", "a": "Q4", "b": "D", "value": float(c + e), "tol_pct": PCT},
    {"type": "distance", "label": "① side = a (left column width)", "a": "B", "b": "Q3", "value": float(a), "tol_pct": PCT},
    {"type": "distance", "label": "① right edge = a", "a": "Q2", "b": "Q1", "value": float(a), "tol_pct": PCT},
    {"type": "distance", "label": "④ left strip = a-d", "a": "B", "b": "Q9", "value": float(a - d), "tol_pct": PCT},
]

# ------------------------------------------------------------------ drawing
fills = [
    # bottom-left shaded rectangle
    {"points": ["B", "Q9", "QA", "Q0"], "close": True, "fill": True},
    # top-right shaded L: top strip + strip right of ③
    {"points": ["Q2", "D", "Q4", "Q6", "Q7", "Q8"], "close": True, "fill": True},
]
lines = [
    {"points": ["A", "B"]},          # left edge
    {"points": ["B", "C"]},          # bottom edge
    {"points": ["C", "D"]},          # right edge
    {"points": ["D", "A"]},          # top edge
    {"points": ["Q2", "Q3"]},        # full divider
    {"points": ["Q0", "Q1"]},        # ① bottom edge (also ④ top-left part)
    {"points": ["Q8", "Q7"]},        # ③ top edge
    {"points": ["Q5", "Q4"]},        # ② top edge (also ③ bottom)
    {"points": ["Q6", "Q7"]},        # ③ right edge
    {"points": ["Q9", "QA"]},        # ④ left edge
]

labels = [
    # rectangle corners (A top-left, D top-right, B bottom-left, C bottom-right,
    # as printed): offsets outward, ~6-8% of the figure scale
    {"text": "A", "anchor": "A", "ox": -3.0, "oy": 7.0},
    {"text": "D", "anchor": "D", "ox": -3.0, "oy": 7.0},
    {"text": "B", "anchor": "B", "ox": -3.0, "oy": -7.0},
    {"text": "C", "anchor": "C", "ox": 3.0, "oy": -7.0},
    {"text": "\u2460", "anchor": "C1", "ox": 0.0, "oy": 0.0},   # ①
    {"text": "\u2461", "anchor": "C2", "ox": 0.0, "oy": 0.0},   # ②
    {"text": "\u2462", "anchor": "C3", "ox": 0.0, "oy": 0.0},   # ③
    {"text": "\u2463", "anchor": "C4", "ox": 0.0, "oy": 0.0},   # ④
]

spec = {
    "q": 5,
    "title": "四张互不相同的正方形无缝放入矩形ABCD, 右上/左下两块阴影; l=周长的差",
    "png": "captures/jxqz-figs/fig08.png",
    "unit_note": "1 model unit = 1 printed-figure pixel; W=127 H=93; "
                 "sides 1-4 = %d,%d,%d,%d (distinct)" % (a, b, c, d),
    "points": points,
    "checks": checks,
    "paths": fills + lines,
    "labels": labels,
    "dots": [],
}

os.makedirs("analysis/specs/nb", exist_ok=True)
out = "analysis/specs/nb/q05.model.json"
with open(out, "w", encoding="utf-8") as fh:
    json.dump(spec, fh, ensure_ascii=False, indent=1)

# ---------------------------------------------------------------- report
print("wrote", out)
print("measured: a=①%d  b=②%d  c=③%d  d=④%d  e(top strip)=%d" % (a, b, c, d, e))
print("rectangle W=%d H=%d   closure: W=a+b=%d  H=a+d=%d  H=b+c+e=%d"
      % (Wt, Ht, a + b, a + d, b + c + e))
print("tiling area: squares %d + top grey %d + bottom grey %d = %d = W*H %d"
      % (area_sq, area_gray_top, area_gray_bot,
         area_sq + area_gray_top + area_gray_bot, Wt * Ht))
print("shaded perimeters: top-right=%d (=2H=%d)  bottom-left=%d (=2a=%d)"
      % (per_top, 2 * Ht, per_bot, 2 * a))
print("l = %d = 2*side(④)=%d  ->  perimeter(④)=2l; answer D (④)"
      % (ell, 2 * d))
print("labels: ①②③④ at centres", [round(C1[0], 1), round(C2[0], 1),
                                    round(C3[0], 1), round(C4[0], 1)])
