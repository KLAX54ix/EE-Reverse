"""Generate an EE NATIVE function-image graph by driving the 函数曲线 dialog.

Reverse-engineered 2026-10-19 from the live modeless dialog (class #32770):

  id 5690  Edit   multiline  -> Y(x) formula
  id 5691  Edit              -> 常量定义
  id 5046  Button(check)     -> 使用自定义变量域  (enables from/to edits)
  id 5000  Edit              -> 从 (x from)
  id 5001  Edit              -> 至 (x to)
  id 5047  Button(check)     -> 输出为曲线对象 (leave UNCHECKED for the native
                                function-image object linked to the axis)
  id 5832  Button            -> 生成曲线
  id 1     Button            -> 确定

Cross-process notes: WM_SETTEXT via SendMessage returns 0 (not marshalled), but
the Win32 SetWindowTextW API works.  So text is written with SetWindowTextW.

Usage:
  python tools/ee_funcgen.py --formula "36/x" --from 3 --to 11
  python tools/ee_funcgen.py --dump          # show control states only
"""
import argparse
import ctypes
import ctypes.wintypes as wt
import sys
import time

u32 = ctypes.WinDLL("user32", use_last_error=True)

WM_GETTEXT = 0x000D
WM_GETTEXTLENGTH = 0x000E
BM_CLICK = 0x00F5
BM_GETCHECK = 0x00F0
BM_SETCHECK = 0x00F1
BST_CHECKED = 1

EnumChildProc = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
EnumProc = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)


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


def find_dialog(title="函数曲线"):
    found = []

    def cb(h, _):
        if u32.IsWindowVisible(h) and class_name(h) == "#32770" \
                and text_of(h) == title:
            found.append(h)
        return True

    u32.EnumWindows(EnumProc(cb), 0)
    return found[0] if found else None


def visible_edits(dlg):
    return [c for c in children(dlg)
            if class_name(c) == "Edit" and u32.IsWindowVisible(c)]


def visible_buttons(dlg):
    return [c for c in children(dlg)
            if class_name(c) == "Button" and u32.IsWindowVisible(c)]


def set_text(hwnd, text):
    return bool(u32.SetWindowTextW(hwnd, text))


def find_visible_edit_by_id(dlg, cid):
    for c in visible_edits(dlg):
        if ctrl_id(c) == cid:
            return c
    return None


def find_visible_button_by_id(dlg, cid):
    for c in visible_buttons(dlg):
        if ctrl_id(c) == cid:
            return c
    return None


def dump(dlg):
    print("dialog 0x%x" % dlg)
    for c in visible_edits(dlg):
        print("  edit  id=%-5d hwnd=0x%-8x text=%r"
              % (ctrl_id(c), c, text_of(c)))
    for c in visible_buttons(dlg):
        chk = u32.SendMessageW(c, BM_GETCHECK, 0, 0)
        print("  btn   id=%-5d hwnd=0x%-8x check=%d text=%r"
              % (ctrl_id(c), c, chk, text_of(c)))


def generate(formula, x0, x1, use_custom=True):
    dlg = find_dialog()
    if not dlg:
        print("ERROR: 函数曲线 dialog is not open")
        return 2

    formula_edit = find_visible_edit_by_id(dlg, 5690)
    if not formula_edit:
        print("ERROR: formula edit (5690) not visible")
        return 3
    if not set_text(formula_edit, formula):
        print("ERROR: could not set formula")
        return 4
    print("formula -> %r" % text_of(formula_edit))

    if use_custom:
        cb = find_visible_button_by_id(dlg, 5046)   # 使用自定义变量域
        if not cb:
            print("ERROR: 使用自定义变量域 checkbox (5046) not found")
            return 5
        # BM_CLICK toggles: only click when currently unchecked.
        chk = u32.SendMessageW(cb, BM_GETCHECK, 0, 0)
        if chk != BST_CHECKED:
            u32.SendMessageW(cb, BM_CLICK, 0, 0)
            time.sleep(0.2)
        chk = u32.SendMessageW(cb, BM_GETCHECK, 0, 0)
        print("checkbox 使用自定义变量域 check=%d" % chk)
        if chk != BST_CHECKED:
            print("ERROR: could not check 使用自定义变量域")
            return 5

        from_edit = find_visible_edit_by_id(dlg, 5000)
        to_edit = find_visible_edit_by_id(dlg, 5001)
        if not (from_edit and to_edit):
            print("ERROR: 从/至 edits (5000/5001) not visible")
            dump(dlg)
            return 6
        set_text(from_edit, str(x0))
        set_text(to_edit, str(x1))
        print("range -> %r .. %r" % (text_of(from_edit), text_of(to_edit)))

    gen = find_visible_button_by_id(dlg, 5832)      # 生成曲线
    if not gen:
        print("ERROR: 生成曲线 button (5832) not found")
        dump(dlg)
        return 7
    u32.SendMessageW(gen, BM_CLICK, 0, 0)
    print("clicked 生成曲线")
    time.sleep(0.3)
    return 0


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--formula")
    ap.add_argument("--from", dest="x0", default="0")
    ap.add_argument("--to", dest="x1", default="10")
    ap.add_argument("--dump", action="store_true")
    ap.add_argument("--no-custom-domain", action="store_true")
    a = ap.parse_args()
    dlg = find_dialog()
    if not dlg:
        print("函数曲线 dialog not found (open 绘图 -> 坐标轴和曲线 first)")
        return 1
    if a.dump or not a.formula:
        dump(dlg)
        return 0
    return generate(a.formula, a.x0, a.x1,
                    use_custom=not a.no_custom_domain)


if __name__ == "__main__":
    sys.exit(main())
