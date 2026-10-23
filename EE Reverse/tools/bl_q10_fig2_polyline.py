"""北仑卷 题10 图2 —— **土方法版**：抛物线用加密折线，不用原生 esSegBezier。

为什么不用原生曲线：`esSegBezier`(0x4703) 每个单点检查都过（Create 成功、
控制点存回 +0x58/+0x5C、steps 有 oncreate、升阶误差 2.4e-14），但**挂上活画布后
画布变色、对象点不动**（图形链被写坏）。用户已判定：放弃原生曲线，改手搓。

数学约束（见 analysis/beilun-q10-constraints.md）：
    过原点，最高点 N(n, 6√3)，过 I(1.5,y1)/J(5.5,y2)，选项 D 说 y1=y2
    => 对称轴 x=3.5 => n=3.5，另一交点 x=7
    => y = 6√3/12.25 · x · (7 − x)，x、y 同尺度
"""
import json
import math

U = 760.0                        # 1 题目单位 = 760 画布单位（x、y 同尺度）
OX, OY = 7000.0, 21000.0         # 原点 O 的画布位置（y 向下）
A = 6 * math.sqrt(3) / 12.25
X0, X1 = 0.0, 5.5                # 图2 是"部分图象"，右端落在 J(5.5)
N_PTS = 56                       # 0.1 单位一段：折线偏离真曲线 < 0.3 画布单位


def ymath(x):
    return A * x * (7.0 - x)


def to_canvas(x, y):
    return (OX + U * x, OY - U * y)


def main():
    xs = [X0 + (X1 - X0) * i / (N_PTS - 1) for i in range(N_PTS)]
    curve = [tuple(round(v) for v in to_canvas(x, ymath(x))) for x in xs]

    # ---- 自检：折线相对真抛物线的最大偏差（垂距，画布单位）----
    worst = 0.0
    for i in range(N_PTS - 1):
        (x0, y0), (x1, y1) = curve[i], curve[i + 1]
        for k in range(1, 20):
            t = k / 20.0
            px = x0 + (x1 - x0) * t
            py = y0 + (y1 - y0) * t
            xm = (px - OX) / U
            worst = max(worst, abs(py - (OY - U * ymath(xm))))
    print("polyline vs true parabola: max deviation = %.2f canvas units = %.5f mm"
          % (worst, worst / 400.0))
    print("points = %d, x %d..%d, y %d..%d"
          % (len(curve), min(p[0] for p in curve), max(p[0] for p in curve),
             min(p[1] for p in curve), max(p[1] for p in curve)))
    print("vertex N = (%.2f, %.4f)  6*sqrt(3) = %.4f" % (3.5, ymath(3.5), 6 * math.sqrt(3)))
    print("I(1.5)=%.4f  J(5.5)=%.4f  equal=%s"
          % (ymath(1.5), ymath(5.5), abs(ymath(1.5) - ymath(5.5)) < 1e-9))

    ax_l, ax_r = round(OX - 0.55 * U), round(OX + 6.1 * U)
    ax_y = round(OY)
    y_top = round(OY - 7.3 * U)
    ar = 330
    spec = {
        "method": "polyline (no native esSegBezier)",
        "curve_points": [list(p) for p in curve],
        "paths": [
            {"points": [[ax_l, ax_y], [ax_r, ax_y]]},                       # x 轴
            {"points": [[round(OX), round(OY + 0.75 * U)], [round(OX), y_top]]},  # y 轴
            {"points": [[ax_r, ax_y], [ax_r - ar, ax_y - ar // 2],
                        [ax_r, ax_y], [ax_r - ar, ax_y + ar // 2]]},        # x 箭头
            {"points": [[round(OX), y_top], [round(OX) - ar // 2, y_top + ar],
                        [round(OX), y_top], [round(OX) + ar // 2, y_top + ar]]},  # y 箭头
        ],
        "labels": [
            {"text": "y", "x": round(OX - 0.45 * U), "y": y_top - 90},
            {"text": "O", "x": round(OX - 0.36 * U), "y": round(OY + 0.45 * U)},
            {"text": "x", "x": ax_r - 70, "y": round(OY + 0.48 * U)},
            {"text": "N(n, 6\u221a3)", "x": round(OX + 4.5 * U), "y": round(OY - 6.9 * U)},
            {"text": "\u56fe2", "x": round(OX + 2.6 * U), "y": round(OY + 1.6 * U)},
        ],
    }
    out = r"D:\EE Reverse\analysis\bl-q10-fig2-polyline.json"
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(spec, fh, ensure_ascii=False, indent=1)
    print("\naxes:")
    for p in spec["paths"]:
        print("  %s" % (p["points"],))
    print("labels:")
    for lb in spec["labels"]:
        print("  %-12s (%d, %d)" % (lb["text"], lb["x"], lb["y"]))
    print("\nwrote analysis/bl-q10-fig2-polyline.json")


if __name__ == "__main__":
    main()
