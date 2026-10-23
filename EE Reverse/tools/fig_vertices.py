import sys
import numpy as np
from PIL import Image

def load(path):
    a = np.array(Image.open(path).convert('L'), dtype=np.uint8)
    return (a < 128).astype(np.uint8)

def junctions(ink, rad=14, need=3):
    h, w = ink.shape
    # 16 directions
    angs = np.linspace(0, 2*np.pi, 16, endpoint=False)
    dirs = [(int(round(rad*np.cos(a))), int(round(rad*np.sin(a)))) for a in angs]
    ys, xs = np.nonzero(ink)
    pts = []
    for x, y in zip(xs, ys):
        cnt = 0
        for dx, dy in dirs:
            # sample along the ray
            hit = 0
            for t in range(rad//2, rad+1):
                px = x + int(round(dx*t/rad)); py = y + int(round(dy*t/rad))
                if 0 <= px < w and 0 <= py < h and ink[py, px]:
                    hit = 1; break
            cnt += hit
        if cnt >= need:
            pts.append((x, y, cnt))
    return pts

def cluster(pts, r=12):
    used = [False]*len(pts)
    clusters = []
    for i in range(len(pts)):
        if used[i]: continue
        stack = [i]; used[i] = True; comp = [i]
        while stack:
            k = stack.pop()
            x0, y0, _ = pts[k]
            for j in range(len(pts)):
                if used[j]: continue
                x1, y1, _ = pts[j]
                if (x0-x1)**2 + (y0-y1)**2 <= r*r:
                    used[j] = True; stack.append(j); comp.append(j)
        cx = int(np.mean([pts[k][0] for k in comp]))
        cy = int(np.mean([pts[k][1] for k in comp]))
        mx = max(pts[k][2] for k in comp)
        clusters.append((cx, cy, len(comp), mx))
    clusters.sort(key=lambda c: -c[2])
    return clusters

def main(path):
    ink = load(path)
    pts = junctions(ink)
    cl = cluster(pts)
    print(f"{path}: {len(pts)} junction px -> {len(cl)} clusters (x, y, size, maxdirs)")
    for c in cl[:25]:
        print(f"  ({c[0]:4d},{c[1]:4d})  n={c[2]:4d}  dirs={c[3]}")

if __name__ == '__main__':
    main(sys.argv[1])
