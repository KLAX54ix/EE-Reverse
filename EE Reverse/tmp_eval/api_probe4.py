import re
names = open(r"D:\EE Reverse\tmp_eval\eslib_exports.txt", encoding="utf-8").read().splitlines()
def show(label, pat, limit=100):
    hit = [n for n in names if re.search(pat, n)]
    print(f"\n## {label}: {len(hit)}")
    for n in hit[:limit]:
        print("  ", n)
show("esDocument methods", r"@esDocument@@")
show("file/path/title", r"(FileName|DocumentPath|DocPath|GetPath|GetTitle|DocName|GetName)", 120)
show("exam/answer area", r"(AnswerArea|Explan|QuestionArea|ExamArea|GetQues|EnumQues)", 120)
