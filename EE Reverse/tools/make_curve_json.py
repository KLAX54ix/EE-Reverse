"""Write a fitted bezier control polygon (canvas coords) for a demo function.

Usage: python tools/make_curve_json.py <out.json> <expr> <x0> <x1> <ox> <oy> <scale> [tol]
Only the small demo subset of syntax is supported (+, -, *, /, **, math funcs).
"""
import json
import math
import sys

sys.path.insert(0, r"D:\EE Reverse\tools")
from bezier_fit import fit_bezier  # noqa: E402

SAFE = {
    "sin": math.sin, "cos": math.cos, "tan": math.tan, "asin": math.asin,
    "acos": math.acos, "atan": math.atan, "sqrt": math.sqrt, "abs": abs,
    "log": math.log, "exp": math.exp, "pi": math.pi, "e": math.e,
}


def f(x, expr):
    return float(eval(expr, {"__builtins__": {}}, dict(SAFE, x=x)))


def main():
    out_path, expr = sys.argv[1], sys.argv[2]
    x0, x1 = float(sys.argv[3]), float(sys.argv[4])
    ox, oy = float(sys.argv[5]), float(sys.argv[6])
    sc = float(sys.argv[7])
    tol = float(sys.argv[8]) if len(sys.argv) > 8 else 1.2
    # dense adaptive sampling in canvas space (so the fitter sees the true shape)
    pts = []
    max_pts = 20000
    x = x0
    span = x1 - x0
    while x < x1 and len(pts) < max_pts:
        y = f(x, expr)
        if not (math.isfinite(y)):
            break
        pts.append((ox + x * sc, oy - y * sc))
        d = (f(x + 1e-6, expr) - f(x, expr)) / 1e-6
        grad = sc * math.hypot(1.0, d)
        step = 8.0 / max(1e-9, grad)
        x = min(x1, x + max(step, span * 1e-9))
    pts.append((ox + x1 * sc, oy - f(x1, expr) * sc))
    ctrl = fit_bezier(pts, tol=tol)
    data = {
        "expr": expr,
        "samples": len(pts),
        "segments": (len(ctrl) - 1) // 3,
        "ctrl": [[int(round(x)), int(round(y))] for x, y in ctrl],
    }
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(data, fh)
    print("samples=%d segments=%d ctrl=%d -> %s"
          % (data["samples"], data["segments"], len(data["ctrl"]), out_path))


if __name__ == "__main__":
    main()
