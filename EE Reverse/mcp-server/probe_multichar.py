#!/usr/bin/env python3
"""Decisive probe: does the EQLine item-count override truncate multi-char
labels?

Creates the same texts through both pipelines:
  * ee_draw_label        (makeLabelShape, no post-create item-count write)
  * ee_draw_figure       (post-create write seg+0xB0 = 1)

and reads back each label's EQLine item count (+0x30), character count at
seg+0x70, and the wrapper box width so truncation is visible as data, not as
squinting at pixels.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from smoke_test import MCP  # noqa: E402


def probe_one(m, cv, y, text, x=4500):
    r = m.call("ee_draw_label", {"text": text, "x": x, "y": y, "canvas": cv})
    res = r.get("result") or {}
    seg = res.get("seg")
    info = None
    if seg:
        b = int(seg, 16)
        info = {
            "eqlineItems": m.call("ee_diag", {"op": "readu32",
                                              "args": {"addr": hex(b + 0x80 + 0x30)}}).get("value"),
            "charCount70": m.call("ee_diag", {"op": "readu32",
                                              "args": {"addr": hex(b + 0x70)}}).get("value"),
            "f73": m.call("ee_diag", {"op": "readu32",
                                      "args": {"addr": hex(b + 0x74)}}).get("value"),
        }
    box = res.get("box") or {}
    return {"text": text, "shape": res.get("shape"), "seg": seg,
            "ok": res.get("ok"), "steps": [s for s in (res.get("steps") or [])
                                            if "eqline" in s],
            "segInfo": info,
            "boxW": (box.get("p2x", 0) - box.get("p1x", 0)),
            "boxH": (box.get("p2y", 0) - box.get("p1y", 0))}


def main():
    cv = sys.argv[1] if len(sys.argv) > 1 else None
    m = MCP()
    if not cv:
        cv = m.call("ee_canvases").get("chosen")
    print("canvas:", cv)

    print("\n-- via ee_draw_label --")
    for i, t in enumerate(["A", "AB", "ABC"]):
        print(json.dumps(probe_one(m, cv, 20000, t, x=4500 + i * 4000),
                         ensure_ascii=False))

    print("\n-- via ee_draw_figure --")
    r = m.call("ee_draw_figure", {
        "canvas": cv, "apply_pen": False, "apply_lable_style": False,
        "labels": [{"text": "A", "x": 4500, "y": 26000},
                   {"text": "AB", "x": 8500, "y": 26000},
                   {"text": "ABC", "x": 12500, "y": 26000}],
    })
    print(json.dumps(r, ensure_ascii=False))
    for lab in r.get("labels", []):
        sh = lab.get("shape")
        if not sh:
            continue
        b = int(sh, 16)
        segp = m.call("ee_diag", {"op": "readu32",
                                  "args": {"addr": hex(b + 0x40)}}).get("value")
        rec = {"text": lab.get("text"), "shape": sh, "seg": hex(segp or 0)}
        if segp:
            rec["eqlineItems"] = m.call("ee_diag", {
                "op": "readu32",
                "args": {"addr": hex(segp + 0x80 + 0x30)}}).get("value")
            rec["charCount70"] = m.call("ee_diag", {
                "op": "readu32", "args": {"addr": hex(segp + 0x70)}}).get("value")
        rec["boxW"] = (m.call("ee_diag", {"op": "readu32",
                                          "args": {"addr": hex(b + 0x1c)}}).get("value", 0)
                       - m.call("ee_diag", {"op": "readu32",
                                            "args": {"addr": hex(b + 0x14)}}).get("value", 0))
        print(json.dumps(rec, ensure_ascii=False))
    m.close()


if __name__ == "__main__":
    main()
