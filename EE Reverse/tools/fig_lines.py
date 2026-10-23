import sys
import numpy as np
from PIL import Image

def load(path):
    a = np.array(Image.open(path).convert('L'), dtype=np.uint8)
    ink = (a < 128).astype(np.uint8)
    return a, ink

def hough(ink, theta_steps=720, rho_step=2, min_votes=40):
    h, w = ink.shape
    ys, xs = np.nonzero(ink)
    diag = int(np.hypot(h, w))
    thetas = np.linspace(0, np.pi, theta_steps, endpoint=False)
    cos = np.cos(thetas); sin = np.sin(thetas)
    nrho = (2*diag)//rho_step + 1
    center = diag//rho_step
    acc = np.zeros((nrho, theta_steps), dtype=np.int32)
    rhos = np.outer(xs, cos) + np.outer(ys, sin)
    idx = (rhos/rho_step).astype(np.int32) + center
    np.add.at(acc, (idx, np.broadcast_to(np.arange(theta_steps), idx.shape)), 1)
    # find peaks (non-max suppression in rho)
    lines = []
    for t in range(theta_steps):
        col = acc[:, t]
        # local maxima
        for r in range(1, nrho-1):
            v = col[r]
            if v >= min_votes and v >= col[r-1] and v >= col[r+1]:
                lines.append((v, thetas[t], (r-center)*rho_step, r, t))
    # dedupe: sort by votes desc, drop near-duplicates
    lines.sort(reverse=True)
    kept = []
    for v, th, rho, r, t in lines:
        if any(abs(th-k[1]) < 0.03 and abs(rho-k[2]) < 6 for k in kept):
            continue
        kept.append((v, th, rho, r, t))
    return kept, h, w

def main(path):
    a, ink = load(path)
    h, w = ink.shape
    lines, H, W = hough(ink)
    print(f"size {W}x{H}, detected {len(lines)} lines (votes, theta_deg, rho):")
    for v, th, rho, r, t in lines[:40]:
        deg = th*180/np.pi
        # classify
        cls = 'H' if abs(deg)<1 or abs(deg-180)<1 else ('V' if abs(deg-90)<1 else 'D')
        print(f"  votes={v:4d}  theta={deg:7.2f}deg  rho={rho:7.1f}  class={cls}")

if __name__ == '__main__':
    main(sys.argv[1])
