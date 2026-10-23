#!/usr/bin/env python3
"""Staged, self-verifying programmatic draw into EE.

Each step checks the target is still alive before continuing, so a failure
identifies the exact call rather than the whole pipeline.
"""
import sys

sys.path.insert(0, r"D:\EE Reverse\bridge")
from ee_client import EE, VT  # noqa: E402

CREATE_FROM_PATH_DATA_RVA = 0x19FA10
ADD_ITEM = "?AddItem@esCanvas@@QAEXPAVesShapeBase@@H@Z"
PAGE_GET_ACTIVE_CANVAS = "?GetActiveCanvas@esPageList@@QBEPAVesCanvas@@H@Z"

T_START, T_LINE, T_CLOSE = 0x00, 0x01, 0x80


class Staged:
    def __init__(self):
        self.ee = EE()
        self.base = int(self.ee.rpc("info")["eslibBase"], 16)

    def step(self, name):
        pid = self.ee.rpc("info")["pid"]
        print(f"  [ok] {name}  (pid={pid})")

    def canvas(self):
        best, best_list = None, None
        for a in self.ee.rpc("instances", VT["esPageList"], 12)["addresses"]:
            r = self.ee.rpc("call", PAGE_GET_ACTIVE_CANVAS, "pointer", ["int"],
                            a, [0], "thiscall")
            if r.get("ret") and r["ret"] != "0x0":
                best, best_list = r["ret"], a
        return best, best_list

    def make_path(self, points, types, close=0):
        n = len(points)
        pts = self.ee.rpc("alloc", n * 8)
        tys = self.ee.rpc("alloc", max(1, n))
        p = int(pts, 16)
        for i, (x, y) in enumerate(points):
            self.ee.rpc("writeI32", hex(p + i * 8), int(x))
            self.ee.rpc("writeI32", hex(p + i * 8 + 4), int(y))
        t = int(tys, 16)
        for i, v in enumerate(types):
            self.ee.rpc("writeU8", hex(t + i), v)
        print(f"    buffers: pts={pts} tys={tys} n={n}")
        return self.ee.rpc("calladdr", hex(self.base + CREATE_FROM_PATH_DATA_RVA),
                           "pointer", ["pointer", "pointer", "int", "int"],
                           [pts, tys, n, close], "sysv")

    def add(self, canvas, shape, flags=1):
        return self.ee.rpc("call", ADD_ITEM, "void", ["pointer", "int"],
                           canvas, [shape, flags], "thiscall")

    def close(self):
        try:
            self.ee.close()
        except Exception:
            pass


def main():
    want = sys.argv[1] if len(sys.argv) > 1 else "triangle"
    s = Staged()
    try:
        s.step("attached + eslib base resolved")
        canvas, plist = s.canvas()
        print(f"  canvas={canvas} (pageList={plist})")
        if not canvas:
            print("no active canvas"); return 2
        s.step("active canvas resolved")

        print("  creating esShapePath via CreateFromPathData ...")
        if want == "line":
            pts = [(12000, 20000), (24000, 20000)]
            tys = [T_START, T_LINE]
        else:
            pts = [(12000, 17000), (22000, 17000), (17000, 23000), (12000, 17000)]
            tys = [T_START, T_LINE, T_LINE, T_CLOSE]
        r = s.make_path(pts, tys, close=0)
        print(f"    -> {r}")
        shape = r.get("ret")
        if not shape or shape == "0x0":
            print("  shape creation returned null"); return 3
        s.step("esShapePath created")
        print(s.ee.rpc("hexdump", shape, 96))

        v = s.ee.rpc("readU32", shape)
        print(f"    new shape vtable = {hex(v) if v else None} "
              f"(esShapePath={VT['esShapePath']} runtime)")

        ar = s.add(canvas, shape, 1)
        print(f"  AddItem -> {ar}")
        s.step("AddItem done")

        print(f"  redrawAll -> {s.ee.rpc('redrawAll')}")
        s.step("redraw requested")
    finally:
        s.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
