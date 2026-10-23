names = open(r"D:\EE Reverse\tmp_eval\eslib_exports.txt", encoding="utf-8").read().splitlines()
for n in names:
    if "@esPara@@" in n:
        print(n)
