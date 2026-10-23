#!/usr/bin/env python3
"""End-to-end smoke test for the EE MCP server (stdio JSON-RPC).

Drives the server exactly like a host would, runs a full draw cycle on the
open document, and prints a compact JSON report.  Everything that is verified
here is what an agent would call in production:

  initialize -> tools/list -> ee_status -> ee_canvases -> ee_list_shapes
            -> ee_canvas_bounds -> ee_draw_figure -> ee_draw_circle
            -> ee_draw_arc -> ee_draw_label -> ee_list_shapes -> ee_redraw

Usage:
  python smoke_test.py               # full cycle on the chosen canvas
  python smoke_test.py --probe       # read-only introspection only
  python smoke_test.py --new-canvas  # insert a canvas natively (ee_new_canvas),
                                     # then draw the cycle into THAT canvas
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.join(HERE, "ee_mcp_server.py")


class MCP:
    def __init__(self):
        self.p = subprocess.Popen(
            [sys.executable, SERVER],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, encoding="utf-8",
            errors="replace", bufsize=1,
            env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        self._id = 0
        self.init()

    def _send(self, obj):
        self.p.stdin.write(json.dumps(obj) + "\n")
        self.p.stdin.flush()

    def _recv(self):
        line = self.p.stdout.readline()
        if not line:
            err = self.p.stderr.read()
            raise SystemExit(f"server closed; stderr:\n{err}")
        return json.loads(line)

    def req(self, method, params=None):
        self._id += 1
        mid = self._id
        self._send({"jsonrpc": "2.0", "id": mid, "method": method,
                    "params": params or {}})
        return self._recv()

    def init(self):
        r = self.req("initialize", {"protocolVersion": "2024-11-05",
                                    "capabilities": {},
                                    "clientInfo": {"name": "smoke",
                                                   "version": "0"}})
        assert r.get("result"), r
        self._send({"jsonrpc": "2.0",
                    "method": "notifications/initialized"})
        return r["result"]

    def tools(self):
        return self.req("tools/list")["result"]["tools"]

    def call(self, name, args=None):
        self._id += 1
        self._send({"jsonrpc": "2.0", "id": self._id, "method": "tools/call",
                    "params": {"name": name, "arguments": args or {}}})
        r = self._recv()
        res = r.get("result") or {"error": r.get("error")}
        if res.get("isError"):
            return {"__isError": True,
                    "text": res["content"][0]["text"]}
        try:
            return json.loads(res["content"][0]["text"])
        except Exception:
            return {"__raw": res["content"][0]["text"]}

    def close(self):
        try:
            self.p.stdin.close()
        except Exception:
            pass
        self.p.terminate()


def main():
    probe_only = "--probe" in sys.argv
    m = MCP()
    try:
        print("== tools ==")
        print("count:", len(m.tools()))

        st = m.call("ee_status")
        print("\n== ee_status ==")
        print(json.dumps(st, ensure_ascii=False)[:600])

        cvs = m.call("ee_canvases")
        print("\n== ee_canvases ==")
        print(json.dumps(cvs, ensure_ascii=False)[:900])

        shapes = m.call("ee_list_shapes", {"limit": 50})
        print("\n== ee_list_shapes ==")
        rows = shapes.get("shapes", [])
        print(f"{len(rows)} shapes")
        for r in rows[:12]:
            print(" ", json.dumps(r, ensure_ascii=False)[:220])

        bounds = m.call("ee_canvas_bounds")
        print("\n== ee_canvas_bounds ==")
        print(json.dumps(bounds, ensure_ascii=False)[:300])

        if probe_only:
            return 0

        cv = cvs.get("chosen")
        if "--new-canvas" in sys.argv:
            print("\n== ee_new_canvas ==")
            nc = m.call("ee_new_canvas")
            print(json.dumps(nc, ensure_ascii=False)[:500])
            if nc.get("ok") and nc.get("canvas"):
                cv = nc["canvas"]
                ct = m.call("ee_caret_canvas")
                print("caret canvas:", json.dumps(ct, ensure_ascii=False)[:300])
                bounds = m.call("ee_canvas_bounds", {"canvas": cv})
                print("new canvas bounds:",
                      json.dumps(bounds, ensure_ascii=False)[:200])

        print("\n== drawing test on", cv, "==")

        w = bounds.get("width") or 16000
        h = bounds.get("height") or 16000

        # Layout inside the real canvas: a square in the top-left quadrant,
        # a circle top-right, an arc bottom-left.
        q = min(w, h) // 4
        fig = m.call("ee_draw_figure", {
            "canvas": cv,
            "pen_mm": 0.25,
            "paths": [
                {"points": [[q, q], [3 * q, q], [3 * q, 3 * q], [q, 3 * q]],
                 "fill": False},
                {"points": [[q, q], [3 * q, 3 * q]], "close": False},
            ],
            "labels": [{"text": "A", "x": q - 800, "y": q - 800},
                       {"text": "B", "x": 3 * q + 400, "y": q - 800},
                       {"text": "AB", "x": 2 * q - 800, "y": 3 * q + 600}],
        })
        print(json.dumps(fig, ensure_ascii=False)[:900])

        c = m.call("ee_draw_circle", {"cx": w - 2 * q, "cy": 2 * q, "r": q,
                                      "canvas": cv})
        print("\ncircle:", json.dumps(c, ensure_ascii=False)[:400])

        a = m.call("ee_draw_arc", {"cx": 2 * q, "cy": h - 2 * q, "r": q,
                                   "start_deg": 0, "end_deg": 90,
                                   "canvas": cv})
        print("\narc:", json.dumps(a, ensure_ascii=False)[:400])

        am = m.call("ee_draw_angle_mark", {
            "vertex": [3 * q, 3 * q], "point_a": [q, 3 * q],
            "point_b": [3 * q, q], "kind": "right",
            "canvas": cv})
        print("\nangle_mark:", json.dumps(am, ensure_ascii=False)[:300])

        shapes2 = m.call("ee_list_shapes", {"limit": 60})
        print("\nshapes after:", len(shapes2.get("shapes", [])))

        rd = m.call("ee_redraw")
        print("redraw:", json.dumps(rd, ensure_ascii=False)[:200])
        return 0
    finally:
        m.close()


if __name__ == "__main__":
    sys.exit(main())
