import sys, re
sys.path.insert(0, r"D:\EE Reverse\tmp_eval")
import parser as P
w = r"Z:\菜鸡工作室\团队共享\#2课程资料\26年秋季资料\七A\26秋季初一培优班19次课前6讲答案\26秋季初一培优班19次课.wsd"
t = P.parse_wsd(open(w, "rb").read()).raw_text
for k in ["【答案】", "（梯子）", "(梯子)", "【典型例题】", "【巩固练习】", "（答案）", "第1讲", "第2讲", "第6讲"]:
    print(f"{k!r}: {t.count(k)}")
print("\n--- 每讲起始位置与片段 ---")
for n in range(1, 7):
    i = t.find(f"2026秋季第{n}讲")
    j = t.find(f"第{n}讲", i) if i < 0 else i
    print(f"第{n}讲 marker: A={i} B={t.find('第'+str(n)+'讲 典型例题（答案）')}")
    if i >= 0:
        print("   A:", t[i:i+120].replace("\n", " "))
print("\n--- 找 Q1 题干/答案特征 ---")
for pat in ["点A在数轴上", "距离等于3", "由题意得", "应选", "故选"]:
    idx = [m.start() for m in re.finditer(re.escape(pat), t)]
    print(f"{pat!r}: {len(idx)} 处，前3: {idx[:3]}")
