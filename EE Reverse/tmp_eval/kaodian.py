import sys
sys.path.insert(0, r"D:\EE Reverse\tmp_eval")
import parser as P
p = r"C:\Users\84184\Desktop\26秋季初一培优班19次课.wsd"
doc = P.parse_wsd(open(p,"rb").read())
t = doc.raw_text
print("total chars:", len(t))
# teacher part was ~23597 chars in original; answer block starts around there
idx7 = t.find("第7讲 典型例题（答案）")
# locate first answers of lecture 7 and 8
i7 = t.find("-2或10")
i8 = t.find("∵i1=i")
print("idx 第7讲典型首段:", i7, " idx 第8讲典型首段:", i8)
for key in ["考点"]:
    pos = 0
    n = 0
    while True:
        pos = t.find(key, pos)
        if pos < 0: break
        n += 1
        print(n, pos, repr(t[max(0,pos-40):pos+60]))
        pos += 1
print("---- candidates around answer-block 考点 ----")
pos = 0
while True:
    pos = t.find("考点", pos)
    if pos < 0 or pos > len(t): break
    if pos > 23000:
        print(pos, repr(t[pos-30:pos+80]))
    pos += 1
