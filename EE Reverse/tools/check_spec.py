#!/usr/bin/env python3
"""Numerical constraint checker for an EE figure spec.

This is the executable half of the project's "construct from constraints, not
pixels" rule.  Describe the points you intend to draw and the constraints the
problem statement forces; the script prints the residuals and exits non-zero if
any check fails.  Run it BEFORE calling ee_draw_figure.

Spec format (JSON)
------------------
{
  "name": "2025-zhenhai-q2",
  "points": {"A": [x, y], "B": [x, y], ...},     # canvas units, 1 unit = 1/400 mm
  "checks": [
    {"type": "equal",        "a": ["A","B"], "b": ["B","C"], "tol_pct": 0.01},
    {"type": "angle",        "vertex": "F", "a": "D", "b": "E",
                             "deg": 60, "tol_deg": 0.01},
    {"type": "collinear",    "points": ["A","D","B"], "tol": 1.0},
    {"type": "on_segment",   "point": "D", "segment": ["A","B"], "tol": 1.0},
    {"type": "midpoint",     "point": "F", "a": "A", "b": "C", "tol": 1.0},
    {"type": "distance",     "a": "A", "b": "B", "value": 100, "tol_pct": 0.01},
    {"type": "parallel",     "a": ["A","B"], "b": ["C","D"], "tol_deg": 0.01},
    {"type": "perpendicular","a": ["A","B"], "b": ["A","C"], "tol_deg": 0.01},
    {"type": "point_eq",     "a": "A", "b": "B", "tol": 0.01}
  ]
}

Exit codes: 0 = all checks pass, 1 = at least one failure, 2 = bad input.

Usage:
  python tools/check_spec.py my-figure.json
  python tools/check_spec.py my-figure.json --json
"""
import argparse
import json
import math
import sys

DEFAULT_TOL = 1.0          # canvas units
DEFAULT_TOL_PCT = 0.01     # percent
DEFAULT_TOL_DEG = 0.01


class SpecError(Exception):
    pass


def _pt(points, name):
    if name not in points:
        raise SpecError("unknown point %r" % (name,))
    p = points[name]
    if isinstance(p, dict):
        return float(p["x"]), float(p["y"])
    if isinstance(p, (list, tuple)) and len(p) >= 2:
        return float(p[0]), float(p[1])
    raise SpecError("point %r is not [x, y]: %r" % (name, p))


def _seg(points, spec, key="segment"):
    """Accept ["A","B"] or {"a":"A","b":"B"}."""
    if isinstance(spec, dict):
        a, b = spec.get("a"), spec.get("b")
    else:
        if not isinstance(spec, (list, tuple)) or len(spec) != 2:
            raise SpecError("%s must be [A,B] or {a,b}: %r" % (key, spec))
        a, b = spec
    return _pt(points, a), _pt(points, b)


def _len(pa, pb):
    return math.hypot(pb[0] - pa[0], pb[1] - pa[1])


def _angle(vertex, a, b):
    ux, uy = a[0] - vertex[0], a[1] - vertex[1]
    vx, vy = b[0] - vertex[0], b[1] - vertex[1]
    lu, lv = math.hypot(ux, uy), math.hypot(vx, vy)
    if lu == 0 or lv == 0:
        raise SpecError("angle check: degenerate ray")
    c = max(-1.0, min(1.0, (ux * vx + uy * vy) / (lu * lv)))
    return math.degrees(math.acos(c))


