#!/usr/bin/env python3
"""Live test for the native canvas insert (esTextUI::InsertCanvas 2-arg path).

Reverse-engineered 2026-10; see the insertCanvasNative() comment in
ee_bridge.js. This replaces the Space+G keyboard simulation.

Usage:
  python probe_native_insert.py status          # caret/UI state, no writes
  python probe_native_insert.py dry             # build+measure canvas, no insert
  python probe_native_insert.py insert [w h]    # insert at the CURRENT CARET

Before `insert`: save the document (Ctrl+S) and click the caret into the page
text (IsValid must be 1); Ctrl+Z in the editor can undo the test canvas.
"""
import json
import sys

sys.path.insert(0, r"D:\EE Reverse\bridge")
from ee_client import EE  # noqa: E402


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    mode = sys.argv[1]
    ee = EE()
    try:
        if mode == "status":
            out = {
                "liveTextUI": ee.rpc("liveTextUI"),
                "caretContext": ee.rpc("caretContext"),
                "caretCanvas": ee.rpc("caretCanvas"),
            }
        elif mode == "dry":
            out = ee.rpc("insertCanvasNative", None, None, None,
                         {"dryRun": True})
        elif mode == "insert":
            w = int(sys.argv[2]) if len(sys.argv) > 2 else None
            h = int(sys.argv[3]) if len(sys.argv) > 3 else None
            out = ee.rpc("insertCanvasNative", None, w, h, {})
        else:
            print(__doc__)
            return 1
        print(json.dumps(out, indent=2))
    finally:
        ee.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
