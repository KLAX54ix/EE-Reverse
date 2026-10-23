#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""split_answer_pdf.py — 把一个由 EduEditer 原生导出的“答案合集”PDF，按书签/标题拆成
每讲每部分的独立 PDF。

适用场景（本项目的答案整理工作流）：
    整本 wsd -> EE 原生导出 PDF（每节标题会生成 PDF 书签）
    -> 本脚本按书签把“第X讲 典型例题（答案） / 第X讲 巩固练习（答案）”拆成单文件

特性：
  * 优先用 PDF 大纲（EduEditer 导出时由标题段落自动生成）；
  * 没有大纲时回退为“扫描每页开头文字找标题”；
  * 页级复制（insert_pdf），不重渲染、不损文字层/图片；
  * 输出清单 CSV（讲次 / 部分 / 起止页 / 文件名 / 校验信息）；
  * --compare 可与“人工拆好的参考目录”逐页对比文本与页数，验证拆分是否正确。

用法示例：
  python split_answer_pdf.py "整本.pdf" --out out_dir
  python split_answer_pdf.py "整本.pdf" --out out_dir --only 巩固练习
  python split_answer_pdf.py "整本.pdf" --out out_dir --course "26秋季初一培优班19次课" \
      --compare "参考拆分目录"
"""
import argparse
import csv
import os
import re
import sys
import unicodedata

try:
    import pymupdf as fitz
except ImportError:  # 旧版 PyMuPDF
    import fitz

# 第1讲 典型例题（答案） / 第2讲  巩固练习（答案）
SEC_RE = re.compile(r"第\s*(\d+)\s*讲\s*(典型例题|巩固练习)")
KINDS = ("典型例题", "巩固练习")
COURSE_TAIL_RE = re.compile(r"(?:前\s*\d+\s*讲\s*答案|答案)\s*$")


def norm(s: str) -> str:
    """比对用：去空白差异、全角/半角统一。"""
    s = unicodedata.normalize("NFKC", s or "")
    return re.sub(r"\s+", "", s)


def page_head(pdf, pageno: int, max_lines: int = 4) -> str:
    """某页（1 基）开头几行拼成的字符串，用于校验标题是否在页首。"""
    text = pdf[pageno - 1].get_text("text")
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    return "".join(lines[:max_lines])


def sections_from_outline(pdf):
    """从 PDF 大纲提取 [(n, kind, start_page, title)]，按页码排序、去重。"""
    out, seen = [], set()
    for item in pdf.get_toc(simple=True) or []:
        _lvl, title, page = item[0], item[1], item[2]
        m = SEC_RE.search(title or "")
        if not m:
            continue
        key = (int(m.group(1)), m.group(2))
        if key in seen:
            continue
        seen.add(key)
        out.append((key[0], key[1], page, title))
    out.sort(key=lambda x: (x[2], x[0]))
    return out


def sections_from_text(pdf):
    """无大纲时的兜底：扫描每页开头找“第X讲 典型例题/巩固练习”。"""
    out, seen = [], set()
    for pno in range(1, pdf.page_count + 1):
        head = page_head(pdf, pno, 4)
        m = SEC_RE.search(head)
        if not m:
            continue
        key = (int(m.group(1)), m.group(2))
        if key in seen:
            continue
        seen.add(key)
        out.append((key[0], key[1], pno, head))
    return out


def build_sections(pdf):
    """返回 (sections, source)，sections = [(n,kind,start,end,title,warn)]。"""
    outline = sections_from_outline(pdf)
    source = "outline"
    if not outline:
        outline = sections_from_text(pdf)
        source = "page-text"
    if not outline:
        raise SystemExit("FAIL: 没有找到任何“第X讲 典型例题/巩固练习”标题（大纲和页面文字都没有）")

    secs = []
    for i, (n, kind, start, title) in enumerate(outline):
        end = outline[i + 1][2] - 1 if i + 1 < len(outline) else pdf.page_count
        warn = []
        if end < start:
            warn.append("下一页起点不在本页之后，页范围为空")
        # 标题应出现在起始页开头（容许标题被排版拆成两行）
        head = norm(page_head(pdf, start, 6))
        if norm(f"第{n}讲{kind}") not in head and norm(title) not in head:
            warn.append("起始页开头未找到该标题，可能拆分点不在页首")
        secs.append((n, kind, start, end, title, warn))
    return secs, source, outline


def course_from_pdf(pdf_path, override=None):
    if override:
        return override
    stem = os.path.splitext(os.path.basename(pdf_path))[0]
    return COURSE_TAIL_RE.sub("", stem) or stem


def out_name(course, n, kind):
    return f"【答案】{course} 第{n}讲 {kind}.pdf"


def extract_nk(name):
    m = SEC_RE.search(name)
    if not m:
        return None
    return int(m.group(1)), m.group(2)


def compare_with_reference(out_dir, ref_dir):
    """把生成文件与人工拆分参考目录逐项对比（页数 + 每页文本）。"""
    ref_map = {}
    for fn in os.listdir(ref_dir):
        if not fn.lower().endswith(".pdf"):
            continue
        nk = extract_nk(fn)
        if nk:
            ref_map[nk] = os.path.join(ref_dir, fn)

    rows = []
    for nk, ref_path in sorted(ref_map.items()):
        n, kind = nk
        gen_path = find_generated(out_dir, n, kind)
        row = {"n": n, "kind": kind, "ref": os.path.basename(ref_path),
               "gen": os.path.basename(gen_path) if gen_path else None,
               "ref_pages": None, "gen_pages": None, "pages_match": False,
               "text_match": False, "note": ""}
        try:
            r = fitz.open(ref_path)
            row["ref_pages"] = r.page_count
            if gen_path:
                g = fitz.open(gen_path)
                row["gen_pages"] = g.page_count
                row["pages_match"] = (r.page_count == g.page_count)
                if row["pages_match"]:
                    ok = True
                    for i in range(r.page_count):
                        if norm(r[i].get_text("text")) != norm(g[i].get_text("text")):
                            ok = False
                            row["note"] = f"第{i+1}页文本不一致"
                            break
                    row["text_match"] = ok
                else:
                    row["note"] = "页数不同"
                g.close()
            else:
                row["note"] = "生成目录里没找到对应文件"
            r.close()
        except Exception as e:  # noqa: BLE001
            row["note"] = f"读取失败: {e}"
        rows.append(row)
    return rows


def find_generated(out_dir, n, kind):
    for fn in os.listdir(out_dir):
        if not fn.lower().endswith(".pdf"):
            continue
        nk = extract_nk(fn)
        if nk == (n, kind):
            return os.path.join(out_dir, fn)
    return None


def main(argv=None):
    ap = argparse.ArgumentParser(description="按 EE 导出 PDF 的书签/标题拆分答案 PDF")
    ap.add_argument("pdf", help="EduEditer 原生导出的整本 PDF")
    ap.add_argument("--out", required=True, help="输出目录（不存在会自动创建）")
    ap.add_argument("--course", default=None,
                    help="文件名里的课程名，默认从 PDF 文件名去掉“前N讲答案/答案”后缀")
    ap.add_argument("--only", choices=list(KINDS) + ["both"], default="both",
                    help="只输出某一部分（默认两部分都输出）")
    ap.add_argument("--overwrite", action="store_true", help="允许覆盖已存在的输出文件")
    ap.add_argument("--dry-run", action="store_true", help="只打印计划，不写文件")
    ap.add_argument("--compare", default=None, help="人工拆分参考目录，逐页对比验证")
    args = ap.parse_args(argv)

    pdf = fitz.open(args.pdf)
    secs, source, outline = build_sections(pdf)
    course = course_from_pdf(args.pdf, args.course)

    print(f"PDF: {args.pdf}")
    print(f"页数: {pdf.page_count} | 标题来源: {source} | 课程名: {course}")
    print(f"发现 {len(secs)} 个部分:")
    plans = []
    for n, kind, start, end, title, warn in secs:
        if args.only != "both" and kind != args.only:
            continue
        fn = out_name(course, n, kind)
        plans.append((n, kind, start, end, title, warn, fn))
        flag = ("  ! " + "; ".join(warn)) if warn else ""
        print(f"  第{n}讲 {kind}: p{start}-{end} ({end-start+1}页) -> {fn}{flag}")

    total = sum(x[3] - x[2] + 1 for x in plans)
    total_all = sum(s[3] - s[2] + 1 for s in secs)
    print(f"计划输出 {len(plans)} 个文件，共 {total} 页（整本 {pdf.page_count} 页）")
    if args.only != "both":
        print(f"  只输出「{args.only}」，其余 {pdf.page_count - total} 页不参与本次输出（正常）")
    elif total != pdf.page_count:
        print(f"  ! 注意：所有部分合计 {total_all} 页，整本 {pdf.page_count} 页"
              f"（有 {pdf.page_count - total_all} 页不属于任何部分）")
    if args.dry_run:
        return 0

    os.makedirs(args.out, exist_ok=True)
    manifest = []
    for n, kind, start, end, title, warn, fn in plans:
        dst = os.path.join(args.out, fn)
        if os.path.exists(dst) and not args.overwrite:
            print(f"  SKIP 已存在: {fn}")
            continue
        out = fitz.open()
        out.insert_pdf(pdf, from_page=start - 1, to_page=end - 1, links=True, annots=True)
        md = dict(pdf.metadata or {})
        md["title"] = f"第{n}讲 {kind}（答案）"
        out.set_metadata(md)
        out.save(dst, garbage=3, deflate=True)
        out.close()
        manifest.append({"讲次": n, "部分": kind, "起始页": start, "结束页": end,
                         "页数": end - start + 1, "文件": fn,
                         "校验": "OK" if not warn else "; ".join(warn)})
        print(f"  写入 {fn} (p{start}-{end})")

    csv_path = os.path.join(args.out, "_split_manifest.csv")
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["讲次", "部分", "起始页", "结束页", "页数", "文件", "校验"])
        w.writeheader()
        w.writerows(manifest)
    print(f"清单: {csv_path}")

    if args.compare:
        print("\n== 与参考拆分对比 ==")
        rows = compare_with_reference(args.out, args.compare)
        bad = 0
        for r in rows:
            status = "OK" if (r["pages_match"] and r["text_match"]) else "DIFF"
            if status != "OK":
                bad += 1
            print(f"  第{r['n']}讲 {r['kind']}: {status} "
                  f"(参考 {r['ref_pages']}p / 生成 {r['gen_pages']}p) {r['note']}")
        print(f"  共 {len(rows)} 项，{len(rows)-bad} 项一致，{bad} 项不一致")
        rep = os.path.join(args.out, "_split_compare.csv")
        with open(rep, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else [])
            w.writeheader()
            w.writerows(rows)
        print(f"  对比报告: {rep}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
