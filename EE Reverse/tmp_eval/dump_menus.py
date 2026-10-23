import struct, sys, os
sys.path.insert(0, r"D:\EE Reverse\tools")
import pe_resources as pr
path = r"D:\EduEditer\EduEditer208\Editer.exe"
data, sections, rsrc = pr.load(path)
res = pr.walk(data, sections, rsrc)
print("resources:", len(res))
menus = [(p, b) for p, b in res if len(p) == 3 and p[0] == pr.RT_MENU]
print("menu resources:", len(menus))
def utf16_strings(blob):
    out = []
    i = 0
    while i + 4 <= len(blob):
        # try decode UTF-16 run of printable chars
        j = i; chars = []
        while j + 1 < len(blob):
            c = blob[j] | (blob[j+1] << 8)
            if 0x20 <= c <= 0x7e or 0x4e00 <= c <= 0x9fff or 0x3000 <= c <= 0x303f or 0xff00 <= c <= 0xffef:
                chars.append(chr(c)); j += 2
            else:
                break
        if len(chars) >= 2:
            out.append((i, ''.join(chars)))
            i = j
        else:
            i += 1
    return out
for p, blob in menus:
    ss = utf16_strings(blob)
    hit = [x for x in ss if '答案' in x[1] or '插入' in x[1]]
    if hit:
        print(f"MENU id={p[1]} size={len(blob)}")
        for off, s in ss:
            print(f"  {off:5d}  {s!r}")
