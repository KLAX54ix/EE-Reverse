#!/usr/bin/env python3
"""Poll frida's process list and record when a python.exe (the MCP server) appears.

Usage: python poll_procs.py <seconds>
Writes one line per distinct observation to stdout.
"""
import os
import sys
import time

import frida

secs = float(sys.argv[1]) if len(sys.argv) > 1 else 20.0
me = os.getpid()
dev = frida.get_local_device()
seen_states = set()
last = None
deadline = time.time() + secs
while time.time() < deadline:
    try:
        ps = dev.enumerate_processes()
    except Exception as exc:
        print(f"{time.strftime('%H:%M:%S')} enumerate error: {exc}", flush=True)
        time.sleep(0.25)
        continue
    pythons = sorted(p.pid for p in ps if "python" in p.name.lower())
    others = sorted(p.pid for p in ps if p.pid == 15208)
    state = (tuple(pythons), tuple(others), len(ps))
    if state != last:
        print(f"{time.strftime('%H:%M:%S')} n={len(ps)} python={pythons} "
              f"editer15208={others} me={me}", flush=True)
        last = state
    seen_states.add(state)
    time.sleep(0.25)
print("distinct states:", len(seen_states), flush=True)
