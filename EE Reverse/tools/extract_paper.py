"""Extract the readable text of an EE .wsd document.

The document text is stored as plain UTF-16LE and every text run is
terminated by the 16-bit value 0x0008.  So instead of guessing run starts,
find every 08 00 terminator and walk backwards over printable UTF-16 units.
Binary noise is rejected by requiring enough common Chinese characters.
"""
import sys

PATH = sys.argv[1] if len(sys.argv) > 1 else \
    r"D:\EE Reverse\2025-2026学年浙江省宁波市镇海区九年级（上）期末数学试卷.wsd"
OUT = sys.argv[2] if len(sys.argv) > 2 else r"D:\EE Reverse\analysis\paper.txt"

COMMON = set(
    "的一是不了在人有我他这个上们来到时大地为子中你说生国年着就那和要她出也得里后自以会家可下而过天去能"
    "对小多然于心学么之都好看起发当没成只如事把还用第样道想作种开美总从无情己面最女但现前些所同日手又行"
    "意动方期它头经长儿回位分爱老因很给名法间斯知世什两次使身者被高已亲其进此话常与活正感"
    "图选填答题解证明求若则交连接长边角形方式值列"
)


def texty(ch):
    o = ord(ch)
    if o < 0x20 and ch != "\x08":
        return False
    if o == 0xFFFD or 0xE000 <= o <= 0xF8FF or 0xD800 <= o <= 0xDFFF or o >= 0xFFF0:
        return False
    return True


def main():
    b = open(PATH, "rb").read()
    runs = []
    seen = set()
    for i in range(0, len(b) - 1, 2):
        if b[i] != 0x08 or b[i + 1] != 0x00:
            continue
        j = i
        buf = []
        while j - 2 >= 0 and len(buf) < 800:
            c = b[j - 2:j].decode("utf-16-le", "replace")
            if len(c) != 1 or not texty(c):
                break
            buf.append(c)
            j -= 2
        t = "".join(reversed(buf))
        if len(t) >= 5 and sum(1 for c in t if c in COMMON) >= 2:
            key = (j, t)
            if key not in seen:
                seen.add(key)
                runs.append((j, t))
    runs.sort()
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n\n".join("@0x%X (%d)\n%s" % (o, len(s), s.replace(chr(8), ""))
                            for o, s in runs))
    print("runs =", len(runs), " chars =", sum(len(s) for _, s in runs))


main()
