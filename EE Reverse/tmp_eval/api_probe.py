import struct, sys, os, re
sys.path.insert(0, r"D:\EE Reverse\tmp_eval")
import pe_exports as PE
names = PE.read_exports(r"D:\EduEditer\EduEditer208\eslib.dll")
open(r"D:\EE Reverse\tmp_eval\eslib_exports.txt", "w", encoding="utf-8").write("\n".join(names))
print("total exports:", len(names))
pats = ["?SetCaret", "?MoveCaret", "?Insert", "?Paste", "?Typing", "?Command", "?Exec", "?DoCmd", "?InsertText", "?ReplaceSel", "?DeleteSel", "?GetCaret", "?Select"]
for p in pats:
    hit = [n for n in names if p in n]
    print(f"\n## {p} ({len(hit)})")
    for n in hit[:25]:
        print("  ", n)
print("\n## esTextUI methods (sample)")
hit = [n for n in names if "@esTextUI@@" in n]
print("count:", len(hit))
for n in hit[:120]:
    print("  ", n)
