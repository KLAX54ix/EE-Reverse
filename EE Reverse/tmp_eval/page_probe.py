names = open(r"D:\EE Reverse\tmp_eval\eslib_exports.txt", encoding="utf-8").read().splitlines()
import re
for pat in ["PageCount", "GetPage", "PageNum", "TotalPage", "GetCount", "GetDocPage", "PageList"]:
    print("##", pat)
    for n in names:
        if pat in n:
            print("  ", n)
