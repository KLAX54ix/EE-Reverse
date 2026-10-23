#!/usr/bin/env python3
"""Discover the live document -> page -> canvas path inside EE.

Only calls methods on objects whose class is known, so `this` is always valid.
"""
import json
import sys

sys.path.insert(0, r"D:\EE Reverse\bridge")
from ee_client import EE, VT  # noqa: E402

EXPORTS = {
    "pageList_GetActiveCanvas_i": "?GetActiveCanvas@esPageList@@QBEPAVesCanvas@@H@Z",
    "pageList_GetCanvasList": "?GetCanvasList@esPageList@@QBEPAVesCanvasList@@XZ",
    "pageList_GetActiveGPage": "?GetActiveGPage@esPageList@@QBEHXZ",
    "pageList_GetDocument": "?GetDocument@esPageList@@QBEPAVesBaseDoc@@XZ",
    "base_GetActiveCanvas": "?GetActiveCanvas@esBaseDoc@@QBEPAVesCanvas@@XZ",
    "base_GetPage_i": "?GetPage@esBaseDoc@@QBEPAVesDocPage@@H@Z",
    "base_GetViewType": "?GetViewType@esBaseDoc@@QBEGXZ",
    "canvas_GetActive": "?GetActive@esCanvas@@QBEPAVesShapeBase@@XZ",
    "pageList_GetPageMode": "?GetPageMode@esPageList@@QBEHXZ",
}


def show(label, res):
    if res.get("error"):
        print(f"    {label}: ERROR {res['error']}")
    else:
        print(f"    {label}: {res.get('ret')}")


def call(ee, name, ret, self_ptrs, argtypes=None, args=None, abi="thiscall"):
    out = {}
    for a in self_ptrs:
        r = ee.rpc("call", EXPORTS[name], ret, argtypes or [], a, args or [], abi)
        out[a] = r
    return out


def main():
    ee = EE()
    try:
        docs = ee.rpc("instances", VT["esDocument"], 12)["addresses"]
        lists = ee.rpc("instances", VT["esPageList"], 12)["addresses"]
        canvases = ee.rpc("instances", VT["esCanvas"], 200)["addresses"]
        print(f"docs={len(docs)} pageLists={len(lists)} canvases={len(canvases)}")

        print("\n[1] esPageList::GetDocument")
        for a, r in call(ee, "pageList_GetDocument", "pointer", lists).items():
            show(a, r)

        print("\n[2] esPageList::GetCanvasList")
        for a, r in call(ee, "pageList_GetCanvasList", "pointer", lists).items():
            show(a, r)

        print("\n[3] esPageList::GetActiveCanvas(int idx)")
        for idx in (0, 1, 2):
            print(f"  -- idx={idx}")
            for a, r in call(ee, "pageList_GetActiveCanvas_i", "pointer", lists,
                             ["int"], [idx]).items():
                show(a, r)

        print("\n[4] esPageList::GetPageMode / GetActiveGPage")
        show("mode", next(iter(call(ee, "pageList_GetPageMode", "int", lists).values())))
        show("gpage", next(iter(call(ee, "pageList_GetActiveGPage", "int", lists).values())))

        print("\n[5] esBaseDoc::GetPage(int)")
        for idx in (0, 1):
            print(f"  -- idx={idx}")
            for a, r in call(ee, "base_GetPage_i", "pointer", docs,
                             ["int"], [idx]).items():
                show(a, r)

        print("\n[6] esCanvas::GetActive() on first canvases")
        for a, r in list(call(ee, "canvas_GetActive", "pointer",
                              canvases[:6]).items()):
            show(a, r)
    finally:
        ee.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
