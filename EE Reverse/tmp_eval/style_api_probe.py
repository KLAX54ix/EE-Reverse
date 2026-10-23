names = open(r"D:\EE Reverse\tmp_eval\eslib_exports.txt", encoding="utf-8").read().splitlines()
for pat in ["CopyPropTo", "ApplyStyle", "GetParaModel", "ApplyParaStyle", "SetParaType", "OnSetFirstParaType", "SetRole", "GetOutlineRank", "ApplyTmpl", "ApplyPara"]:
    print("##", pat)
    for n in names:
        if pat in n:
            print("  ", n)
