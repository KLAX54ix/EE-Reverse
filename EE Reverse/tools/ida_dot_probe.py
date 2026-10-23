"""Dump everything needed to build EE's native 'bold point' (加粗点) from eslib/Editer.

Run:  idat64.exe -A -S"ida_dot_probe.py" -L"ida_dot_probe.log" <target>
Writes a report next to the script (or to %TEMP%).
"""
import os
import sys
import idautils
import idaapi
import ida_funcs
import ida_name
import ida_bytes
import ida_ua
import idc

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)) or ".", "ida_dot_probe.txt")
if not os.path.isdir(os.path.dirname(OUT)):
    OUT = os.path.join(os.environ.get("TEMP", "."), "ida_dot_probe.txt")

TARGETS = [
    "??0esSegPoint@@QAE@XZ",
    "??0esSegPoint@@QAE@VzPoint@@G@Z",
    "?__autoclassinit2@esSegPoint@@QAEXI@Z",
    "??_7esSegPoint@@6B@",
    "?Build@esSegPoint@@MAEXH@Z",
    "?RecalcLayout@esSegPoint@@MAEXXZ",
    "?Draw@esSegPoint@@UAEXPAVesRender@@PAUtag_DRAWPARAM@@PBVMatrix@Gdiplus@@@Z",
    "?SetPointPos@esSegPoint@@UAEHPAVesSnapManager@@HIPAVMatrix@Gdiplus@@@Z",
    "??0esShapeLine@@QAE@XZ",
    "?__autoclassinit2@esShapeLine@@QAEXI@Z",
]

lines = []


def w(s=""):
    lines.append(str(s))


def disasm_window(ea, before=0, count=24):
    """linear disassembly listing starting at ea"""
    out = []
    cur = ea
    for _ in range(count):
        if cur == idaapi.BADADDR:
            break
        ins = ida_ua.insn_t()
        n = ida_ua.decode_insn(ins, cur)
        if n == 0:
            out.append("  %08X  <undecodable>" % cur)
            cur += 1
            continue
        text = idc.generate_disasm_line(cur, 0)
        out.append("  %08X  %s" % (cur, text))
        cur += n
    return out


def main():
    idaapi.auto_wait()
    w("target: %s" % idaapi.get_input_file_path())
    w("imagebase: 0x%08X" % idaapi.get_imagebase())
    w("")

    found = {}
    w("=== symbols")
    for t in TARGETS:
        ea = ida_name.get_name_ea(idaapi.BADADDR, t)
        found[t] = ea
        w("  %-70s %s" % (t, ("0x%08X" % ea) if ea != idaapi.BADADDR else "NOT FOUND"))

    w("")
    w("=== xrefs to esSegPoint ctor / autoclassinit / vtable")
    for t in ("??0esSegPoint@@QAE@XZ", "??0esSegPoint@@QAE@VzPoint@@G@Z",
              "?__autoclassinit2@esSegPoint@@QAEXI@Z", "??_7esSegPoint@@6B@"):
        ea = found.get(t, idaapi.BADADDR)
        if ea == idaapi.BADADDR:
            continue
        w("-- %s @ 0x%08X" % (t, ea))
        for x in idautils.XrefsTo(ea, 0):
            fn = ida_funcs.get_func(x.frm)
            fnname = ida_funcs.get_func_name(fn.start_ea) if fn else "?"
            w("   from 0x%08X (%s) type=%d func=%s" % (x.frm, fnname, x.type,
                                                       ("0x%08X" % fn.start_ea) if fn else "-"))
            # the instruction that references it, plus a window: the allocation
            # size is usually a push/mov immediate a few instructions earlier
            start = x.frm
            for _ in range(6):
                prev = idc.prev_head(start)
                if prev == idaapi.BADADDR:
                    break
                start = prev
            for ln in disasm_window(start, count=14):
                w("      " + ln)
            w("")

    w("")
    w("=== every immediate passed to __autoclassinit2 (class sizes)")
    for t, ea in found.items():
        if ea == idaapi.BADADDR:
            continue
        if "__autoclassinit2" not in t:
            continue
        for x in idautils.XrefsTo(ea, 0):
            w("  %s <- 0x%08X" % (t, x.frm))
            for ln in disasm_window(x.frm, count=1):
                w("      " + ln)
            # walk back for the immediate size argument
            cur = x.frm
            for _ in range(8):
                cur = idc.prev_head(cur)
                if cur == idaapi.BADADDR:
                    break
                ins = ida_ua.insn_t()
                if ida_ua.decode_insn(ins, cur):
                    for i in range(6):
                        if ins.ops[i].type == ida_ua.o_imm:
                            w("      size-candidate @0x%08X = 0x%X (%d)"
                              % (cur, ins.ops[i].value, ins.ops[i].value))
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("wrote %s (%d lines)" % (OUT, len(lines)))
    idc.qexit(0)


main()
