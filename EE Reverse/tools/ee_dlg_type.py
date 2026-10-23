"""Typing helper for the EE 函数曲线 dialog: focus + WM_CHAR (same-thread path).

Cross-process WM_SETTEXT/WM_CHAR without focus had no effect on the reopened
panel (the CEdit ignores input it did not receive through its own focus/state),
so this attaches the input queue to the dialog's thread, foregrounds the dialog,
focuses the edit and posts WM_CHAR characters, then restores.

  python tools/ee_dlg_type.py --id 5690 --text "36/x"
  python tools/ee_dlg_type.py --check 5046      # toggle a checkbox (click)
  python tools/ee_dlg_type.py --click 5832      # click a button
  python tools/ee_dlg_type.py --read
"""
import argparse
import ctypes
import ctypes.wintypes as wt
import sys
import time

u32 = ctypes.WinDLL("user32", use_last_error=True)
k32 = ctypes.WinDLL("kernel32", use_last_error=True)
WM_GETTEXT = 0x000D
WM_GETTEXTLENGTH = 0x000E
WM_CHAR = 0x0102
BM_CLICK = 0x00F5
BM_GETCHECK = 0x00F0
BST_CHECKED = 1

EnumChildProc = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
EnumProc = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)


def class_name(h):
    b = ctypes.create_unicode_buffer(256)
    u32.GetClassNameW(h, b, 256)
    return b.value


def text_of(h):
    n = u32.SendMessageW(h, WM_GETTEXTLENGTH, 0, 0)
    b = ctypes.create_unicode_buffer(n + 2)
    u32.SendMessageW(h, WM_GETTEXT, n + 1, b)
    return b.value


def children(h):
    out = []
    u32.EnumChildWindows(h, EnumChildProc(
        lambda c, _: (out.append(c), True)[1]), 0)
    return out


def find_dialog():
    found = []

    def cb(h, _):
        if u32.IsWindowVisible(h) and class_name(h) == "#32770" \
                and text_of(h) == "函数曲线":
            found.append(h)
        return True

    u32.EnumWindows(EnumProc(cb), 0)
    return found[0] if found else None


def find_child(dlg, cid, cls=None):
    for c in children(dlg):
        if u32.GetDlgCtrlID(c) == cid and (cls is None or class_name(c) == cls):
            return c
    return None


def focus_for_input(dlg, target):
    """Attach to the dialog's thread, foreground it, focus target."""
    fg = u32.GetForegroundWindow()
    fg_tid = u32.GetWindowThreadProcessId(fg, None)
    dlg_tid = u32.GetWindowThreadProcessId(dlg, None)
    my_tid = k32.GetCurrentThreadId()
    attached = bool(u32.AttachThreadInput(my_tid, dlg_tid, True))
    u32.SetForegroundWindow(dlg)
    u32.BringWindowToTop(dlg)
    u32.SetFocus(target)
    time.sleep(0.1)
    return (fg, fg_tid, dlg_tid, my_tid, attached)


def restore(ctx):
    fg, fg_tid, dlg_tid, my_tid, attached = ctx
    try:
        if fg:
            u32.SetForegroundWindow(fg)
    except Exception:
        pass
    if attached:
        try:
            u32.AttachThreadInput(my_tid, dlg_tid, False)
        except Exception:
            pass


def type_text(dlg, cid, text):
    target = find_child(dlg, cid, "Edit")
    if not target:
        print("edit %d not found" % cid)
        return 2
    ctx = focus_for_input(dlg, target)
    try:
        for ch in text:
            u32.SendMessageW(target, WM_CHAR, ord(ch), 0)
            time.sleep(0.01)
    finally:
        restore(ctx)
    print("edit %d -> %r" % (cid, text_of(target)))
    return 0


def click(dlg, cid):
    c = find_child(dlg, cid)
    if not c:
        print("control %d not found" % cid)
        return 2
    before = u32.SendMessageW(c, BM_GETCHECK, 0, 0) \
        if class_name(c) == "Button" else None
    u32.SendMessageW(c, BM_CLICK, 0, 0)
    time.sleep(0.15)
    after = u32.SendMessageW(c, BM_GETCHECK, 0, 0) \
        if class_name(c) == "Button" else None
    print("clicked %d (%s) check %r->%r"
          % (cid, text_of(c), before, after))
    return 0


def read(dlg):
    for c in children(dlg):
        if class_name(c) in ("Edit", "Button") and u32.IsWindowVisible(c):
            extra = ""
            if class_name(c) == "Button":
                extra = " check=%d" % u32.SendMessageW(c, BM_GETCHECK, 0, 0)
            print("  %-8s id=%-5d hwnd=0x%-8x text=%r%s"
                  % (class_name(c), u32.GetDlgCtrlID(c), c, text_of(c), extra))
    return 0


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", type=int)
    ap.add_argument("--text")
    ap.add_argument("--click", type=int)
    ap.add_argument("--check", type=int)
    ap.add_argument("--read", action="store_true")
    a = ap.parse_args()
    dlg = find_dialog()
    if not dlg:
        print("函数曲线 dialog not open")
        return 1
    if a.read or not (a.text or a.click or a.check):
        return read(dlg)
    if a.text is not None:
        rc = type_text(dlg, a.id or 5690, a.text)
        if rc:
            return rc
    if a.check is not None:
        c = find_child(dlg, a.check)
        if c and u32.SendMessageW(c, BM_GETCHECK, 0, 0) != BST_CHECKED:
            u32.SendMessageW(c, BM_CLICK, 0, 0)
            time.sleep(0.1)
        print("check %d state=%r" % (a.check,
              u32.SendMessageW(c, BM_GETCHECK, 0, 0) if c else None))
    if a.click is not None:
        rc = click(dlg, a.click)
        if rc:
            return rc
    return read(dlg)


if __name__ == "__main__":
    sys.exit(main())
