import json, struct, sys

ASAR = r'D:\deepseek-harness\resources\app.asar'

def load():
    f = open(ASAR, 'rb')
    a, hsz, c, jlen = struct.unpack('<IIII', f.read(16))
    js = f.read(jlen).decode('utf-8', 'replace')
    return f, json.loads(js), 16 + hsz, 16 + jlen

def find(node, parts):
    if not parts:
        return node
    files = node.get('files', {})
    if parts[0] not in files:
        return None
    return find(files[parts[0]], parts[1:])

def read_at(f, base, node):
    f.seek(base + int(node['offset']))
    return f.read(int(node['size']))

def main():
    f, idx, base_hsz, base_jlen = load()
    target = sys.argv[1]
    node = find(idx, target.strip('/').split('/'))
    if node is None:
        print('NOT FOUND:', target); return
    if 'files' in node:
        for name, v in sorted(node['files'].items()):
            print(' ', name, ('DIR' if 'files' in v else '%s B' % v.get('size')))
        return
    # try both bases, pick the one whose bytes look like text
    for base, label in ((base_jlen, 'jlen'), (base_hsz, 'hsz')):
        try:
            data = read_at(f, base, node)
        except Exception as e:
            print('base', label, 'err', e); continue
        try:
            txt = data.decode('utf-8')
            ok = sum(1 for ch in txt[:200] if ch.isprintable() or ch in '\r\n\t') > 180
        except Exception:
            ok = False
        if ok:
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
            print(txt)
            return
    print('could not decode', target)

main()
