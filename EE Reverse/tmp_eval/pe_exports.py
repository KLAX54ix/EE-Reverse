import struct, sys, os

def read_exports(path):
    data = open(path, "rb").read()
    if data[:2] != b'MZ': return []
    e_lfanew = struct.unpack_from('<I', data, 0x3c)[0]
    assert data[e_lfanew:e_lfanew+4] == b'PE\0\0'
    coff = e_lfanew + 4
    nsec = struct.unpack_from('<H', data, coff+2)[0]
    opt_size = struct.unpack_from('<H', data, coff+16)[0]
    opt = coff + 20
    magic = struct.unpack_from('<H', data, opt)[0]
    pe32plus = magic == 0x20b
    dd = opt + (112 if pe32plus else 96)
    exp_rva, exp_size = struct.unpack_from('<II', data, dd)
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
    if not exp_rva: return []
    eo = r2o(exp_rva)
    nnames = struct.unpack_from('<I', data, eo+24)[0]
    names_rva = struct.unpack_from('<I', data, eo+32)[0]
    no = r2o(names_rva)
    out = []
    for i in range(nnames):
        nrva = struct.unpack_from('<I', data, no + i*4)[0]
        off = r2o(nrva)
        end = data.find(b'\0', off)
        out.append(data[off:end].decode('latin1'))
    return out

for path in [r"D:\EduEditer\EduEditer208\Editer.exe", r"D:\EduEditer\EduEditer208\eslib.dll"]:
    names = read_exports(path)
    print("="*90)
    print(os.path.basename(path), "exports:", len(names))
    kw = ["Caret", "Para", "TextUI", "Selection", "Select", "Insert", "Answer", "AnswerArea", "Question", "Test"]
    for n in names:
        if any(k in n for k in kw):
            print("  ", n)
