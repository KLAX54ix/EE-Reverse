// EE runtime probe #1 — module load state + engine export/vtable inventory
// Target: Editer.exe (pid from REA Frida session). Read-only: no hooks installed yet.

function send2(kind, payload) {
  send(Object.assign({ kind: kind }, payload));
}

var KEY = [
  'esDocument', 'esBaseDoc', 'esCanvas', 'esPageList', 'esDocPage',
  'esSegLine', 'esSegRect', 'esSegPolygon', 'esSegArcBase', 'esSegArc',
  'esShapePath', 'esShapeBase', 'esObject', 'esShapeGroup',
  'esSegFormulaBox', 'esSegTextBox', 'esGraph', 'esSnapManager',
  'zArchive', 'esStyleSheet', 'esRender', 'esUndo'
];

setImmediate(function () {
  try {
    send2('info', {
      pointerSize: Process.pointerSize,
      arch: Process.arch,
      platform: Process.platform,
      pid: Process.id,
      mainModule: Process.mainModule ? Process.mainModule.name : null
    });

    var mods = Process.enumerateModules().map(function (m) {
      return { name: m.name, base: m.base.toString(), size: m.size, path: m.path };
    });
    send2('modules', { count: mods.length, mods: mods });
  } catch (e) {
    send2('error', { where: 'modules', message: String(e) });
  }

  try {
    var es = Process.findModuleByName('eslib.dll');
    if (!es) {
      send2('eslib', { present: false });
    } else {
      var exps = es.enumerateExports();
      var vt = {};
      var counts = { vtable: 0, ctor: 0, serialize: 0, setpoint: 0 };
      var wanted = {};

      exps.forEach(function (e) {
        if (e.name.indexOf('??_7') === 0) counts.vtable++;
        if (e.name.indexOf('??0') === 0) counts.ctor++;
        if (e.name.indexOf('Serialize@') > 0) counts.serialize++;
        if (e.name.indexOf('SetPointPos@') > 0) counts.setpoint++;
      });

      KEY.forEach(function (cls) {
        var needle7 = '??_7' + cls + '@@6B@';
        var found = exps.filter(function (e) { return e.name === needle7; })[0];
        if (found) {
          vt[cls] = found.address.toString();
          wanted[cls] = exps.filter(function (e) {
            var i = e.name.indexOf('@' + cls + '@@');
            return i > 0;
          }).map(function (e) { return e.name; }).length;
        }
      });

      send2('eslib', {
        present: true,
        base: es.base.toString(),
        size: es.size,
        path: es.path,
        exportCount: exps.length,
        counts: counts,
        vtables: vt,
        methodCounts: wanted
      });
    }
  } catch (e) {
    send2('error', { where: 'eslib', message: String(e) });
  }
});
