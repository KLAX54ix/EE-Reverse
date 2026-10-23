#!/usr/bin/env python3
"""Inspect a created label's text and layout state."""
import sys

sys.path.insert(0, r"D:\EE Reverse\bridge")
from ee_client import EE  # noqa: E402

seg = int(sys.argv[1], 16) if len(sys.argv) > 1 else 0x3203068

ee = EE()
try:
    buf = ee.rpc("readU32", hex(seg + 0x70))
    ln = ee.rpc("readI32", hex(seg + 0x74))
    cap = ee.rpc("readI32", hex(seg + 0x78))
    print(f"esSegText {hex(seg)}")
    print(f"  zwstr @+0x70 = {{ptr={hex(buf) if buf else None}, len={ln}, f3={cap}}}")
    if buf:
        print(f"  text = {ee.rpc('readStr', hex(buf), True)!r}")
    for off in (0x04, 0x08, 0x0C, 0x7C, 0x80, 0x84, 0x88, 0x8C, 0x90):
        print(f"  +0x{off:02x} = {ee.rpc('readI32', hex(seg + off))}")
finally:
    ee.close()
