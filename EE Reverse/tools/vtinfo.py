#!/usr/bin/env python3
"""Dump PE export vtables from eslib.dll/Editer.exe with resolved slot names.

Offline only: parses the PE on disk plus the export listings produced earlier in
recon/, so it needs no running target and no Frida session.

Usage:
  python vtinfo.py vt "<vtable-export>"            # dump slots of one vtable
  python vtinfo.py rva <0xRVA>                     # name of the export at an RVA
  python vtinfo.py slot "<vtable-export>" <0xNN>   # resolve one slot
  python vtinfo.py find "<substring>"              # exports whose name contains it
"""
import re
import struct
import sys

EXPORT_FILES = [
    (r"D:\EE Reverse\recon\eslib_exports.txt",
     r"D:\educationeditor\EduEditer\eslib.dll"),
    (r"D:\EE Reverse\recon\eulib_exports.txt", None),
    (r"D:\EE Reverse\recon\zoro_exports.txt", None),
]

LINE_RX = re.compile(r"^\s*(\d+)\s+0x([0-9a-fA-F]{8})\s+(\S+)\s*$")


def load_exports():
    """Return (name2rva, rva2name) merged from every recon export listing."""
    name2rva, rva2name = {}, {}
    for path, _ in EXPORT_FILES:
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    m = LINE_RX.match(line)
                    if not m:
                        continue
                    rva, name = int(m.group(2), 16), m.group(3)
                    name2rva.setdefault(name, rva)
                    rva2name.setdefault(rva, name)
        except OSError:
            pass
    return name2rva, rva2name


def parse_pe(path):
    with open(path, "rb") as fh:
        data = fh.read()
    e_lfanew = struct.unpack_from("<I", data, 0x3C)[0]
    if data[e_lfanew:e_lfanew + 4] != b"PE\0\0":
        raise SystemExit(f"{path}: not a PE")
    coff = e_lfanew + 4
    nsec = struct.unpack_from("<H", data, coff + 2)[0]
    opt_size = struct.unpack_from("<H", data, coff + 16)[0]
    opt = coff + 20
    image_base = struct.unpack_from("<I", data, opt + 28)[0]
    secs = []
    start = opt + opt_size
    for i in range(nsec):
        off = start + i * 40
        nm = data[off:off + 8].rstrip(b"\0").decode("latin1")
        vsize, vaddr, rawsize, rawptr = struct.unpack_from("<IIII", data, off + 8)
        secs.append((nm, vaddr, vsize, rawptr, rawsize))
    return data, image_base, secs


def rva_to_off(secs, rva):
    for _nm, vaddr, vsize, rawptr, rawsize in secs:
        if vaddr <= rva < vaddr + max(vsize, rawsize):
            return rawptr + (rva - vaddr)
    return None


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    name2rva, rva2name = load_exports()
    data, image_base, secs = parse_pe(r"D:\educationeditor\EduEditer\eslib.dll")
    print(f"# eslib.dll image_base=0x{image_base:08x} sections={len(secs)}")
    cmd = sys.argv[1]

    if cmd == "find":
        sub = sys.argv[2]
        for n, r in sorted(name2rva.items(), key=lambda kv: kv[1]):
            if sub in n:
                print(f"0x{r:08x}  {n}")
        return 0

    if cmd == "rva":
        rva = int(sys.argv[2], 16)
        print(rva2name.get(rva, "<no export at that RVA>"))
        return 0

    if cmd == "slot":
        vt = name2rva.get(sys.argv[2])
        if vt is None:
            print("no such vtable export")
            return 1
        slot = int(sys.argv[3], 16)
        foff = rva_to_off(secs, vt + slot)
        if foff is None:
            print("slot outside mapped sections")
            return 1
        tgt = struct.unpack_from("<I", data, foff)[0]
        trva = tgt - image_base
        print(f"{sys.argv[2]} +0x{slot:x} -> 0x{tgt:08x} (rva 0x{trva:x}) "
              f"{rva2name.get(trva, '<no export>')}")
        return 0

    if cmd == "vt":
        vt = name2rva.get(sys.argv[2])
        if vt is None:
            print("no such vtable export")
            return 1
        print(f"# {sys.argv[2]} rva=0x{vt:x}")
        for slot in range(0, 0x100, 4):
            foff = rva_to_off(secs, vt + slot)
            if foff is None:
                break
            tgt = struct.unpack_from("<I", data, foff)[0]
            if tgt == 0:
                print(f"  +0x{slot:03x}  0x00000000  <null>")
                continue
            trva = tgt - image_base
            nm = rva2name.get(trva)
            print(f"  +0x{slot:03x}  0x{tgt:08x}  {nm if nm else '<no export>'}")
        return 0

    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main())
