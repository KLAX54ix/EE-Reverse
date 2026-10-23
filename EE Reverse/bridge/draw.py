#!/usr/bin/env python3
"""Create vector shapes inside the running EE editor via the engine API.

Pipeline (confirmed by decompilation of eslib.dll):
  esShapePath::CreateFromPathData(POINT*, uchar* types, int count, int close)
      -> operator_new(0x74) + esShapePath() ctor + segment list from GDI+ types
  esCanvas::AddItem(canvas, shape, flags)   # intrusive list insert

Units: EE internal page units (the user's own line ran 10454 -> 30854 on X).

Usage:
  python draw.py canvas
  python draw.py polyline [--canvas ADDR] x1,y1 x2,y2 x3,y3 ...
  python draw.py rect [--canvas ADDR] x1,y1 x2,y2
  python draw.py triangle [--canvas ADDR] x1,y1 x2,y2 x3,y3
"""
import sys

sys.path.insert(0, r"D:\EE Reverse\bridge")
from ee_client import EE, VT  # noqa: E402

CREATE_FROM_PATH_DATA_RVA = 0x19FA10      # static, __cdecl
ADD_ITEM = "?AddItem@esCanvas@@QAEXPAVesShapeBase@@H@Z"
PAGE_GET_ACTIVE_CANVAS = "?GetActiveCanvas@esPageList@@QBEPAVesCanvas@@H@Z"
CANVAS_SET_MODIFIED = "?SetModifiedFlags@esCanvas@@UAEXH@Z"

# GDI+ PathPointType values used by EE's parser
T_START = 0x00
T_LINE = 0x01
T_BEZIER = 0x03
T_CLOSE = 0x80


def eslib_base(ee):
    return int(ee.rpc("info")["eslibBase"], 16)


def find_canvas(ee):
    lists = ee.rpc("instances", VT["esPageList"], 20)["addresses"]
    for a in lists:
        r = ee.rpc("call", PAGE_GET_ACTIVE_CANVAS, "pointer", ["int"], a, [0], "thiscall")
        ret = r.get("ret")
        if ret and ret not in ("0x0",):
            return ret
    return None


def call_cdecl(ee, addr, ret_type, arg_types, args):
    last = None
    for abi in ("sysv", "cdecl", "stdcall"):
        r = ee.rpc("calladdr", hex(addr), ret_type, arg_types, args, abi)
        if "error" not in r:
            r["abi"] = abi
            return r
        last = r
    return last


def create_path(ee, points, types, close=False):
    base = eslib_base(ee)
    n = len(points)
    pts = ee.rpc("alloc", n * 8)
    tys = ee.rpc("alloc", max(1, n))
    for i, (x, y) in enumerate(points):
        ee.rpc("writeI32", hex(int(pts, 16) + i * 8), int(x))
        ee.rpc("writeI32", hex(int(pts, 16) + i * 8 + 4), int(y))
    for i, t in enumerate(types):
        ee.rpc("writeU8", hex(int(tys, 16) + i), t)
    r = call_cdecl(ee, base + CREATE_FROM_PATH_DATA_RVA, "pointer",
                   ["pointer", "pointer", "int", "int"],
                   [pts, tys, n, 1 if close else 0])
    r["points_ptr"] = pts
    r["types_ptr"] = tys
    return r


def add_to_canvas(ee, canvas, shape, tail=True):
    r = ee.rpc("call", ADD_ITEM, "void", ["pointer", "int"], canvas,
               [shape, 1 if tail else 0], "thiscall")
    return r


def parse_pts(argv):
    out = []
    for a in argv:
        x, y = a.split(",")
        out.append((int(x), int(y)))
    return out


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 1
    cmd = args[0]
    args = args[1:]

    canvas_override = None
    if "--canvas" in args:
        i = args.index("--canvas")
        canvas_override = args[i + 1]
        args = args[:i] + args[i + 2:]

    ee = EE()
    try:
        canvas = canvas_override or find_canvas(ee)
        print(f"canvas = {canvas}")
        if cmd == "canvas":
            return 0
        if not canvas:
            print("no active canvas found")
            return 2

        if cmd == "rect":
            (x1, y1), (x2, y2) = parse_pts(args)
            points = [(x1, y1), (x2, y1), (x2, y2), (x1, y2), (x1, y1)]
            types = [T_START, T_LINE, T_LINE, T_LINE, T_CLOSE]
            close = False
        elif cmd == "triangle":
            pts = parse_pts(args)
            points = pts + [pts[0]]
            types = [T_START] + [T_LINE] * (len(pts) - 1) + [T_CLOSE]
            close = False
        elif cmd == "polyline":
            pts = parse_pts(args)
            points = pts
            types = [T_START] + [T_LINE] * (len(pts) - 1)
            close = False
        else:
            print(__doc__)
            return 1

        print(f"points={points}")
        print(f"types ={[hex(t) for t in types]}")
        r = create_path(ee, points, types, close)
        print(f"CreateFromPathData -> {r}")
        shape = r.get("ret")
        if not shape or shape == "0x0":
            print("shape creation failed")
            return 3

        v = ee.rpc("readU32", shape)
        print(f"new shape {shape} vtable={hex(v) if v else None}")
        print(ee.rpc("hexdump", shape, 96))

        print(f"AddItem -> {add_to_canvas(ee, canvas, shape)}")
        print(f"SetModifiedFlags -> {ee.rpc('call', CANVAS_SET_MODIFIED, 'void', ['int'], canvas, [1], 'thiscall')}")
        print(f"redrawAll -> {ee.rpc('redrawAll')}")
    finally:
        ee.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
