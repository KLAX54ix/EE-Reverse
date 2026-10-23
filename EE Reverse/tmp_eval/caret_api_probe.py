names = open(r"D:\EE Reverse\tmp_eval\eslib_exports.txt", encoding="utf-8").read().splitlines()
kw = ["SetOffset", "Scroll", "ScrollTo", "EnsureVisible", "MakeVisible", "BringIntoView",
      "SetCaret", "MoveCaret", "Goto", "GoTo", "Locate", "SetEditPos", "SetActivePage",
      "SetPage", "PageDownUp", "ShowCaret", "SetSel", "SelectAll", "SelParaByGenre",
      "MakeCaret", "OnSetCaret", "GetCaret"]
seen=set()
for k in kw:
    print("##", k)
    for n in names:
        if k in n and n not in seen:
            seen.add(n)
            print("  ", n)
