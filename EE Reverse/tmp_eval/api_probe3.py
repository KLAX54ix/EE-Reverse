import re
names = open(r"D:\EE Reverse\tmp_eval\eslib_exports.txt", encoding="utf-8").read().splitlines()
def show(label, pat, limit=120):
    hit = [n for n in names if re.search(pat, n)]
    print(f"\n## {label}: {len(hit)}")
    for n in hit[:limit]:
        print("  ", n)
show("esPara methods", r"@esPara@@")
show("esQues/Exam methods", r"@es(?:Ques|Exam|ExamItem)@@", 100)
show("InsertAnser/Break/Text", r"esTextUI@@.*(InsertAnser|InsertBreak|InsertText|InsertContents)")
show("paragraph style/type words", r"(ParaType|GetGenre|GetType|IsAnswer|IsExplan|GetStyleWord|GetStyleId|GetParaStyle)", 150)
