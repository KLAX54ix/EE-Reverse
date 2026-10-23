#!/usr/bin/env python3
"""Identify and dissect shape objects created by real EE drawing operations."""
import json
import sys

sys.path.insert(0, r"D:\EE Reverse\bridge")
from ee_client import EE, VT  # noqa: E402

CANVAS = "0xa7729a8"          # ecx of esCanvas::AddItem during capture
SHAPES = {
    "line(0x4701)": "0x10562768",
    "rect(0x4281)": "0x10564568",
}
GET_SHAPE_LIST = "?GetShapeList@esCanvas@@QAEPAVesShapeList@@XZ"
GET_COUNT = "?GetCount@esShapeList@@QBEHXZ"
GET_ACTIVE_CANVAS = "?GetActiveCanvas@esPageList@@QBEPAVesCanvas@@H@Z"


def main():
    ee = EE()
    try:
        vts = ee.rpc("vtables")
        rev = {}
        for name, addr in vts.items():
            cls = name[len("??_7"):].split("@@")[0]
            rev.setdefault(addr.lower(), cls)

        print("=== shape identity ===")
        for label, ptr in SHAPES.items():
            v = ee.rpc("readU32", ptr)
            cls = rev.get(hex(v), f"<unknown vtable {hex(v) if v else None}>")
            print(f"  {label:<16} ptr={ptr}  vtable={hex(v) if v else None}  class={cls}")

        print("\n=== shape memory (first 160 bytes) ===")
        for label, ptr in SHAPES.items():
            print(f"  --- {label} ---")
            print(ee.rpc("hexdump", ptr, 160))

        print("\n=== canvas shape list ===")
        r = ee.rpc("call", GET_SHAPE_LIST, "pointer", [], CANVAS, [], "thiscall")
        print(f"  esCanvas::GetShapeList(canvas={CANVAS}) -> {r}")
        lst = r.get("ret")
        if lst and lst != "0x0":
            c = ee.rpc("call", GET_COUNT, "int", [], lst, [], "thiscall")
            print(f"  esShapeList::GetCount({lst}) -> {c}")

        print("\n=== all live esSegLine / esSegRect vtables (recount) ===")
        for cls in ("esSegLine", "esSegRect", "esSegPolygon", "esSegArc"):
            n = ee.rpc("instances", VT[cls], 500)["count"]
            print(f"  {cls}: {n}")
    finally:
        ee.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
