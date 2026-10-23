"""Render a figure spec (same JSON the ee_draw_figure tool takes) as a PNG
side by side with the original textbook figure, for visual diffing.

usage: fig_render.py spec.json out.png
spec.json:
{
  "png":   "D:/EE Reverse/captures/mock-figs/fig01.png",
  "scale": 65,            # canvas units per source pixel
  "ox": 22155, "oy": 1587,# canvas coords of source pixel (0,0)
  "paths": [{"points": [[x,y],...], "close": bool, "dash": bool, "fill": bool}],
  "arcs":  [{"cx":..,"cy":..,"r":..,"a0":..,"a1":..,"steps":..}],
  "labels":[{"text":"A","x":..,"y":..}]
}
"""
import json
import math
import sys
from PIL import Image, ImageDraw, ImageFont

def main(spec_path, out_path):
    s = json.load(open(spec_path, encoding='utf-8'))
    orig = Image.open(s['png']).convert('L')
    W, H = orig.size
    sc, ox, oy = float(s['scale']), float(s['ox']), float(s['oy'])
    def M(x, y):
        return ((x - ox) / sc, (y - oy) / sc)
    im = Image.new('L', (W, H), 255)
    d = ImageDraw.Draw(im)

    def dashline(p1, p2, on=14, off=9, w=2):
        x1, y1 = p1; x2, y2 = p2
        L = math.hypot(x2-x1, y2-y1)
        if L < 1: return
        ux, uy = (x2-x1)/L, (y2-y1)/L
        k = 0
        while k*(on+off) < L:
            a = k*(on+off); b = min(a+on, L)
            d.line([(x1+ux*a, y1+uy*a), (x1+ux*b, y1+uy*b)], fill=0, width=w)
            k += 1

    for p in s.get('paths', []):
        pts = [M(x, y) for x, y in p['points']]
        if p.get('dash'):
            for i in range(len(pts)-1):
                dashline(pts[i], pts[i+1])
        else:
            if p.get('close'):
                pts = pts + [pts[0]]
            d.line(pts, fill=0, width=2)
            if p.get('fill'):
                d.polygon(pts[:-1] if p.get('close') else pts, fill=0)
    for a in s.get('arcs', []):
        cx, cy, r = float(a['cx']), float(a['cy']), float(a['r'])
        a0, a1 = float(a['a0']), float(a['a1'])
        n = int(a.get('steps', 64))
        pts = []
        for k in range(n+1):
            t = math.radians(a0 + (a1-a0)*k/n)
            pts.append(M(cx + r*math.cos(t), cy + r*math.sin(t)))
        d.line(pts, fill=0, width=2)
    try:
        font = ImageFont.truetype("timesi.ttf", 20)
    except Exception:
        try: font = ImageFont.truetype("times.ttf", 20)
        except Exception: font = ImageFont.load_default()
    for lb in s.get('labels', []):
        x, y = M(lb['x'], lb['y'])
        d.text((x, y-10), lb['text'], fill=0, font=font)

    combo = Image.new('L', (W*2+20, H), 255)
    combo.paste(orig, (0, 0))
    combo.paste(im, (W+20, 0))
    combo.save(out_path)
    print("saved", out_path, combo.size)

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
