#!/usr/bin/env python3
"""ledger_group.py - group ledger.csv rows by module / owner class (phase-2 planner).

Usage:
  python tools/ledger_group.py [module ...]          # default: zoro eulib eglib
  python tools/ledger_group.py --members zoro zStringTemplate   # list functions of one owner

Prints an inventory: per module, function counts by owner_class (desc),
named-vs-unnamed, plus standalone export kinds. Read-only.
"""

import csv
import sys
from collections import Counter, defaultdict
from pathlib import Path

WS = Path(__file__).resolve().parent.parent
LEDGER = WS / "ledger" / "ledger.csv"


def load():
    funcs = defaultdict(list)
    with open(LEDGER, "r", encoding="utf-8", newline="") as f:
        r = csv.reader(f)
        next(r, None)
        for row in r:
            if row[1] != "function":
                continue
            mod, owner = row[5], row[4]
            funcs[mod].append({
                "rva": row[6], "name": row[2], "owner": owner,
                "size": row[7], "status": row[10],
            })
    return funcs


def inventory(modules):
    funcs = load()
    for mod in modules:
        rows = funcs.get(mod, [])
        by_owner = Counter(x["owner"] or "(none)" for x in rows)
        named = sum(1 for x in rows if not x["name"].startswith(("FUN_", "thunk_FUN_", "LAB_")))
        print("=== %s: %d functions, named=%d ===" % (mod, len(rows), named))
        for owner, n in by_owner.most_common(40):
            print("  %-48s %4d" % (owner[:48], n))
        print()


def members(mod, owner):
    funcs = load()
    hits = [x for x in funcs.get(mod, []) if owner.lower() in (x["owner"] or "").lower()
            or owner.lower() in x["name"].lower()]
    hits.sort(key=lambda x: -int(x["size"]))
    print("=== %s members matching %r: %d ===" % (mod, owner, len(hits)))
    for x in hits:
        print("  %-10s %-64s %6s B  %s" % (x["rva"], x["name"][:64], x["size"], x["status"]))


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "--members":
        members(args[1], args[2])
    else:
        inventory(args or ["zoro", "eulib", "eglib"])
