names = open(r"D:\EE Reverse\tmp_eval\eslib_exports.txt", encoding="utf-8").read().splitlines()
for pat in ["GetExamTag", "GetExamHead", "GetExamTail", "IsExamTail", "GetRole", "GetOutlineRank", "GetPartOfArea", "GetPartOfNatrue", "GetContents", "IsTrivialPara", "CheckFeatre", "GetCache"]:
    print("##", pat)
    for n in names:
        if pat in n:
            print("  ", n)
