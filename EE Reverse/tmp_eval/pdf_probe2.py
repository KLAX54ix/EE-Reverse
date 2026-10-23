import os, glob, pymupdf
base = r"Z:\菜鸡工作室\团队共享\#2课程资料\26年秋季资料\七A"
for pat in ["【答案】26秋七A 第01讲*.pdf", "【讲义】26秋七A 第01讲*.pdf", "【答案】26秋七A 第03讲*.pdf", "【讲义】26秋七A 第03讲*.pdf"]:
    for f in glob.glob(os.path.join(base, pat)):
        d = pymupdf.open(f)
        print("="*90)
        print(os.path.basename(f), "| pages:", d.page_count, "| size:", os.path.getsize(f))
        print("outline:", d.get_toc())
        for i, p in enumerate(d):
            lines = [l.strip() for l in p.get_text("text").splitlines() if l.strip()]
            print("  P%02d (%d lines): %r" % (i+1, len(lines), lines[:4]))
            if i >= 3: 
                print("  ... (stop after 4 pages)")
                break
        d.close()
