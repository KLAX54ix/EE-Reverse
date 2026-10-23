"""慈溪卷 Q15(fig19) / Q4(fig01) —— 离线测量 + 约束式构造 + 预览渲染。

原则（AGENTS.md）：约束式构造，不照抄像素。
  Q15: 圆 O 半径 R；A,B,C 在圆上，∠CAB=90° → BC 为直径；
       过 C 作 AO 垂线交 AO 延长线于 D（垂足在 O 外），AB = 2·OD。
       精确解（已验算）：A=240°, C=120°, B=300°, D=0.5·(cos60°,sin60°)，
       AB=1.0R, OD=0.5R, AC=√3·R。原图与之对照（Kabsch 验证朝向）。
  Q4:  l1∥l2∥l3，截线 a 过 A,B,C；b 过 D,E,F。
       精确约束：垂直间距 d12:d23 = 5:2；AB/BC = 5/2；DE/EF = 5/2；
       AB/DE = 5/4（⇒ sinαb = 1.25·sinαa，αa≤53.13°，原图 63° 实为错误，
       取最接近原图的可行情景——黄金分割搜索）。

输出：analysis/cixi/meas-fig19.json / meas-fig01.json + preview PNG（红=我们的构造）
"""
import json
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

ROOT = r"D:\EE Reverse"
FIGS = os.path.join(ROOT, "captures", "cixi-figs")
OUT = os.path.join(ROOT, "analysis", "cixi")


def load(path):
    a = np.array(Image.open(path).convert("L"))
    ys, xs = np.nonzero(a < 128)
    pts = np.stack([xs, ys], axis=1).astype(np.float64)
    return pts, a.shape[1], a.shape[0]


def refine(pts, theta_deg, rho, tol):
    t = math.radians(theta_deg)
    nx, ny = math.cos(t), math.sin(t)
    d = pts[:, 0] * nx + pts[:, 1] * ny - rho
    sel = pts[np.abs(d) <= tol]
    if len(sel) < 20:
        return None, 0, None
    c = sel.mean(axis=0)
    _, _, vt = np.linalg.svd(sel - c, full_matrices=False)
    dirv = vt[0]
    n = np.array([-dirv[1], dirv[0]])
    if n[0] * nx + n[1] * ny < 0:
        n = -n
    rho2 = float(n @ c)
    th2 = float(math.degrees(math.atan2(n[1], n[0])))
    return (th2, rho2), len(sel), sel


def inter(l1, l2):
    t1, r1 = l1
    t2, r2 = l2
    a1, b1 = math.cos(math.radians(t1)), math.sin(math.radians(t1))
    a2, b2 = math.cos(math.radians(t2)), math.sin(math.radians(t2))
    det = a1 * b2 - a2 * b1
    if abs(det) < 1e-9:
        return None
    x = (r1 * b2 - r2 * b1) / det
    y = (a1 * r2 - a2 * r1) / det
    return (x, y)


def seg_endpoints(sel, line):
    t, r = line
    dirv = np.array([-math.sin(math.radians(t)), math.cos(math.radians(t))])
    ts = sel @ dirv
    i0, i1 = int(np.argmin(ts)), int(np.argmax(ts))
    return tuple(sel[i0]), tuple(sel[i1])


def circle_fit(px):
    # Kasa algebraic fit with iterative trimming
    p = px.copy()
    for _ in range(5):
        x, y = p[:, 0], p[:, 1]
        A = np.stack([x, y, np.ones_like(x)], axis=1)
        b = x ** 2 + y ** 2
        sol, *_ = np.linalg.lstsq(A, b, rcond=None)
        cx, cy = sol[0] / 2, sol[1] / 2
        r = math.sqrt(sol[2] + cx ** 2 + cy ** 2)
        d = np.abs(np.hypot(x - cx, y - cy) - r)
        keep = d < max(4.0, float(np.percentile(d, 80)))
        if keep.sum() < 100:
            break
        p = p[keep]
    return (cx, cy), r, len(p)