def _line_dist(p, a, b):
    """Perpendicular distance from p to the infinite line a-b."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    n = math.hypot(dx, dy)
    if n == 0:
        raise SpecError("collinear check: two identical reference points")
    return abs(dy * p[0] - dx * p[1] + b[0] * a[1] - b[1] * a[0]) / n


def _angle_between(pa, pb, pc, pd):
    ax, ay = pb[0] - pa[0], pb[1] - pa[1]
    bx, by = pd[0] - pc[0], pd[1] - pc[1]
    la, lb = math.hypot(ax, ay), math.hypot(bx, by)
    if la == 0 or lb == 0:
        raise SpecError("parallel/perpendicular check: zero-length segment")
    c = max(-1.0, min(1.0, (ax * bx + ay * by) / (la * lb)))
    a = math.degrees(math.acos(c))
    return min(a, 180.0 - a)


def _fmt(x):
    if x is None:
        return "-"
    if abs(x) >= 1000:
        return "%.1f" % x
    if abs(x) >= 1:
        return "%.4f" % x
    return "%.6g" % x


def run_check(points, chk, index):
    typ = (chk.get("type") or "").strip()
    tol = float(chk.get("tol", DEFAULT_TOL))
    tol_pct = float(chk.get("tol_pct", DEFAULT_TOL_PCT))
    tol_deg = float(chk.get("tol_deg", DEFAULT_TOL_DEG))
    label = chk.get("label") or typ
    detail = ""
    residual = None
    passed = False

    if typ == "equal":
        pa, pb = _seg(points, chk.get("a"), "a")
        pc, pd = _seg(points, chk.get("b"), "b")
        la, lb = _len(pa, pb), _len(pc, pd)
        mean = (la + lb) / 2.0
        if mean == 0:
            raise SpecError("equal: zero mean length")
        residual = abs(la - lb) / mean * 100.0
        passed = residual <= tol_pct
        detail = "len %.4f vs %.4f, diff %.4f%%" % (la, lb, residual)
    elif typ == "angle":
        v = _pt(points, chk["vertex"])
        a = _pt(points, chk["a"])
        b = _pt(points, chk["b"])
        got = _angle(v, a, b)
        want = float(chk["deg"])
        residual = abs(got - want)
        passed = residual <= tol_deg
        detail = "%.4f deg (want %.4f)" % (got, want)
    elif typ == "collinear":
        names = chk.get("points") or []
        if len(names) < 3:
            raise SpecError("collinear needs >= 3 points")
        pts = [_pt(points, n) for n in names]
        worst = 0.0
        for i in range(len(pts) - 1):
            for j in range(i + 1, len(pts)):
                for k in range(len(pts)):
                    if k in (i, j):
                        continue
                    worst = max(worst, _line_dist(pts[k], pts[i], pts[j]))
        residual = worst
        passed = worst <= tol
        detail = "max perpendicular distance %.4f" % worst
    elif typ == "on_segment":
        p = _pt(points, chk["point"])
        pa, pb = _seg(points, chk.get("segment"), "segment")
        dx, dy = pb[0] - pa[0], pb[1] - pa[1]
        l2 = dx * dx + dy * dy
        if l2 == 0:
            raise SpecError("on_segment: zero-length segment")
        t = ((p[0] - pa[0]) * dx + (p[1] - pa[1]) * dy) / l2
        t_clamped = max(0.0, min(1.0, t))
        cx, cy = pa[0] + t_clamped * dx, pa[1] + t_clamped * dy
        residual = math.hypot(p[0] - cx, p[1] - cy)
        inside = -tol <= t <= 1.0 + tol
        passed = residual <= tol and inside
        detail = "t=%.5f%s, distance %.4f" % (
            t, "" if 0.0 <= t <= 1.0 else " (OUTSIDE segment)", residual)
    elif typ == "midpoint":
        p = _pt(points, chk["point"])
        a = _pt(points, chk["a"])
        b = _pt(points, chk["b"])
        m = ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)
        residual = _len(p, m)
        passed = residual <= tol
        detail = "distance to midpoint %.4f" % residual
    elif typ == "distance":
        pa = _pt(points, chk["a"])
        pb = _pt(points, chk["b"])
        got = _len(pa, pb)
        want = float(chk["value"])
        if want == 0:
            residual = got
            passed = got <= tol
            detail = "value %.4f (want 0)" % got
        else:
            residual = abs(got - want) / abs(want) * 100.0
            passed = residual <= tol_pct
            detail = "value %.4f (want %.4f), diff %.4f%%" % (got, want, residual)
    elif typ == "parallel":
        pa, pb = _seg(points, chk.get("a"), "a")
        pc, pd = _seg(points, chk.get("b"), "b")
        got = _angle_between(pa, pb, pc, pd)
        residual = got
        passed = got <= tol_deg
        detail = "angle between lines %.4f deg" % got
    elif typ == "perpendicular":
        pa, pb = _seg(points, chk.get("a"), "a")
        pc, pd = _seg(points, chk.get("b"), "b")
        got = _angle_between(pa, pb, pc, pd)
        residual = abs(90.0 - got)
        passed = residual <= tol_deg
        detail = "angle between lines %.4f deg (want 90)" % got
    elif typ == "point_eq":
        pa = _pt(points, chk["a"])
        pb = _pt(points, chk["b"])
        residual = _len(pa, pb)
        passed = residual <= tol
        detail = "distance %.4f" % residual
    else:
        raise SpecError("unknown check type %r" % typ)

    return {
        "index": index,
        "type": typ,
        "label": label,
        "pass": bool(passed),
        "residual": residual,
        "detail": detail,
        "points": chk.get("points") or chk.get("label_points"),
        "check": chk,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("spec", help="path to the figure spec JSON")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)

    try:
        with open(args.spec, "r", encoding="utf-8") as fh:
            spec = json.load(fh)
        points = spec.get("points") or {}
        if not points:
            raise SpecError("spec has no 'points' object")
        checks = spec.get("checks") or []
        if not checks:
            raise SpecError("spec has no 'checks' array")
        results = [run_check(points, chk, i) for i, chk in enumerate(checks)]
    except (SpecError, KeyError, TypeError, ValueError) as exc:
        print("[spec] %s" % exc, file=sys.stderr)
        if args.json:
            print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 2

    ok = all(r["pass"] for r in results)
    name = spec.get("name") or args.spec
    if args.json:
        print(json.dumps({
            "ok": ok,
            "name": name,
            "checks": [{k: r[k] for k in ("index", "type", "label", "pass",
                                          "residual", "detail")}
                       for r in results],
        }, ensure_ascii=False, indent=2))
    else:
        print("spec: %s" % name)
        print("%-4s %-14s %-34s %s" % ("", "check", "detail", "residual"))
        for r in results:
            print("%-4s %-14s %-34s %s" % (
                "PASS" if r["pass"] else "FAIL",
                r["label"], r["detail"], _fmt(r["residual"])))
        n_bad = sum(1 for r in results if not r["pass"])
        print("RESULT: %s (%d checks, %d failed)" % (
            "PASS" if ok else "FAIL", len(results), n_bad))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
