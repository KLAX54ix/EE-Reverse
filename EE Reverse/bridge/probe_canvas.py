#!/usr/bin/env python3
"""Find the real, laid-out canvas in the open EE document."""
import sys

sys.path.insert(0, r"D:\EE Reverse\bridge")
from ee_client import EE, VT  # noqa: E402

GET_ACTIVE_CANVAS = "?GetActiveCanvas@esPageList@@QBEPAVesCanvas@@H@Z"
GET_DOC = "?GetDocument@esPageList@@QBEPAVesBaseDoc@@XZ"
W = "?GetWidth@esCanvas@@QBEHXZ"
H = "?GetHeight@esCanvas@@QBEHXZ"
FR = "?GetFrameRect@esCanvas@@QAEABVzRect@@XZ"


def main():
    ee = EE()
    try:
        info = ee.rpc("info")
        print(f"pid={info['pid']} eslib={info['eslibBase']}")

        vts = ee.rpc("vtables")
        rev = {}
        for name, addr in vts.items():
            rev.setdefault(addr.lower(), name[len("??_7"):].split("@@")[0])

        lists = ee.rpc("instances", VT["esPageList"], 20)["addresses"]
        print(f"\npageLists ({len(lists)}):")
        acts = []
        for pl in lists:
            a = ee.rpc("call", GET_ACTIVE_CANVAS, "pointer", ["int"], pl, [0],
                       "thiscall").get("ret")
            d = ee.rpc("call", GET_DOC, "pointer", [], pl, [], "thiscall").get("ret")
            print(f"  {pl} -> canvas={a} doc={d}")
            if a and a != "0x0":
                acts.append(a)

        canvases = ee.rpc("instances", VT["esCanvas"], 400)["addresses"]
        print(f"\nesCanvas instances: {len(canvases)}")

        def probe(addr, tag):
            w = ee.rpc("call", W, "int", [], addr, [], "thiscall").get("ret")
            h = ee.rpc("call", H, "int", [], addr, [], "thiscall").get("ret")
            fr = ee.rpc("call", FR, "pointer", [], addr, [], "thiscall").get("ret")
            rect = None
            if fr and fr != "0x0":
                b = int(fr, 16)
                rect = [ee.rpc("readI32", hex(b + i * 4)) for i in range(4)]
            vt = ee.rpc("readU32", addr)
            cls = rev.get(hex(vt), f"<{hex(vt) if vt else None}>")
            print(f"  [{tag}] {addr} w={w} h={h} rect={rect} class={cls}")
            return w, h

        print("\ngetActiveCanvas results:")
        for a in acts:
            probe(a, "active")

        print("\nall canvases with w>0:")
        found = 0
        for c in canvases:
            w = ee.rpc("call", W, "int", [], c, [], "thiscall").get("ret")
            if w and w > 0:
                probe(c, "scan")
                found += 1
                if found >= 12:
                    break
        print(f"  ({found} shown)")
    finally:
        ee.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
