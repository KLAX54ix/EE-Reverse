import sys
sys.path.insert(0, r"D:\EE Reverse\tmp_eval")
import parser as P
p = r"C:\Users\84184\Desktop\26秋季初一培优班19次课.wsd"
doc = P.parse_wsd(open(p,"rb").read())
paras = {}
order = []
for r in doc.text_runs:
    k = r.paragraph
    if k not in paras:
        paras[k] = []
        order.append(k)
    paras[k].append(r)
def ptext(k):
    return "".join(getattr(r,"text","") for r in paras[k])
pos = {k:i for i,k in enumerate(order)}
def rng(a,b):
    i,j = pos[a], pos[b]
    return order[i:j] if j>i else order[j:i]
# 第7讲 groups
g7 = [("考点1 数轴综合与动点问题（小题）", 2391, 2472),
      ("考点2 数轴综合与动点问题（大题）", 2474, 2593),
      ("考点3 规律探究与周期问题", 2595, 2978),
      ("考点4 程序运算图", 2980, 3095)]
g8 = [("考点5 新定义问题", 3099, 3185),
      ("考点6 进制数问题", 3187, 3197),
      ("考点7 幻方问题", 3199, 3213),
      ("考点8 图形面积周长", 3214, 3214),
      ("考点9 整数条件下的多变量问题", 3216, 3299)]
def lens(groups):
    out=[]
    for name,a,b in groups:
        i,j = pos[a], pos[b]
        seg = order[i:j+1]
        n = sum(len(ptext(k)) for k in seg)
        out.append((name, n))
    return out
L7=lens(g7); L8=lens(g8)
T7=sum(n for _,n in L7); T8=sum(n for _,n in L8)
DEF7, DEF8 = 255, 109
start7, start8 = 2857, 3112
print("第7讲 length total:", T7)
off7=start7; cum=0
for name,n in L7:
    cum+=n
    pgh = start7 + round(DEF7*cum/T7)
    print(f"  第7讲 {name}: est EE para ~{pgh} (block offset {pgh-2266}) page ~{100+(pgh-2266)/34.1:.0f}")
print("第8讲 length total:", T8)
cum=0
for name,n in L8:
    cum+=n
    pgh = start8 + round(DEF8*cum/T8)
    print(f"  第8讲 {name}: est EE para ~{pgh} (block offset {pgh-2266}) page ~{100+(pgh-2266)/34.1:.0f}")