def kabsch(P, Q, allow_reflection=True):
    """Similarity transform mapping P (model, y-down screen space) to Q (px)."""
    Pc = P - P.mean(axis=0)
    Qc = Q - Q.mean(axis=0)
    H = Pc.T @ Qc
    U, S, Vt = np.linalg.svd(H)
    D = np.diag([1.0, 1.0])
    if np.linalg.det(Vt.T @ U.T) < 0:
        if allow_reflection:
            D = np.diag([1.0, -1.0])
        else:
            D = np.diag([1.0, -1.0])
    R = Vt.T @ D @ U.T  # maps model -> data
    scale = (S * np.diag(D)).sum() / (Pc ** 2).sum()
    t = Q.mean(axis=0) - scale * (R @ P.mean(axis=0))
    Q2 = (scale * (R @ P.T)).T + t
    res = np.hypot(*(Q2 - Q).T)
    theta = math.degrees(math.atan2(R[1, 0], R[0, 0]))
    return dict(R=R.tolist(), scale=float(scale), t=[float(v) for v in t],
                theta=float(theta), residuals=res.tolist(),
                rms=float(np.sqrt((res ** 2).mean())),
                reflected=bool(np.linalg.det(R) < 0)), Q2


def apply_sim(model_pts, fit):
    R = np.array(fit["R"])
    s = fit["scale"]
    t = np.array(fit["t"])
    out = []
    for px_, py_ in model_pts:
        v = s * (R @ np.array([px_, py_])) + t
        out.append((float(v[0]), float(v[1])))
    return out


