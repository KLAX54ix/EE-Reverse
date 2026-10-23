import struct, sys, os
sys.path.insert(0, r"D:\EE Reverse\tools")
import pe_resources as pr
RT_STRING = 6
path = r"D:\EduEditer\EduEditer208\Editer.exe"
data, sections, rsrc = pr.load(path)
res = pr.walk(data, sections, rsrc)
for p, blob in res:
    if len(p) == 3 and p[0] == RT_STRING:
        block = p[1]
        pos = 0
        for i in range(16):
            if pos + 2 > len(blob): break
            ln = struct.unpack_from('<H', blob, pos)[0]; pos += 2
            if ln == 0: continue
            s = blob[pos:pos+ln*2].decode('utf-16-le', 'replace'); pos += ln*2
            sid = (block - 1) * 16 + i
            if '答案' in s or '插入' in s or '题目' in s:
                print(f"sid={sid} (block={block} idx={i}) {s!r}")
