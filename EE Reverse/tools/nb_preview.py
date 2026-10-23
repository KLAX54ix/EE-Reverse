#!/usr/bin/env python3
"""Render a CANVAS-UNIT spec (output of tools/nb_build.py) to a PNG so the
geometry can be eyeballed against the paper's original figure BEFORE it is
drawn into EduEditer.

usage: python tools/nb_preview.py analysis/specs/nb/q02.canvas.json out.png [crop]

crop: optional "x1,y1,x2,y2" in canvas units; defaults to the spec's own
canvas_box grown by a margin (labels/axis included).
"""
import json
import math
import sys

from PIL import Image, ImageDraw, ImageFont

CANVAS_W, CANVAS_H = 61340, 30670
S = 1.0 / 26.0          # canvas units -> preview pixels


def main(spec_path, out_path, crop=None):
    s = json.load(open(spec_path, encoding="utf-8"))
    if crop:
        x1, y1, x2, y2 = [float(v) for v in crop.split(",")]
    else:
        bx1, by1 = s["canvas_box"][0]
        bx2, by2 = s["canvas_box"][1]
        pts = [(bx1, by1), (bx2, by2)]
        for lb in s.get("labels", []):
            pts.append((lb["x"], lb["y"]))
        for c in s.get("circles", []):
            pts += [(c["cx"] - c["r"], c["cy"] - c["r"]),
                    (c["cx"] + c["r"], c["cy"] + c["r"])]
        for a in s.get("arcs", []):
            pts += a["points"]
        if s.get("axis"):
            r = s["axis"]["rect"]
            pts += [(r[0], r[1]), (r[2], r[3])]
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        mrg = 2600
        x1, x2 = min(xs) - mrg, max(xs) + mrg
        y1, y2 = min(ys) - mrg, max(ys) + mrg
    W = max(2, int((x2 - x1) * S))
    H = max(2, int((y2 - y1) * S))
    im = Image.new("L", (W, H), 255)
    d = ImageDraw.Draw(im)

    def T(x, y):
        return ((x - x1) * S, (y - y1) * S)

    def dashline(p1, p2, on=7, off=5, w=2):
        (ax, ay), (bx, by) = p1, p2
        L = math.hypot(bx - ax, by - ay)
        if L < 1:
            return
        ux, uy = (bx - ax) / L, (by - ay) / L
        k = 0
        while k * (on + off) < L:
            a = k * (on + off)
            b = min(a + on, L)
            d.line([(ax + ux * a, ay + uy * a), (ax + ux * b, ay + uy * b)],
                   fill=0, width=w)
            k += 1

    # axis first (light)
    if s.get("axis"):
        ax = s["axis"]
        r = ax["rect"]
        o = ax["origin"]
        p1, p2 = T(r[0], r[1]), T(r[2], r[3])
        # draw the two axis lines through the origin
        d.line([T(o[0], r[1]), T(o[0], r[3])], fill=0, width=2)
        d.line([T(r[0], o[1]), T(r[2], o[1])], fill=0, width=2)
        # arrows
        for (px, py, dx, dy) in [(o[0], r[1], 0, -1), (r[2], o[1], 1, 0)]:
            tip = T(px, py)
            d.polygon([tip, (tip[0] - 6 * dy - 3 * dx, tip[1] - 6 * abs(dx) + 3 * abs(dy)),
                       (tip[0] + 6 * dy + 3 * dx, tip[1] + 6 * abs(dx) - 3 * abs(dy))],
                      fill=0)
        fnt = _font(14)
        d.text(T(o[0] + 400, o[1] + 400), "O", fill=0, font=fnt)

    for p in s.get("paths", []):
        pts = [T(x, y) for x, y in p["points"]]
        if p.get("fill"):
            d.polygon(pts, fill=205 if p["fill"] != "dark" else 150)
        if p.get("dash"):
            for i in range(len(pts) - 1):
                dashline(pts[i], pts[i + 1])
        else:
            if p.get("close"):
                pts = pts + [pts[0]]
            d.line(pts, fill=0, width=2)
    for a in s.get("arcs", []):
        d.line([T(x, y) for x, y in a["points"]], fill=0, width=2)
    for cv in s.get("curves", []):
        d.line([T(x, y) for x, y in cv["points"]], fill=0, width=2)
    for c in s.get("circles", []):
        cx, cy = T(c["cx"], c["cy"])
        r = c["r"] * S
        d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=0, width=2)
    for dt in s.get("dots", []):
        x, y = T(dt[0], dt[1])
        d.ellipse([x - 3, y - 3, x + 3, y + 3], fill=0)
    for am in s.get("angle_marks", []):
        vx, vy = am["vertex"]
        ax, ay = am["point_a"]
        bx, by = am["point_b"]
        u1 = _unit(ax - vx, ay - vy)
        u2 = _unit(bx - vx, by - vy)
        r = am["size"]
        if am["kind"] == "right":
            p1 = (vx + u1[0] * r, vy + u1[1] * r)
            p3 = (vx + u2[0] * r, vy + u2[1] * r)
            p2 = (p1[0] + u2[0] * r, p1[1] + u2[1] * r)
            d.line([T(*p1), T(*p2), T(*p2), T(*p3)], fill=0, width=2)
        else:
            a0 = math.degrees(math.atan2(u1[1], u1[0]))
            a1 = math.degrees(math.atan2(u2[1], u2[0]))
            if a1 < a0:
                a0, a1 = a1, a0
            if a1 - a0 > 180:
                a0, a1 = a1, a0 + 360
            pts = [(vx + r * math.cos(math.radians(a0 + (a1 - a0) * k / 24)),
                    vy + r * math.sin(math.radians(a0 + (a1 - a0) * k / 24)))
                   for k in range(25)]
            d.line([T(*p) for p in pts], fill=0, width=2)

    fnt = _font(20)
    for lb in s.get("labels", []):
        x, y = T(lb["x"], lb["y"])
        txt = lb["text"] + (lb.get("sup") or "") + (lb.get("sub") or "")
        tw, th = d.textbbox((0, 0), txt, font=fnt)[2:]
        d.text((x - tw / 2, y - th / 2 - 2), txt, fill=0, font=fnt)

    im.save(out_path)
    print("saved", out_path, im.size, "box", [int(x1), int(y1), int(x2), int(y2)])


def _unit(dx, dy):
    L = math.hypot(dx, dy) or 1.0
    return (dx / L, dy / L)


def _font(size):
    for name in ("timesi.ttf", "times.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    return ImageFont.load_default()


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2],
         sys.argv[3] if len(sys.argv) > 3 else None)
