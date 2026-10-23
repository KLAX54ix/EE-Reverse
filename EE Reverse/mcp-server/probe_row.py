#!/usr/bin/env python3
"""Draw a visible multi-char label row on the chosen canvas for a screenshot."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from smoke_test import MCP  # noqa: E402


def main():
    cv = sys.argv[1] if len(sys.argv) > 1 else None
    m = MCP()
    if not cv:
        cv = m.call("ee_canvases").get("chosen")
    print("canvas:", cv)
    texts = ["A", "AB", "ABC", "A\u2032", "1\u2032", "x\u2081"]
    got = []
    for i, t in enumerate(texts):
        r = m.call("ee_draw_label", {"text": t, "x": 3000 + i * 4500,
                                     "y": 5000, "canvas": cv})
        res = r.get("result") or {}
        box = res.get("box") or {}
        got.append({"t": t,
                    "w": box.get("p2x", 0) - box.get("p1x", 0),
                    "cx": (box.get("p1x", 0) + box.get("p2x", 0)) // 2})
        print(json.dumps(got[-1], ensure_ascii=True))
    print("redraw:", json.dumps(m.call("ee_redraw"), ensure_ascii=False))
    m.close()


if __name__ == "__main__":
    main()
