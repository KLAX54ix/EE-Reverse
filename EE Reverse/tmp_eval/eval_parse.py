# -*- coding: utf-8 -*-
"""快速评测 EduConverter 的 parser.py 在真实 .wsd 上的解析效果。"""
import sys, os, time, collections, unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import parser as P


def stats_text(s):
    c = collections.Counter()
    for ch in s:
        o = ord(ch)
        if ch.isspace():
            c['space'] += 1
        elif 0x4E00 <= o <= 0x9FFF:
            c['han'] += 1
        elif 0x0020 <= o <= 0x007E:
            c['ascii'] += 1
        elif 0x3000 <= o <= 0x303F or 0xFF00 <= o <= 0xFFEF:
            c['cjk_punct'] += 1
        elif 0x0370 <= o <= 0x03FF:
            c['greek'] += 1
        elif 0xE000 <= o <= 0xF8FF or 0xF0000 <= o <= 0xFFFFD:
            c['private_use'] += 1
        else:
            c['other'] += 1
    return c


def main(path):
    t0 = time.time()
    data = open(path, 'rb').read()
    print('file:', path, len(data), 'bytes')
    print('magic:', data[:12])
    doc = P.parse_wsd(data)
    dt = time.time() - t0
    print('parse time: %.2fs' % dt)
    print('fonts: %d' % len(doc.fonts))
    for f in doc.fonts:
        print('   [%d] cn=%r en=%r prop=0x%04x' % (f.index, f.cn_name, f.en_name, f.property_val))
    print('text objs/runs: %d, raw_text chars: %d, images: %d, tables: %d'
          % (len(doc.text_runs), len(doc.raw_text), len(doc.images), len(doc.tables)))
    st = stats_text(doc.raw_text)
    print('char categories:', dict(st))
    print('--- raw_text first 500 ---')
    print(doc.raw_text[:500].replace('\r', '\\r').replace('\n', '\\n'))
    print('--- runs (first 30) ---')
    for r in doc.text_runs[:30]:
        fname = r.font.cn_name if r.font else None
        flags = ''.join([('B' if r.bold else ''), ('I' if r.italic else ''),
                         ('S' if r.strikethrough else ''), ('U' if r.underline else '')])
        print('%r | font=%r size=%s fg=%s bg=%s %s para=%d'
              % (r.text[:50], fname, r.font_size_pt, r.color, r.bgcolor, flags, r.paragraph))
    print('--- per-paragraph sample (first 8) ---')
    by_para = collections.OrderedDict()
    for r in doc.text_runs:
        by_para.setdefault(r.paragraph, []).append(r.text)
    for i, (p, parts) in enumerate(list(by_para.items())[:8]):
        line = ''.join(parts)
        print('para %d (%d runs): %r' % (p, len(parts), line[:120]))
    # 简单 HTML 落盘
    html = doc.to_html()
    out = os.path.splitext(path)[0] + '.educonv_eval.html'
    open(out, 'w', encoding='utf-8').write(
        '<!DOCTYPE html><meta charset="utf-8"><body>' + html + '</body>')
    print('saved:', out)


if __name__ == '__main__':
    main(sys.argv[1])
