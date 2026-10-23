import struct, sys, os, re
sys.path.insert(0, r"D:\EE Reverse\tools")
import pe_resources as pr

root = r"D:\EduEditer\EduEditer208"

def utf16_runs(data, minlen=2):
    out = []
    i = 0
    n = len(data)
    while i + 3 < n:
        j = i; chars = []
        while j + 1 < n:
            c = data[j] | (data[j+1] << 8)
            if 0x20 <= c <= 0x7e or 0x4e00 <= c <= 0x9fff or 0x3000 <= c <= 0x303f or 0xff00 <= c <= 0xffef or c in (0x2103,0x00b0,0x00d7,0x00f7,0x221a,0x2264,0x2265,0x2248,0x00b1):
                chars.append(chr(c)); j += 2
            else:
                break
        if len(chars) >= minlen:
            out.append((i, ''.join(chars)))
            i = j
        else:
            i += 1
    return out

path = os.path.join(root, "Editer.exe")
data = open(path, "rb").read()
runs = utf16_runs(data, 2)
print("Editer.exe utf16 runs:", len(runs))
kw = ["答案", "题目", "插入", "题组", "隐藏", "显示"]
seen = set()
for off, s in runs:
    if any(k in s for k in kw) and s not in seen:
        seen.add(s)
        print(f"  {off:8d}  {s!r}")

print("\n== res types ==")
d, sections, rsrc = pr.load(path)
res = pr.walk(d, sections, rsrc)
types = {}
for p, b in res:
    types[p[0]] = types.get(p[0], 0) + 1
print(types)

print("\n== language wsd contexts ==")
for fn, offs in [(os.path.join(root, "Language", "eduediter_cn.wsd"), [244794, 269466, 269661, 275711, 275773, 338272]),
                 (os.path.join(root, "Language", "stringtable_cn.wsd"), [42107, 42441, 88497, 130697])]:
    d2 = open(fn, "rb").read()
    print("---", os.path.basename(fn))
    for off in offs:
        seg = d2[max(0, off-300):off+500]
        ss = utf16_runs(seg, 1)
        # keep runs that look like UI strings (length>=2 and mostly printable)
        keep = [s for _, s in ss if len(s) >= 2]
        print(f"  off {off}: " + " | ".join(keep[:40]))
