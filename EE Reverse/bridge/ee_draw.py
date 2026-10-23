#!/usr/bin/env python3
"""Canonical EE drawing API (basis for the MCP server).

Verified against a live editor:
  esShapePath::CreateFromPathData(POINT*, uchar* types, int count, int close)
  esCanvas::AddItem(canvas, shape, flags)      # intrusive list insert

Point/type semantics follow GDI+ GraphicsPath:
  0x00 start, 0x01 line, 0x03 bezier, 0x80 close subpath.
Coordinates are EE internal page units (the reference document used
X 10454..34454, Y 8012..25412).

CLI:
  python ee_draw.py canvas
  python ee_draw.py rect      [--canvas A] x1,y1 x2,y2
  python ee_draw.py triangle  [--canvas A] x1,y1 x2,y2 x3,y3
  python ee_draw.py polygon   [--canvas A] x1,y1 x2,y2 x3,y3 ...
  python ee_draw.py polyline  [--canvas A] x1,y1 x2,y2 ...
  python ee_draw.py line      [--canvas A] x1,y1 x2,y2
"""
import sys

sys.path.insert(0, r"D:\EE Reverse\bridge")
from ee_client import EE, VT  # noqa: E402

T_START, T_LINE, T_BEZIER, T_CLOSE = 0x00, 0x01, 0x03, 0x80


class EEDraw:
    def __init__(self):
        self.ee = EE()
        self._canvas = None

    # ---------- discovery ----------
    def info(self):
        return self.ee.rpc("info")

    def page_lists(self, cap=12):
        return self.ee.rpc("instances", VT["esPageList"], cap)["addresses"]

    def active_canvas(self):
        if self._canvas:
            return self._canvas
        for pl in self.page_lists():
            r = self.ee.rpc("call", "?GetActiveCanvas@esPageList@@QBEPAVesCanvas@@H@Z",
                            "pointer", ["int"], pl, [0], "thiscall")
            ret = r.get("ret")
            if ret and ret != "0x0":
                self._canvas = ret
                return ret
        return None

    # ---------- drawing ----------
    def create_path(self, points, types, close=False):
        return self.ee.rpc("createPath", points, types, 1 if close else 0)

    def add_item(self, shape, canvas=None, flags=1):
        canvas = canvas or self.active_canvas()
        return self.ee.rpc("addItem", canvas, shape, flags)

    def add_polygon(self, points, closed=True, canvas=None):
        """Build a path the way EE's own parser expects.

        Empirically verified against eslib.dll's
        esShapePath::CreateFromPathData:
          * types[i] == 0x01 emits one segment ending at points[i-1];
          * an explicit trailing 0x80 entry is required or the factory
            destroys the object and returns null;
          * the 0x80 entry only CLOSES the figure when the `close` argument
            is non-zero, otherwise the closing edge is silently missing.
        """
        v = list(points)
        n = len(v)
        if closed:
            pts = v + [v[0]]
            types = [T_START] + [T_LINE] * (n - 1) + [T_CLOSE]
        else:
            pts = list(v)
            types = [T_START] + [T_LINE] * (n - 1)
        r = self.create_path(pts, types, close=1 if closed else 0)
        if not r.get("ret"):
            return r
        r["canvas"] = canvas or self.active_canvas()
        r["addItem"] = self.add_item(r["ret"], r["canvas"])
        return r

    def add_rect(self, x1, y1, x2, y2, canvas=None):
        return self.add_polygon([(x1, y1), (x2, y1), (x2, y2), (x1, y2)],
                                closed=True, canvas=canvas)

    def redraw(self):
        return self.ee.rpc("redrawAll")

    def verify(self, shape):
        """Ask the engine to recompute layout, then read the cached geometry."""
        r = self.ee.rpc("call", "?RecalcLayout@esShapePath@@MAEXXZ", "void", [],
                        shape, [], "thiscall")
        out = {"recalc": r}
        for name, off in (("id", 0x10), ("p1x", 0x14), ("p1y", 0x18),
                          ("p2x", 0x1C), ("p2y", 0x20),
                          ("boxL", 0x24), ("boxT", 0x28),
                          ("boxR", 0x2C), ("boxB", 0x30), ("style", 0x34)):
            out[name] = self.ee.rpc(
                "readI32", hex(int(shape, 16) + off))
        return out

    def close(self):
        try:
            self.ee.close()
        except Exception:
            pass


def parse_pts(args):
    return [tuple(int(v) for v in a.split(",")) for a in args]


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 1
    cmd, rest = args[0], args[1:]
    canvas = None
    if "--canvas" in rest:
        i = rest.index("--canvas")
        canvas = rest[i + 1]
        rest = rest[:i] + rest[i + 2:]

    d = EEDraw()
    try:
        print(f"ee pid={d.info()['pid']} eslib={d.info()['eslibBase']}")
        if cmd == "canvas":
            print(f"active canvas = {d.active_canvas()}")
            return 0
        if cmd == "rect":
            p = parse_pts(rest)
            r = d.add_rect(p[0][0], p[0][1], p[1][0], p[1][1], canvas)
        else:
            pts = parse_pts(rest)
            r = d.add_polygon(pts, closed=(cmd != "polyline" and cmd != "line"),
                              canvas=canvas)
        print(f"createPath -> {r.get('ret')}  canvas={r.get('canvas')}  "
              f"addItem={r.get('addItem')}")
        if r.get("error"):
            print(f"ERROR: {r['error']}")
            return 3
        if r.get("ret") and r["ret"] != "0x0":
            v = d.ee.rpc("readU32", r["ret"])
            print(f"shape vtable = {hex(v) if v else None}")
            print(f"geometry = {d.verify(r['ret'])}")
        print(f"redraw -> {d.redraw()}")
    finally:
        d.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
