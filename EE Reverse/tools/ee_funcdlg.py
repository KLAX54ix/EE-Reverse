"""Drive EE's modeless "函数曲线" (function-curve) dialog from the command line.

Discovered 2026-10-19 while solving "native function graph" (see AGENTS.md):
the panel opened by 绘图 -> 坐标轴和曲线 is a plain #32770 dialog, so its
controls can be read and written with User32 messages -- no mouse automation,
no focus games.  That lets us create REAL native function-image objects
(axis-linked) instead of approximating curves with beziers.

Commands
--------
dump [--hwnd 0x120658]
    list every child control with class / id / text / rect
set --formula "36/x" --from 3 --to 11 [--ok] [--hwnd 0x...]
    write the formula and x-range edits, optionally press 确定
tabs
    list the tab pages (function / axis style)

Notes
-----
* WM_SETTEXT / WM_GETTEXT are marshalled by the OS, so a 64-bit Python can
  talk to the 32-bit dialog.
* The dialog is modeless: it applies to the currently active canvas, so make
  sure the target canvas is the active one (esCanvas::SetFocus via the bridge).
"""
import argparse
import ctypes
import ctypes.wintypes as wt
import sys

u32 = ctypes.WinDLL("user32", use_last_error=True)
WM_SETTEXT = 0x000C
WM_GETTEXT = 0x000D
WM_GETTEXTLENGTH = 0x000E
WM_COMMAND = 0x0111
BM_CLICK = 0x00F5
IDOK = 1

EnumChildProc = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)


class RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


def class_name(hwnd):
    buf = ctypes.create_unicode_buffer(256)
    u32.GetClassNameW(hwnd, buf, 256)
    return buf.value


def text_of(hwnd):
    n = u32.SendMessageW(hwnd, WM_GETTEXTLENGTH, 0, 0)
    buf = ctypes.create_unicode_buffer(n + 2)
    u32.SendMessageW(hwnd, WM_GETTEXT, n + 1, buf)
    return buf.value


def window_rect(hwnd):
    r = RECT()
    u32.GetWindowRect(hwnd, ctypes.byref(r))
    return (r.left, r.top, r.right, r.bottom)


def children(hwnd):
    out = []

    def cb(child, _):
        out.append(child)
        return True

    u32.EnumChildWindows(hwnd, EnumChildProc(cb), 0)
    return out


def find_dialog(title="函数曲线"):
    found = []

    EnumProc = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)

    def cb(hwnd, _):
        if (u32.IsWindowVisible(hwnd)
                and class_name(hwnd) == "#32770"
                and text_of(hwnd) == title):
            found.append(hwnd)
        return True

    u32.EnumWindows(EnumProc(cb), 0)
    return found[0] if found else None


def ctrl_id(hwnd):
    return u32.GetDlgCtrlID(hwnd)


def dump(hwnd):
    print("dialog 0x%x '%s' rect=%r" % (hwnd, text_of(hwnd), window_rect(hwnd)))
    for c in children(hwnd):
        cls = class_name(c)
        if cls in ("Static", "Button", "Edit", "ComboBox", "SysTabControl32",
                   "#32770", "msctls_trackbar32", "ListBox", "SysTreeView32"):
            vis = u32.IsWindowVisible(c)
            print("  0x%-8x id=%-5d %-20s vis=%d rect=%-26r text=%r"
                  % (c, ctrl_id(c), cls, vis, window_rect(c), text_of(c)))


def visible_edits(hwnd):
    """currently visible Edit controls, top-to-bottom, label guess by rect"""
    rows = []
    for c in children(hwnd):
        if class_name(c) == "Edit" and u32.IsWindowVisible(c):
            rows.append(c)
    rows.sort(key=lambda h: (window_rect(h)[1], window_rect(h)[0]))
    return rows


def set_text(hwnd, text):
    ok = u32.SendMessageW(hwnd, WM_SETTEXT, 0, text)
    return ok


def by_id(hwnd, cid, cls=None):
    for c in children(hwnd):
        if ctrl_id(c) == cid and (cls is None or class_name(c) == cls):
            return c
    return None


def click_button(hwnd, cid):
    b = by_id(hwnd, cid)
    if not b:
        return False
    u32.SendMessageW(b, BM_CLICK, 0, 0)
    return True


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("dump")
    d.add_argument("--hwnd", default=None)
    d.add_argument("--out", default=None,
                   help="write the UTF-8 listing to this file instead of stdout")

    s = sub.add_parser("set")
    s.add_argument("--formula", required=True)
    s.add_argument("--from", dest="x0", default=None)
    s.add_argument("--to", dest="x1", default=None)
    s.add_argument("--ok", action="store_true")
    s.add_argument("--gen", action="store_true",
                   help="press the 生成曲线 button (id 5832) after setting")
    s.add_argument("--hwnd", default=None)
    s.add_argument("--print-values", action="store_true")

    args = ap.parse_args()
    hwnd = int(args.hwnd, 16) if args.hwnd else find_dialog()
    if not hwnd:
        print("dialog not found (is the 函数曲线 panel open?)")
        return 2

    if args.cmd == "dump":
        import io
        buf = io.StringIO()
        old = sys.stdout
        sys.stdout = buf
        try:
            dump(hwnd)
        finally:
            sys.stdout = old
        listing = buf.getvalue()
        if args.out:
            with open(args.out, "w", encoding="utf-8") as fh:
                fh.write(listing)
            print("wrote %s" % args.out)
        else:
            sys.stdout.write(listing)
        return 0

    edits = visible_edits(hwnd)
    print("visible edits: %s" % [hex(e) for e in edits])
    # Explicit control ids, read off the dialog dump (tools/ee_funcdlg.py dump):
    #   5690 = Y(x) formula (tall edit), 5691 = 常量定义,
    #   5000 = 从 (x from), 5001 = 至 (x to)
    formula_edit = by_id(hwnd, 5690) or (edits[0] if edits else None)
    from_edit = by_id(hwnd, 5000) or by_id(hwnd, 5000, "Edit")
    to_edit = by_id(hwnd, 5001) or by_id(hwnd, 5001, "Edit")
    if not (formula_edit and from_edit and to_edit):
        print("could not identify the formula/range edits, dumping")
        dump(hwnd)
        return 3
    print("formula=0x%x from=0x%x to=0x%x"
          % (formula_edit, from_edit, to_edit))
    set_text(formula_edit, args.formula)
    if args.x0 is not None:
        set_text(from_edit, str(args.x0))
    if args.x1 is not None:
        set_text(to_edit, str(args.x1))
    if args.print_values:
        for e, name in ((formula_edit, "formula"), (from_edit, "from"),
                        (to_edit, "to")):
            print("%s = %r" % (name, text_of(e)))
    if args.gen:
        ok = click_button(hwnd, 5832)
        print("clicked 生成曲线: %s" % ok)
    if args.ok:
        # pressing 确定 == WM_COMMAND IDOK to the dialog
        u32.SendMessageW(hwnd, WM_COMMAND, IDOK, 0)
        print("sent IDOK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
