#!/usr/bin/env python3
"""Run the EE engine call recorder and stream every intercepted call to a file.

Usage:
  python ee_hook_recorder.py --out log.jsonl [--seconds 900] [--stop-file STOP]

Runs until the duration elapses or the stop file appears. Prints a heartbeat so
a caller can confirm hooks are live.
"""
import argparse
import json
import os
import sys
import time

import frida

BRIDGE = r"D:\EE Reverse\bridge\ee_hooks.js"
TARGET = "Editer.exe"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=r"D:\EE Reverse\analysis\hooks.jsonl")
    ap.add_argument("--seconds", type=int, default=900)
    ap.add_argument("--stop-file", default=r"D:\EE Reverse\analysis\STOP_HOOKS")
    ap.add_argument("--bridge", default=BRIDGE)
    args = ap.parse_args()

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    dev = frida.get_local_device()
    session = dev.attach(TARGET)
    with open(args.bridge, "r", encoding="utf-8") as fh:
        src = fh.read()
    script = session.create_script(src)

    out = open(args.out, "w", encoding="utf-8")
    stats = {"calls": 0}

    def on_message(msg, data):
        if msg.get("type") == "error":
            print("JS ERROR:", msg.get("description"), file=sys.stderr, flush=True)
            return
        payload = msg.get("payload")
        if not payload:
            return
        payload["ts"] = time.time()
        out.write(json.dumps(payload, ensure_ascii=False) + "\n")
        if payload.get("k") == "install":
            ok = [i for i in payload["installed"] if i.get("hooked")]
            bad = [i for i in payload["installed"] if not i.get("hooked")]
            print(f"HOOKS INSTALLED: {len(ok)} ok, {len(bad)} failed", flush=True)
            for i in bad:
                print(f"  MISS {i['label']}: {i.get('reason')}", flush=True)
        else:
            stats["calls"] += 1
            if stats["calls"] % 25 == 0:
                out.flush()
                print(f"  ...{stats['calls']} calls captured", flush=True)

    script.on("message", on_message)
    script.load()
    out.flush()
    print(f"RECORDING -> {args.out}", flush=True)
    print(f"stop file: {args.stop_file}   duration: {args.seconds}s", flush=True)

    deadline = time.time() + args.seconds
    try:
        while time.time() < deadline:
            if os.path.exists(args.stop_file):
                print("stop file detected", flush=True)
                break
            time.sleep(1.0)
    finally:
        out.flush()
        out.close()
        try:
            script.unload()
        finally:
            session.detach()
    print(f"DONE: {stats['calls']} engine calls captured", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
