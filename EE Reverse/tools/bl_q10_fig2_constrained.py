"""北仑卷 题10 图2 —— 按【题干数学约束】生成精确的贝塞尔控制点。

题干约束（活文档 dump，见 analysis/beilun-q10-constraints.md）：
    抛物线经过原点，最高点为 N(n, 6*sqrt(3))，且经过点 I(1.5, y1), J(5.5, y2)
    选项 D "y1 = y2"  =>  对称轴 x = (1.5+5.5)/2 = 3.5  =>  n = 3.5
    顶点 (3.5, 6*sqrt(3))，另一交点 x = 7
    =>  y = 6*sqrt(3)/12.25 * x * (7 - x)

关键：**x 与 y 必须同尺度**，否则画出来的不是抛物线。
顶点高度 6*sqrt(3) ≈ 10.392 是题干给的数学量，**不能**去量栅格像素的纵横比
（上一版照像素量比例，把 10.39 压成了 2.0 —— 错）。

抛物线在顶点处切成两段二次贝塞尔，每段用"两端点 + 两端切线交点"升阶成三次贝塞尔，
这是**精确**的（抛物线本身就是二次贝塞尔）。
"""
import json
import math

# --- 布局（画布实测 65803 x 32901，y 向下为正） ------------------------------
U = 760.0                       # 1 个题目单位 = 760 画布单位（x、y 同尺度）
OX, OY = 7000.0, 21000.0        # 画布上原点 O 的位置
X_END = 5.5                     # 图2 是"部分图象"，右端落在 J(5.5)

A = 6 * math.sqrt(3) / 12.25    # y = A * x * (7 - x)，顶点在 x = 3.5
VX = 3.5


def ymath(x):
    return A * x * (7.0 - x)


def to_canvas(x, y):
    """题目坐标 -> 画布坐标（画布 y 向下，题目 y 向上）。"""
    return (OX + U * x, OY - U * y)


def quad_segment(x0, x1):
    """区间 [x0,x1] 上抛物线的二次贝塞尔：两端点 + 两端切线交点。"""
    y0, y1 = ymath(x0), ymath(x1)
    d0 = A * (7 - 2 * x0)
    d1 = A * (7 - 2 * x1)
    xc = 0.5 * (x0 + x1) if abs(d0 - d1) < 1e-12 else \
        (y1 - y0 + d0 * x0 - d1 * x1) / (d0 - d1)
    yc = y0 + d0 * (xc - x0)
    return (x0, y0), (xc, yc), (x1, y1)


def to_cubic(p0, p1, p2):
    """二次 -> 三次升阶（精确）：C1 = P0 + 2/3(P1-P0), C2 = P2 + 2/3(P1-P2)。"""
    c1 = (p0[0] + 2.0 / 3.0 * (p1[0] - p0[0]), p0[1] + 2.0 / 3.0 * (p1[1] - p0[1]))
    c2 = (p2[0] + 2.0 / 3.0 * (p1[0] - p2[0]), p2[1] + 2.0 / 3.0 * (p1[1] - p2[1]))
    return [p0, c1, c2, p2]


def bez(t, p):
    mt = 1 - t
    return (mt**3 * p[0][0] + 3 * mt**2 * t * p[1][0] + 3 * mt * t**2 * p[2][0] + t**3 * p[3][0],
            mt**3 * p[0][1] + 3 * mt**2 * t * p[1][1] + 3 * mt * t**2 * p[2][1] + t**3 * p[3][1])


