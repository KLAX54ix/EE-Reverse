#!/usr/bin/env python3
"""Map every candidate drawing canvas so canvas selection can be made deterministic.

Read-only except for GetActiveCanvas/GetWidth/GetHeight/GetActivePPage/GetUI, which
are pure accessors. Walks each canvas' intrusive shape list to count primitives.

Usage:  python probe_canvas2.py
"""
import sys

sys.path.insert(0, r"D:\EE Reverse\bridge")
from ee_client import EE, VT  # noqa: E402

GET_ACTIVE_CANVAS_PL = "?GetActiveCanvas@esPageList@@QBEPAVesCanvas@@H@Z"
GET_ACTIVE_CANVAS_DOC = "?GetActiveCanvas@esBaseDoc@@QBEPAVesCanvas@@XZ"
GET_WIDTH = "?GetWidth@esCanvas@@QBEHXZ"
GET_HEIGHT = "?GetHeight@esCanvas@@QBEHXZ"
GET_ACTIVE_PPAGE = "?GetActivePPage@esPageList@@QBEHXZ"
GET_DOCUMENT = "?GetDocument@esPageList@@QBEPAVesBaseDoc@@XZ"
GET_UI = "?GetUI@esPageList@@QBEPAVesTextUI@@XZ"

CANVAS_HEAD = 0x38
SHAPE_NEXT = 0x48
DOC_PPL = 0xD00


def call_ret(ee, export, ret, argv, self_ptr, abi="thiscall"):
    try:
        return ee.rpc("call", export, ret, argv, self_ptr, [], abi).get("ret")
    except Exception as exc:
        return f"<err {exc}>"


def walk_shapes(ee, cv, limit=2000):
    """Return (count, first_vtables) by following canvas+0x38 then shape+0x48."""
    head = ee.rpc("readU32", hex(cv + CANVAS_HEAD))
    seen = set()
    vts = []
    n = 0
    while head and head > 0x10000 and head not in seen and n < limit:
        seen.add(head)
        vt = ee.rpc("readU32", hex(head))
        vts.append(vt)
        n += 1
        nxt = ee.rpc("readU32", hex(head + SHAPE_NEXT))
        head = nxt if nxt and nxt > 0x10000 else 0
    return n, vts


def main():
    ee = EE()
    try:
        print(f"pid={ee.rpc('info')['pid']}")

        docs = ee.rpc("instances", VT["esDocument"], 8)["addresses"]
        pls = ee.rpc("instances", VT["esPageList"], 16)["addresses"]
        print(f"esDocument x{len(docs)}: {docs}")
        print(f"esPageList x{len(pls)}: {pls}")

        print("\n== esBaseDoc::GetActiveCanvas ==")
        for d in docs:
            cv = call_ret(ee, GET_ACTIVE_CANVAS_DOC, "pointer", ["pointer"], d)
            print(f"  doc {d} -> {cv}")
            inner = ee.rpc("readU32", hex(int(d, 16) + DOC_PPL))
            print(f"      +0xD00 pageList = {hex(inner) if inner else None}")

        print("\n== esPageList detail ==")
        print(f"  {'pageList':>10} {'activeCanvas':>14} {'width':>8} {'height':>8} "
              f"{'pPage':>6} {'shapes':>7}  doc")
        for pl in pls:
            cv = call_ret(ee, GET_ACTIVE_CANVAS_PL, "pointer", ["pointer", "int"], pl)
            doc = call_ret(ee, GET_DOCUMENT, "pointer", ["pointer"], pl)
            ui = call_ret(ee, GET_UI, "pointer", ["pointer"], pl)
            ppage = call_ret(ee, GET_ACTIVE_PPAGE, "int", ["pointer"], pl)
            w = h = n = None
            if isinstance(cv, str) and cv.startswith("0x") and cv != "0x0":
                w = call_ret(ee, GET_WIDTH, "int", ["pointer"], cv)
                h = call_ret(ee, GET_HEIGHT, "int", ["pointer"], cv)
                n, _ = walk_shapes(ee, int(cv, 16))
            print(f"  {pl:>10} {str(cv):>14} {str(w):>8} {str(h):>8} "
                  f"{str(ppage):>6} {str(n):>7}  doc={doc} ui={ui}")

        print("\n== every esCanvas, by shape count ==")
        canvases = ee.rpc("instances", VT["esCanvas"], 400)["addresses"]
        print(f"esCanvas total instances found: {len(canvases)}")
        rows = []
        for cv in canvases:
            n, vts = walk_shapes(ee, int(cv, 16), limit=2000)
            if n:
                w = call_ret(ee, GET_WIDTH, "int", ["pointer"], cv)
                rows.append((n, cv, w, vts[:6]))
        rows.sort(reverse=True)
        for n, cv, w, vts in rows[:20]:
            print(f"  shapes={n:>4} canvas={cv} width={w} first_vtables="
                  + ",".join(hex(v) if v else "None" for v in vts))
        if not rows:
            print("  (no canvas has any shapes)")
    finally:
        try:
            ee.close()
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
