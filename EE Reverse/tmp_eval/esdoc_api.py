names = open(r"D:\EE Reverse\tmp_eval\eslib_exports.txt", encoding="utf-8").read().splitlines()
import re
for n in names:
    if "@esDocument@@" in n:
        print(n)
