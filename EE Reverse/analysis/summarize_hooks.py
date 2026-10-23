#!/usr/bin/env python3
"""Summarise the EE engine call recorder log."""
import collections
import json
import sys

path = sys.argv[1] if len(sys.argv) > 1 else r"D:\EE Reverse\analysis\hooks.jsonl"
show = int(sys.argv[2]) if len(sys.argv) > 2 else 150

rows = []
for line in open(path, encoding="utf-8", errors="replace"):
    line = line.strip()
    if not line:
        continue
    try:
        rows.append(json.loads(line))
    except Exception:
        pass

print(f"file={path}")
print(f"total records={len(rows)}")

counts = collections.Counter(r.get("label") or r.get("k") for r in rows)
print("\n=== calls per hook ===")
for k, v in counts.most_common():
    print(f"  {v:6d}  {k}")

calls = [r for r in rows if r.get("k") == "call"]
print(f"\n=== chronological (first {show} of {len(calls)}) ===")
for r in calls[:show]:
    print(f"  {r.get('label'):<46} self={r.get('self')}  a={r.get('a')}")
