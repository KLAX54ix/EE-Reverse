#!/usr/bin/env python3
"""Walk the active canvas and reveal each shape's child objects (segments)."""
import sys

sys.path.insert(0, r"D:\EE Reverse\bridge")
from ee_client import EE, VT  # noqa: E402

GET_ACTIVE_CANVAS = "?GetActiveCanvas@esPageList@@QBEPAVesCanvas@@H@Z"
CANVAS_HEAD = 0x38
SHAPE_NEXT = 0x48
SHAPE_SEGLIST = 0x60      # from CreateFromPathData: shape+0x60 is the seg list


def walk_children(ee, rev, addr, limit=0x90):
    """Report plausible object pointers inside [addr, addr+limit)."""
    out = []
    for off in range(0, limit, 4):
        try:
            v = ee.rpc("readU32", hex(addr + off))
        except Exception:
            continue
        if not v or v < 0x10000 or v > 0x7FFFFFFF:
            continue
        try:
            t = ee.rpc("readU32", hex(v))
        except Exception:
            continue
        if t and hex(t) in rev:
            out.append((off, v, rev[hex(t)]))
    return out


def main():
    ee = EE()
    try:
        vts = ee.rpc("vtables")
        rev = {}
        for name, a in vts.items():
            rev.setdefault(a.lower(), name[len("??_7"):].split("@@")[0])

        canvas = None
        for pl in ee.rpc("instances", VT["esPageList"], 16)["addresses"]:
            r = ee.rpc("call", GET_ACTIVE_CANVAS, "pointer", ["int"], pl, [0],
                       "thiscall")
            if r.get("ret") and r["ret"] != "0x0":
                canvas = r["ret"]
        print(f"canvas = {canvas}")
        if not canvas:
            return 2

        head = ee.rpc("readU32", hex(int(canvas, 16) + CANVAS_HEAD))
        print(f"head shape = {hex(head) if head else None}\n")

        idx, seen = 0, set()
        while head and head not in seen and idx < 40:
            seen.add(head)
            vt = ee.rpc("readU32", hex(head))
            cls = rev.get(hex(vt), f"<{hex(vt) if vt else None}>")
            print(f"[{idx}] shape {hex(head)}  class={cls}")
            kids = walk_children(ee, rev, head, 0x8C)
            for off, ptr, kcls in kids:
                print(f"      +0x{off:02x} -> {hex(ptr)}  {kcls}")
            seg = ee.rpc("readU32", hex(head + SHAPE_SEGLIST))
            print(f"      +0x60 seglist = {hex(seg) if seg else None}")
            if seg and seg > 0x10000:
                svt = ee.rpc("readU32", hex(seg))
                print(f"           seglist class = "
                      f"{rev.get(hex(svt), hex(svt) if svt else None)}")
                for off, ptr, kcls in walk_children(ee, rev, seg, 0x60):
                    print(f"           +0x{off:02x} -> {hex(ptr)}  {kcls}")
            nxt = ee.rpc("readU32", hex(head + SHAPE_NEXT))
            head = nxt if nxt and nxt > 0x10000 else None
            idx += 1
    finally:
        ee.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
