#!/usr/bin/env python3
"""Decode esSegLable's vtable so we know what slot +0x80 is."""
import sys

sys.path.insert(0, r"D:\EE Reverse\bridge")
from ee_client import EE  # noqa: E402

ee = EE()
try:
    vt = ee.rpc("expaddr", "??_7esSegLable@@6B@")
    print("esSegLable vtable =", vt)
    if not vt:
        sys.exit(2)
    base = int(vt, 16)
    for i in range(40):
        a = ee.rpc("readU32", hex(base + i * 4))
        if not a:
            break
        nm = ee.rpc("expNameOf", hex(a))
        mark = "   <== +0x80 (EE calls this)" if i == 0x80 // 4 else ""
        print(f"  [{i:2d}] +0x{i*4:02x}  {hex(a)}  {nm}{mark}")
finally:
    ee.close()
