#!/usr/bin/env python3
"""Verify multi-char labels end-to-end AFTER the char-count fix.

Phase A (label tool): draw A / AB / ABC via ee_draw_label on a clean row.
Phase B (figure tool): same texts via ee_draw_figure (no +0xB0 override now).
Reads back: box width per label, EQLine +0x30 item count, +0x84 format word,
and the seg char count byte (+0x70).
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from smoke_test import MCP  # noqa: E402


def seg_fields(m, seg):
    b = int(seg, 16)
    return {
        "charCount70": (m.call("ee_diag", {"op": "readu32",
                                           "args": {"addr": hex(b + 0x70)}})
                        .get("value", 0)),
        "eqlineItems30": (m.call("ee_diag", {"op": "readu32",
                                             "args": {"addr": hex(b + 0xB0)}})
                          .get("value", 0)),
        "eqlineFmt84": (m.call("ee_diag", {"op": "readu32",
                                           "args": {"addr": hex(b + 0x84)}})
                        .get("value", 0)),
    }


def main():
    cv = sys.argv[1] if len(sys.argv) > 1 else None
    m = MCP()
    if not cv:
        cv = m.call("ee_canvases").get("chosen")
    print("canvas:", cv)

    print("\n-- ee_draw_label --")
    for i, t in enumerate(["A", "AB", "ABC", "A\u2032"]):
        r = m.call("ee_draw_label", {"text": t, "x": 4500 + i * 6000,
                                     "y": 34000, "canvas": cv})
        res = r.get("result") or {}
        seg = res.get("seg")
        box = res.get("box") or {}
        rec = {"text": t, "shape": res.get("shape"),
               "boxW": box.get("p2x", 0) - box.get("p1x", 0)}
        if seg:
            rec.update(seg_fields(m, seg))
        print(json.dumps(rec, ensure_ascii=False))

    print("\n-- ee_draw_figure --")
    r = m.call("ee_draw_figure", {
        "canvas": cv, "apply_pen": False, "apply_lable_style": False,
        "labels": [{"text": "A", "x": 4500, "y": 40000},
                   {"text": "AB", "x": 10500, "y": 40000},
                   {"text": "ABC", "x": 16500, "y": 40000}],
    })
    for lab in r.get("labels", []):
        sh = lab.get("shape")
        rec = {"text": lab.get("text"), "shape": sh, "ok": lab.get("ok")}
        if sh:
            segp = m.call("ee_diag", {"op": "readu32",
                                      "args": {"addr": hex(int(sh, 16) + 0x40)}}).get("value")
            if segp:
                rec["seg"] = hex(segp)
                rec.update(seg_fields(m, hex(segp)))
        print(json.dumps(rec, ensure_ascii=False))

    print("redraw:", json.dumps(m.call("ee_redraw"), ensure_ascii=False))
    m.close()


if __name__ == "__main__":
    main()
