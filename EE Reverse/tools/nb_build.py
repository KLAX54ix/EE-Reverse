#!/usr/bin/env python3
"""Build a CANVAS-UNIT ee_draw_figure spec (plus axis/extra ops) from a
MODEL-UNIT constrained figure spec.

The model spec is what a solver writes: pure mathematics, y UP, arbitrary
units, every dependent point derived from the problem's constraints.  This
script does only the boring part -- a similarity placement into the EE canvas
(1 unit = 1/400 mm) so that every figure lands at a consistent size/position.

usage:  python tools/nb_build.py analysis/specs/nb/q02.model.json [out.canvas.json]

model spec format
-----------------
{
  "q": 2,
  "png": "captures/nb-curated-figs/fig03.png",   # optional, for preview/review
  "points": {"A":[x,y], ...},                    # MODEL units, y UP
  "checks": [ ...tools/check_spec.py format... ], # run this FIRST
  "paths":  [{"points":["A","B"], "dash":false, "fill":false|"dark"}],
  "polylines": [{"points":[[x,y],[x,y],...], "dash":false, "fill":false}],
  "arcs":   [{"cx":..,"cy":..,"r":..,"a0":deg,"a1":deg, "steps":48}],
  "curves": [{"sx":..,"sy":..,"ox":..,"oy":..,"cx":..,"cy":..,"h":..,"x0":..,"x1":..,"steps":60}],
  "circles":[{"center":"A","through":"D"}]  or {"cx":..,"cy":..,"r":..},
  "labels": [{"text":"A","anchor":"A","ox":dx,"oy":dy}],   # offset MODEL units
  "dots":   ["O"],
  "angle_marks": [{"kind":"arc"|"right"|"double","vertex":"F","a":"D","b":"E",
                   "size":0.25}],                          # size MODEL units
  "axis":   {"rect":[x1,y1,x2,y2], "origin":[ox,oy]}       # MODEL units
}

output (canvas spec) is exactly what tools/nb_preview.py renders and what the
ee_* draw calls consume: all coordinates in canvas units, y DOWN.
"""
import json
import math
import sys

CANVAS_W = 61340
CANVAS_H = 30670
CX = 30670.0          # canvas centre -- every figure bbox is centred here
CY = 15335.0
MAX_W = 34000.0       # fit box for the drawing itself (labels may stick out)
MAX_H = 23500.0


def bbox(points_dict, names):
    xs = [points_dict[n][0] for n in names]
    ys = [points_dict[n][1] for n in names]
    return min(xs), min(ys), max(xs), max(ys)


