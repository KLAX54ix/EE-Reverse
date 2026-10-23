"""List ink runs per column so the traced curve can be separated from a text
label that sits in the same panel."""
import sys

import numpy as np
from PIL import Image


def main():
    path = sys.argv[1]
    x0, x1, y0, y1 = (int(v) for v in sys.argv[2:6])
    ink = np.asarray(Image.open(path).convert("L")) < 128
    sub = ink[y0:y1 + 1, x0:x1 + 1]
    h, w = sub.shape
    for c in range(w):
        col = np.where(sub[:, c])[0]
        if len(col) == 0:
            continue
        runs, start = [], col[0]
        prev = col[0]
        for y in col[1:]:
            if y != prev + 1:
                runs.append((int(start), int(prev)))
                start = y
            prev = y
        runs.append((int(start), int(prev)))
        runs = [(a + y0, b + y0) for a, b in runs]
        print("%4d %s" % (x0 + c, " ".join("%d-%d" % r for r in runs)))


if __name__ == "__main__":
    main()
