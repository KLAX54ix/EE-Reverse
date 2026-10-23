#!/usr/bin/env python3
"""Inspect the newest object in the active canvas list."""
import sys

sys.path.insert(0, r"D:\EE Reverse\bridge")
from ee_client import EE, VT  # noqa: E402

GET_ACTIVE_CANVAS = "?GetActiveCanvas@esPageList@@QBEPAVesCanvas@@H@Z"
MODS = {}


def classify(addr, mods):
    for name, (base, size) in mods.items():
        if base <= addr < base + size:
            return f"{name}+0x{addr - base:x}"
    return "?"


def main():
    ee = EE()
    try:
        mods = {}
        for m in ee.rpc("info").get("mainModule", "") and []:
            pass
        # module map
        info = ee.rpc("info")
        print("pid", info["pid"])

        canvas = None
        for pl in ee.rpc("instances", VT["esPageList"], 16)["addresses"]:
            got = ee.rpc("call", GET_ACTIVE_CANVAS, "pointer", ["int"], pl, [0],
                         "thiscall").get("ret")
            if got and got != "0x0":
                canvas = got
        print("canvas =", canvas)

        head = ee.rpc("readU32", hex(int(canvas, 16) + 0x38))
        print(f"head = {hex(head) if head else None}")
        print(ee.rpc("hexdump", hex(head), 96))

        vt = ee.rpc("readU32", hex(head))
        print(f"vtable = {hex(vt) if vt else None}")

        print("\nfirst vtable entries:")
        base = int(canvas, 16)
        for i in range(8):
            e = ee.rpc("readU32", hex(vt + i * 4)) if vt else None
            print(f"  [{i}] {hex(e) if e else None}")

        print("\nwalk list:")
        cur, n = head, 0
        while cur and n < 10:
            v = ee.rpc("readU32", hex(cur))
            print(f"  [{n}] {hex(cur)} vtable={hex(v) if v else None}")
            nxt = ee.rpc("readU32", hex(cur + 0x48))
            cur = nxt if nxt and nxt > 0x10000 else None
            n += 1
    finally:
        ee.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
