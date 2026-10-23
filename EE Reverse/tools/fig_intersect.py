import sys
import numpy as np
from PIL import Image

def load(path):
    a = np.array(Image.open(path).convert('L'), dtype=np.uint8)
    return (a < 128).astype(np.uint8)

def hough(ink, theta_steps=1440, rho_step=1, min_votes=120, nms_t=0.02, nms_r=8):
    h, w = ink.shape
    ys, xs = np.nonzero(ink)
    diag = int(np.hypot(h, w))
    thetas = np.linspace(0, np.pi, theta_steps, endpoint=False)
    cos = np.cos(thetas); sin = np.sin(thetas)
    center = diag // rho_step
    nrho = 2*center + 1
    acc = np.zeros((nrho, theta_steps), dtype=np.int32)
    rhos = np.outer(xs, cos) + np.outer(ys, sin)
    idx = (rhos/rho_step).astype(np.int32) + center
    np.add.at(acc, (idx, np.broadcast_to(np.arange(theta_steps), idx.shape)), 1)
    cands = []
    for t in range(theta_steps):
        col = acc[:, t]
        for r in range(1, nrho-1):
            v = col[r]
            if v >= min_votes and v >= col[r-1] and v >= col[r+1] and v >= col[r+2]:
                cands.append((int(v), float(thetas[t]), float((r-center)*rho_step)))
    cands.sort(reverse=True)
    kept = []
    for v, th, rho in cands:
        if any(abs(th-k[1]) < nms_t and abs(rho-k[2]) < nms_r for k in kept):
            continue
        kept.append((v, th, rho))
    return kept

def intersect(l1, l2):
    v1, t1, r1 = l1; v2, t2, r2 = l2
    c1, s1 = np.cos(t1), np.sin(t1)
    c2, s2 = np.cos(t2), np.sin(t2)
    det = c1*s2 - c2*s1
    if abs(det) < 1e-6: return None
    x = (r1*s2 - r2*s1)/det
    y = (c1*r2 - c2*r1)/det
    return float(x), float(y)

def main(path, maxlines=18):
    ink = load(path)
    h, w = ink.shape
    lines = hough(ink)
    print(f"{w}x{h}: {len(lines)} lines after NMS; top {maxlines}:")
    for v, th, rho in lines[:maxlines]:
        print(f"  votes={v:4d} theta={np.degrees(th):7.2f} rho={rho:7.1f}")
    print("\nintersections near ink (clustered):")
    pts = []
    for i in range(min(maxlines, len(lines))):
        for j in range(i+1, min(maxlines, len(lines))):
            p = intersect(lines[i], lines[j])
            if p is None: continue
            x, y = p
            if not (0 <= x < w and 0 <= y < h): continue
            xi, yi = int(round(x)), int(round(y))
            r = 4
            x0, x1 = max(0, xi-r), min(w, xi+r+1)
            y0, y1 = max(0, yi-r), min(h, yi+r+1)
            if ink[y0:y1, x0:x1].sum() >= 3:
                pts.append((round(x,1), round(y,1)))
    # cluster
    used = [False]*len(pts); out = []
    for i in range(len(pts)):
        if used[i]: continue
        stack=[i]; used[i]=True; comp=[i]
        while stack:
            k=stack.pop()
            for j in range(len(pts)):
                if used[j]: continue
                if (pts[k][0]-pts[j][0])**2 + (pts[k][1]-pts[j][1])**2 <= 15*15:
                    used[j]=True; stack.append(j); comp.append(j)
        cx = np.mean([pts[k][0] for k in comp]); cy = np.mean([pts[k][1] for k in comp])
        out.append((round(cx,1), round(cy,1), len(comp)))
    out.sort(key=lambda c:-c[2])
    for c in out[:20]:
        print(f"  ({c[0]:7.1f},{c[1]:7.1f})  n={c[2]}")

if __name__ == '__main__':
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv)>2 else 18)
