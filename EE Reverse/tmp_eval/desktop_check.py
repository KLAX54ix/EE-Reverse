import sys, os, collections
sys.path.insert(0, r"D:\EE Reverse\tmp_eval")
import parser as P
p = r"C:\Users\84184\Desktop\26秋季初一培优班19次课.wsd"
data = open(p, "rb").read()
print("size:", len(data), "magic:", data[:12])
try:
    doc = P.parse_wsd(data)
    t = doc.raw_text
    print("fonts:", len(doc.fonts), "runs:", len(doc.text_runs), "raw chars:", len(t), "images:", len(doc.images), "tables:", len(doc.tables))
    for kw in ["（答案）", "第1讲 典型例题", "2026秋季第1讲", "2026秋季第8讲", "考点1"]:
        print(kw, t.count(kw))
    print("head:", repr(t[:200]))
    print("tail:", repr(t[-200:]))
except Exception as e:
    print("parse error:", e)
