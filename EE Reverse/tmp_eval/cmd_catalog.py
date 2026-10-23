import sys, os, re
sys.path.insert(0, r"D:\EE Reverse\tmp_eval")
import parser as P
fn = r"D:\EduEditer\EduEditer208\Language\eduediter_cn.wsd"
doc = P.parse_wsd(open(fn, "rb").read())
t = doc.raw_text
# split into command entries: 4-digit id followed by label; description follows
entries = []
for m in re.finditer(r"(?<!\d)(\d{4})([^\d].{0,200}?)(?=\d{4}[^\d]|$)", t):
    sid = int(m.group(1))
    body = m.group(2)
    entries.append((sid, body))
print("entries:", len(entries))
kw = ["答案", "解析", "试题", "题目", "分页", "标题", "导出", "PDF", "保存"]
for sid, body in entries:
    if any(k in body for k in kw):
        print(f"{sid}: {body[:170]!r}")
