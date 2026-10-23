"""Probe cross-process text injection into the EE 函数曲线 dialog.

Reports SendMessage/SetWindowText return codes and the read-back text, so we can
tell whether the control is a plain CEdit (which the OS marshals WM_SETTEXT for)
or a superclassed control that ignores it.

  python tools/ee_funcdlg_probe2.py
"""
import ctypes
import ctypes.wintypes as wt
import sys

u32 = ctypes.WinDLL("user32", use_last_error=True)
WM_SETTEXT = 0x000C
WM_GETTEXT = 0x000D
WM_GETTEXTLENGTH = 0x000E
WM_CHAR = 0x0102

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
    got = u32.SendMessageW(hwnd, WM_GETTEXT, n + 1, b)
    return got, b.value


def children(hwnd):
    out = []
    u32.EnumChildWindows(hwnd, EnumChildProc(
        lambda c, _: (out.append(c), True)[1]), 0)
    return out


def find_dialog():
    found = []
    EnumProc = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    u32.EnumWindows(EnumProc(lambda h, _: (found.append(h), True)[1]
                             if u32.IsWindowVisible(h)
                             and class_name(h) == "#32770"
                             else True), 0)
    for h in found:
        got, t = text_of(h)
        if t == "函数曲线":
            return h
    return None


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    dlg = find_dialog()
    if not dlg:
        print("no 函数曲线 dialog")
        return 1
    print("dialog 0x%x" % dlg)
    kids = {ctrl_id(c): c for c in children(dlg) if class_name(c) == "Edit"}
    for cid in (5690, 5691, 5000, 5001):
        c = kids.get(cid)
        if not c:
            print("id %d: no edit" % cid)
            continue
        got, before = text_of(c)
        ret = u32.SendMessageW(c, WM_SETTEXT, 0, "TEST123")
        got2, after = text_of(c)
        ret2 = u32.SetWindowTextW(c, "WINAPI")
        got3, after2 = text_of(c)
        print("id %-5d hwnd=0x%-8x before=%r sm_settext_ret=%r after=%r "
              "settextW_ret=%r after2=%r"
              % (cid, c, before, ret, after, ret2, after2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
