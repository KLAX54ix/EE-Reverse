#!/usr/bin/env python3
"""Second label attempt: esShapeLine wrapper + esSegLable + Initialize(fontSheet)."""
import sys

sys.path.insert(0, r"D:\EE Reverse\bridge")
from ee_client import EE, VT  # noqa: E402

GET_ACTIVE_CANVAS = "?GetActiveCanvas@esPageList@@QBEPAVesCanvas@@H@Z"
ADD_ITEM = "?AddItem@esCanvas@@QAEXPAVesShapeBase@@H@Z"
RECALC = "?RecalcLayout@esShapePath@@MAEXXZ"


def alive(ee, tag):
    try:
        return ee.rpc("info")["pid"]
    except Exception as exc:
        print(f"  !! TARGET LOST after {tag}: {exc}")
        return None


def main():
    text = sys.argv[1] if len(sys.argv) > 1 else "A"
    x = int(sys.argv[2]) if len(sys.argv) > 2 else 25200
    y = int(sys.argv[3]) if len(sys.argv) > 3 else 22800
    ee = EE()
    try:
        print(f"pid={ee.rpc('info')['pid']}  label={text!r} at ({x},{y})")

        fs = ee.rpc("findInstance", "??_7esFontSheet@@6B@")
        print(f"fontSheet -> {fs}")
        if not fs.get("ok"):
            print("no font sheet; trying NULL")
            fsp = "0x0"
        else:
            fsp = fs["addr"]

        canvas = None
        for pl in ee.rpc("instances", VT["esPageList"], 16)["addresses"]:
            got = ee.rpc("call", GET_ACTIVE_CANVAS, "pointer", ["int"], pl, [0],
                         "thiscall").get("ret")
            if got and got != "0x0":
                canvas = got
        print(f"canvas={canvas}")

        r = ee.rpc("makeLabelShape", text, x, y, fsp)
        print(f"makeLabelShape -> {r}")
        if not r.get("ok"):
            return 3
        if not alive(ee, "makeLabelShape"):
            return 4
        print("  shape dump:")
        print(ee.rpc("hexdump", r["shape"], 112))

        print(f"AddItem -> {ee.rpc('call', ADD_ITEM, 'void', ['pointer', 'int'], canvas, [r['shape'], 1], 'thiscall')}")
        if not alive(ee, "AddItem"):
            return 5
        print("  after AddItem:")
        print(ee.rpc("hexdump", r["shape"], 112))
        print(f"redraw -> {ee.rpc('redrawAll')}")
        print(f"alive pid={alive(ee, 'end')}")
    finally:
        try:
            ee.close()
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
