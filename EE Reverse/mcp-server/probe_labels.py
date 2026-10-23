#!/usr/bin/env python3
"""Focused probe: multi-char / math-glyph label rendering on the current
canvas.  Draws a row of labels in the visible region and prints raw results.
"""
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from smoke_test import MCP  # noqa: E402


def main():
    cv = sys.argv[1] if len(sys.argv) > 1 else None
    m = MCP()
    if not cv:
        cv = m.call("ee_canvases").get("chosen")
    print("canvas:", cv)
    tests = [
        ("AB", 4500, 4500),
        ("\u2299O", 6500, 4500),
        ("A\u2032", 8500, 4500),
        ("\u03b1", 10500, 4500),
        ("\u25b3ABC", 13000, 4500),
    ]
    for text, x, y in tests:
        r = m.call("ee_draw_label", {"text": text, "x": x, "y": y,
                                     "canvas": cv})
        keep = {k: r.get(k) for k in
                ("shape", "fontIndex", "fontIndexSource", "variant")}
        res = r.get("result") or {}
        keep["ok"] = res.get("ok")
        keep["err"] = res.get("error")
        keep["steps"] = res.get("steps")
        keep["box"] = res.get("box")
        print(json.dumps({text: keep}, ensure_ascii=False))
    print("redraw:", json.dumps(m.call("ee_redraw"), ensure_ascii=False))
    m.close()


if __name__ == "__main__":
    main()
