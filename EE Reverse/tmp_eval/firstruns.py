import sys
sys.path.insert(0, r"D:\EE Reverse\tmp_eval")
import parser as P

def dump(path, label, n=30):
    data = open(path,"rb").read()
    print("==", label, "size:", len(data))
    doc = P.parse_wsd(data)
    print("runs:", len(doc.text_runs), "chars:", len(doc.raw_text), "fonts:", len(doc.fonts))
    for i, r in enumerate(doc.text_runs[:n]):
        txt = getattr(r, "text", None)
        if txt is None:
            txt = str(r)
        print(i, repr(txt)[:60], "| attrs:", {k: getattr(r,k) for k in dir(r) if not k.startswith("_") and k in ("font","size","font_size","font_index","style","color")})
    print("raw head:", repr(doc.raw_text[:120]))

dump(r"C:\Users\84184\Desktop\26秋季初一培优班19次课.wsd", "desktop working")
dump(r"Z:\菜鸡工作室\团队共享\#2课程资料\26年秋季资料\七A\26秋季初一培优班19次课前6讲答案\26秋季初一培优班19次课.wsd", "teacher original")
