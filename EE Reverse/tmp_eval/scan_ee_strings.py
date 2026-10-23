import os, re, glob
root = r"D:\EduEditer\EduEditer208"
keys = ["插入答案", "答案", "答案解析", "显示答案", "隐藏答案", "插入"]
def find_utf16(data, s):
    b = s.encode("utf-16-le")
    i = data.find(b)
    out = []
    while i >= 0 and len(out) < 20:
        out.append(i); i = data.find(b, i+2)
    return out
files = []
for ext in ("*.wsd","*.lst","*.sds","*.dat","*.exe","*.dll","*.ini","*.txt"):
    files += glob.glob(os.path.join(root, "**", ext), recursive=True)
print("scan files:", len(files))
hits = {}
for f in files:
    try:
        data = open(f, "rb").read()
    except Exception:
        continue
    for k in keys:
        pos = find_utf16(data, k)
        if pos:
            hits.setdefault(f, []).append((k, len(pos), pos[:3]))
for f, h in hits.items():
    print(os.path.relpath(f, root), "|", h)
