import os, glob, pymupdf
base = r"Z:\菜鸡工作室\团队共享\#2课程资料\26年秋季资料\七A\26秋季初一培优班19次课前6讲答案"
full = os.path.join(base, "26秋季初一培优班19次课前6讲答案.pdf")
d = pymupdf.open(full)
print("FULL:", full)
print("pages:", d.page_count)
print("metadata:", d.metadata)
print("outline:", d.get_toc())
for i, p in enumerate(d):
    t = p.get_text("text")
    lines = [l.strip() for l in t.splitlines() if l.strip()]
    print("P%02d lines=%d | %r" % (i+1, len(lines), lines[:5]))
    imgs = p.get_images(full=True)
    if imgs: print("     images:", len(imgs))
print("="*80)
for f in sorted(glob.glob(os.path.join(base, "*.pdf"))):
    if f == full: continue
    x = pymupdf.open(f)
    print(os.path.basename(f), "| pages:", x.page_count)
    for i, p in enumerate(x):
        lines = [l.strip() for l in p.get_text("text").splitlines() if l.strip()]
        print("   P%d: %r" % (i+1, lines[:4]))
    x.close()
