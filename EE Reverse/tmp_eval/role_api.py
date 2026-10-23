names = open(r"D:\EE Reverse\tmp_eval\eslib_exports.txt", encoding="utf-8").read().splitlines()
for pat in ["@esStyleSheet@@", "@esRole@@", "Role"]:
    print("##", pat)
    for n in names:
        if pat in n:
            print("  ", n)