def main(model_path, out_path=None):
    m = json.load(open(model_path, encoding="utf-8"))
    pts = {k: (float(v[0]), float(v[1])) for k, v in m["points"].items()}

    # ---- which points define the drawing extent (labels excluded) ----------
    used = set()
    for p in m.get("paths", []):
        used.update(p["points"])
    for a in m.get("angle_marks", []):
        used.update([a["vertex"], a["a"], a["b"]])
    for c in m.get("circles", []):
        if "center" in c:
            used.add(c["center"])
        if "through" in c:
            used.add(c["through"])
    for dname in m.get("dots", []):
        used.add(dname)
    for lb in m.get("labels", []):
        used.add(lb["anchor"])
    if not used:
        used = set(pts)
    x1, y1, x2, y2 = bbox(pts, sorted(used))
    # circles can extend past the point bbox
    for c in m.get("circles", []):
        if "center" in c and "through" in c:
            c0, t0 = pts[c["center"]], pts[c["through"]]
            r = math.hypot(t0[0] - c0[0], t0[1] - c0[1])
            x1, x2 = min(x1, c0[0] - r), max(x2, c0[0] + r)
            y1, y2 = min(y1, c0[1] - r), max(y2, c0[1] + r)
        elif "cx" in c:
            x1, x2 = min(x1, c["cx"] - c["r"]), max(x2, c["cx"] + c["r"])
            y1, y2 = min(y1, c["cy"] - c["r"]), max(y2, c["cy"] + c["r"])
    w, h = max(x2 - x1, 1e-9), max(y2 - y1, 1e-9)
    # polylines participate in the extent too
    for pl in m.get("polylines", []):
        for p in pl["points"]:
            x1, x2 = min(x1, p[0]), max(x2, p[0])
            y1, y2 = min(y1, p[1]), max(y2, p[1])
    # ... and so does the axis frame (its content rectangle IS the drawing box)
    if m.get("axis"):
        ax = m["axis"]
        r = ax["rect"]
        x1, x2 = min(x1, r[0], r[2]), max(x2, r[0], r[2])
        y1, y2 = min(y1, r[1], r[3]), max(y2, r[1], r[3])
    w, h = max(x2 - x1, 1e-9), max(y2 - y1, 1e-9)
    scale = min(MAX_W / w, MAX_H / h)
    mx, my = (x1 + x2) / 2.0, (y1 + y2) / 2.0

    def M(p):
        """model (y up) -> canvas (y down)."""
        return [int(round(CX + (p[0] - mx) * scale)),
                int(round(CY - (p[1] - my) * scale))]

    def MV(v):
        """model VECTOR (y up) -> canvas vector (y down), unscaled rounding."""
        return [v[0] * scale, -v[1] * scale]

    out = {
        "q": m.get("q"), "title": m.get("title"),
        "png": m.get("png"),
        "scale": scale,
        "model_bbox": [x1, y1, x2, y2],
        "canvas_box": [M((x1, y1)), M((x2, y2))],
        "pen_mm": 0.25,
        "paths": [], "arcs": [], "curves": [], "labels": [], "dots": [],
        "angle_marks": [], "circles": [], "axis": None,
    }

    # ---- explicit model-coordinate polylines (hyperbolas, free curves) -----
    for pl in m.get("polylines", []):
        pp = {"points": [M(p) for p in pl["points"]]}
        if pl.get("dash"):
            pp["dash"] = True
        if pl.get("fill"):
            pp["fill"] = pl["fill"]
        if pl.get("close"):
            pp["close"] = True
        else:
            pp["close"] = False      # never let ee_draw_figure auto-close a curve
        out["paths"].append(pp)

    # ---- straight paths ----------------------------------------------------
    for p in m.get("paths", []):
        pp = {"points": [M(pts[n]) for n in p["points"]]}
        # explicit: ee_draw_figure defaults to CLOSED for >2 points, which
        # silently appended chords to open polylines (2026-10-19 defect).
        pp["close"] = bool(p.get("close", False))
        if p.get("dash"):
            pp["dash"] = True
        if p.get("fill"):
            pp["fill"] = p["fill"]
        out["paths"].append(pp)

    # ---- sampled arcs (already exact polylines after sampling) -------------
    # NOTE: an entry with >2 points defaults to CLOSED inside ee_draw_figure,
    # which appends a chord from the last sample back to the first.  Every
    # sampled curve here is an OPEN polyline, so close must be explicit False.
    for a in m.get("arcs", []):
        n = int(a.get("steps", 48))
        a0, a1 = float(a["a0"]), float(a["a1"])
        pts_c = []
        for k in range(n + 1):
            t = math.radians(a0 + (a1 - a0) * k / n)
            pts_c.append(M((a["cx"] + a["r"] * math.cos(t),
                            a["cy"] + a["r"] * math.sin(t))))
        out["arcs"].append({"points": pts_c, "n": n, "close": False})

    # ---- parabolas (quadratic sampler), model units -----------------------
    for cv in m.get("curves", []):
        n = int(cv.get("steps", 60))
        x0, x1 = float(cv["x0"]), float(cv["x1"])
        pts_c = []
        for k in range(n + 1):
            x = x0 + (x1 - x0) * k / n
            y = float(cv.get("h", 1.0)) * (x - float(cv.get("cx", 0.0))) ** 2 \
                + float(cv.get("cy", 0.0))
            pts_c.append(M((x, y)))
        out["curves"].append({"points": pts_c, "n": n, "close": False})

    # ---- circles (native ee_draw_circle) -----------------------------------
    for c in m.get("circles", []):
        if "center" in c:
            c0 = pts[c["center"]]
            t0 = pts[c["through"]]
            r = math.hypot(t0[0] - c0[0], t0[1] - c0[1])
            cxy = c0
        else:
            cxy = (c["cx"], c["cy"])
            r = c["r"]
        cc = M(cxy)
        out["circles"].append({"cx": cc[0], "cy": cc[1],
                               "r": int(round(r * scale))})

    # ---- labels (anchor = CENTRE of the text box) --------------------------
    for lb in m.get("labels", []):
        a = pts[lb["anchor"]]
        pos = M((a[0] + float(lb.get("ox", 0)), a[1] + float(lb.get("oy", 0))))
        rec = {"text": lb["text"], "x": pos[0], "y": pos[1]}
        if lb.get("sup"):
            rec["sup"] = lb["sup"]
        if lb.get("sub"):
            rec["sub"] = lb["sub"]
        if lb.get("font_index") is not None:
            rec["font_index"] = lb["font_index"]
        out["labels"].append(rec)

    # ---- bold dots ---------------------------------------------------------
    for dn in m.get("dots", []):
        out["dots"].append(M(pts[dn]))

    # ---- native angle / right-angle marks ---------------------------------
    for a in m.get("angle_marks", []):
        v = M(pts[a["vertex"]])
        pa = M(pts[a["a"]])
        pb = M(pts[a["b"]])
        out["angle_marks"].append({
            "kind": a.get("kind", "arc"), "vertex": v,
            "point_a": pa, "point_b": pb,
            "size": int(round(float(a.get("size", 1.0)) * scale)),
        })

    # ---- native coordinate axis (ee_draw_axis) ----------------------------
    if m.get("axis"):
        ax = m["axis"]
        r = ax["rect"]
        p1, p2 = M((r[0], r[1])), M((r[2], r[3]))
        out["axis"] = {
            "rect": [min(p1[0], p2[0]), min(p1[1], p2[1]),
                     max(p1[0], p2[0]), max(p1[1], p2[1])],
            "origin": M(ax["origin"]),
            "visible_x": ax.get("visible_x", 1),
            "visible_y": ax.get("visible_y", 1),
        }

    if out_path:
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
        print("saved", out_path,
              "scale=%.2f paths=%d labels=%d circles=%d" %
              (scale, len(out["paths"]), len(out["labels"]),
               len(out["circles"])))
    else:
        print(json.dumps(out, ensure_ascii=False))
    return out


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
