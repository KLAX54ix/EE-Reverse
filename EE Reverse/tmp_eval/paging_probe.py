import sys
sys.path.insert(0, r"D:\EE Reverse\tmp_eval")
import parser as P
fn = r"D:\EduEditer\EduEditer208\Language\eduediter_cn.wsd"
t = P.parse_wsd(open(fn, "rb").read()).raw_text
import re
for kw in ["新的一页", "段前", "分页符", "换栏", "分栏符"]:
    print("="*30, kw)
    for m in re.finditer(re.escape(kw), t):
        print(repr(t[max(0,m.start()-120):m.start()+120]))
