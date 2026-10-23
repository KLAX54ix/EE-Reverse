import sys, os, re
sys.path.insert(0, r"D:\EE Reverse\tmp_eval")
import parser as P
w = r"Z:\菜鸡工作室\团队共享\#2课程资料\26年秋季资料\七A\26秋季初一培优班19次课前6讲答案\26秋季初一培优班19次课.wsd"
doc = P.parse_wsd(open(w,"rb").read())
t = doc.raw_text
print("chars:", len(t))
pat = re.compile(r"第\s*\d+\s*讲|典型例题|巩固练习|（答案）|【答案】|答案解析")
ms = list(pat.finditer(t))
print("markers:", len(ms))
for m in ms[:80]:
    s = max(0, m.start()-40); e = min(len(t), m.end()+60)
    print("%6d %-16r ... %s" % (m.start(), m.group(), t[s:e].replace("\n"," ")))
print("--- tail 600 ---")
print(t[-600:])
