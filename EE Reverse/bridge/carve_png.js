// Carve every embedded PNG out of the live Editer process.
//   rpc.exports.carvePngs(outDir, minBytes)  -> {count, files:[...]}
// Writes real files so big images never have to cross the RPC/JSON boundary.
var _carveWritten = {};

function _carvePngs(outDir, minBytes) {
  var SIG = '89 50 4e 47 0d 0a 1a 0a';
  var min = minBytes || 200;
  var jobs = [];
  Process.enumerateRanges('r--').forEach(function (r) {
    if (r.size < 64) return;
    // The document images live in the app heap; skip huge mapped images of the
    // executables themselves to keep the scan bounded.
    if (r.size > 256 * 1024 * 1024) return;
    jobs.push(r);
  });
  var found = [];
  jobs.forEach(function (r) {
    var cur = r.base;
    var end = r.base.add(r.size);
    var guard = 0;
    while (cur.compare(end) < 0 && guard++ < 20000) {
      var m = Memory.scanSync(cur, end.sub(cur).toInt32(), SIG);
      if (!m || m.length === 0) break;
      var hit = m[0].address;
      // PNG length: parse chunks from the signature forward.
      var p = hit.add(8);
      var total = 8, ok = false, w = 0, h = 0;
      for (var k = 0; k < 64; k++) {
        var len = p.readU32();
        var type = p.add(4).readUtf8String(4);
        total += 12 + len;
        if (type === 'IHDR') { w = p.add(8).readU32(); h = p.add(12).readU32(); }
        if (type === 'IEND') { ok = true; break; }
        if (len > 64 * 1024 * 1024) break;
        p = p.add(12 + len);
      }
      if (ok && total >= min) found.push({ addr: hit, len: total, w: w, h: h });
      cur = hit.add(8);
    }
  });
  // Deduplicate identical byte ranges (identical pointers scanned twice).
  var seen = {}, files = [];
  found.forEach(function (f) {
    var key = f.addr.toString() + ':' + f.len;
    if (seen[key]) return;
    seen[key] = 1;
    var name = 'p_' + f.addr.toString().replace('0x', '') + '_' + f.w + 'x' + f.h + '.png';
    var path = outDir + '\\' + name;
    try {
      var bytes = f.addr.readByteArray(f.len);
      var fh = new File(path, 'wb');
      fh.write(bytes);
      fh.flush();
      fh.close();
      files.push({ name: name, addr: f.addr.toString(), bytes: f.len, w: f.w, h: f.h });
    } catch (e) {
      files.push({ name: name, addr: f.addr.toString(), error: String(e) });
    }
  });
  files.sort(function (a, b) { return a.addr < b.addr ? -1 : (a.addr > b.addr ? 1 : 0); });
  return { ok: true, scanned: jobs.length, count: files.length, files: files };
}
