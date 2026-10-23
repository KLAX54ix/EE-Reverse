import sys
PATH = r"D:\EE Reverse\2025-2026学年浙江省宁波市镇海区九年级（上）期末数学试卷.wsd"
OUT  = r"D:\EE Reverse\analysis\paper-align.txt"
b = open(PATH, "rb").read()
def texty(ch):
    o = ord(ch)
    if o < 0x20 and ch != "\x08": return False
    if o == 0xFFFD or 0xE000 <= o <= 0xF8FF or 0xD800 <= o <= 0xDFFF or o >= 0xFFF0: return False
    return True
COMMON = set("的一是不了在人有我他这个上们来到时大地为子中你说生国年着就那和要她出也得里后自以会家可下而过天去能对小多然于心学么之都好看起发当没成只如事把还用第样道想作种开美总从无情己面最女但现前些所同日手又行意动方期它头经长儿回位分爱老因很给名法间斯知世什两次使身者被高已亲其进此话常与活正感图选填答题解证明求若则交连接长边角形方式值列")
runs = []
for base in (0, 1):
    i = 0x124200 + base
    while i < 0x128000:
        c = b[i:i+2].decode("utf-16-le", "replace")
        if len(c) == 1 and texty(c) and c != "\x08":
            j, buf = i, []
            while j < 0x128000:
                d = b[j:j+2].decode("utf-16-le", "replace")
                if len(d) != 1 or not texty(d): break
                buf.append(d); j += 2
            t = "".join(buf)
            if len(t) >= 10 and sum(1 for ch in t if ch in COMMON) >= 3:
                runs.append((i, t))
            i = j if j > i else i + 2
        else:
            i += 2
runs.sort()
seen = set(); out = []
for o, t in runs:
    key = t[:60]
    if key in seen: continue
    seen.add(key); out.append((o, t))
with open(OUT, "w", encoding="utf-8") as f:
    for o, t in out:
        f.write("@0x%06X %3d  %s\n" % (o, len(t), t.replace(chr(8), "")))
print("runs =", len(out), " chars =", sum(len(t) for _, t in out))
