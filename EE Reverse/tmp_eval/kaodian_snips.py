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
kd = [k for k in order if "考点" in ptext(k)]
for k in kd:
    i = pos[k]
    print("=====", k, ptext(k))
    for j in range(i+1, min(i+5, len(order))):
        print("   ", order[j], repr(ptext(order[j])[:70]))
# also lecture 7/8 headings
for k in order:
    t = ptext(k)
    if t.startswith("2026秋季第7讲") or t.startswith("2026秋季第8讲"):
        print("LECTURE:", k, t)
