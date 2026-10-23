import sys
sys.path.insert(0, r"D:\EE Reverse\tmp_eval")
import parser as P
p = r"C:\Users\84184\Desktop\26秋季初一培优班19次课.wsd"
doc = P.parse_wsd(open(p,"rb").read())
print("fields:", [f for f in dir(doc.text_runs[0]) if not f.startswith("_")])
paras = {}
order = []
for r in doc.text_runs:
    k = r.paragraph
    if k not in paras:
        paras[k] = []
        order.append(k)
    paras[k].append(r)
print("text objects:", len(doc.text_runs), "paragraph buckets:", len(paras))
def ptext(k):
    return "".join(getattr(r,"text","") for r in paras[k])
first = []
for k in order[:16]:
    rs = paras[k]
    size = getattr(rs[0], "font_size_pt", None)
    first.append((k, ptext(k)[:40], size))
print("first paras:", first)
# find paragraphs containing 考点
kd = []
for k in order:
    t = ptext(k)
    if "考点" in t:
        kd.append((k, t[:40]))
print("考点 paragraphs:", kd)
# find second occurrence of first answer text
needle = "由题意得：|2a+1|=3，"
occ = [k for k in order if ptext(k).startswith(needle)]
print("occurrences of first-answer paragraph:", occ)
if len(occ) >= 2:
    start = occ[1]
    idx = order.index(start)
    block = order[idx:]
    print("block paragraphs:", len(block), "first:", ptext(block[0])[:40], "last:", ptext(block[-1])[:40])
    kd2 = [(k, ptext(k)[:30]) for k in block if "考点" in ptext(k)]
    print("考点 inside block:", kd2)
