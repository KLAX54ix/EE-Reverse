#!/usr/bin/env python3
"""Audit canvases: identity (vtable) + shape-chain count.

Focus-free: pure engine memory reads via the bridge, safe while the user works.

Usage:
  python audit_canvases.py list                 # census: all TRULY live canvases
  python audit_canvases.py 0x8c7d508 0x1818ee8  # explicit handles

Notes:
  The process holds 500+ objects with the esCanvas vtable, but only canvases
  that went through layout have a non-zero +0xc8 rect (w/h > 0). `list` uses
  that filter because ee_canvases / canvasCandidates rankings are noisy
  (ghost objects get ranked alongside real canvases).
"""
import re
import sys

sys.path.insert(0, r"D:\EE Reverse\bridge")
from ee_client import EE  # noqa: E402

RECT = 0xC8


def rect_of(ee, h):
    """(left, top, right, bottom) from the cached rect at +0xc8, or None."""
    hx = ee.rpc("hexdump", hex(int(h, 16) + RECT), 16)
    m = re.search(r"^[0-9a-f]+  ((?:[0-9a-f]{2} ){16})", hx, re.M)
    if not m:
        return None
    b = bytes.fromhex(m.group(1).replace(" ", ""))
    return tuple(int.from_bytes(b[i:i + 4], "little", signed=True)
                 for i in (0, 4, 8, 12))


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    ee = EE()
    try:
        if argv[0] == "list":
            r = ee.rpc("instances", "??_7esCanvas@@6B@", 3000)
            addrs = r.get("addresses", [])
            live = []
            for h in addrs:
                try:
                    l, t, rt, bt = rect_of(ee, h)
                except Exception:
                    continue
                w, hh = rt - l, bt - t
                if w > 0 and hh > 0:
                    live.append((h, w, hh))
            print(f"scan: {len(addrs)} objects with the esCanvas vtable, "
                  f"{len(live)} laid out (w>0,h>0)")
            for h, w, hh in live:
                sc = ee.rpc("shapeCount", h)
                n = sc.get("count") if sc.get("ok") else None
                vt = ee.rpc("readU32", h)
                fts = ee.rpc("call", "?GetFrameType@esCanvas@@QBEKXZ", "uint",
                             [], h, [], "thiscall").get("ret")
                print(f"  {h}: {w}x{hh} vtable={hex(vt)} frameType={hex(fts) if fts else fts} "
                      f"shapes={n}")
            return 0

        vts = ee.rpc("vtables")
        rev = {}
        for name, addr in vts.items():
            cls = name[len("??_7"):].split("@@")[0]
            rev.setdefault(addr.lower(), cls)

        for c in argv:
            try:
                v = ee.rpc("readU32", c)
                cls = rev.get(hex(v), "<unknown>")
                r = ee.rpc("shapeCount", c)
                n = r.get("count") if r.get("ok") else None
                print(f"{c}: vtable={hex(v)} ({cls}) shapes={n}")
            except Exception as exc:
                print(f"{c}: ERROR {exc}")
    finally:
        ee.close()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
