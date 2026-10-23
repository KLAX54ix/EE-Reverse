"""List every readable UTF-16LE run inside an EE .wsd text region.

No filtering beyond "printable", so nothing is silently dropped; the caller
reads the list and picks out the real document text.
"""
import sys

PATH = sys.argv[1] if len(sys.argv) > 1 else \
    r"D:\EE Reverse\2025-2026学年浙江省宁波市镇海区九年级（上）期末数学试卷.wsd"
OUT = sys.argv[2] if len(sys.argv) > 2 else r"D:\EE Reverse\analysis\paper-raw.txt"
START = int(sys.argv[3], 0) if len(sys.argv) > 3 else 0x120000
END = int(sys.argv[4], 0) if len(sys.argv) > 4 else 0x134000
MINLEN = int(sys.argv[5]) if len(sys.argv) > 5 else 8


def texty(ch):
    o = ord(ch)
    if o < 0x20 and ch != "\x08":
        return False
    if o == 0xFFFD or 0xE000 <= o <= 0xF8FF or 0xD800 <= o <= 0xDFFF or o >= 0xFFF0:
        return False
    return True


def main():
    b = open(PATH, "rb").read()
    end = min(END, len(b))
    i = START
    out = []
    while i < end - 1:
        c = b[i:i + 2].decode("utf-16-le", "replace")
        if len(c) == 1 and texty(c) and c != "\x08":
            j, buf = i, []
            while j < end - 1:
                d = b[j:j + 2].decode("utf-16-le", "replace")
                if len(d) != 1 or not texty(d):
                    break
                buf.append(d)
                j += 2
            t = "".join(buf)
            if len(t) >= MINLEN:
                out.append((i, t))
            i = j if j > i else i + 2
        else:
            i += 2
    with open(OUT, "w", encoding="utf-8") as f:
        for o, t in out:
            f.write("@0x%06X  %3d  %s\n" % (o, len(t), t.replace(chr(8), "")))
    print("runs =", len(out), " chars =", sum(len(t) for _, t in out))


main()
