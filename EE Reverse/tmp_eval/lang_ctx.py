import sys
fn = r"D:\EduEditer\EduEditer208\Language\eduediter_cn.wsd"
d = open(fn, "rb").read()
target = "插入答案".encode("utf-16-le")
i = d.find(target)
while i >= 0:
    print("offset:", i)
    seg = d[max(0, i-600):i+700]
    # decode as utf-16 aligned to seg start (seg start might be odd relative to real alignment)
    for shift in (0,1):
        try:
            t = seg[shift:].decode('utf-16-le', 'ignore')
            keep = ''.join(c if (c.isprintable() or c in '\t\r\n') else '·' for c in t)
            print(f"  shift{shift}: {keep[:400]!r}")
        except Exception as e:
            pass
    i = d.find(target, i+2)
    if i > 0 and target[:2] and len(str(i))>0:
        pass
