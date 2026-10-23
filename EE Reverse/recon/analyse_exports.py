#!/usr/bin/env python3
"""Summarise MSVC-mangled PE export tables into a class/method inventory."""
import sys
import re
import argparse
from collections import Counter, defaultdict

KW_GROUPS = {
    "geometry": ["line", "circle", "arc", "ellipse", "poly", "rect", "angle",
                 "bezier", "curve", "spline", "path", "coord", "axis",
                 "vector", "point", "segment", "ray", "triangle", "parallel",
                 "perp", "tangent", "midpoint", "intersect"],
    "shape": ["shape", "object", "canvas", "layer", "group", "page", "frame"],
    "text": ["text", "para", "font", "formula", "word", "glyph", "label"],
    "doc": ["document", "doc", "save", "load", "serial", "archive", "zip",
            "export", "import", "print", "render", "draw"],
    "app": ["addin", "plugin", "script", "macro", "command", "menu", "tool",
            "action", "bind", "hook", "auto"],
}


def parse_export(line):
    parts = line.split()
    if len(parts) < 3:
        return None
    try:
        ordinal = int(parts[0])
    except ValueError:
        return None
    rva = parts[1]
    name = " ".join(parts[2:])
    return ordinal, rva, name


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--mode", default="classes",
                    choices=["classes", "kw", "methods", "all"])
    ap.add_argument("--top", type=int, default=60)
    ap.add_argument("--pattern", default=None)
    a = ap.parse_args()

    classes = Counter()
    methods = Counter()
    per_class = defaultdict(list)
    plain = []
    for line in open(a.file, encoding="utf-8", errors="replace"):
        line = line.strip()
        if not line or line.startswith("#") or not re.match(r"^\s*\d+\s", line):
            continue
        p = parse_export(line)
        if not p:
            continue
        _, _, name = p
        if not name.startswith("?"):
            plain.append(name)
            continue
        toks = [t for t in name[1:].split("@") if t]
        if not toks:
            continue
        m = toks[0]
        methods[m] += 1
        if len(toks) > 1:
            cls = toks[1]
            classes[cls] += 1
            per_class[cls].append(m)

    if a.mode in ("classes", "all"):
        print(f"=== distinct exported classes: {len(classes)} ===")
        for c, n in classes.most_common(a.top):
            print(f"{n:6d}  {c}")

    if a.mode in ("kw", "all"):
        print(f"\n=== keyword groups (classes matching) ===")
        for g, kws in KW_GROUPS.items():
            hits = [(c, n) for c, n in classes.items()
                    if any(k in c.lower() for k in kws)]
            hits.sort(key=lambda x: -x[1])
            print(f"\n[{g}] {len(hits)} classes")
            for c, n in hits[:a.top]:
                print(f"  {n:6d}  {c}")

    if a.mode in ("methods", "all"):
        print(f"\n=== top method-name tokens: {len(methods)} distinct ===")
        for m, n in methods.most_common(a.top):
            print(f"{n:6d}  {m}")

    if a.pattern:
        rx = re.compile(a.pattern, re.I)
        print(f"\n=== regex '{a.pattern}' ===")
        for c, ms in sorted(per_class.items()):
            if rx.search(c):
                print(f"\n{c}  ({len(ms)} exports)")
                for m in sorted(set(ms))[:40]:
                    print(f"   {m}")

    if plain:
        print(f"\n=== plain (undecorated) exports: {len(plain)} ===")
        for n in plain[:a.top]:
            print(f"  {n}")


if __name__ == "__main__":
    main()
