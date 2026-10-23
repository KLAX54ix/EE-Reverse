#!/usr/bin/env python3
"""Direct controller for the EE (EduEditer) runtime bridge.

Usage:
  python ee_client.py info
  python ee_client.py instances <vtable-export> [max]
  python ee_client.py names <substring> [limit]
  python ee_client.py chain
  python ee_client.py hexdump <addr> [len]
  python ee_client.py call <export> <retType> <selfPtr> [args...] [--abi A]

Danger: `call` invokes real engine code inside the editor process. It is a
control primitive, not a read-only tool.
"""
import json
import sys
import time

import frida

TARGET = "Editer.exe"
BRIDGE = r"D:\EE Reverse\bridge\ee_bridge.js"

VT = {
    "esDocument": "??_7esDocument@@6B@",
    "esBaseDoc": "??_7esBaseDoc@@6B@",
    "esCanvas": "??_7esCanvas@@6B@",
    "esPageList": "??_7esPageList@@6B@",
    "esDocPage": "??_7esDocPage@@6B@",
    "esSegLine": "??_7esSegLine@@6B@",
    "esSegRect": "??_7esSegRect@@6B@",
    "esSegPolygon": "??_7esSegPolygon@@6B@",
    "esSegArc": "??_7esSegArc@@6B@",
    "esShapePath": "??_7esShapePath@@6B@",
    "esObject": "??_7esObject@@6B@",
    "esSnapManager": "??_7esSnapManager@@6B@",
    "esUndo": "??_7esUndo@@6B@",
}

EX = {
    "base_GetActiveCanvas": "?GetActiveCanvas@esBaseDoc@@QBEPAVesCanvas@@XZ",
    "pageList_GetDocument": "?GetDocument@esPageList@@QBEPAVesBaseDoc@@XZ",
    "canvas_GetActive": "?GetActive@esCanvas@@QBEPAVesShapeBase@@XZ",
    "canvas_AddItem": "?AddItem@esCanvas@@QAEXPAVesShapeBase@@H@Z",
    "pageList_CreateObject": "?CreateObject@esPageList@@UBEPAVesObject@@G@Z",
    "doc_GetActiveUndoObj": "?GetActiveUndoObj@esDocument@@QAEPAVesUndo@@H@Z",
}


class EE:
    def __init__(self, target=TARGET, bridge=BRIDGE):
        self.dev = frida.get_local_device()
        self.session = self.dev.attach(target)
        with open(bridge, "r", encoding="utf-8") as fh:
            src = fh.read()
        self.script = self.session.create_script(src)
        self.script.on("message", self._on_message)
        self.script.load()
        self._msgs = []

    @staticmethod
    def _on_message(msg, data):
        if msg.get("type") == "error":
            print("BRIDGE ERROR:", msg.get("description"), file=sys.stderr)

    def rpc(self, name, *args):
        return getattr(self.script.exports_sync, name)(*args)

    def close(self):
        try:
            self.script.unload()
        finally:
            self.session.detach()


def cmd_info(ee):
    print(json.dumps(ee.rpc("info"), indent=2))


def cmd_instances(ee, name, mx=60):
    vt = VT.get(name, name)
    print(json.dumps(ee.rpc("instances", vt, int(mx)), indent=2))


def cmd_names(ee, sub, limit=200):
    for n in ee.rpc("names", sub, int(limit)):
        print(n)


def cmd_hexdump(ee, addr, ln=64):
    print(ee.rpc("hexdump", addr, int(ln)))


def cmd_call(ee, export, ret_type, self_ptr, args, abi, types=None):
    if export in EX:
        export = EX[export]
    if types is None:
        types = []
        for a in args:
            s = str(a)
            types.append("pointer" if s.startswith("0x") and len(s) > 4 else "int")
    r = ee.rpc("call", export, ret_type, types, self_ptr, args, abi)
    print(json.dumps({"export": export, "retType": ret_type, "argTypes": types,
                      "this": self_ptr, "args": args, "abi": abi, "result": r},
                     indent=2))


def cmd_chain(ee):
    """Resolve: esDocument -> esPageList -> esBaseDoc -> esCanvas."""
    docs = ee.rpc("instances", VT["esDocument"], 8)["addresses"]
    lists = ee.rpc("instances", VT["esPageList"], 8)["addresses"]
    print(f"documents: {docs}")
    print(f"pageLists: {lists}")

    gc = EX["base_GetActiveCanvas"]
    print("\n-- esBaseDoc::GetActiveCanvas(this) --")
    for label, addrs in (("doc", docs), ("pageList", lists)):
        for a in addrs:
            r = ee.rpc("call", gc, "pointer", ["pointer"], a, [], "thiscall")
            print(f"  {label} {a} -> {r}")

    print("\n-- esPageList::GetDocument(this) --")
    gd = EX["pageList_GetDocument"]
    for a in lists:
        r = ee.rpc("call", gd, "pointer", ["pointer"], a, [], "thiscall")
        print(f"  pageList {a} -> {r}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    cmd, rest = sys.argv[1], sys.argv[2:]
    ee = EE()
    try:
        if cmd == "info":
            cmd_info(ee)
        elif cmd == "instances":
            cmd_instances(ee, rest[0], rest[1] if len(rest) > 1 else 60)
        elif cmd == "names":
            cmd_names(ee, rest[0], rest[1] if len(rest) > 1 else 200)
        elif cmd == "hexdump":
            cmd_hexdump(ee, rest[0], rest[1] if len(rest) > 1 else 64)
        elif cmd == "chain":
            cmd_chain(ee)
        elif cmd == "call":
            abi = "thiscall"
            types = None
            if "--abi" in rest:
                i = rest.index("--abi")
                abi = rest[i + 1]
                rest = rest[:i] + rest[i + 2:]
            if "--types" in rest:
                i = rest.index("--types")
                types = [t for t in rest[i + 1].split(",") if t]
                rest = rest[:i] + rest[i + 2:]
            cmd_call(ee, rest[0], rest[1], rest[2], rest[3:], abi, types)
        else:
            print(__doc__)
            return 1
    finally:
        ee.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
