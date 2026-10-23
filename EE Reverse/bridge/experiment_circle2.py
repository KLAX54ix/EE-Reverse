#!/usr/bin/env python3
"""Build a TRUE circle: esShapePath + esSegCircel, mirroring CreateFromPathData.

Layout learned from a live circle the user drew with the circle tool:
  esSegCircel +0x04 = 0x4284 (circle tool id)
              +0x08 = owning esSegList
              +0x68 = radius (float)
              +0x6C = angle  (float, default pi/2)
              +0x70 = center.x (float)
              +0x74 = center.y (float)
  esSegList   +0x34 / +0x38 = first / last seg
  esShapePath +0x40 = first seg, +0x60 = seg list, +0x34 = style (0x40700ff)
"""
import sys

sys.path.insert(0, r"D:\EE Reverse\bridge")
from ee_client import EE, VT  # noqa: E402

OPNEW = ("msvcrt.dll", "??2@YAPAXI@Z")
CTOR_CIRCEL = "??0esSegCircel@@QAE@VPointF@Gdiplus@@MMPAVMatrix@2@@Z"
AUTOINIT_CIRCEL = "?__autoclassinit2@esSegCircel@@QAEXI@Z"
CTOR_LIST = "??0esSegList@@QAE@XZ"
AUTOINIT_LIST = "?__autoclassinit2@esSegList@@QAEXI@Z"
CTOR_PATH = "??0esShapePath@@QAE@XZ"
AUTOINIT_PATH = "?__autoclassinit2@esShapePath@@QAEXI@Z"
LIST_ADDSEG = "?AddSegObject@esSegList@@QAEXPAVesSeg@@H@Z"
PATH_ADDSEGLIST = "?AddSegList@esShapePath@@QAEXPAVesSegList@@@Z"
ADD_ITEM = "?AddItem@esCanvas@@QAEXPAVesShapeBase@@H@Z"
RECALC = "?RecalcLayout@esShapePath@@MAEXXZ"
GET_ACTIVE_CANVAS = "?GetActiveCanvas@esPageList@@QBEPAVesCanvas@@H@Z"

SIZES = {"circel": 0x100, "list": 0x44, "path": 0x74}
CIRCLE_TOOL_ID = 0x4284


def alive(ee, tag):
    try:
        return ee.rpc("info")["pid"]
    except Exception as exc:
        print(f"  !! TARGET LOST after {tag}: {exc}")
        return None


def main():
    px, py, r = (int(v) for v in (sys.argv[1:4] if len(sys.argv) > 3
                                  else (17000, 17000, 6000)))
    ee = EE()
    try:
        print(f"pid={ee.rpc('info')['pid']}  new circle centre=({px},{py}) r={r}")

        canvas = None
        for pl in ee.rpc("instances", VT["esPageList"], 16)["addresses"]:
            got = ee.rpc("call", GET_ACTIVE_CANVAS, "pointer", ["int"], pl, [0],
                         "thiscall").get("ret")
            if got and got != "0x0":
                canvas = got
        print(f"canvas={canvas}")

        def opnew(n):
            res = ee.rpc("callfn", OPNEW[0], OPNEW[1], "pointer", ["int"], [n], "sysv")
            if not res.get("ret"):
                raise RuntimeError(f"operator new failed: {res}")
            return res["ret"]

        # ---- 1. segment object ----
        seg = opnew(SIZES["circel"])
        print(f"1) esSegCircel alloc -> {seg}")
        ee.rpc("call", AUTOINIT_CIRCEL, "void", ["int"], seg,
               [SIZES["circel"]], "thiscall")
        c = ee.rpc("call", CTOR_CIRCEL, "void",
                   ["float", "float", "float", "float", "pointer"], seg,
                   [float(px), float(py), float(r), 1.5707963, None], "thiscall")
        print(f"   ctor -> {c}")
        if not alive(ee, "esSegCircel ctor"):
            return 3
        ee.rpc("writeI32", hex(int(seg, 16) + 0x04), CIRCLE_TOOL_ID)
        print("   after ctor:")
        print(ee.rpc("hexdump", seg, 128))

        # ---- 2. segment list ----
        lst = opnew(SIZES["list"])
        ee.rpc("call", AUTOINIT_LIST, "void", ["int"], lst, [SIZES["list"]],
               "thiscall")
        ee.rpc("call", CTOR_LIST, "void", [], lst, [], "thiscall")
        print(f"2) esSegList -> {lst}")
        ee.rpc("call", LIST_ADDSEG, "void", ["pointer", "int"], lst,
               [seg, 1], "thiscall")
        if not alive(ee, "SegList::AddSegObject"):
            return 4

        # ---- 3. shape ----
        shape = opnew(SIZES["path"])
        ee.rpc("call", AUTOINIT_PATH, "void", ["int"], shape, [SIZES["path"]],
               "thiscall")
        ee.rpc("call", CTOR_PATH, "void", [], shape, [], "thiscall")
        ee.rpc("writeI32", hex(int(shape, 16) + 0x34), 0x040700FF)
        print(f"3) esShapePath -> {shape}")
        ee.rpc("call", PATH_ADDSEGLIST, "void", ["pointer"], shape, [lst],
               "thiscall")
        if not alive(ee, "ShapePath::AddSegList"):
            return 5

        # ---- 4. attach to canvas ----
        print(f"4) AddItem -> {ee.rpc('call', ADD_ITEM, 'void', ['pointer', 'int'], canvas, [shape, 1], 'thiscall')}")
        if not alive(ee, "AddItem"):
            return 6
        ee.rpc("call", RECALC, "void", [], shape, [], "thiscall")
        print("   shape after recalc:")
        print(ee.rpc("hexdump", shape, 128))
        print(f"   redraw -> {ee.rpc('redrawAll')}")
        print(f"   still alive pid={alive(ee, 'end')}")
    finally:
        try:
            ee.close()
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
