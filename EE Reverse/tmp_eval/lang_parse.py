import sys, os
sys.path.insert(0, r"D:\EE Reverse\tmp_eval")
import parser as P
for fn in [r"D:\EduEditer\EduEditer208\Language\eduediter_cn.wsd",
           r"D:\EduEditer\EduEditer208\Language\stringtable_cn.wsd"]:
    doc = P.parse_wsd(open(fn, "rb").read())
    t = doc.raw_text
    print("="*100)
    print(os.path.basename(fn), "chars:", len(t))
    for key in ["4204", "插入答案", "将各个试题中的答案集中插入到指定位置", "导出", "PDF", "分页"]:
        i = t.find(key)
        print(f"--- {key!r}: first at {i}")
        if i >= 0:
            print(repr(t[max(0,i-200):i+300]))
