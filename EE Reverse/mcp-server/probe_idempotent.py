#!/usr/bin/env python3
"""Idempotency probe: repeated esSegLable::Build must not grow the label.

Old failure mode: Build re-appended text items and/or re-layout inked garbage.
Now Build -> RecalcLayoutLable -> esText::ClearAllContent -> append N chars,
so item count must stay == char count across repeated Builds.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from smoke_test import MCP  # noqa: E402


def read_items(m, seg):
    b = int(seg, 16)
    return m.call("ee_diag", {"op": "readu32",
                              "args": {"addr": hex(b + 0xB0)}}).get("value")


def main():
    cv = sys.argv[1] if len(sys.argv) > 1 else None
    m = MCP()
    if not cv:
        cv = m.call("ee_canvases").get("chosen")
    print("canvas:", cv)
    r = m.call("ee_draw_label", {"text": "ABC", "x": 5000, "y": 9000,
                                 "canvas": cv})
    res = r.get("result") or {}
    seg = res.get("seg")
    print("created:", seg, "steps:", res.get("steps"))
    print("items after create:", read_items(m, seg))
    for i in range(3):
        bld = m.call("ee_diag", {"op": "call",
                                 "args": {"name": "?Build@esSegLable@@MAEXH@Z",
                                          "ret": "void", "argTypes": ["int"],
                                          "selfPtr": seg, "args": [1],
                                          "abi": "thiscall"}})
        print("build", i + 1, "->", json.dumps(bld)[:120],
              "items:", read_items(m, seg))
    st = m.call("ee_diag", {"op": "call",
                            "args": {"name": "?RecalcLayout@esSegLable@@MAEXXZ",
                                     "ret": "void", "argTypes": [],
                                     "selfPtr": seg, "args": [],
                                     "abi": "thiscall"}})
    print("recalc ->", json.dumps(st)[:120], "items:", read_items(m, seg))
    print("redraw:", json.dumps(m.call("ee_redraw"), ensure_ascii=False))
    m.close()


if __name__ == "__main__":
    main()
