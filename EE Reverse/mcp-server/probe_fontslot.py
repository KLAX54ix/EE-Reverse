#!/usr/bin/env python3
"""Live test: ee_fonts listing + automatic font-slot resolution.

Part 1: ee_fonts must list real faces (Times New Roman italic = the slot the
        user's "AY" style means), stopping before the invalid-slot fallback.
Part 2: on a canvas WITHOUT any label, ee_draw_label with no font_index must
        auto-resolve the face from the font sheet (fontIndexSource reports it)
        and the created label must contain one item per character.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from smoke_test import MCP  # noqa: E402


def items_of(m, seg):
    return m.call("ee_diag", {"op": "readu32",
                              "args": {"addr": hex(int(seg, 16) + 0xB0)}}).get("value")


def main():
    m = MCP()
    try:
        fonts = m.call("ee_fonts", {})
        print("== ee_fonts ==")
        print("sheet:", fonts.get("sheet"), "| reason:", fonts.get("reason"),
              "| stoppedAtRepeat:", fonts.get("stoppedAtRepeat"))
        for f in fonts.get("fonts") or []:
            print("  slot %2s  %-20s italic=%s bold=%s size=%s"
                  % (f.get("slot"), f.get("name"), f.get("italic"),
                     f.get("bold"), f.get("size")))

        cans = m.call("ee_canvases")
        ranked = cans.get("ranked") or []
        empty = None
        for r in ranked:
            if not r.get("shapeCount"):
                empty = r
                break
        print("\nempty canvas:", json.dumps(empty, ensure_ascii=False)
              if empty else "(none; falling back to lowest-ranked)")
        cv = (empty or {}).get("canvas") or (ranked[-1]["canvas"] if ranked else None)
        if not cv:
            print("no canvas at all -- abort")
            return

        for text in ("A", "AB"):
            r = m.call("ee_draw_label", {"text": text, "x": 2000, "y": 6000,
                                         "canvas": cv})
            res = r.get("result") or {}
            seg = res.get("seg")
            box = res.get("box") or {}
            print("\nlabel %r on %s" % (text, cv))
            print("  fontIndex:", r.get("fontIndex"),
                  "| source:", r.get("fontIndexSource"))
            print("  ok:", res.get("ok"), "| seg:", seg,
                  "| box:", json.dumps(box))
            if seg:
                print("  items(+0xB0):", items_of(m, seg),
                      "  expected:", len(text))
        print("\nredraw:", json.dumps(m.call("ee_redraw")))
    finally:
        m.close()


if __name__ == "__main__":
    main()
