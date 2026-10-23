"""Build the exact canvas spec for 北仑 题10 图2 (the function-graph panel).

The parabola is fitted by least squares to the traced centreline of the ORIGINAL
raster (captures/beilun-figs/fig24.png, right panel):

    row = 0.031788*col^2 - 41.490259*col + 13588.534843      (rms 0.69 px)
    vertex (652.6, 50.2);  x-intercepts col 570.9 and 734.3

It is emitted as TWO exact cubic Beziers meeting at the vertex, where each
segment's control point is the intersection of the end tangents (exact for a
parabola, since a parabola IS a quadratic Bezier).

Canvas mapping:  P_canvas = (900 + 16*col, 400 + 16*row)
  1 canvas unit = 1/400 mm and y grows downward, matching raster rows.
"""
import json
import os

CX0, CY0, S = 900.0, 400.0, 16.0
A, B, C = 0.031788, -41.490259, 13588.534843     # fitted parabola, raster space
COL_V, ROW_V = 652.60, 50.19                     # vertex
COL_L, COL_R = 571.0, 695.0                      # curve extent (raster cols)
AX_ROW, AX_COL = 260.0, 570.0                    # x-axis row, y-axis col
X0COL, X1COL = 537.0, 796.0                      # x-axis extent
Y0ROW, Y1ROW = 296.0, 7.0                        # y-axis extent


def row_of(col):
    return A * col * col + B * col + C


def to_canvas(col, row):
    return (CX0 + S * col, CY0 + S * row)


def quad_bezier_segment(x0, x1):
    """Control point of the single quadratic Bezier over [x0, x1] (tangent
    intersection); for y = ax^2+bx+c that is the midpoint of the chord plus the
    parabola's 'bulge' along the axis of symmetry."""
    y0, y1 = row_of(x0), row_of(x1)
    xm = 0.5 * (x0 + x1)
    # tangent-line intersection
    d0 = 2 * A * x0 + B
    d1 = 2 * A * x1 + B
    # solve y = y0 + d0 (x-x0) and y = y1 + d1 (x-x1)
    xi = (y1 - y0 + d0 * x0 - d1 * x1) / (d0 - d1)
    yi = y0 + d0 * (xi - x0)
    return (x0, y0), (xi, yi), (x1, y1)


def quad_to_cubic(p0, p1, p2):
    c1 = (p0[0] + 2.0 / 3.0 * (p1[0] - p0[0]), p0[1] + 2.0 / 3.0 * (p1[1] - p0[1]))
    c2 = (p2[0] + 2.0 / 3.0 * (p1[0] - p2[0]), p2[1] + 2.0 / 3.0 * (p1[1] - p2[1]))
    return [p0, c1, c2, p2]


def bezier(p, t):
    mt = 1.0 - t
    return (
        mt ** 3 * p[0][0] + 3 * mt ** 2 * t * p[1][0] + 3 * mt * t ** 2 * p[2][0] + t ** 3 * p[3][0],
        mt ** 3 * p[0][1] + 3 * mt ** 2 * t * p[1][1] + 3 * mt * t ** 2 * p[2][1] + t ** 3 * p[3][1],
    )


def main():
    segL = quad_to_cubic(*quad_bezier_segment(COL_L, COL_V))
    segR = quad_to_cubic(*quad_bezier_segment(COL_V, COL_R))

    worst = 0.0
    for seg, xa, xb in ((segL, COL_L, COL_V), (segR, COL_V, COL_R)):
        fs = [(float(c), float(r)) for c, r in seg]
        for k in range(201):
            t = k / 200.0
            bx, by = bezier(fs, t)
            worst = max(worst, abs(by - row_of(bx)))
    print("max |bezier - fitted parabola| = %.4f raster px" % worst)

    curve_pts = [tuple(round(v) for v in to_canvas(c, r)) for c, r in segL] + \
                [tuple(round(v) for v in to_canvas(c, r)) for c, r in segR[1:]]

    arrow = 7.0
    spec = {
        "mapping": "canvas = (900 + 16*col, 400 + 16*row)",
        "raster_parabola": "row = %.6f*col^2 + %.6f*col + %.6f" % (A, B, C),
        "vertex_raster": [COL_V, ROW_V],
        "curve_points": [list(p) for p in curve_pts],
        "paths": [
            {"_what": "x axis", "points": [[round(v) for v in to_canvas(X0COL, AX_ROW)],
                                           [round(v) for v in to_canvas(X1COL, AX_ROW)]]},
            {"_what": "y axis", "points": [[round(v) for v in to_canvas(AX_COL, Y0ROW)],
                                           [round(v) for v in to_canvas(AX_COL, Y1ROW)]]},
            {"_what": "x arrowhead", "points": [[round(v) for v in to_canvas(X1COL, AX_ROW)],
                                                [round(v) for v in to_canvas(X1COL - arrow, AX_ROW - arrow * 0.5)],
                                                [round(v) for v in to_canvas(X1COL, AX_ROW)],
                                                [round(v) for v in to_canvas(X1COL - arrow, AX_ROW + arrow * 0.5)]]},
            {"_what": "y arrowhead", "points": [[round(v) for v in to_canvas(AX_COL, Y1ROW)],
                                                [round(v) for v in to_canvas(AX_COL - arrow * 0.5, Y1ROW + arrow)],
                                                [round(v) for v in to_canvas(AX_COL, Y1ROW)],
                                                [round(v) for v in to_canvas(AX_COL + arrow * 0.5, Y1ROW + arrow)]]},
        ],
        "labels": [
            {"text": "y", "x": round(CX0 + S * 552), "y": round(CY0 + S * 4)},
            {"text": "O", "x": round(CX0 + S * 549), "y": round(CY0 + S * 286)},
            {"text": "x", "x": round(CX0 + S * 790), "y": round(CY0 + S * 278)},
            {"text": "N(a,b,\u221a3)", "x": round(CX0 + S * 660), "y": round(CY0 + S * 20)},
            {"text": "\u56fe2", "x": round(CX0 + S * 640), "y": round(CY0 + S * 306)},
        ],
    }
    out = r"D:\EE Reverse\analysis\bl-q10-fig2.json"
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(spec, fh, ensure_ascii=False, indent=1)

    print("\ncurve control points (%d):" % len(curve_pts))
    for p in curve_pts:
        print("   %s" % (p,))
    print("\nlabels (canvas):")
    for lb in spec["labels"]:
        print("   %-10s (%d, %d)" % (lb["text"], lb["x"], lb["y"]))
    print("\naxes (canvas):")
    for pth in spec["paths"]:
        print("   %-12s %s" % (pth["_what"], pth["points"]))
    print("\nwrote %s" % os.path.basename(out))


if __name__ == "__main__":
    main()
