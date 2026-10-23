"""Probe the EE 函数曲线 dialog edits: style bits, read-only, and try typing.

WM_SETTEXT was silently rejected on the formula edit (text read back ''), so the
control is probably ES_READONLY or a custom formula editor.  This script reports
the real state and optionally injects WM_CHAR keystrokes.

  python tools/ee_funcdlg_probe.py info
  python tools/ee_funcdlg_probe.py type --text "36/x"
"""
import argparse
import ctypes
import ctypes.wintypes as wt
import sys

u32 = ctypes.WinDLL("user32", use_last_error=True)
GWL_STYLE = -16
WS_DISABLED = 0x08000000
ES_READONLY = 0x0800
ES_MULTILINE = 0x0004
WM_CHAR = 0x0102
WM_SETTEXT = 0x000C
WM_GETTEXT = 0x000D
WM_GETTEXTLENGTH = 0x000E
BM_CLICK = 0x00F5

EnumChildProc = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)


def class_name(hwnd):
    b = ctypes.create_unicode_buffer(256)
    u32.GetClassNameW(hwnd, b, 256)
    return b.value


def ctrl_id(hwnd):
    return u32.GetDlgCtrlID(hwnd)


def text_of(hwnd):
    n = u32.SendMessageW(hwnd, WM_GETTEXTLENGTH, 0, 0)
    b = ctypes.create_unicode_buffer(n + 2)
    u32.SendMessageW(hwnd, WM_GETTEXT, n + 1, b)
    return b.value


def children(hwnd):
    out = []
    u32.EnumChildWindows(hwnd, EnumChildProc(
        lambda c, _: (out.append(c), True)[1]), 0)
    return out


def find_dialog():
    found = []
    EnumProc = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)

    def cb(hwnd, _):
        if u32.IsWindowVisible(hwnd) and class_name(hwnd) == "#32770" \
                and text_of(hwnd) == "函数曲线":
            found.append(hwnd)
        return True

    u32.EnumWindows(EnumProc(cb), 0)
    return found[0] if found else None


def info():
    dlg = find_dialog()
    if not dlg:
        print("dialog not open")
        return 1
    print("dialog 0x%x" % dlg)
    for c in children(dlg):
        if ctrl_id(c) in (5690, 5688, 5685, 5691, 5000, 5001):
            style = u32.GetWindowLongW(c, GWL_STYLE) & 0xFFFFFFFF
            print("  0x%-8x id=%-5d %-8s vis=%d enabled=%d readonly=%d "
                  "multiline=%d text=%r"
                  % (c, ctrl_id(c), class_name(c), u32.IsWindowVisible(c),
                     u32.IsWindowEnabled(c),
                     1 if style & ES_READONLY else 0,
                     1 if style & ES_MULTILINE else 0,
                     text_of(c)))
    return 0


def type_text(text, cid=5690):
    dlg = find_dialog()
    if not dlg:
        print("dialog not open")
        return 1
    target = None
    for c in children(dlg):
        if ctrl_id(c) == cid and class_name(c) == "Edit":
            target = c
            break
    if not target:
        print("edit id %d not found" % cid)
        return 2
    print("typing into 0x%x (id %d)" % (target, cid))
    u32.SetFocus(target)
    for ch in text:
        u32.SendMessageW(target, WM_CHAR, ord(ch), 0)
    print("after: %r" % text_of(target))
    return 0


def click(cid):
    dlg = find_dialog()
    if not dlg:
        print("dialog not open")
        return 1
    for c in children(dlg):
        if ctrl_id(c) == cid:
            u32.SendMessageW(c, BM_CLICK, 0, 0)
            print("clicked 0x%x id %d" % (c, cid))
            return 0
    print("control id %d not found" % cid)
    return 2


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("info")
    t = sub.add_parser("type")
    t.add_argument("--text", required=True)
    t.add_argument("--id", type=int, default=5690)
    sub.add_parser("gen").add_argument("--id", type=int, default=5832)
    a = ap.parse_args()
    if a.cmd == "info":
        return info()
    if a.cmd == "type":
        return type_text(a.text, a.id)
    if a.cmd == "gen":
        return click(a.id)
    return 0


if __name__ == "__main__":
    sys.exit(main())
