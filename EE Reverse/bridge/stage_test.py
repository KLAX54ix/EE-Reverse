#!/usr/bin/env python3
"""Bisect where the EE bridge dies: Frida allocator vs engine calls.

Each stage prints before running so the last printed line identifies the
crashing stage even when the process dies.
"""
import sys
import time

sys.path.insert(0, r"D:\EE Reverse\bridge")
from ee_client import EE, VT  # noqa: E402


def alive(ee, tag):
    try:
        return ee.rpc("info")["pid"]
    except Exception as e:
        print(f"  [{tag}] TARGET LOST: {type(e).__name__}: {e}")
        return None


def main():
    ee = EE()
    try:
        print(f"stage 0: attached, pid={ee.rpc('info')['pid']}")

        print("stage 1: Frida Memory.alloc(64)")
        a = ee.rpc("alloc", 64)
        print(f"  alloc -> {a}")

        print("stage 2: writeI32 into Frida allocation")
        ee.rpc("writeI32", a, 0x1234)
        print(f"  readI32 -> {hex(ee.rpc('readI32', a) or 0)}")

        print("stage 3: resolve msvcp140.dll!??2@YAPAXI@Z (operator new)")
        opnew = ee.rpc("expOf", "msvcp140.dll", "??2@YAPAXI@Z")
        print(f"  operator new -> {opnew}")

        print("stage 4: engine-side allocation via operator new")
        r = ee.rpc("callfn", "msvcp140.dll", "??2@YAPAXI@Z", "pointer",
                   ["int"], [256], "sysv")
        print(f"  -> {r}")

        print("stage 5: write into engine-side allocation")
        if r.get("ret") and r["ret"] != "0x0":
            ee.rpc("writeI32", r["ret"], 0x5678)
            print(f"  readI32 -> {hex(ee.rpc('readI32', r['ret']) or 0)}")

        print("stage 6: find active canvas")
        lists = ee.rpc("instances", VT["esPageList"], 8)["addresses"]
        print(f"  pageLists={lists}")
        canvas = None
        for a2 in lists:
            rr = ee.rpc("call", "?GetActiveCanvas@esPageList@@QBEPAVesCanvas@@H@Z",
                        "pointer", ["int"], a2, [0], "thiscall")
            print(f"    GetActiveCanvas({a2}) -> {rr}")
            if rr.get("ret") and rr["ret"] != "0x0":
                canvas = rr["ret"]
                break
        print(f"  canvas={canvas}")

        print("stage 7: CreateFromPathData (no AddItem)")
        base = int(ee.rpc("info")["eslibBase"], 16)
        pts = r["ret"]
        pts2 = ee.rpc("callfn", "msvcp140.dll", "??2@YAPAXI@Z", "pointer",
                      ["int"], [64], "sysv")["ret"]
        tys = ee.rpc("callfn", "msvcp140.dll", "??2@YAPAXI@Z", "pointer",
                     ["int"], [16], "sysv")["ret"]
        for i, (x, y) in enumerate([(12000, 17000), (22000, 17000),
                                    (17000, 23000), (12000, 17000)]):
            ee.rpc("writeI32", hex(int(pts2, 16) + i * 8), x)
            ee.rpc("writeI32", hex(int(pts2, 16) + i * 8 + 4), y)
        for i, t in enumerate([0x00, 0x01, 0x01, 0x80]):
            ee.rpc("writeU8", hex(int(tys, 16) + i), t)
        print("  buffers written")
        r2 = ee.rpc("calladdr", hex(base + 0x19FA10), "pointer",
                    ["pointer", "pointer", "int", "int"], [pts2, tys, 4, 0], "sysv")
        print(f"  CreateFromPathData -> {r2}")
        if r2.get("ret") and r2["ret"] != "0x0":
            print(ee.rpc("hexdump", r2["ret"], 96))

        print(f"still alive? pid={alive(ee, 'end')}")
    finally:
        try:
            ee.close()
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
