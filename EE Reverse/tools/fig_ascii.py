import sys
import numpy as np
from PIL import Image

def load(path):
    im = Image.open(path).convert('L')
    a = np.array(im, dtype=np.uint8)
    ink = (a < 128).astype(np.float32)
    return a, ink

def block_art(ink, cols=150, frac=0.25):
    h, w = ink.shape
    rows = max(1, int(cols * h / w / 2.0))
    # block-sum
    bw = w // cols
    bh = h // rows
    art = np.zeros((rows, cols), dtype=np.float32)
    for r in range(rows):
        for c in range(cols):
            art[r, c] = ink[r*bh:(r+1)*bh, c*bw:(c+1)*bw].mean()
    lines = []
    for r in range(rows):
        line = ''.join('#' if art[r,c] > frac else ('.' if art[r,c] < 0.05 else '+') for c in range(cols))
        lines.append(line)
    return lines, rows, cols

def axes(ink):
    h, w = ink.shape
    rowsum = ink.sum(axis=1)
    colsum = ink.sum(axis=0)
    # axis = row/col with a long contiguous run; approximate by max sum within middle band
    return rowsum, colsum

def main(path, cols=150, frac=0.20):
    a, ink = load(path)
    h, w = a.shape
    print(f"size: {w}x{h}  ink={ink.mean():.4f}")
    rowsum, colsum = axes(ink)
    # top 5 rows by ink
    top_rows = np.argsort(rowsum)[::-1][:6]
    top_cols = np.argsort(colsum)[::-1][:6]
    print("top rows (y, ink):", [(int(r), int(rowsum[r])) for r in top_rows])
    print("top cols (x, ink):", [(int(c), int(colsum[c])) for c in top_cols])
    lines, rows, cols = block_art(ink, cols, frac)
    print(f"ascii {cols}x{rows} (1 cell ~ {w//cols}x{h//rows}px), '#'=line '+'=faint")
    for i, ln in enumerate(lines):
        print(f"{i*h//rows:4d} {ln}")

if __name__ == '__main__':
    path = sys.argv[1]
    cols = int(sys.argv[2]) if len(sys.argv) > 2 else 150
    frac = float(sys.argv[3]) if len(sys.argv) > 3 else 0.20
    main(path, cols, frac)
