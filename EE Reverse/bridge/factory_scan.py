#!/usr/bin/env python3
"""Enumerate esPageList::CreateObject's type table by calling it empirically.

Calls the exported virtual implementation on a page list whose primary vtable
IS `??_7esPageList@@6B@`, so the direct call is equivalent to the vtable slot.
Every returned object's vtable is then mapped back to a class name.

Created objects are NOT added to the document; they are only probed.
"""
import json
import sys

sys.path.insert(0, r"D:\EE Reverse\bridge")
from ee_client import EE, VT  # noqa: E402

CREATE_OBJECT = "?CreateObject@esPageList@@UBEPAVesObject@@G@Z"


def main():
    lo = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    hi = int(sys.argv[2]) if len(sys.argv) > 2 else 200
    ee = EE()
    try:
        vts = ee.rpc("vtables")
        rev = {}
        for name, addr in vts.items():
            cls = name[len("??_7"):].split("@@")[0]
            rev.setdefault(addr.lower(), cls)

        lists = ee.rpc("instances", VT["esPageList"], 12)["addresses"]
        # the page list that actually has an active canvas is the live document
        target = None
        for a in lists:
            r = ee.rpc("call", "?GetActiveCanvas@esPageList@@QBEPAVesCanvas@@H@Z",
                       "pointer", ["int"], a, [0], "thiscall")
            if r.get("ret") not in (None, "0x0"):
                target = a
                break
        if target is None:
            target = lists[0]
        print(f"# probing CreateObject on pageList {target} (ids {lo}..{hi-1})")

        rows = []
        for tid in range(lo, hi):
            r = ee.rpc("call", CREATE_OBJECT, "pointer", ["int"], target,
                       [tid], "thiscall")
            if r.get("error"):
                rows.append((tid, None, "ERROR " + r["error"]))
                continue
            ret = r.get("ret")
            if not ret or ret == "0x0":
                rows.append((tid, None, "null"))
                continue
            v = ee.rpc("readU32", ret)
            if v is None:
                rows.append((tid, ret, "<unreadable>"))
                continue
            cls = rev.get(hex(v), f"<vtable {hex(v)}>")
            rows.append((tid, ret, cls))

        for tid, ptr, cls in rows:
            if cls not in ("null",):
                print(f"  id={tid:4d}  obj={ptr}  class={cls}")

        nonnull = [r for r in rows if r[2] not in ("null",)]
        print(f"# non-null ids: {len(nonnull)} / {len(rows)}")
        print(json.dumps([{"id": t, "class": c} for t, _, c in nonnull], indent=1))
    finally:
        ee.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
