import sys, re
sys.path.insert(0, r"D:\EE Reverse\tmp_eval")
import parser as P
t = P.parse_wsd(open(r"D:\EduEditer\EduEditer208\Language\eduediter_cn.wsd","rb").read()).raw_text
for kw in ["撤销", "撤消", "恢复", "重做"]:
    for m in re.finditer(kw, t):
        s = max(0, m.start()-80); e = min(len(t), m.end()+80)
        print(kw, "|", repr(t[s:e]))
