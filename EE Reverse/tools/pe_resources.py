"""Minimal PE resource walker for Editer.exe.

Extracts the accelerator table (RT_ACCELERATOR) and menu string tables so we can
learn the editor's real command ids (= what its own toolbar/menu buttons send in
WM_COMMAND). Needed because our bridge bypasses the editor command layer: the
canvas objects it inserts are not registered with the document, so Ctrl+S is a
no-op and deleting such a canvas crashes the process.
"""
import struct
import sys

RT_ACCELERATOR = 9
RT_MENU = 4
RT_STRING = 6


def load(path):
    data = open(path, 'rb').read()
    e_lfanew = struct.unpack_from('<I', data, 0x3C)[0]
    assert data[e_lfanew:e_lfanew + 4] == b'PE\0\0'
    coff = e_lfanew + 4
    nsec = struct.unpack_from('<H', data, coff + 2)[0]
    opt_size = struct.unpack_from('<H', data, coff + 16)[0]
    opt = coff + 20
    magic = struct.unpack_from('<H', data, opt)[0]
    pe32plus = magic == 0x20b
    dd_off = opt + (112 if pe32plus else 96)
    nrva = struct.unpack_from('<I', data, dd_off - 4)[0]
    rsrc_rva = struct.unpack_from('<I', data, dd_off + 2 * 8)[0]
    sec_off = opt + opt_size
    sections = []
    for i in range(nsec):
        base = sec_off + i * 40
        name = data[base:base + 8].rstrip(b'\0').decode('latin1')
        vsize, vaddr, rsize, raddr = struct.unpack_from('<IIII', data, base + 8)
        sections.append((name, vaddr, vsize, raddr, rsize))
    return data, sections, rsrc_rva


def rva_to_off(sections, rva):
    for name, vaddr, vsize, raddr, rsize in sections:
        if vaddr <= rva < vaddr + max(vsize, rsize):
            return raddr + (rva - vaddr)
    return None


def walk(data, sections, rsrc_rva):
    """Yield (type_id, name_id, lang, bytes) for every named resource leaf."""
    base = rva_to_off(sections, rsrc_rva)
    out = []

    def entries(dir_off, depth, path):
        if depth > 4:
            return
        nnamed, nid = struct.unpack_from('<HH', data, dir_off + 12)
        total = nnamed + nid
        for i in range(total):
            off = dir_off + 16 + i * 8
            name_field, off_field = struct.unpack_from('<II', data, off)
            if name_field & 0x80000000:
                so = base + (name_field & 0x7FFFFFFF)
                ln = struct.unpack_from('<H', data, so)[0]
                ident = data[so + 2:so + 2 + ln * 2].decode('utf-16-le', 'replace')
            else:
                ident = name_field
            if off_field & 0x80000000:
                entries(base + (off_field & 0x7FFFFFFF), depth + 1, path + [ident])
            else:
                doff = base + off_field
                drva, dsize = struct.unpack_from('<II', data, doff)
                foff = rva_to_off(sections, drva)
                out.append((path + [ident], data[foff:foff + dsize]))

    entries(base, 0, [])
    return out


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else r'D:\educationeditor\EduEditer\Editer.exe'
    mode = sys.argv[2] if len(sys.argv) > 2 else 'accel'
    data, sections, rsrc_rva = load(path)
    res = walk(data, sections, rsrc_rva)
    if mode == 'accel':
        for path_, blob in res:
            if len(path_) == 3 and path_[0] == RT_ACCELERATOR:
                # ACCEL entries: BYTE fVirt; WORD key; WORD cmd  (5 bytes each)
                n = len(blob) // 5
                rows = []
                for i in range(n):
                    f, key, cmd = struct.unpack_from('<BHH', blob, i * 5)
                    rows.append((f, key, cmd))
                print(f'ACCEL table id={path_[1]} entries={n}')
                for f, key, cmd in rows:
                    if key in (0x53,) or cmd in (0xE103, 0xE104) or (key >= 0x41 and key <= 0x5A):
                        print(f'  fVirt={f:#04x} key={key:#06x} cmd={cmd:#06x}')
        keys = {}
        for path_, blob in res:
            if len(path_) == 3 and path_[0] == RT_ACCELERATOR:
                n = len(blob) // 5
                for i in range(n):
                    f, key, cmd = struct.unpack_from('<BHH', blob, i * 5)
                    keys.setdefault(cmd, []).append((path_[1], f, key))
        print('--- commands with Ctrl accelerators (fVirt&0x2 set) ---')
        for cmd, lst in sorted(keys.items()):
            if any(f & 0x02 for _, f, _ in lst):
                print(f'  cmd={cmd:#06x}  ' + ' '.join(f'tbl{t} fVirt={f:#04x} key={k:#06x}' for t, f, k in lst))
    elif mode == 'menu':
        for path_, blob in res:
            if len(path_) == 3 and path_[0] == RT_MENU:
                print(f'MENU id={path_[1]} size={len(blob)}')
    elif mode == 'list':
        types = {}
        for path_, blob in res:
            if len(path_) >= 1:
                types.setdefault(path_[0], 0)
                types[path_[0]] += 1
        for t, c in sorted(types.items(), key=lambda x: str(x[0])):
            print(t, c)


if __name__ == '__main__':
    main()