# ----------------------------------------------------------------------------
# Q15 / fig19
# ----------------------------------------------------------------------------
def do_fig19():
    pts, W, H = load(os.path.join(FIGS, "fig19.png"))
    print("== fig19  %dx%d  ink=%d" % (W, H, len(pts)))
    guesses = {
        "AC": (0.0, 140.0),
        "CD": (122.0, -25.0),
        "AD": (29.5, 348.0),
        "AB": (92.0, 466.0),
        "OB": (-28.0, 95.0),
    }
    lines, sel = {}, {}
    for k, (t, r) in guesses.items():
        ref, n, s = refine(pts, t, r, 6)
        lines[k] = ref
        sel[k] = s
        print("  %-3s theta=%7.2f rho=%8.2f  (%d px)" % (k, ref[0], ref[1], n))
        ep = seg_endpoints(s, ref)
        print("      ends (%5.0f,%5.0f)-(%5.0f,%5.0f)" % (ep[0] + ep[1]))

    A = inter(lines["AC"], lines["AB"])
    B = inter(lines["AB"], lines["OB"])
    C = inter(lines["AC"], lines["CD"])
    D = inter(lines["CD"], lines["AD"])
    O = inter(lines["AD"], lines["OB"])
    meas = {"A": A, "B": B, "C": C, "D": D, "O": O}
    print("  intersections:")
    for k, v in meas.items():
        print("    %s = (%7.2f, %7.2f)" % (k, v[0], v[1]))

    # circle fit: exclude line bands and rough label boxes
    label_boxes = {"C": (40, 5, 130, 75), "A": (45, 475, 135, 545),
                   "B": (360, 480, 450, 545), "D": (310, 130, 360, 190),
                   "O": (272, 240, 330, 295)}
    mask = np.ones(len(pts), dtype=bool)
    for ln in lines.values():
        t, r = ln
        nx, ny = math.cos(math.radians(t)), math.sin(math.radians(t))
        mask &= np.abs(pts[:, 0] * nx + pts[:, 1] * ny - r) > 8
    for (x0, y0, x1, y1) in label_boxes.values():
        inside = (pts[:, 0] >= x0) & (pts[:, 0] <= x1) & (pts[:, 1] >= y0) \
            & (pts[:, 1] <= y1)
        mask &= ~inside
    cxy, cr, nin = circle_fit(pts[mask])
    print("  circle: center=(%.2f, %.2f)  r=%.2f  (%d px)" % (cxy[0], cxy[1], cr, nin))

    # distances model checks on measured points
    def dist(p, q):
        return math.hypot(p[0] - q[0], p[1] - q[1])
    print("  measured |OA|=%.1f |OB|=%.1f |OC|=%.1f |OD|=%.1f  |AB|=%.1f"
          % (dist(O, A), dist(O, B), dist(O, C), dist(O, D), dist(A, B)))

    # exact clean model (math y-up -> screen y-down)
    def sxy(deg, r):
        return (r * math.cos(math.radians(deg)), -r * math.sin(math.radians(deg)))
    model = {
        "A": sxy(240, 1.0), "B": sxy(300, 1.0), "C": sxy(120, 1.0),
        "D": sxy(60, 0.5), "O": (0.0, 0.0),
    }
    order = ["A", "B", "C", "D", "O"]
    P = np.array([model[k] for k in order])
    Q = np.array([meas[k] for k in order])
    fit, Q2 = kabsch(P, Q)
    print("  Kabsch: scale=%.2f px/unit theta=%+.2f deg rms=%.2f px reflected=%s"
          % (fit["scale"], fit["theta"], fit["rms"], fit["reflected"]))
    for k, r_ in zip(order, fit["residuals"]):
        print("    %s residual %.2f px" % (k, r_))
    # mirrored alternative
    P_m = P.copy(); P_m[:, 0] *= -1
    fit_m, Q2m = kabsch(P_m, Q)
    print("  mirror check: rms %.2f px (mirror) vs %.2f px (as-is)"
          % (fit_m["rms"], fit["rms"]))

    # precise label glyph centers: leftover px after removing line bands + circle
    mask2 = np.ones(len(pts), dtype=bool)
    for ln in lines.values():
        t, r = ln
        nx, ny = math.cos(math.radians(t)), math.sin(math.radians(t))
        mask2 &= np.abs(pts[:, 0] * nx + pts[:, 1] * ny - r) > 6
    d_c = np.abs(np.hypot(pts[:, 0] - cxy[0], pts[:, 1] - cxy[1]) - cr)
    mask2 &= d_c > 7
    rest = pts[mask2]
    # connected clusters (grid hashing, 8-neighbour)
    def clusters(p, eps=4.0):
        from collections import deque
        cell = {}
        for i, (x, y) in enumerate(p):
            cell.setdefault((int(x // eps), int(y // eps)), []).append(i)
        seen = np.zeros(len(p), dtype=bool)
        out = []
        for i in range(len(p)):
            if seen[i]:
                continue
            dq = deque([i]); seen[i] = True; grp = []
            while dq:
                j = dq.popleft(); grp.append(j)
                gx, gy = int(p[j][0] // eps), int(p[j][1] // eps)
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        for k2 in cell.get((gx + dx, gy + dy), []):
                            if not seen[k2]:
                                seen[k2] = True; dq.append(k2)
            out.append(grp)
        return out
    cl = [c for c in clusters(rest) if len(c) >= 30]
    glyphs = {}
    for c in cl:
        gg = rest[c]
        cxm, cym = gg[:, 0].mean(), gg[:, 1].mean()
        w = gg[:, 0].max() - gg[:, 0].min()
        h = gg[:, 1].max() - gg[:, 1].min()
        best = min(meas.items(), key=lambda kv: dist(kv[1], (cxm, cym)))
        if dist(best[1], (cxm, cym)) < 70 and w < 60 and h < 60:
            glyphs[best[0]] = (cxm, cym, w, h)
    print("  label glyph centers:")
    for k in "ABCDO":
        if k in glyphs:
            g = glyphs[k]
            print("    %s center=(%.1f, %.1f) box %dx%d" % (k, g[0], g[1], g[2], g[3]))

    # preview
    img = Image.open(os.path.join(FIGS, "fig19.png")).convert("RGB")
    dr = ImageDraw.Draw(img)
    for k in ("AC", "CD", "AD", "AB", "OB"):
        ep = seg_endpoints(sel[k], lines[k])
        dr.line([ep[0][0], ep[0][1], ep[1][0], ep[1][1]], fill=(255, 0, 0), width=1)
    dr.ellipse([cxy[0] - cr, cxy[1] - cr, cxy[0] + cr, cxy[1] + cr],
               outline=(0, 128, 255), width=1)
    for k in order:
        q = Q2[order.index(k)]
        dr.ellipse([q[0] - 3, q[1] - 3, q[0] + 3, q[1] + 3], fill=(0, 160, 0))
    img.save(os.path.join(OUT, "preview-fig19.png"))

    out = {
        "image": {"w": W, "h": H},
        "lines": {k: {"theta": v[0], "rho": v[1],
                      "ends": seg_endpoints(sel[k], v)} for k, v in lines.items()},
        "measured_points": meas,
        "circle": {"center": cxy, "r": cr, "inliers": nin},
        "model_points": model,
        "kabsch": fit,
        "kabsch_mirror_rms": fit_m["rms"],
        "glyphs": {k: list(v) for k, v in glyphs.items()},
    }
    with open(os.path.join(OUT, "meas-fig19.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print("  saved meas-fig19.json + preview-fig19.png")
    return out


# ----------------------------------------------------------------------------
# Q4 / fig01
# ----------------------------------------------------------------------------
def do_fig01():
    pts, W, H = load(os.path.join(FIGS, "fig01.png"))
    print("== fig01  %dx%d  ink=%d" % (W, H, len(pts)))
    guesses = {
        "l1": (90.0, 70.0),
        "l2": (90.0, 198.0),
        "l3": (90.0, 260.0),
        "a": (26.6, 220.0),
        "b": (155.9, -250.0),
    }
    lines, sel = {}, {}
    for k, (t, r) in guesses.items():
        ref, n, s = refine(pts, t, r, 6)
        lines[k] = ref
        sel[k] = s
        print("  %-3s theta=%7.2f rho=%8.2f  (%d px)" % (k, ref[0], ref[1], n))
        ep = seg_endpoints(s, ref)
        print("      ends (%5.0f,%5.0f)-(%5.0f,%5.0f)" % (ep[0] + ep[1]))

    A = inter(lines["l1"], lines["a"])
    B = inter(lines["l2"], lines["a"])
    C = inter(lines["l3"], lines["a"])
    D = inter(lines["l1"], lines["b"])
    E = inter(lines["l2"], lines["b"])
    F = inter(lines["l3"], lines["b"])
    meas = {"A": A, "B": B, "C": C, "D": D, "E": E, "F": F}
    print("  intersections:")
    for k, v in meas.items():
        print("    %s = (%7.2f, %7.2f)" % (k, v[0], v[1]))

    def dist(p, q):
        return math.hypot(p[0] - q[0], p[1] - q[1])
    AB, BC = dist(A, B), dist(B, C)
    DE, EF = dist(D, E), dist(E, F)
    y1, y2, y3 = lines["l1"][1], lines["l2"][1], lines["l3"][1]
    d12, d23 = abs(y2 - y1), abs(y3 - y2)
    ta = lines["a"][0]; tb = lines["b"][0]
    aa = abs(90.0 - (ta % 180.0))
    ab = abs(90.0 - (tb % 180.0))
    print("  measured: d12=%.1f d23=%.1f | AB=%.1f BC=%.1f DE=%.1f EF=%.1f"
          % (d12, d23, AB, BC, DE, EF))
    print("  measured angles to parallel: a=%.2f deg  b=%.2f deg" % (aa, ab))
    print("  measured ratios: AB/BC=%.3f DE/EF=%.3f AB/DE=%.3f"
          % (AB / BC, DE / EF, AB / DE))
    print("  exact requires sin(b)=1.25*sin(a); measured sin(b)/sin(a)=%.3f"
          % (math.sin(math.radians(ab)) / math.sin(math.radians(aa))))

    # spacing scale: minimize |5L-d12| + |2L-d23|
    Ls = np.linspace(1.0, 60.0, 100000)
    cost = np.abs(5 * Ls - d12) + np.abs(2 * Ls - d23)
    Ll = float(Ls[int(np.argmin(cost))])
    print("  spacing: 5L=%.1f (was %.1f), 2L=%.1f (was %.1f)  [L=%.2f]"
          % (5 * Ll, d12, 2 * Ll, d23, Ll))

    # angles: golden search  min (aa-aa_m)^2 + (ab-abe)^2  s.t. sin(abe)=1.25 sin(aa)
    def cost_ang(x):
        s = 1.25 * math.sin(math.radians(x))
        if s >= 1.0:
            return 1e9
        abe = math.degrees(math.asin(s))
        return (x - aa) ** 2 + (abe - ab) ** 2
    lo, hi = 5.0, 53.13
    phi = (math.sqrt(5) - 1) / 2
    for _ in range(200):
        c = hi - phi * (hi - lo)
        d = lo + phi * (hi - lo)
        if cost_ang(c) < cost_ang(d):
            hi = d
        else:
            lo = c
    aa_s = (lo + hi) / 2
    ab_s = math.degrees(math.asin(1.25 * math.sin(math.radians(aa_s))))
    print("  exact angles: a*=%.2f deg (meas %.2f), b*=%.2f deg (meas %.2f)"
          % (aa_s, aa, ab_s, ab))

    # construct exact (screen coords, y-down)
    y1s, y2s, y3s = y1, y1 + 5 * Ll, y1 + 7 * Ll
    Ax, _ = meas["A"]
    Dx, _ = meas["D"]
    ua = np.array([-math.cos(math.radians(aa_s)), math.sin(math.radians(aa_s))])
    ub = np.array([math.cos(math.radians(ab_s)), math.sin(math.radians(ab_s))])
    A2 = np.array([Ax, y1s]); D2 = np.array([Dx, y1s])
    def at_y(p, u, y):
        tt = (y - p[1]) / u[1]
        return p + tt * u
    B2 = at_y(A2, ua, y2s); C2 = at_y(A2, ua, y3s)
    E2 = at_y(D2, ub, y2s); F2 = at_y(D2, ub, y3s)
    exact = {"A": tuple(A2), "B": tuple(B2), "C": tuple(C2),
             "D": tuple(D2), "E": tuple(E2), "F": tuple(F2)}
    eAB = float(np.hypot(*(B2 - A2))); eBC = float(np.hypot(*(C2 - B2)))
    eDE = float(np.hypot(*(E2 - D2))); eEF = float(np.hypot(*(F2 - E2)))
    print("  exact px: AB=%.3f BC=%.3f DE=%.3f EF=%.3f  ratios %.6f %.6f %.6f"
          % (eAB, eBC, eDE, eEF, eAB / eBC, eDE / eEF, eAB / eDE))

    # label glyphs
    mask = np.ones(len(pts), dtype=bool)
    for ln in lines.values():
        t, r = ln
        nx, ny = math.cos(math.radians(t)), math.sin(math.radians(t))
        mask &= np.abs(pts[:, 0] * nx + pts[:, 1] * ny - r) > 6
    rest = pts[mask]
    def clusters(p, eps=4.0):
        from collections import deque
        cell = {}
        for i, (x, y) in enumerate(p):
            cell.setdefault((int(x // eps), int(y // eps)), []).append(i)
        seen = np.zeros(len(p), dtype=bool)
        out = []
        for i in range(len(p)):
            if seen[i]:
                continue
            dq = deque([i]); seen[i] = True; grp = []
            while dq:
                j = dq.popleft(); grp.append(j)
                gx, gy = int(p[j][0] // eps), int(p[j][1] // eps)
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        for k2 in cell.get((gx + dx, gy + dy), []):
                            if not seen[k2]:
                                seen[k2] = True; dq.append(k2)
            out.append(grp)
        return out
    cl = [c for c in clusters(rest) if len(c) >= 30]
    glyphs = {}
    for c in cl:
        gg = rest[c]
        cxm, cym = gg[:, 0].mean(), gg[:, 1].mean()
        w = gg[:, 0].max() - gg[:, 0].min(); h = gg[:, 1].max() - gg[:, 1].min()
        if w > 60 or h > 60:
            continue
        best = min(meas.items(), key=lambda kv: dist(kv[1], (cxm, cym)))
        if dist(best[1], (cxm, cym)) < 90:
            glyphs.setdefault(best[0], (cxm, cym, w, h))
    print("  label glyph centers:")
    for k in "ABCDEF":
        if k in glyphs:
            g = glyphs[k]
            print("    %s center=(%.1f, %.1f) box %dx%d" % (k, g[0], g[1], g[2], g[3]))

    # line endpoint extents (from ink selections)
    ends = {k: seg_endpoints(sel[k], lines[k]) for k in lines}
    print("  line extents:")
    for k, ep in ends.items():
        print("    %-3s (%5.0f,%5.0f)-(%5.0f,%5.0f)"
              % ((k,) + ep[0] + ep[1]))

    # preview
    img = Image.open(os.path.join(FIGS, "fig01.png")).convert("RGB")
    dr = ImageDraw.Draw(img)
    for k in lines:
        ep = ends[k]
        dr.line([ep[0][0], ep[0][1], ep[1][0], ep[1][1]], fill=(255, 0, 0), width=1)
    for k, p in exact.items():
        dr.ellipse([p[0] - 3, p[1] - 3, p[0] + 3, p[1] + 3], fill=(0, 160, 0))
    img.save(os.path.join(OUT, "preview-fig01.png"))

    out = {
        "image": {"w": W, "h": H},
        "lines": {k: {"theta": v[0], "rho": v[1], "ends": ends[k]}
                  for k, v in lines.items()},
        "measured_points": meas,
        "measured": {"d12": d12, "d23": d23, "AB": AB, "BC": BC,
                     "DE": DE, "EF": EF, "angle_a": aa, "angle_b": ab},
        "exact": {"L": Ll, "angle_a": aa_s, "angle_b": ab_s,
                  "y1": y1s, "y2": y2s, "y3": y3s,
                  "points": {k: list(v) for k, v in exact.items()},
                  "lengths": {"AB": eAB, "BC": eBC, "DE": eDE, "EF": eEF}},
        "glyphs": {k: list(v) for k, v in glyphs.items()},
    }
    with open(os.path.join(OUT, "meas-fig01.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print("  saved meas-fig01.json + preview-fig01.png")
    return out


if __name__ == "__main__":
    do_fig19()
    do_fig01()
