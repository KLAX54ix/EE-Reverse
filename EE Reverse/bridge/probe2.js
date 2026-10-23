// EE runtime probe #2 — locate live engine object instances by vtable scan
// Read-only. Derives vtable addresses from real exports, then scans writable
// memory for objects whose first word is that vtable pointer.

var WANT = [
  'esDocument', 'esBaseDoc', 'esCanvas', 'esPageList', 'esDocPage',
  'esSegLine', 'esSegRect', 'esSegPolygon', 'esSegArc', 'esShapePath',
  'esObject', 'esShapeBase', 'esSnapManager', 'esUndo'
];

var MAX_PER_CLASS = 40;
var MAX_DUMP = 4;
var MAX_RANGE = 192 * 1024 * 1024;

function hexdump16(p) {
  try {
    return hexdump(p, { length: 48, ansi: false });
  } catch (e) {
    return '<unreadable: ' + e + '>';
  }
}

setImmediate(function () {
  var mod = Process.findModuleByName('eslib.dll');
  if (!mod) { send({ kind: 'error', message: 'eslib.dll not loaded' }); return; }

  var exps = mod.enumerateExports();
  var byName = {};
  exps.forEach(function (e) { byName[e.name] = e.address; });

  var targets = [];
  WANT.forEach(function (cls) {
    var a = byName['??_7' + cls + '@@6B@'];
    if (a) targets.push({ cls: cls, vtable: a });
  });
  send({ kind: 'targets', targets: targets.map(function (t) {
    return { cls: t.cls, vtable: t.vtable.toString() };
  }) });

  var ranges = Process.enumerateRanges('rw-').filter(function (r) {
    return r.size > 0 && r.size <= MAX_RANGE;
  });
  send({ kind: 'ranges', count: ranges.length,
         totalMB: Math.round(ranges.reduce(function (a, r) {
           return a + r.size; }, 0) / 1048576) });

  targets.forEach(function (t) {
    var hits = [];
    var pattern = t.vtable.toMatchPattern();
    ranges.forEach(function (r) {
      if (hits.length >= MAX_PER_CLASS) return;
      try {
        Memory.scanSync(r.base, r.size, pattern).forEach(function (m) {
          if (hits.length < MAX_PER_CLASS) hits.push(m.address);
        });
      } catch (e) { /* unreadable page mid-range */ }
    });
    var dumps = hits.slice(0, MAX_DUMP).map(function (h) {
      return { addr: h.toString(), head: hexdump16(h) };
    });
    send({ kind: 'instances', cls: t.cls, vtable: t.vtable.toString(),
           count: hits.length, addresses: hits.map(function (h) {
             return h.toString(); }), dumps: dumps });
  });
});
