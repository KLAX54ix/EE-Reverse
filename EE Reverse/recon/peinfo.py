#!/usr/bin/env python3
"""Minimal PE inspector: imports, exports, sections. 32/64-bit, no dependencies."""
import sys
import struct
import argparse


class PE:
    def __init__(self, path):
        self.path = path
        self.data = open(path, "rb").read()
        d = self.data
        if d[:2] != b"MZ":
            raise ValueError("not MZ")
        self.pe_off = struct.unpack_from("<I", d, 0x3C)[0]
        if d[self.pe_off:self.pe_off + 4] != b"PE\0\0":
            raise ValueError("not PE")
        fh = self.pe_off + 4
        (self.machine, self.nsec, _, _, _, self.opt_size,
         self.characteristics) = struct.unpack_from("<HHIIIHH", d, fh)
        self.opt_off = fh + 20
        self.magic = struct.unpack_from("<H", d, self.opt_off)[0]
        self.is64 = self.magic == 0x20B
        if self.is64:
            self.dd_off = self.opt_off + 112
            self.num_dd = struct.unpack_from("<I", d, self.opt_off + 108)[0]
        else:
            self.dd_off = self.opt_off + 96
            self.num_dd = struct.unpack_from("<I", d, self.opt_off + 92)[0]
        self.sections = []
        so = self.opt_off + self.opt_size
        for i in range(self.nsec):
            base = so + i * 40
            name = d[base:base + 8].rstrip(b"\0").decode("latin1")
            vsize, vaddr, rsize, raw = struct.unpack_from("<IIII", d, base + 8)
            self.sections.append((name, vaddr, vsize, raw, rsize))

    def rva2off(self, rva):
        for name, vaddr, vsize, raw, rsize in self.sections:
            if vaddr <= rva < vaddr + max(vsize, rsize):
                return raw + (rva - vaddr)
        return None

    def cstr(self, rva):
        off = self.rva2off(rva)
        if off is None:
            return None
        end = self.data.find(b"\0", off)
        return self.data[off:end].decode("latin1", "replace")

    def datadir(self, idx):
        if idx >= self.num_dd:
            return 0, 0
        return struct.unpack_from("<II", self.data, self.dd_off + idx * 8)

    def exports(self):
        rva, size = self.datadir(0)
        if not rva:
            return None
        off = self.rva2off(rva)
        (_, _, _, _, name_rva, base, nfunc, nnames,
         afunc, anames, aords) = struct.unpack_from("<IIHHIIIIIII", self.data, off)
        dll = self.cstr(name_rva)
        funcs = struct.unpack_from("<%dI" % nfunc, self.data, self.rva2off(afunc))
        names = struct.unpack_from("<%dI" % nnames, self.data, self.rva2off(anames))
        ords = struct.unpack_from("<%dH" % nnames, self.data, self.rva2off(aords))
        out = [{"dll": dll, "base": base, "count": nfunc, "named": []}]
        for i in range(nnames):
            out[0]["named"].append({
                "name": self.cstr(names[i]),
                "ordinal": base + ords[i],
                "rva": funcs[ords[i]],
            })
        return out

    def imports(self):
        rva, size = self.datadir(1)
        if not rva:
            return []
        off = self.rva2off(rva)
        out = []
        while True:
            desc = struct.unpack_from("<IIIII", self.data, off)
            if not any(desc):
                break
            oft, _, _, name_rva, ft = desc
            dll = self.cstr(name_rva)
            thunk_rva = oft or ft
            toff = self.rva2off(thunk_rva)
            names = []
            step = 8 if self.is64 else 4
            flag = 1 << 63 if self.is64 else 1 << 31
            i = 0
            while True:
                val = struct.unpack_from("<Q" if self.is64 else "<I",
                                         self.data, toff + i * step)[0]
                if val == 0:
                    break
                if val & flag:
                    names.append(f"ordinal#{val & 0xFFFF}")
                else:
                    noff = self.rva2off(val & 0x7FFFFFFF)
                    if noff is None:
                        names.append("?")
                    else:
                        end = self.data.find(b"\0", noff + 2)
                        names.append(self.data[noff + 2:end].decode("latin1", "replace"))
                i += 1
            out.append({"dll": dll, "funcs": names})
            off += 20
        return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["imports", "exports", "sections", "summary"])
    ap.add_argument("file")
    ap.add_argument("--filter", default=None)
    ap.add_argument("--dll", default=None)
    a = ap.parse_args()
    pe = PE(a.file)
    arch = {0x14c: "x86", 0x8664: "x64", 0xaa64: "arm64"}.get(pe.machine, hex(pe.machine))
    print(f"# {a.file}  arch={arch} pe={('PE32+' if pe.is64 else 'PE32')} "
          f"sections={pe.nsec} datadirs={pe.num_dd}")

    if a.cmd == "summary":
        for name, vaddr, vsize, raw, rsize in pe.sections:
            print(f"  {name:<9} vaddr={vaddr:#010x} vsize={vsize:#09x} "
                  f"raw={raw:#09x} rsize={rsize:#09x}")
        ex = pe.exports()
        if ex:
            print(f"  exports: dll={ex[0]['dll']} count={ex[0]['count']} "
                  f"named={len(ex[0]['named'])}")
        im = pe.imports()
        print(f"  imported dlls={len(im)} funcs={sum(len(x['funcs']) for x in im)}")

    elif a.cmd == "sections":
        for name, vaddr, vsize, raw, rsize in pe.sections:
            print(f"{name:<9} vaddr={vaddr:#010x} vsize={vsize:#09x} "
                  f"raw={raw:#09x} rsize={rsize:#09x}")

    elif a.cmd == "exports":
        ex = pe.exports()
        if not ex:
            print("# no export directory")
            return
        print(f"# dll={ex[0]['dll']} base={ex[0]['base']} "
              f"functions={ex[0]['count']} named={len(ex[0]['named'])}")
        for e in sorted(ex[0]["named"], key=lambda x: x["ordinal"]):
            print(f"  {e['ordinal']:5d} {e['rva']:#010x} {e['name']}")

    elif a.cmd == "imports":
        for d in pe.imports():
            if a.dll and a.dll.lower() not in (d["dll"] or "").lower():
                continue
            funcs = d["funcs"]
            if a.filter:
                funcs = [f for f in funcs if a.filter.lower() in f.lower()]
                if not funcs:
                    continue
            print(f"\n[{d['dll']}]  ({len(funcs)} shown)")
            for i in range(0, len(funcs), 4):
                print("   " + ", ".join(funcs[i:i + 4]))


if __name__ == "__main__":
    main()
