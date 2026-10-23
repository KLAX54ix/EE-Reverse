import struct, re, os

def read_exports(path):
    data = open(path, "rb").read()
    e = struct.unpack_from('<I', data, 0x3c)[0]
    coff = e + 4
    nsec = struct.unpack_from('<H', data, coff+2)[0]
    opt_size = struct.unpack_from('<H', data, coff+16)[0]
    opt = coff + 20
    pe32plus = struct.unpack_from('<H', data, opt)[0] == 0x20b
    dd = opt + (112 if pe32plus else 96)
    exp_rva = struct.unpack_from('<I', data, dd)[0]
    sec_off = opt + opt_size
    secs = []
    for i in range(nsec):
        b = sec_off + i*40
        vsize, vaddr, rsize, raddr = struct.unpack_from('<IIII', data, b+8)
        secs.append((vaddr, vsize, raddr, rsize))
    def r2o(rva):
        for vaddr, vsize, raddr, rsize in secs:
            if vaddr <= rva < vaddr + max(vsize, rsize):
                return raddr + (rva - vaddr)
        return None
    eo = r2o(exp_rva)
    if eo is None: return []
    nnames = struct.unpack_from('<I', data, eo+24)[0]
    no = r2o(struct.unpack_from('<I', data, eo+32)[0])
    out = []
    for i in range(nnames):
        off = r2o(struct.unpack_from('<I', data, no + i*4)[0])
        end = data.find(b'\0', off)
        out.append(data[off:end].decode('latin1'))
    return out

names = read_exports(r"D:\EduEditer\EduEditer208\eslib.dll")
print("total:", len(names))
open(r"D:\EE Reverse\tmp_eval\eslib_exports.txt", "w", encoding="utf-8").write("\n".join(names))

def show(label, pred, limit=80):
    hit = [n for n in names if pred(n)]
    print(f"\n## {label}: {len(hit)}")
    for n in hit[:limit]:
        print("  ", n)

show("esTextUI methods", lambda n: "@esTextUI@@" in n, 240)
show("caret-related", lambda n: "Caret" in n, 100)
show("esPara get/type/style", lambda n: "@esPara@@" in n and re.search(r"\?(Get|Is|Set|Query|Find)[A-Za-z]*", n), 120)
