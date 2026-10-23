#!/usr/bin/env python3
"""Smoke-test the EE MCP server over its stdio JSON-RPC interface."""
import json
import subprocess
import sys

SERVER = r"D:\EE Reverse\mcp-server\ee_mcp_server.py"


def main():
    p = subprocess.Popen([sys.executable, SERVER],
                         stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, text=True, encoding="utf-8",
                         errors="replace", bufsize=1,
                         env={**__import__("os").environ,
                              "PYTHONIOENCODING": "utf-8"})

    def call(obj, expect=True):
        p.stdin.write(json.dumps(obj) + "\n")
        p.stdin.flush()
        if not expect:
            return None
        line = p.stdout.readline()
        if not line:
            err = p.stderr.read()
            raise SystemExit(f"server closed. stderr:\n{err}")
        return json.loads(line)

    try:
        r = call({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                  "params": {"protocolVersion": "2024-11-05",
                             "capabilities": {},
                             "clientInfo": {"name": "test", "version": "0"}}})
        print("initialize ->", json.dumps(r.get("result", r))[:300])

        call({"jsonrpc": "2.0", "method": "notifications/initialized"},
             expect=False)

        r = call({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        tools = r["result"]["tools"]
        print(f"tools/list -> {len(tools)} tools: "
              f"{[t['name'] for t in tools]}")

        r = call({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                  "params": {"name": "ee_status", "arguments": {}}})
        print("ee_status ->", r["result"]["content"][0]["text"][:400])

        r = call({"jsonrpc": "2.0", "id": 4, "method": "tools/call",
                  "params": {"name": "ee_draw_polygon",
                             "arguments": {"points": [[15000, 26000],
                                                      [21000, 26000],
                                                      [18000, 30000]]}}})
        print("ee_draw_polygon ->", r["result"]["content"][0]["text"][:400])

        r = call({"jsonrpc": "2.0", "id": 5, "method": "tools/call",
                  "params": {"name": "ee_list_shapes",
                             "arguments": {"limit": 5}}})
        print("ee_list_shapes ->", r["result"]["content"][0]["text"][:500])

        r = call({"jsonrpc": "2.0", "id": 6, "method": "tools/call",
                  "params": {"name": "ee_canvas_bounds", "arguments": {}}})
        print("ee_canvas_bounds ->", r["result"]["content"][0]["text"][:300])

        r = call({"jsonrpc": "2.0", "id": 7, "method": "tools/call",
                  "params": {"name": "ee_draw_circle",
                             "arguments": {"cx": 15000, "cy": 34000, "r": 2000}}})
        print("ee_draw_circle ->", r["result"]["content"][0]["text"][:400])

        r = call({"jsonrpc": "2.0", "id": 8, "method": "tools/call",
                  "params": {"name": "ee_redraw", "arguments": {}}})
        print("ee_redraw ->", r["result"]["content"][0]["text"][:200])
    finally:
        p.stdin.close()
        p.terminate()
    return 0


if __name__ == "__main__":
    sys.exit(main())