def main():
    segL = quad_segment(0.0, VX)
    segR = quad_segment(VX, X_END)

    # ---- 自检 1：升阶是精确的吗（在【画布】坐标里比对，避免单位混淆） ----
    def canvas_y(x):
        return OY - U * ymath(x)

    worst = 0.0
    for seg, (xa, xb) in ((segL, (0.0, VX)), (segR, (VX, X_END))):
        cub = [to_canvas(x, y) for x, y in to_cubic(*seg)]
        cub = [(float(a), float(b)) for a, b in cub]
        for k in range(401):
            t = k / 400.0
            bx, by = bez(t, cub)
            xm = (bx - OX) / U
            worst = max(worst, abs(by - canvas_y(xm)))
    print("max |bezier - parabola| = %.6f canvas units  (%.2e math units)"
          % (worst, worst / U))

    # ---- 自检 2：题干给定的数学量 ----
    print("vertex N = (%.2f, %.4f)   6*sqrt(3) = %.4f" % (VX, ymath(VX), 6 * math.sqrt(3)))
    print("I(1.5) = %.4f   J(5.5) = %.4f   equal -> %s"
          % (ymath(1.5), ymath(5.5), abs(ymath(1.5) - ymath(5.5)) < 1e-9))
    print("other x-intercept: x = 7 -> y(7) = %.6f" % ymath(7.0))

    cps = [tuple(round(v) for v in to_canvas(x, y)) for x, y in to_cubic(*segL)] + \
          [tuple(round(v) for v in to_canvas(x, y)) for x, y in to_cubic(*segR)[1:]]
    cps = [list(p) for p in cps]

    # ---- 自检 3：控制点必须落在画布内 ----
    xs = [p[0] for p in cps]; ys = [p[1] for p in cps]
    print("\ncurve bbox x %d..%d   y %d..%d   (canvas 65803 x 32901)"
          % (min(xs), max(xs), min(ys), max(ys)))

    print("\ncurve_points (%d):" % len(cps))
    for p in cps:
        print("  %s" % (p,))

    # ---- 坐标轴 / 箭头 / 标注 ----
    ax_l, ax_r = round(OX - 0.55 * U), round(OX + 6.1 * U)
    ax_y = round(OY)
    y_top = round(OY - 7.3 * U)
    arrow = 330
    spec = {
        "source": "stem: origin, vertex N(n,6sqrt3), I(1.5,y1), J(5.5,y2), y1=y2 -> n=3.5",
        "n": VX, "vertex_math": [VX, 6 * math.sqrt(3)], "unit_canvas": U,
        "origin_canvas": [OX, OY],
        "curve_points": cps,
        "paths": {
            "x_axis": [[ax_l, ax_y], [ax_r, ax_y]],
            "y_axis": [[round(OX), round(OY + 0.75 * U)], [round(OX), y_top]],
            "x_arrow": [[ax_r, ax_y], [ax_r - arrow, ax_y - arrow // 2],
                        [ax_r, ax_y], [ax_r - arrow, ax_y + arrow // 2]],
            "y_arrow": [[round(OX), y_top], [round(OX) - arrow // 2, y_top + arrow],
                        [round(OX), y_top], [round(OX) + arrow // 2, y_top + arrow]],
        },
        "labels": [
            {"text": "y", "x": round(OX - 0.45 * U), "y": y_top - 90},
            {"text": "O", "x": round(OX - 0.36 * U), "y": round(OY + 0.45 * U)},
            {"text": "x", "x": ax_r - 70, "y": round(OY + 0.48 * U)},
            {"text": "N(n, 6\u221a3)", "x": round(OX + 4.5 * U), "y": round(OY - 6.6 * U)},
            {"text": "\u56fe2", "x": round(OX + 2.6 * U), "y": round(OY + 1.6 * U)},
        ],
    }
    out = r"D:\EE Reverse\analysis\bl-q10-fig2-constrained.json"
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(spec, fh, ensure_ascii=False, indent=1)
    print("\naxes:")
    for k, v in spec["paths"].items():
        print("  %-8s %s" % (k, v))
    print("labels:")
    for lb in spec["labels"]:
        print("  %-12s (%d, %d)" % (lb["text"], lb["x"], lb["y"]))
    print("\nwrote analysis/bl-q10-fig2-constrained.json")


if __name__ == "__main__":
    main()
