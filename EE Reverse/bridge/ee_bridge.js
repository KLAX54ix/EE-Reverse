'use strict';
// EE (EduEditer) runtime bridge — injected into Editer.exe.
// Resolves eslib.dll exports and exposes a callable RPC surface.
//
// Contract: the only target-memory writes are (a) scratch buffers built for
// engine calls, (b) engine object construction, and (c) explicit canvas list
// surgery in unlinkShape. Nothing else is mutated.

var MODNAME = 'eslib.dll';
var EXP = null;

// Byte offsets verified against eslib.dll's export tables (tools/vtinfo.py).
var VT_RECALC = 0x64;        // esShapeBase/esShapePath/esSegLable::RecalcLayout
var VT_BUILD = 0x7c;         // esSegLable::Build(int)
var CANVAS_HEAD = 0x38;      // esCanvas + 0x38 -> newest shape
var SHAPE_NEXT = 0x48;       // esShapeBase + 0x48 -> older shape
var SEGLABEL_SIZE = 0xd8;    // esSegLable
var SEGPOINT_SIZE = 0x68;    // esSegPoint  (the 加粗点 / bold-point segment)
var SHAPELINE_SIZE = 0x5c;   // esShapeLine
var STYLE_LABEL = 0x4001007; // style bits the editor ORs into +0x34 for labels

function eslib() { return Process.findModuleByName(MODNAME); }

function ensureExports() {
  if (EXP) return EXP;
  EXP = {};
  var m = eslib();
  if (m) m.enumerateExports().forEach(function (e) { EXP[e.name] = e.address; });
  return EXP;
}

function toPtr(v) {
  if (v === null || v === undefined) return ptr(0);
  if (typeof v === 'string') return ptr(v);
  return v;
}

// Scalars stay numbers; pointers/64-bit values become hex strings.
function numOrPtr(r) {
  if (r === null || r === undefined) return null;
  if (typeof r === 'number') return r;
  return r.toString();
}

function isLivePtr(p) {
  if (p === null || p === undefined) return false;
  var v = typeof p === 'string' ? parseInt(p, 16) : p;
  return typeof v === 'number' && v > 0x10000 && v < 0x7fffffff;
}

// Scan writable memory for objects whose first dword is the given vtable.
function scanInstances(vtAddr, max, maxRangeMB) {
  var cap = max || 64;
  var maxRange = (maxRangeMB || 192) * 1024 * 1024;
  var pattern = vtAddr.toMatchPattern();
  var hits = [];
  var ranges = Process.enumerateRanges('rw-');
  for (var i = 0; i < ranges.length && hits.length < cap; i++) {
    var r = ranges[i];
    if (r.size <= 0 || r.size > maxRange) continue;
    try {
      var found = Memory.scanSync(r.base, r.size, pattern);
      for (var j = 0; j < found.length && hits.length < cap; j++) {
        hits.push(found[j].address);
      }
    } catch (err) { /* page vanished mid-scan */ }
  }
  return hits;
}

rpc.exports = {
  info: function () {
    var m = eslib(), e = ensureExports(), n = 0;
    for (var k in e) n++;
    return {
      pid: Process.id,
      arch: Process.arch,
      pointerSize: Process.pointerSize,
      eslibBase: m ? m.base.toString() : null,
      eslibSize: m ? m.size : null,
      exportCount: n,
      mainModule: Process.mainModule ? Process.mainModule.name : null
    };
  },

  expaddr: function (name) {
    var e = ensureExports();
    return e[name] ? e[name].toString() : null;
  },

  names: function (pattern, limit) {
    var e = ensureExports(), out = [];
    for (var k in e) {
      if (k.indexOf(pattern) >= 0) {
        out.push(k);
        if (out.length >= (limit || 200)) break;
      }
    }
    return out;
  },

  // name -> address for every exported vtable (`??_7<Class>@@6B@`)
  vtables: function () {
    var e = ensureExports(), out = {};
    for (var k in e) {
      if (k.indexOf('??_7') === 0) out[k] = e[k].toString();
    }
    return out;
  },

  // Scan writable memory for objects whose primary vtable is the given export.
  instances: function (vtableExport, max, maxRangeMB) {
    var e = ensureExports();
    var vt = e[vtableExport];
    if (!vt) return { error: 'vtable export not found: ' + vtableExport };
    var hits = scanInstances(vt, max, maxRangeMB).map(function (p) {
      return p.toString();
    });
    return { vtable: vt.toString(), count: hits.length, addresses: hits };
  },

  // Address -> name of the export that is this exact vtable (null if unknown).
  vtNameOf: function (addr) {
    try {
      var e = ensureExports();
      var t = ptr(addr).toString();
      for (var k in e) if (e[k].toString() === t) return k;
      return null;
    } catch (err) { return null; }
  },

  // Call an exported function. selfPtr becomes `this`; args follow.
  // Frida's thiscall ABI requires `this` to be declared inside the signature.
  //
  // An exportName of the form "js:<code>" instead evaluates <code> in the agent
  // with every module helper in scope (ensureExports, ptr, scanInstances,
  // hexdump, rpc.exports, ...).  This is what lets a new engine call be tried
  // out through the existing ee_diag {op:"call"} surface without restarting the
  // MCP server for every experiment.  The snippet must `return` its value.
  call: function (exportName, retType, argTypes, selfPtr, args, abi) {
    if (typeof exportName === 'string' && exportName.indexOf('js:') === 0) {
      try {
        var r = eval('(function(){' + exportName.slice(3) + '\n})()');
        if (r === null || r === undefined) return { ok: true, ret: null };
        return { ok: true, ret: (typeof r === 'object') ? r : String(r) };
      } catch (err) {
        return { ok: false, error: String(err),
                 stack: (err && err.stack) ? String(err.stack) : null };
      }
    }
    var e = ensureExports();
    var addr = e[exportName];
    if (!addr) return { error: 'export not found: ' + exportName };
    var types = ['pointer'].concat(argTypes || []);
    var f;
    try {
      f = new NativeFunction(addr, retType, types, abi || 'thiscall');
    } catch (err) {
      return { error: 'NativeFunction(' + (abi || 'thiscall') + '): ' + err };
    }
    var argv = [toPtr(selfPtr)].concat((args || []).map(toPtr));
    try {
      var r = f.apply(null, argv);
      return { ok: true, ret: numOrPtr(r) };
    } catch (err) {
      return { error: 'invoke: ' + err };
    }
  },

  // Call a virtual method through an object's own vtable, so the correct
  // override runs (esShapeLine's +0x64 is esShapeBase::RecalcLayout, NOT the
  // esShapePath export — calling the export on a 0x5c object reads past the end).
  callVirt: function (objPtr, slot, retType, argTypes, args) {
    try {
      var vt = ptr(objPtr).readPointer();
      if (vt.isNull()) return { error: 'null vtable' };
      var fn = vt.add(slot).readPointer();
      if (fn.isNull()) return { error: 'null vtable slot 0x' + slot.toString(16) };
      var types = ['pointer'].concat(argTypes || []);
      var f = new NativeFunction(fn, retType, types, 'thiscall');
      var argv = [ptr(objPtr)].concat((args || []).map(toPtr));
      var r = f.apply(null, argv);
      return { ok: true, ret: numOrPtr(r), fn: fn.toString(), slot: slot };
    } catch (err) { return { error: 'callVirt: ' + err }; }
  },

  // Virtual RecalcLayout (+0x64) — valid for any esShapeBase-derived class.
  recalcShape: function (shape) {
    return this.callVirt(shape, VT_RECALC, 'void', [], []);
  },

  hexdump: function (addr, len) {
    try { return hexdump(ptr(addr), { length: len || 64, ansi: false }); }
    catch (err) { return '<err ' + err + '>'; }
  },

  // ---- memory primitives (for building argument buffers) ----
  // NOTE: Frida's Memory.alloc is GC-scoped to the returned NativePointer.
  // Converting it to a string drops that reference and the block is freed, so
  // every allocation is retained here until explicitly released.
  alloc: function (n) {
    var p = Memory.alloc(n);
    var k = p.toString();
    this._keep = this._keep || {};
    this._keep[k] = p;
    return k;
  },
  free: function (addr) {
    try {
      if (this._keep) delete this._keep[String(addr)];
      Memory.free(ptr(addr));
      return true;
    } catch (e) { return false; }
  },
  writeI32: function (addr, v) { ptr(addr).writeS32(v | 0); return true; },
  writeU8: function (addr, v) { ptr(addr).writeU8(v & 0xff); return true; },
  readI32: function (addr) { try { return ptr(addr).readS32(); } catch (e) { return null; } },

  // Create an esShapePath entirely inside one JS frame so the point/type
  // buffers stay referenced for the duration of the engine call.
  //   points: [[x,y], ...]   types: [uint8, ...]   close: 0|1
  createPath: function (points, types, close) {
    try {
      var e = ensureExports();
      var addr = e['?CreateFromPathData@esShapePath@@SAPAV1@PAUtagPOINT@@PAEHH@Z'];
      if (!addr) return { error: 'CreateFromPathData export missing' };
      var n = points.length;
      var pts = Memory.alloc(n * 8);
      var tys = Memory.alloc(Math.max(1, types.length));
      for (var i = 0; i < n; i++) {
        pts.add(i * 8).writeS32(points[i][0] | 0);
        pts.add(i * 8 + 4).writeS32(points[i][1] | 0);
      }
      for (var j = 0; j < types.length; j++) tys.add(j).writeU8(types[j] & 0xff);
      var f = new NativeFunction(addr, 'pointer',
                                 ['pointer', 'pointer', 'int', 'int'], 'sysv');
      var shape = f(pts, tys, n, close ? 1 : 0);
      return { ok: true, ret: shape.isNull() ? null : shape.toString() };
    } catch (err) {
      return { error: 'createPath: ' + err };
    }
  },

  // Link a shape into a canvas (esCanvas::AddItem is a list insert).
  addItem: function (canvas, shape, flags) {
    try {
      var e = ensureExports();
      var addr = e['?AddItem@esCanvas@@QAEXPAVesShapeBase@@H@Z'];
      if (!addr) return { error: 'AddItem export missing' };
      var f = new NativeFunction(addr, 'void',
                                 ['pointer', 'pointer', 'int'], 'thiscall');
      f(ptr(canvas), ptr(shape), flags | 0);
      return { ok: true };
    } catch (err) {
      return { error: 'addItem: ' + err };
    }
  },

  // Look up an export inside any loaded module (cached, case-insensitive).
  expOf: function (modName, fnName) {
    try {
      if (!this._modmaps) this._modmaps = {};
      var key = modName.toLowerCase();
      var mm = this._modmaps[key];
      if (!mm) {
        var mod = null;
        var all = Process.enumerateModules();
        for (var i = 0; i < all.length; i++) {
          if (all[i].name.toLowerCase() === key) { mod = all[i]; break; }
        }
        if (!mod) return null;
        mm = {};
        mod.enumerateExports().forEach(function (e) { mm[e.name] = e.address; });
        this._modmaps[key] = mm;
      }
      return mm[fnName] ? mm[fnName].toString() : null;
    } catch (e) { return null; }
  },

  // Call an export from any module with an explicit ABI.
  callfn: function (modName, fnName, retType, argTypes, args, abi, selfPtr) {
    var a = this.expOf(modName, fnName);
    if (!a) return { error: 'export not found: ' + modName + '!' + fnName };
    var types = argTypes || [];
    var argv = (args || []).map(toPtr);
    if (selfPtr) { types = ['pointer'].concat(types); argv = [toPtr(selfPtr)].concat(argv); }
    var f;
    try { f = new NativeFunction(ptr(a), retType, types, abi || 'sysv'); }
    catch (e) { return { error: 'NativeFunction: ' + e }; }
    try {
      var r = f.apply(null, argv);
      return { ok: true, ret: numOrPtr(r) };
    } catch (e) { return { error: 'invoke: ' + e }; }
  },

  // Search every loaded module for an export name.
  findExport: function (fnName) {
    var out = [];
    Process.enumerateModules().forEach(function (m) {
      try {
        m.enumerateExports().forEach(function (e) {
          if (e.name === fnName) out.push({ module: m.name, addr: e.address.toString() });
        });
      } catch (err) { /* some modules hide exports */ }
    });
    return out;
  },

  // EE's own allocator, so the engine can free what we allocate for it.
  opnew: function (n) {
    var a = this.expOf('msvcrt.dll', '??2@YAPAXI@Z');
    if (!a) return null;
    var f = new NativeFunction(ptr(a), 'pointer', ['int'], 'sysv');
    var p = f(n | 0);
    return p.isNull() ? null : p.toString();
  },

  // ---- discovery helpers -------------------------------------------------

  // Count the primitives linked into a canvas (canvas+0x38 then shape+0x48).
  shapeCount: function (canvas, limit) {
    try {
      var c = ptr(canvas);
      var head = c.add(CANVAS_HEAD).readPointer();
      var seen = {}, n = 0, cap = limit || 4000, vts = [];
      while (!head.isNull() && n < cap) {
        var key = head.toString();
        if (seen[key]) break;
        seen[key] = 1;
        try { vts.push(head.readPointer().toString()); } catch (e) { vts.push(null); }
        n++;
        var nxt;
        try { nxt = head.add(SHAPE_NEXT).readPointer(); } catch (e) { break; }
        if (nxt.isNull() || nxt.toInt32() <= 0x10000) break;
        head = nxt;
      }
      return { ok: true, count: n, firstVtables: vts.slice(0, 8) };
    } catch (err) { return { error: 'shapeCount: ' + err }; }
  },

  // Set the stroke width of every primitive on a canvas.  The value is in
  // 1/400 mm (0.20mm = 80, 0.25mm = 100, bold-dot 0.40mm = 160) and is stored
  // at shape+0x58 (the embedded esPenInfo's +0x08).
  // GetPenInfo is declared on esShapeLine but works on esShapePath too; guard by
  // vtable so an unrelated primitive can never be handed to it.
  // Bold dots are SKIPPED: their 0.40mm pen IS their dot size, so a canvas-wide
  // 0.25mm pass would shrink every previously drawn dot to a thin tick
  // (verified live 2026-10-18: dot 160 -> 100).
  setPenWidth: function (canvas, value) {
    try {
      var e = ensureExports();
      var getPen = e['?GetPenInfo@esShapeLine@@QAEPAVesPenInfo@@XZ'];
      if (!getPen) return { error: 'GetPenInfo export missing' };
      var f = new NativeFunction(getPen, 'pointer', ['pointer'], 'thiscall');
      var c = ptr(canvas);
      var head = c.add(CANVAS_HEAD).readPointer();
      var seen = {}, items = [], n = 0;
      while (!head.isNull() && n < 4000) {
        var key = head.toString();
        if (seen[key]) break;
        seen[key] = 1;
        n++;
        var cls = null;
        try { cls = this.vtNameOf(head.readPointer().toString()); } catch (err) { }
        // The bold dot is an esShapeLine wrapper around a 0x6001 esSegPoint;
        // match the SEGMENT type, not the shape class (the wrapper hides it).
        var segType = 0;
        try {
          var segP = head.add(0x40).readPointer();
          if (!segP.isNull()) segType = segP.add(0x04).readU16();
        } catch (err) { }
        if (segType === 0x6001) {
          items.push({ shape: key, cls: cls, skipped: 'bold-dot(0x6001)',
                       pen: head.add(0x58).readU32() });
        } else if (cls && (cls.indexOf('esShapePath') >= 0 || cls.indexOf('esShapeLine') >= 0)) {
          try {
            var pen = f(head);
            if (!pen.isNull()) {
              var before = pen.add(0x08).readS32();
              pen.add(0x08).writeS32(value | 0);
              items.push({ shape: key, cls: cls, pen: pen.toString(),
                           before: before, after: pen.add(0x08).readS32() });
            } else {
              items.push({ shape: key, cls: cls, pen: null });
            }
          } catch (err) { items.push({ shape: key, cls: cls, error: String(err) }); }
        } else {
          items.push({ shape: key, cls: cls, skipped: true });
        }
        var nxt;
        try { nxt = head.add(SHAPE_NEXT).readPointer(); } catch (err) { break; }
        if (nxt.isNull() || nxt.toInt32() <= 0x10000) break;
        head = nxt;
      }
      return { ok: true, canvas: String(canvas), value: value, items: items };
    } catch (err) { return { error: 'setPenWidth: ' + err }; }
  },

  // Apply the "文字标注" (text label) dialog's parameters to every label on a
  // canvas.  Field layout (CORRECTED 2026-10-18, after the old k-word model was
  // disproved -- see figures-progress.md §2 and makeLabelShape below):
  //   +0x68  wchar_t*  text buffer
  //   +0x6c  u16       margin (边距), same unit as the pen width: 1/400 mm
  //   +0x6e  u16       font slot (字体 + 样式[斜体] + 大小 resolve to one slot)
  //   +0x70  u8        MAIN-TEXT CHARACTER COUNT  <-- NOT the 数学化 checkbox
  //   +0x71  u8        标注点 character count
  //   +0x72  u8        边框 character count
  //   +0x73  u8        flags: bit7 = 数学化, low nibble = settle/position state
  // Writing +0x70 = 1 (the old "math" write) silently truncated every
  // multi-character label to its first glyph on the next RecalcLayoutLable;
  // verified live on 2026-10-18 (ABC 3->1, AB 2->1).  `math` now only touches
  // bit7 of +0x73 and never the per-part character counts.
  setLableStyle: function (canvas, opts) {
    try {
      var e = ensureExports();
      var o = opts || {};
      var c = ptr(canvas);
      var head = c.add(CANVAS_HEAD).readPointer();
      var seen = {}, items = [], n = 0;
      while (!head.isNull() && n < 4000) {
        var key = head.toString();
        if (seen[key]) break;
        seen[key] = 1;
        n++;
        try {
          var seg = head.add(0x40).readPointer();
          if (!seg.isNull() && seg.add(0x04).readU16() === 0x600d) {
            var before = {
              margin: seg.add(0x6c).readU16(),
              font: seg.add(0x6e).readU16(),
              charCount: seg.add(0x70).readU8(),
              pointChars: seg.add(0x71).readU8(),
              borderChars: seg.add(0x72).readU8(),
              flags: seg.add(0x73).readU8()
            };
            if (o.margin !== undefined) seg.add(0x6c).writeU16(o.margin & 0xffff);
            if (o.fontIndex !== undefined) seg.add(0x6e).writeU16(o.fontIndex & 0xffff);
            // 数学化 is bit7 of +0x73.  Do NOT write +0x70/+0x71/+0x72 here:
            // those bytes are the per-part CHARACTER COUNTS, owned by
            // makeLabelShape / esSegLable::RecalcLayoutLable.
            if (o.math !== undefined) {
              var fl = seg.add(0x73).readU8();
              seg.add(0x73).writeU8((fl & 0x7f) | (o.math ? 0x80 : 0x00));
            }
            // The visible text lives in the embedded esEQLine at +0x80 and was
            // already populated with the OLD font, so writing +0x6e alone changes
            // nothing on screen.  Re-run Build (which repopulates the line from
            // the text at +0x68) and the label layout.
            var rebuilt = null;
            // OPT-IN only.  With "!== false" a bare read-back call rebuilt every
            // label on the canvas, and esSegLable::Build re-appends to the
            // embedded esEQLine -- so each audit added another text item and the
            // labels grew a run of garbage glyphs.
            if (o.rebuild === true) {
              try {
                var bld = e['?Build@esSegLable@@MAEXH@Z'];
                var rll = e['?RecalcLayoutLable@esSegLable@@IAEXXZ'];
                if (bld) {
                  new NativeFunction(bld, 'void', ['pointer', 'int32'], 'thiscall')(seg, 1);
                  rebuilt = 'build';
                }
                if (rll) {
                  new NativeFunction(rll, 'void', ['pointer'], 'thiscall')(seg);
                  rebuilt = rebuilt ? 'build+recalc' : 'recalc';
                }
              } catch (err) { rebuilt = 'error: ' + err; }
            }
            items.push({
              shape: key, seg: seg.toString(), before: before, rebuilt: rebuilt,
              after: {
                margin: seg.add(0x6c).readU16(),
                font: seg.add(0x6e).readU16(),
                charCount: seg.add(0x70).readU8(),
                pointChars: seg.add(0x71).readU8(),
                borderChars: seg.add(0x72).readU8(),
                flags: seg.add(0x73).readU8()
              }
            });
          }
        } catch (err) { /* not a label-bearing shape */ }
        var nxt;
        try { nxt = head.add(SHAPE_NEXT).readPointer(); } catch (err) { break; }
        if (nxt.isNull() || nxt.toInt32() <= 0x10000) break;
        head = nxt;
      }
      return { ok: true, canvas: String(canvas), applied: o, labels: items.length, items: items };
    } catch (err) { return { error: 'setLableStyle: ' + err }; }
  },

  // Ask the document's font sheet for the slot that a (family, style) pair maps
  // to -- exactly the dialog's 字体 + 样式 dropdowns collapsed into one slot.
  // Tries the exported lookup helpers and reports every raw answer so a wrong
  // guess is visible rather than silently written into a label.
  fontSlot: function (sheet, face, style) {
    function wsz(s) {
      var b = Memory.alloc((String(s).length + 1) * 2);
      b.writeUtf16String(String(s));
      return b;
    }
    var e = ensureExports(), out = {};
    try {
      var a = e['?GetFontID@esFontSheet@@SAGPB_W0@Z'];
      if (a) {
        var f1 = new NativeFunction(a, 'uint16', ['pointer', 'pointer'], 'stdcall');
        out.getFontID = f1(wsz(face), wsz(style));
      } else { out.getFontID = 'export missing'; }
    } catch (err) { out.getFontIDError = String(err); }
    try {
      var b2 = e['?CheckFont@esFontSheet@@QAEG_WGH@Z'];
      if (b2 && sheet) {
        var f2 = new NativeFunction(b2, 'uint16',
                                    ['pointer', 'pointer', 'uint16', 'int32'], 'thiscall');
        out.checkFontByStyle = {};
        for (var s = 0; s < 8; s++) {
          try { out.checkFontByStyle['style' + s] = f2(ptr(sheet), wsz(face), s, 0); }
          catch (err) { out.checkFontByStyle['style' + s] = String(err); }
        }
      } else { out.checkFont = 'export missing'; }
    } catch (err) { out.checkFontError = String(err); }
    try {
      var c = e['?BuildFont@esFontSheet@@QAEG_WHH@Z'];
      if (c && sheet) {
        var f3 = new NativeFunction(c, 'uint16',
                                    ['pointer', 'pointer', 'int32', 'int32'], 'thiscall');
        out.buildFont = f3(ptr(sheet), wsz(face), 0, 0);
      } else { out.buildFont = 'export missing'; }
    } catch (err) { out.buildFontError = String(err); }
    return { ok: true, face: face, style: style, sheet: String(sheet), results: out };
  },

  // Caret read/write on the live text UI.  This is the foundation for placing
  // the caret programmatically instead of asking the user to click:
  //   esTextUI::GetCaretRect(tagRECT*)      -> caret rect in view coords
  //   esTextUI::GetPointsOfCaret(tagPOINT*) -> caret corner points
  //   esTextUI::OnSetCaretByPoint(zPoint, int, uint)  -> what a mouse click runs
  // Resolve the live text UI and describe its caret.
  //
  // Resolution order (first hit wins, `source` says which one it was):
  //   1. explicit uiAddr argument
  //   2. esPageList::GetUI(pageList)          -- authoritative, but NULL unless
  //                                              the caret is in that document
  //   3. heap scan filtered by IsValid() == 1 -- the UI the user is typing in
  //   4. first heap-scan hit                  -- for diagnostics only
  caretInfo: function (pageList, uiAddr) {
    try {
      var e = ensureExports();
      var getUI = e['?GetUI@esPageList@@QAEPAVesTextUI@@XZ']
               || e['?GetUI@esPageList@@QBEPAVesTextUI@@XZ'];
      var vt = e['??_7esTextUI@@6B@'];
      var fValid = e['?IsValid@esTextUI@@QBEHXZ'];
      var fIsValid = fValid ? new NativeFunction(fValid, 'int', ['pointer'],
                                                 'thiscall') : null;
      var ui = null, source = null;
      if (uiAddr && ptr(uiAddr).toInt32() > 0x10000) {
        ui = ptr(uiAddr); source = 'explicit';
      }
      if (!ui && pageList && getUI) {
        try {
          var u2 = new NativeFunction(getUI, 'pointer', ['pointer'],
                                      'thiscall')(ptr(pageList));
          if (u2 && !u2.isNull()) { ui = u2; source = 'pageList.GetUI'; }
        } catch (e0) { /* that list has no UI */ }
      }
      var tried = [];
      if (!ui && vt) {
        var hits = scanInstances(vt, 32);
        var first = null;
        for (var i = 0; i < hits.length; i++) {
          var v = null;
          try { v = fIsValid ? fIsValid(hits[i]) : null; } catch (e1) { v = 'err'; }
          tried.push(hits[i].toString() + ' IsValid=' + v);
          if (first === null) first = hits[i];
          if (v === 1) { ui = hits[i]; source = 'heap scan (IsValid=1)'; break; }
        }
        if (!ui && first !== null) { ui = first; source = 'heap scan (first hit)'; }
      }
      if (!ui) return { error: 'no text UI', pageList: pageList || null,
                        tried: tried };
      var out = { ui: ui.toString(), source: source,
                  pageList: pageList || null, tried: tried };
      try { out.isValid = fIsValid ? fIsValid(ui) : null; } catch (e2) { out.isValid = 'err'; }
      try { out.sheet = ui.add(0x1e0).readPointer().toString(); } catch (e3) { out.sheet = 'err'; }
      try {
        var fOwner = e['?GetOwner@esTextUI@@QBEPAVesObject@@XZ'];
        out.owner = fOwner ? new NativeFunction(fOwner, 'pointer', ['pointer'], 'thiscall')(ui).toString() : null;
      } catch (e4) { out.owner = 'err'; }
      try {
        var fOT = e['?GetOwnerType@esTextUI@@QBEGXZ'];
        out.ownerType = fOT ? new NativeFunction(fOT, 'uint16', ['pointer'], 'thiscall')(ui) : null;
      } catch (e5) { out.ownerType = 'err'; }
      try {
        var fPg = e['?GetActivePage@esTextUI@@QAEHXZ'];
        out.activePage = fPg ? new NativeFunction(fPg, 'int', ['pointer'], 'thiscall')(ui) : null;
      } catch (e6) { out.activePage = 'err'; }
      try {
        var fUiRect = e['?GetUiRect@esTextUI@@QAE?AUtagRECT@@XZ'];
        if (fUiRect) {
          var q = Memory.alloc(16);
          new NativeFunction(fUiRect, 'pointer', ['pointer', 'pointer'], 'thiscall')(ui, q);
          out.uiRect = { l: q.readS32(), t: q.add(4).readS32(),
                         r: q.add(8).readS32(), b: q.add(12).readS32() };
        }
      } catch (e7) { out.uiRect = 'err'; }
      try {
        var fOff = e['?GetOffset@esTextUI@@QBE?AUtagPOINT@@XZ'];
        if (fOff) {
          var r8 = new NativeFunction(fOff, 'uint64', ['pointer'], 'thiscall')(ui);
          out.offset = { x: r8.toNumber() | 0, y: ((r8 >> 32) & 0xffffffff) | 0 };
        }
      } catch (e8) { out.offset = 'err'; }

      var gcr = e['?GetCaretRect@esTextUI@@QAEHPAUtagRECT@@@Z'];
      if (gcr) {
        var r = Memory.alloc(16);
        var ok = new NativeFunction(gcr, 'int', ['pointer', 'pointer'],
                                    'thiscall')(ui, r);
        out.caretRect = { ok: ok, left: r.readS32(), top: r.add(4).readS32(),
                          right: r.add(8).readS32(), bottom: r.add(12).readS32() };
      } else { out.caretRect = { error: 'GetCaretRect export missing' }; }

      var gpc = e['?GetPointsOfCaret@esTextUI@@QAEHPAUtagPOINT@@@Z'];
      if (gpc) {
        var p = Memory.alloc(32);
        var n = new NativeFunction(gpc, 'int', ['pointer', 'pointer'],
                                   'thiscall')(ui, p);
        var pts = [];
        for (var i = 0; i < 4; i++) {
          pts.push([p.add(i * 8).readS32(), p.add(i * 8 + 4).readS32()]);
        }
        out.caretPoints = { ret: n, points: pts };
      } else { out.caretPoints = { error: 'GetPointsOfCaret export missing' }; }

      var gco = e['?GetCaretOwner@esTextUI@@QBEPAVesTextLine@@XZ'];
      if (gco) {
        var ln = new NativeFunction(gco, 'pointer', ['pointer'],
                                    'thiscall')(ui);
        out.caretOwner = ln.isNull() ? null : ln.toString();
      }
      return out;
    } catch (err) { return { error: 'caretInfo: ' + err }; }
  },

  // esSegLable::HandMoveText(seg, tagPOINT&, int) -- what Editer.exe itself
  // calls right after building a label (see FUN_00426900).  It settles the
  // label's text onto its anchor.  Creating a label WITHOUT this leaves the
  // text-offset field at a value the engine never produces, which is why the
  // letter sits off and why a later re-layout (dragging it) inks garbage.
  handMoveText: function (seg, dx, dy, flag) {
    try {
      var e = ensureExports();
      var fn = e['?HandMoveText@esSegLable@@QAEHAAUtagPOINT@@H@Z'];
      if (!fn) return { error: 'HandMoveText export missing' };
      var pt = Memory.alloc(8);
      pt.writeS32(dx | 0);
      pt.add(4).writeS32(dy | 0);
      var r = new NativeFunction(fn, 'int', ['pointer', 'pointer', 'int'],
                                 'thiscall')(ptr(seg), pt, flag | 0);
      return { ok: true, ret: r, pt: [pt.readS32(), pt.add(4).readS32()] };
    } catch (err) { return { error: 'handMoveText: ' + err }; }
  },

  // Loaded modules with their RUNTIME base.  Editer.exe is ASLR-relocated, so a
  // runtime vtable address is only useful once the owning module's actual base
  // is known: rva = runtimeVtable - runtimeBase.
  modules: function (filter) {
    try {
      var out = [];
      var ms = Process.enumerateModules();
      for (var i = 0; i < ms.length; i++) {
        var m = ms[i];
        if (filter && m.name.toLowerCase().indexOf(String(filter).toLowerCase()) < 0) {
          continue;
        }
        out.push({ name: m.name, base: m.base.toString(), size: m.size,
                   path: m.path });
      }
      return { ok: true, count: out.length, modules: out };
    } catch (err) { return { error: 'modules: ' + err }; }
  },

  // List the fonts a document's font sheet actually holds.  A slot number is
  // document-local; the engine answers "which slot is Times New Roman italic
  // 五号" directly, because every esFont exposes its face name and style.
  //   esFontSheet::GetFont(sheet, slot, size) -> esFont*
  //   esFont::GetFontName() -> wchar_t* face   esFont::IsItalic()/IsBold()
  //   esFont::GetFontSize() -> int
  fontList: function (sheet, maxSlot, sizePt) {
    try {
      var e = ensureExports();
      var gf = e['?GetFont@esFontSheet@@QBEPAVesFont@@GM@Z'];
      var gn = e['?GetFontName@esFont@@QBEPB_WXZ'];
      if (!gf || !gn) return { error: 'esFontSheet::GetFont / esFont::GetFontName export missing' };
      var gi = e['?IsItalic@esFont@@QBEHXZ'];
      var gb = e['?IsBold@esFont@@QBEHXZ'];
      var gs = e['?GetFontSize@esFont@@QBEHXZ'];
      var fGet = new NativeFunction(gf, 'pointer',
                                    ['pointer', 'uint16', 'float'], 'thiscall');
      var fName = new NativeFunction(gn, 'pointer', ['pointer'], 'thiscall');
      var fIt = gi ? new NativeFunction(gi, 'int', ['pointer'], 'thiscall') : null;
      var fBold = gb ? new NativeFunction(gb, 'int', ['pointer'], 'thiscall') : null;
      var fSize = gs ? new NativeFunction(gs, 'int', ['pointer'], 'thiscall') : null;
      var sh = ptr(sheet);
      var out = [];
      var seen = {};
      var stopped = null;
      for (var slot = 0; slot <= (maxSlot | 0); slot++) {
        var rec = { slot: slot };
        try {
          var p = fGet(sh, slot, sizePt);
          if (!p || p.isNull()) { rec.error = 'null font'; out.push(rec); continue; }
          // Out-of-range slots resolve to an already-seen font (the sheet's
          // first entry), so the first repeat marks the real end of the list.
          var key = p.toString();
          if (seen[key]) { stopped = slot; break; }
          seen[key] = slot;
          rec.font = key;
          var np = fName(p);
          rec.name = (np && !np.isNull()) ? np.readUtf16String(128) : null;
          rec.italic = fIt ? fIt(p) : null;
          rec.bold = fBold ? fBold(p) : null;
          rec.size = fSize ? fSize(p) : null;
        } catch (err) { rec.error = String(err); }
        out.push(rec);
      }
      return { ok: true, sheet: String(sheet), slots: out.length,
               stoppedAtRepeat: stopped, fonts: out };
    } catch (err) { return { error: 'fontList: ' + err }; }
  },

  // Font slot (+0x6e) that this document's own labels use, read off an existing
  // label so a new one matches the document's letter style (in practice: the
  // difference between the upright slot 0 and the document's italic math slot).
  // Identified by the segment's type word 0x600d, which works for both eslib
  // class instances and the editor's own statically linked copies.
  labelFontIndex: function (canvas) {
    try {
      var head = ptr(canvas).add(CANVAS_HEAD).readPointer();
      var seen = {};
      while (!head.isNull()) {
        var key = head.toString();
        if (seen[key]) break;
        seen[key] = 1;
        try {
          var child = head.add(0x40).readPointer();
          if (!child.isNull() && child.toInt32() > 0x10000 &&
              child.add(4).readU16() === 0x600d) {
            return { ok: true, shape: head.toString(), seg: child.toString(),
                     fontIndex: child.add(0x6e).readU16(),
                     padding: child.add(0x6c).readU16() };
          }
        } catch (e2) { /* not a label container */ }
        var nxt;
        try { nxt = head.add(SHAPE_NEXT).readPointer(); } catch (e2) { break; }
        if (nxt.isNull() || nxt.toInt32() <= 0x10000) break;
        head = nxt;
      }
      return { ok: false, reason: 'no existing label on this canvas' };
    } catch (err) { return { error: 'labelFontIndex: ' + err }; }
  },

  // Every page list and the canvas it currently considers active, with the
  // measurements the canvas picker needs to rank candidates.
  canvasCandidates: function () {
    try {
      var e = ensureExports();
      var getPlCanvas = e['?GetActiveCanvas@esPageList@@QBEPAVesCanvas@@H@Z'];
      var getW = e['?GetWidth@esCanvas@@QBEHXZ'];
      var getH = e['?GetHeight@esCanvas@@QBEHXZ'];
      var getDoc = e['?GetDocument@esPageList@@QBEPAVesBaseDoc@@XZ'];
      var getStyle = e['?GetStyleSheet@esPageList@@QAEPAVesStyleSheet@@XZ'];
      if (!getPlCanvas) return { error: 'GetActiveCanvas export missing' };
      var fCanvas = new NativeFunction(getPlCanvas, 'pointer',
                                       ['pointer', 'int'], 'thiscall');
      var fW = getW ? new NativeFunction(getW, 'int', ['pointer'], 'thiscall') : null;
      var fH = getH ? new NativeFunction(getH, 'int', ['pointer'], 'thiscall') : null;
      var fDoc = getDoc ? new NativeFunction(getDoc, 'pointer', ['pointer'], 'thiscall') : null;
      var fStyle = getStyle ? new NativeFunction(getStyle, 'pointer', ['pointer'], 'thiscall') : null;

      var plVt = e['??_7esPageList@@6B@'];
      var pls = plVt ? scanInstances(plVt, 32) : [];
      var out = [];
      for (var i = 0; i < pls.length; i++) {
        // A page can hold SEVERAL canvases; GetActiveCanvas(pl, n) returns the
        // n-th.  Only looking at n = 0 is why canvases went missing.
        for (var n = 0; n < 8; n++) {
          var row = { pageList: pls[i].toString(), index: i, slot: n };
          try { row.doc = fDoc ? fDoc(pls[i]).toString() : null; } catch (e2) { row.doc = null; }
          try { row.styleSheet = fStyle ? fStyle(pls[i]).toString() : null; }
          catch (e2) { row.styleSheet = null; }
          var cv = null;
          try { cv = fCanvas(pls[i], n); } catch (e2) { break; }
          if (!cv || cv.isNull()) break;
          row.canvas = cv.toString();
          try { row.width = fW ? fW(cv) : null; } catch (e2) { row.width = null; }
          try { row.height = fH ? fH(cv) : null; } catch (e2) { row.height = null; }
          var sc = this.shapeCount(cv);
          row.shapes = sc.ok ? sc.count : null;
          row.firstVtables = sc.ok ? sc.firstVtables : null;
          out.push(row);
        }
      }
      return { ok: true, pageLists: pls.length, candidates: out };
    } catch (err) { return { error: 'canvasCandidates: ' + err }; }
  },

  // Create an esCanvas exactly the way the engine does, then register it.
  //
  // esCanvasList::CreateObject (RVA 0x1c22b0) is literally:
  //   c = operator_new(0xe0); __autoclassinit2(c, 0xe0);
  //       esCanvas::esCanvas(c); *(u16*)(c+4) = typeId;
  // All three steps are exported, and the type word for a normal canvas is
  // 0x2020 (read off the live one).
  //
  // esDocument::InsertNewCanvas (RVA 0x1920e0) then appends the canvas to the
  // page's canvas list, anchors it and focuses it. It needs the page list at
  // doc+0xcfc and no active text object; it returns 1 on a fresh canvas.
  //
  // !! DO NOT INSERT -- IT KILLS Editer.exe !!
  // Creating the object is fine, but registering it this way is fatal: the
  // canvas becomes the page's active canvas without ever being embedded in the
  // text flow. That embedding (operator_new(0x44) + esEmbedder + esText::
  // AddChrObj) lives inside esTextUI::InsertCanvas(canvas,flags), and without
  // it the canvas is left 0x0 and inconsistent, so the next layout or repaint
  // dereferences it and the editor process dies. Verified the hard way: the
  // insert returned 1, ee_canvases listed the new canvas, and Editer.exe was
  // gone moments later with all unsaved edits.
  // Pass confirmDangerous=true only if you accept losing the session.
  createCanvas: function (doc, typeId, confirmDangerous) {
    try {
      var e = ensureExports();
      var opAddr = this.expOf('msvcrt.dll', '??2@YAPAXI@Z');
      if (!opAddr) return { error: 'operator new not found' };
      var ctor = e['??0esCanvas@@QAE@XZ'];
      if (!ctor) return { error: 'esCanvas ctor export missing' };
      var opnew = new NativeFunction(ptr(opAddr), 'pointer', ['int'], 'sysv');
      var SIZE = 0xe0;

      var c = opnew(SIZE);
      new NativeFunction(e['?__autoclassinit2@esCanvas@@QAEXI@Z'], 'void',
                         ['pointer', 'int'], 'thiscall')(c, SIZE);
      new NativeFunction(ctor, 'void', ['pointer'], 'thiscall')(c);
      if (c.readPointer().isNull()) return { error: 'esCanvas ctor left no vtable' };
      c.add(4).writeU16((typeId === undefined || typeId === null)
                        ? 0x2020 : (typeId & 0xffff));

      var out = { ok: true, canvas: c.toString(), size: SIZE };
      try {
        var fw = e['?GetWidth@esCanvas@@QBEHXZ'], fh = e['?GetHeight@esCanvas@@QBEHXZ'];
        out.width = fw ? new NativeFunction(fw, 'int', ['pointer'], 'thiscall')(c) : null;
        out.height = fh ? new NativeFunction(fh, 'int', ['pointer'], 'thiscall')(c) : null;
        var fp = e['?GetFrameType@esCanvas@@QBEKXZ'];
        out.frameType = fp ? new NativeFunction(fp, 'int', ['pointer'], 'thiscall')(c) : null;
      } catch (e2) { out.measure = String(e2); }

      if (doc) {
        if (!confirmDangerous) {
          out.insert = 'REFUSED: registering a bare canvas crashes Editer.exe '
                     + '(it is never embedded in the text flow). See the '
                     + 'comment on createCanvas; pass confirmDangerous=true '
                     + 'only if you accept losing unsaved work.';
          return out;
        }
        var ins = e['?InsertNewCanvas@esDocument@@QAEHPAVesCanvas@@@Z'];
        if (!ins) { out.insert = 'export missing'; return out; }
        var r = new NativeFunction(ins, 'int', ['pointer', 'pointer'],
                                   'thiscall')(ptr(doc), c);
        out.doc = ptr(doc).toString();
        out.insert = r;
        out.inserted = (r !== 0);
      }
      return out;
    } catch (err) { return { error: 'createCanvas: ' + err }; }
  },

  // Walk the exact precondition chain of esTextUI::InsertCanvas() on every
  // esTextUI we can reach (the active page list's own UI plus heap-scanned
  // instances) and report the first step that fails, so "InsertCanvas returned
  // NULL" becomes an actionable answer instead of a dead end.
  //
  // The chain, from the decompilation at RVA 0x48c6e0:
  //   IsAbleToInput(this,1) -> GetMainTable(this,-1,NULL) -> GetSelState(this)
  //   -> sgMedia::GetLamp(this+0x14) -> <lamp as D2DGeometry>::operator
  //      ID2D1Geometry* -> *(short*)(geom+4) == 4
  canvasInsertProbe: function (pageList) {
    try {
      var e = ensureExports();
      var vt = e['??_7esTextUI@@6B@'];
      if (!vt) return { error: 'esTextUI vtable export missing' };
      var fValid = e['?IsValid@esTextUI@@QBEHXZ'];
      var fAble = e['?IsAbleToInput@esTextUI@@QAEHI@Z'];
      var fSel = e['?GetSelState@esTextUI@@QBE?AW4eSS@@XZ'];
      var fMain = e['?GetMainTable@esTextUI@@QBEPAVesMainTable@@HPAUtagPOINT@@@Z'];
      var fLamp = e['?GetLamp@sgMedia@@QAEPAVelfLamp@@XZ'];
      var fGetUI = e['?GetUI@esPageList@@QBEPAVesTextUI@@XZ'];

      var list = [], seen = {};
      function add(p, why) {
        if (!p || p.isNull() || p.toInt32() < 0x10000) return;
        var k = p.toString();
        if (seen[k]) return;
        seen[k] = why;
        list.push({ ptr: p, why: why });
      }
      if (pageList && fGetUI) {
        try {
          add(new NativeFunction(fGetUI, 'pointer', ['pointer'], 'thiscall')
              (ptr(pageList)), 'activePageList.GetUI');
        } catch (e1) { /* no UI on that list */ }
      }
      var hits = scanInstances(vt, 32);
      for (var i = 0; i < hits.length; i++) add(hits[i], 'heap scan');

      var out = [], vtP = ptr(vt);
      for (var j = 0; j < list.length; j++) {
        var t = list[j].ptr, row = { ptr: t.toString(), source: list[j].why };
        // Only poke objects whose vtable is really esTextUI: a heap-scan hit
        // that merely looks like one would crash the editor if called.
        var ok = false;
        try { ok = t.readPointer().equals(vtP); } catch (e2) { ok = false; }
        row.vtableOk = ok;
        if (!ok) { out.push(row); continue; }
        try { row.isValid = fValid ? new NativeFunction(fValid, 'int', ['pointer'], 'thiscall')(t) : null; } catch (e2) { row.isValid = 'err'; }
        try { row.ableToInput = fAble ? new NativeFunction(fAble, 'int', ['pointer', 'int'], 'thiscall')(t, 1) : null; } catch (e2) { row.ableToInput = 'err'; }
        try { row.selState = fSel ? new NativeFunction(fSel, 'int', ['pointer'], 'thiscall')(t) : null; } catch (e2) { row.selState = 'err'; }
        try { row.mainTable = fMain ? new NativeFunction(fMain, 'pointer', ['pointer', 'int', 'pointer'], 'thiscall')(t, -1, ptr(0)).toString() : null; } catch (e2) { row.mainTable = 'err'; }
        try { row.lamp = fLamp ? new NativeFunction(fLamp, 'pointer', ['pointer'], 'thiscall')(t.add(0x14)).toString() : null; } catch (e2) { row.lamp = 'err'; }
        row.sheet = (function () { try { return t.add(0x1e0).readPointer().toString(); } catch (e3) { return 'err'; } })();
        out.push(row);
      }
      return { ok: true, count: out.length, pageList: pageList || null, probes: out };
    } catch (err) { return { error: 'canvasInsertProbe: ' + err }; }
  },

  // Every live esFontSheet with the style sheet it is bound to, so the caller
  // can pick the one belonging to the document being edited (not a template).
  fontSheets: function () {    try {
      var e = ensureExports();
      var vt = e['??_7esFontSheet@@6B@'];
      if (!vt) return { error: 'esFontSheet vtable export missing' };
      var getStyle = e['?GetStyleSheet@esFontSheet@@QBEPAVesStyleSheet@@XZ'];
      var fStyle = getStyle
        ? new NativeFunction(getStyle, 'pointer', ['pointer'], 'thiscall') : null;
      var hits = scanInstances(vt, 32);
      var out = [];
      for (var i = 0; i < hits.length; i++) {
        var row = { addr: hits[i].toString(), index: i };
        try { row.styleSheet = fStyle ? fStyle(hits[i]).toString() : null; }
        catch (e2) { row.styleSheet = null; row.error = String(e2); }
        out.push(row);
      }
      return { ok: true, count: hits.length, items: out };
    } catch (err) { return { error: 'fontSheets: ' + err }; }
  },

  // Inverse of the text search below: which dword in [obj, obj+len) holds a
  // pointer whose UTF-16 contents equal `text`? Reveals where a string landed.
  scanForText: function (objPtr, len, text) {
    try {
      var base = ptr(objPtr), out = [];
      for (var off = 0; off + 4 <= len; off += 4) {
        var v;
        try { v = base.add(off).readU32(); } catch (e) { continue; }
        if (v <= 0x10000 || v >= 0x7fffffff) continue;
        var s = null;
        try { s = ptr(v).readUtf16String(128); } catch (e) { continue; }
        if (s === text) out.push({ offset: off, target: ptr(v).toString() });
      }
      return { ok: true, matches: out, text: text };
    } catch (err) { return { error: 'scanForText: ' + err }; }
  },

  // Characterise zwstr (zoro.dll's string class): its by-value size and field
  // layout matter because esSegLable takes one BY VALUE on the stack.
  zwstrProbe: function (text) {
    try {
      var ctorW = this.expOf('zoro.dll', '??0zwstr@@QAE@PB_W@Z');
      var dtor = this.expOf('zoro.dll', '??1zwstr@@QAE@XZ');
      var strFn = this.expOf('zoro.dll', '?Str@zwstr@@QBEQA_WXZ');
      var opAddr = this.expOf('msvcrt.dll', '??2@YAPAXI@Z');
      if (!ctorW || !opAddr) return { error: 'zwstr ctor or allocator missing' };
      var opnew = new NativeFunction(ptr(opAddr), 'pointer', ['int'], 'sysv');
      var wbuf = Memory.alloc((text.length + 1) * 2);
      wbuf.writeUtf16String(text);
      var z = opnew(0x40);
      for (var i = 0; i < 0x40; i += 4) z.add(i).writeU32(0xcdcdcdcd);
      new NativeFunction(ptr(ctorW), 'void', ['pointer', 'pointer'],
                         'thiscall')(z, wbuf);
      var words = [];
      for (var j = 0; j < 0x20; j += 4) words.push(z.add(j).readU32());
      var strRet = null;
      if (strFn) {
        try {
          var r = new NativeFunction(ptr(strFn), 'pointer', ['pointer'],
                                     'thiscall')(z);
          strRet = r.toString();
        } catch (e) { strRet = '<err ' + e + '>'; }
      }
      var readBack = null;
      try { readBack = ptr(words[0]).readUtf16String(64); }
      catch (e) { readBack = '<err ' + e + '>'; }
      if (dtor) {
        try {
          new NativeFunction(ptr(dtor), 'void', ['pointer'], 'thiscall')(z);
        } catch (e) { /* leak rather than risk */ }
      }
      return { ok: true, text: text, words: words.map(function (w) {
        return '0x' + w.toString(16);
      }), Str: strRet, readAtWord0: readBack };
    } catch (err) { return { error: 'zwstrProbe: ' + err }; }
  },

  // Fill a shape.  **This is the real mechanism** -- the scalar fields everyone
  // looks at (+0x10 fill flag, +0x38 shade) are NOT enough: a shape only renders
  // filled once it owns a brush, and esShapePath::SetSolidBrush(COLORREF)
  // creates that brush.  Proven by reading GetBrush() on a shape the user's own
  // fill tool had filled (non-null) versus one built by the old recipe (0x0).
  setSolidBrush: function (shape, color) {
    try {
      var e = ensureExports();
      var a = e['?SetSolidBrush@esShapePath@@QAEXK@Z'];
      if (!a) return { error: 'SetSolidBrush export missing' };
      var sp = ptr(shape);
      new NativeFunction(a, 'void', ['pointer', 'int'],
                         'thiscall')(sp, color >>> 0);
      var g = e['?GetBrush@esShapePath@@QBEPAVesBrush@@XZ'];
      var br = g
        ? new NativeFunction(g, 'pointer', ['pointer'], 'thiscall')(sp) : null;
      if (this.recalcShape) this.recalcShape(sp);
      return {
        ok: true, shape: shape,
        color: '0x' + (color >>> 0).toString(16),
        brush: br ? br.toString() : null,
        filled: !!(br && !br.isNull())
      };
    } catch (err) { return { error: 'setSolidBrush: ' + err }; }
  },

  // Read back the brush a shape owns.  A non-null brush is the ONLY proof that
  // the shape will really render filled; the scalar +0x10/+0x38 recipe leaves
  // GetBrush() == 0 and draws nothing.  Read-only.
  getBrush: function (shape) {
    try {
      var e = ensureExports();
      var g = e['?GetBrush@esShapePath@@QBEPAVesBrush@@XZ'];
      if (!g) return { error: 'GetBrush export missing' };
      var br = new NativeFunction(g, 'pointer', ['pointer'],
                                'thiscall')(ptr(shape));
      if (br.isNull()) {
        return { ok: true, shape: shape, brush: null, filled: false };
      }
      return { ok: true, shape: shape, brush: br.toString(), filled: true };
    } catch (err) { return { error: 'getBrush: ' + err }; }
  },

  // Build a TRUE circle primitive: esShapePath { esSegList { esSegCircel } }.
  // Whole pipeline runs in one frame so every allocation stays referenced.
  // Layout learned from a circle the editor's own circle tool produced.
  //   esSegCircel +0x04 toolId(=0x4284) +0x08 owning list
  //               +0x68 radius(f) +0x6C angle(f) +0x70/+0x74 centre(f)
  makeCircleShape: function (cx, cy, r, angle, toolId) {
    try {
      var e = ensureExports();
      var opAddr = this.expOf('msvcrt.dll', '??2@YAPAXI@Z');
      if (!opAddr) return { error: 'operator new not found' };
      var opnew = new NativeFunction(ptr(opAddr), 'pointer', ['int'], 'sysv');
      var SEG = 0x100, LIST = 0x44, PATH = 0x74;

      var segP = opnew(SEG);
      new NativeFunction(e['?__autoclassinit2@esSegCircel@@QAEXI@Z'], 'void',
                         ['pointer', 'int'], 'thiscall')(segP, SEG);
      new NativeFunction(
        e['??0esSegCircel@@QAE@VPointF@Gdiplus@@MMPAVMatrix@2@@Z'], 'void',
        ['pointer', 'float', 'float', 'float', 'float', 'pointer'],
        'thiscall')(segP, cx, cy, r, angle, ptr(0));
      segP.add(0x04).writeU32(toolId >>> 0);
      if (segP.add(0x00).readPointer().isNull()) {
        return { error: 'esSegCircel ctor produced no vtable' };
      }

      var lstP = opnew(LIST);
      new NativeFunction(e['?__autoclassinit2@esSegList@@QAEXI@Z'], 'void',
                         ['pointer', 'int'], 'thiscall')(lstP, LIST);
      new NativeFunction(e['??0esSegList@@QAE@XZ'], 'void',
                         ['pointer'], 'thiscall')(lstP);
      new NativeFunction(e['?AddSegObject@esSegList@@QAEXPAVesSeg@@H@Z'], 'void',
                         ['pointer', 'pointer', 'int'],
                         'thiscall')(lstP, segP, 1);

      var shP = opnew(PATH);
      new NativeFunction(e['?__autoclassinit2@esShapePath@@QAEXI@Z'], 'void',
                         ['pointer', 'int'], 'thiscall')(shP, PATH);
      new NativeFunction(e['??0esShapePath@@QAE@XZ'], 'void',
                         ['pointer'], 'thiscall')(shP);
      shP.add(0x34).writeU32(0x040700FF);
      new NativeFunction(e['?AddSegList@esShapePath@@QAEXPAVesSegList@@@Z'], 'void',
                         ['pointer', 'pointer'],
                         'thiscall')(shP, lstP);

      return { ok: true, shape: shP.toString(), seg: segP.toString(),
               list: lstP.toString() };
    } catch (err) {
      return { error: 'makeCircleShape: ' + err };
    }
  },

  // Build an INFINITE LINE primitive: esShapePath { esSegList { esSegLine } }.
  //
  // This is what the editor's own angle tool produces (learned by reverse
  // engineering an angle the user drew): two esSegLine objects meeting at the
  // vertex.  An esSegLine is an *infinite* line, defined by two points; the
  // engine intersects/breaks it where it crosses other esSegLine objects, so
  //   * two lines at 60 degrees give an exactly-60-degree angle, and
  //   * three lines at 60 degrees give an exactly equilateral triangle
  // with no pixel tracing anywhere.  That is the construction tool the user
  // asked for.
  //
  // Layout (from the demo, seg class ??_7esSegLine@@6B@, type word +0x04 = 0x4701):
  //   +0x14/+0x18  first defining point
  //   +0x1c/+0x20  second defining point
  //   +0x24..+0x30 bbox = the two points inflated by 500
  // The segment comes from the engine's own factory esSeg::Create(0x4701) --
  // IDA's dispatch table confirms 0x4701 -> esSegLine::esSegLine(void) -- so the
  // vtable, the embedded esMatrixObj at +0x48 and every default are correct.
  // Native coordinate axis: esSegAxis (type 0x5006).
  // Field layout read off an axis the user drew with EE's own tool:
  //   seg+0x14/+0x18 -> seg+0x1c/+0x20 : axis extent
  //   seg+0x24..+0x30                    : extent padded by 100
  //   seg+0x70/+0x74                     : x tick (spacing, scale)  10 / 10000
  //   seg+0x78                           : 0
  //   seg+0x7c/+0x80                     : y tick (spacing, scale)  10 / 10000
  // The user's axis shape carried type word 0x320b (the same shape wrapper a
  // line uses is 0x330f); we reuse the working esShapePath wrapper and let
  // OnCreate settle the type.
  makeAxisShape: function (x1, y1, x2, y2, canvas, styleSheet, opts) {
    opts = opts || {};
    try {
      var e = ensureExports();
      var opAddr = this.expOf('msvcrt.dll', '??2@YAPAXI@Z');
      if (!opAddr) return { error: 'operator new not found' };
      var opnew = new NativeFunction(ptr(opAddr), 'pointer', ['int'], 'sysv');
      var LIST = 0x44, PATH = 0x74;

      var factory = e['?Create@esSeg@@SAPAV1@G@Z'];
      if (!factory) return { error: 'esSeg::Create missing' };
      var seg = new NativeFunction(factory, 'pointer', ['int'],
                                   'stdcall')(0x5006);
      if (seg.isNull()) return { error: 'esSegAxis create returned null' };

      seg.add(0x14).writeS32(Math.min(x1, x2) | 0);
      seg.add(0x18).writeS32(Math.min(y1, y2) | 0);
      seg.add(0x1c).writeS32(Math.max(x1, x2) | 0);
      seg.add(0x20).writeS32(Math.max(y1, y2) | 0);
      seg.add(0x24).writeS32(Math.min(x1, x2) - 100);
      seg.add(0x28).writeS32(Math.min(y1, y2) - 100);
      seg.add(0x2c).writeS32(Math.max(x1, x2) + 100);
      seg.add(0x30).writeS32(Math.max(y1, y2) + 100);
      var xt = opts.xTick === undefined ? [10, 10000] : opts.xTick;
      var yt = opts.yTick === undefined ? [10, 10000] : opts.yTick;
      seg.add(0x70).writeS32(xt[0] | 0);
      seg.add(0x74).writeS32(xt[1] | 0);
      seg.add(0x78).writeS32(0);
      seg.add(0x7c).writeS32(yt[0] | 0);
      seg.add(0x80).writeS32(yt[1] | 0);

      var lstP = opnew(LIST);
      new NativeFunction(e['?__autoclassinit2@esSegList@@QAEXI@Z'], 'void',
                         ['pointer', 'int'], 'thiscall')(lstP, LIST);
      new NativeFunction(e['??0esSegList@@QAE@XZ'], 'void',
                         ['pointer'], 'thiscall')(lstP);
      new NativeFunction(e['?AddSegObject@esSegList@@QAEXPAVesSeg@@H@Z'], 'void',
                         ['pointer', 'pointer', 'int'],
                         'thiscall')(lstP, seg, 1);

      var shP = opnew(PATH);
      new NativeFunction(e['?__autoclassinit2@esShapePath@@QAEXI@Z'], 'void',
                         ['pointer', 'int'], 'thiscall')(shP, PATH);
      new NativeFunction(e['??0esShapePath@@QAE@XZ'], 'void',
                         ['pointer'], 'thiscall')(shP);
      new NativeFunction(e['?AddSegList@esShapePath@@QAEXPAVesSegList@@@Z'], 'void',
                         ['pointer', 'pointer'], 'thiscall')(shP, lstP);

      if (styleSheet && styleSheet !== '0x0') {
        var onCreate = e['?OnCreate@esShapeBase@@QAEXPAVesStyleSheet@@@Z'];
        if (onCreate) {
          new NativeFunction(onCreate, 'void', ['pointer', 'pointer'],
                             'thiscall')(shP, ptr(styleSheet));
        }
      }
      this.recalcShape(shP);
      if (canvas && canvas !== '0x0' && opts.attach === true) this.addItem(shP, ptr(canvas));
      return {
        ok: true, shape: shP.toString(), seg: seg.toString(),
        extent: [seg.add(0x14).readS32(), seg.add(0x18).readS32(),
                 seg.add(0x1c).readS32(), seg.add(0x20).readS32()],
        shapeType: '0x' + shP.add(0x4).readU32().toString(16),
        style: '0x' + shP.add(0x34).readU32().toString(16)
      };
    } catch (err) {
      return { error: 'makeAxisShape: ' + err };
    }
  },

  // CORRECT native coordinate axis: esShapeCap wrapping esSegAxis (0x5006).
  //
  // RTTI on the axis the user drew with EE's own tool gave
  //     shape  = .?AVesShapeCap@@        (NOT esShapePath)
  //     seg    = .?AVesSegAxis@@
  // Wrapping the axis in esShapePath left the style word (shape+0x34) holding
  // the canvas pointer instead of a style, and attaching that shape crashed the
  // editor on repaint.  esShapeCap exposes
  //     ??0esShapeCap@@QAE@PAVesSnapManager@@GK@Z   (snapMgr, structType, flags)
  // which builds the segment itself and writes the style word -- the same
  // pattern as esShapeLine(pt, 0x6001, flags) that made the bold dot work.
  //
  // Defaults to OFFLINE (no attach) so a bad axis can never reach a canvas:
  // callers must pass opts.attach === true, and should only do so once the
  // returned `style` looks like a style word rather than a pointer.
  makeAxisCap: function (x1, y1, x2, y2, canvas, styleSheet, opts) {
    opts = opts || {};
    var steps = [];
    var note = function (s) { steps.push(s); };
    try {
      var e = ensureExports();
      var opAddr = this.expOf('msvcrt.dll', '??2@YAPAXI@Z');
      if (!opAddr) return { error: 'operator new not found' };
      var opnew = new NativeFunction(ptr(opAddr), 'pointer', ['int'], 'sysv');
      var ctor = e['??0esShapeCap@@QAE@PAVesSnapManager@@GK@Z'];
      var autoInit = e['?__autoclassinit2@esShapeCap@@QAEXI@Z'];
      if (!ctor) return { error: 'esShapeCap ctor missing' };

      note('alloc');
      var SZ = 0x200;
      var sh = opnew(SZ);
      if (autoInit) {
        new NativeFunction(autoInit, 'void', ['pointer', 'int'],
                           'thiscall')(sh, SZ);
      }
      note('ctor');
      new NativeFunction(ctor, 'pointer',
                         ['pointer', 'pointer', 'int', 'int'],
                         'thiscall')(sh, ptr(0), 0x5006, 0);

      var seg = sh.add(0x40).readPointer();
      note('seg=' + seg);
      if (seg.isNull()) return { error: 'no seg built', steps: steps };
      var segType = seg.add(0x4).readU32();
      note('segType=0x' + segType.toString(16));

      seg.add(0x14).writeS32(Math.min(x1, x2) | 0);
      seg.add(0x18).writeS32(Math.min(y1, y2) | 0);
      seg.add(0x1c).writeS32(Math.max(x1, x2) | 0);
      seg.add(0x20).writeS32(Math.max(y1, y2) | 0);
      seg.add(0x24).writeS32(Math.min(x1, x2) - 100);
      seg.add(0x28).writeS32(Math.min(y1, y2) - 100);
      seg.add(0x2c).writeS32(Math.max(x1, x2) + 100);
      seg.add(0x30).writeS32(Math.max(y1, y2) + 100);
      var xt = opts.xTick === undefined ? [10, 10000] : opts.xTick;
      var yt = opts.yTick === undefined ? [10, 10000] : opts.yTick;
      seg.add(0x70).writeS32(xt[0] | 0);
      seg.add(0x74).writeS32(xt[1] | 0);
      seg.add(0x78).writeS32(0);
      seg.add(0x7c).writeS32(yt[0] | 0);
      seg.add(0x80).writeS32(yt[1] | 0);

      if (styleSheet && styleSheet !== '0x0') {
        var onCreate = e['?OnCreate@esShapeBase@@QAEXPAVesStyleSheet@@@Z'];
        if (onCreate) {
          note('oncreate');
          new NativeFunction(onCreate, 'void', ['pointer', 'pointer'],
                             'thiscall')(sh, ptr(styleSheet));
        }
      }
      var style = sh.add(0x34).readU32();
      var shapeType = sh.add(0x4).readU32();
      note('style=0x' + style.toString(16));

      var attached = false;
      if (canvas && canvas !== '0x0' && opts.attach === true) {
        note('recalc');
        this.recalcShape(sh);
        note('add');
        this.addItem(sh, ptr(canvas));
        attached = true;
      }
      return {
        ok: true, attached: attached, shape: sh.toString(), seg: seg.toString(),
        segType: '0x' + segType.toString(16),
        segRttiName: rpc.exports.vtNameOf(seg.readPointer().toString()),
        shapeType: '0x' + shapeType.toString(16),
        style: '0x' + style.toString(16),
        styleLooksValid: (style >>> 24) === 0x04,
        extent: [seg.add(0x14).readS32(), seg.add(0x18).readS32(),
                 seg.add(0x1c).readS32(), seg.add(0x20).readS32()],
        steps: steps
      };
    } catch (err) {
      return { error: 'makeAxisCap: ' + err, steps: steps };
    }
  },

  // Native static curve -- CORRECTED RECIPE (2026-02).
  //
  // The static curve is esSegBezier (type 0x4703), NOT esSegCurve (0x4708):
  // esSegCurve turned out to be the *dynamic* function-graph object (its seg
  // carries four eslib code pointers at +0x70..+0x7C, exactly like the figure
  // the user drew with EE's own function tool), and its AddPoint silently
  // stores nothing.
  //
  // esSegBezier stores its control points OUT OF LINE:
  //     seg+0x58 = pointer to a tagPOINT array      (8 bytes per point)
  //     seg+0x5c = point count
  // and the engine flattens them into samples at +0xd8 onward.  Confirmed by
  // feeding sentinel coordinates through the point-array constructor
  // ??0esSegBezier@@QAE@PAUtagPOINT@@H@Z and finding them in the array.
  // For n cubic segments supply 3n+1 points.
  makeCurveShape: function (points, canvas, styleSheet, opts) {
    opts = opts || {};
    var steps = [];
    var note = function (s) { steps.push(s); };
    try {
      var e = ensureExports();
      var opAddr = this.expOf('msvcrt.dll', '??2@YAPAXI@Z');
      if (!opAddr) return { error: 'operator new not found' };
      var opnew = new NativeFunction(ptr(opAddr), 'pointer', ['int'], 'sysv');
      var LIST = 0x44, PATH = 0x74;

      var factory = e['?Create@esSeg@@SAPAV1@G@Z'];
      var ctor = e['??0esSegBezier@@QAE@PAUtagPOINT@@H@Z'];
      if (!factory || !ctor) {
        return { error: 'esSeg::Create / esSegBezier ctor missing' };
      }
      note('seg-create');
      var seg = new NativeFunction(factory, 'pointer', ['int'],
                                   'stdcall')(0x4703);
      if (seg.isNull()) return { error: 'esSegBezier create returned null' };

      note('control-points');
      var n = points.length;
      var arrP = Memory.alloc(n * 8);
      for (var i = 0; i < n; i++) {
        arrP.add(i * 8).writeS32(points[i][0] | 0);
        arrP.add(i * 8 + 4).writeS32(points[i][1] | 0);
      }
      new NativeFunction(ctor, 'pointer', ['pointer', 'pointer', 'int'],
                         'thiscall')(seg, arrP, n);

      // read back what the engine actually kept
      var stored = seg.add(0x5c).readU32();
      var arrAddr = seg.add(0x58).readPointer();
      var firstPt = null;
      try {
        firstPt = [arrAddr.readS32(), arrAddr.add(4).readS32()];
      } catch (e2) { firstPt = null; }

      note('list');
      var lstP = opnew(LIST);
      new NativeFunction(e['?__autoclassinit2@esSegList@@QAEXI@Z'], 'void',
                         ['pointer', 'int'], 'thiscall')(lstP, LIST);
      new NativeFunction(e['??0esSegList@@QAE@XZ'], 'void',
                         ['pointer'], 'thiscall')(lstP);
      new NativeFunction(e['?AddSegObject@esSegList@@QAEXPAVesSeg@@H@Z'], 'void',
                         ['pointer', 'pointer', 'int'],
                         'thiscall')(lstP, seg, 1);

      note('path');
      var shP = opnew(PATH);
      new NativeFunction(e['?__autoclassinit2@esShapePath@@QAEXI@Z'], 'void',
                         ['pointer', 'int'], 'thiscall')(shP, PATH);
      new NativeFunction(e['??0esShapePath@@QAE@XZ'], 'void',
                         ['pointer'], 'thiscall')(shP);
      new NativeFunction(e['?AddSegList@esShapePath@@QAEXPAVesSegList@@@Z'], 'void',
                         ['pointer', 'pointer'], 'thiscall')(shP, lstP);

      if (styleSheet && styleSheet !== '0x0') {
        var onCreate = e['?OnCreate@esShapeBase@@QAEXPAVesStyleSheet@@@Z'];
        if (onCreate) {
          note('oncreate');
          new NativeFunction(onCreate, 'void', ['pointer', 'pointer'],
                             'thiscall')(shP, ptr(styleSheet));
        }
      }

      note('recalc');
      this.recalcShape(shP);

      if (canvas && canvas !== '0x0') {
        note('add');
        this.addItem(shP, ptr(canvas));
      }
      return {
        ok: true, shape: shP.toString(), seg: seg.toString(),
        points: n, storedCount: stored, firstPoint: firstPt, steps: steps
      };
    } catch (err) {
      return { error: 'makeCurveShape: ' + err, steps: steps };
    }
  },

  // Leftover body of the first (wrong) esSegCurve attempt -- kept as an inert
  // method rather than deleted, so the file stays syntactically balanced.
  _orphanOldCurve4708: function () {
    var opts = {};
    var steps = [];
    var note = function (s) { steps.push(s); };
    try {
      var e = ensureExports();
      var opAddr = this.expOf('msvcrt.dll', '??2@YAPAXI@Z');
      if (!opAddr) return { error: 'operator new not found' };
      var opnew = new NativeFunction(ptr(opAddr), 'pointer', ['int'], 'sysv');
      var LIST = 0x44, PATH = 0x74;

      var factory = e['?Create@esSeg@@SAPAV1@G@Z'];
      var addPoint = e['?AddPoint@esSegCurve@@UAEHVzPoint@@HH@Z'];
      if (!factory || !addPoint) {
        return { error: 'esSeg::Create / esSegCurve::AddPoint missing' };
      }
      note('seg-create');
      var seg = new NativeFunction(factory, 'pointer', ['int'],
                                   'stdcall')(0x4708);
      if (seg.isNull()) return { error: 'esSegCurve create returned null' };

      note('add-points');
      var fAdd = new NativeFunction(addPoint, 'int',
                                    ['pointer', 'int', 'int', 'int', 'int'],
                                    'thiscall');
      var rets = [];
      for (var i = 0; i < points.length; i++) {
        rets.push(fAdd(seg, points[i][0] | 0, points[i][1] | 0, 0, 0));
      }

      note('list');
      var lstP = opnew(LIST);
      new NativeFunction(e['?__autoclassinit2@esSegList@@QAEXI@Z'], 'void',
                         ['pointer', 'int'], 'thiscall')(lstP, LIST);
      new NativeFunction(e['??0esSegList@@QAE@XZ'], 'void',
                         ['pointer'], 'thiscall')(lstP);
      new NativeFunction(e['?AddSegObject@esSegList@@QAEXPAVesSeg@@H@Z'], 'void',
                         ['pointer', 'pointer', 'int'],
                         'thiscall')(lstP, seg, 1);

      note('path');
      var shP = opnew(PATH);
      new NativeFunction(e['?__autoclassinit2@esShapePath@@QAEXI@Z'], 'void',
                         ['pointer', 'int'], 'thiscall')(shP, PATH);
      new NativeFunction(e['??0esShapePath@@QAE@XZ'], 'void',
                         ['pointer'], 'thiscall')(shP);
      new NativeFunction(e['?AddSegList@esShapePath@@QAEXPAVesSegList@@@Z'], 'void',
                         ['pointer', 'pointer'], 'thiscall')(shP, lstP);

      if (styleSheet && styleSheet !== '0x0') {
        var onCreate = e['?OnCreate@esShapeBase@@QAEXPAVesStyleSheet@@@Z'];
        if (onCreate) {
          note('oncreate');
          new NativeFunction(onCreate, 'void', ['pointer', 'pointer'],
                             'thiscall')(shP, ptr(styleSheet));
        }
      }

      note('recalc');
      this.recalcShape(shP);

      if (canvas && canvas !== '0x0') {
        note('add');
        this.addItem(shP, ptr(canvas));
      }
      return {
        ok: true, shape: shP.toString(), seg: seg.toString(),
        points: points.length, addReturns: rets, steps: steps
      };
    } catch (err) {
      return { error: 'makeCurveShape: ' + err, steps: steps };
    }
  },

  makeLineShape: function (x1, y1, x2, y2, canvas, styleSheet, opts) {
    opts = opts || {};
    var steps = [];
    var step = 'init';
    var note = function (s) { steps.push(s); step = s; };
    try {
      var e = ensureExports();
      var opAddr = this.expOf('msvcrt.dll', '??2@YAPAXI@Z');
      if (!opAddr) return { error: 'operator new not found' };
      var opnew = new NativeFunction(ptr(opAddr), 'pointer', ['int'], 'sysv');
      var toolId = opts.toolId === undefined ? 0x4701 : (opts.toolId >>> 0);
      var LIST = 0x44, PATH = 0x74;

      note('seg-create');
      var factory = e['?Create@esSeg@@SAPAV1@G@Z'];
      if (!factory) return { error: 'esSeg::Create missing' };
      var seg = new NativeFunction(factory, 'pointer', ['int'], 'stdcall')(toolId);
      if (seg.isNull()) return { error: 'esSeg::Create returned null' };

      note('seg-points');
      seg.add(0x14).writeS32(x1 | 0);
      seg.add(0x18).writeS32(y1 | 0);
      seg.add(0x1c).writeS32(x2 | 0);
      seg.add(0x20).writeS32(y2 | 0);
      var pad = opts.pad === undefined ? 500 : (opts.pad | 0);
      seg.add(0x24).writeS32(Math.min(x1, x2) - pad);
      seg.add(0x28).writeS32(Math.min(y1, y2) - pad);
      seg.add(0x2c).writeS32(Math.max(x1, x2) + pad);
      seg.add(0x30).writeS32(Math.max(y1, y2) + pad);

      note('list');
      var lstP = opnew(LIST);
      new NativeFunction(e['?__autoclassinit2@esSegList@@QAEXI@Z'], 'void',
                         ['pointer', 'int'], 'thiscall')(lstP, LIST);
      new NativeFunction(e['??0esSegList@@QAE@XZ'], 'void',
                         ['pointer'], 'thiscall')(lstP);
      new NativeFunction(e['?AddSegObject@esSegList@@QAEXPAVesSeg@@H@Z'], 'void',
                         ['pointer', 'pointer', 'int'],
                         'thiscall')(lstP, seg, 1);

      note('path');
      var shP = opnew(PATH);
      new NativeFunction(e['?__autoclassinit2@esShapePath@@QAEXI@Z'], 'void',
                         ['pointer', 'int'], 'thiscall')(shP, PATH);
      new NativeFunction(e['??0esShapePath@@QAE@XZ'], 'void',
                         ['pointer'], 'thiscall')(shP);
      new NativeFunction(e['?AddSegList@esShapePath@@QAEXPAVesSegList@@@Z'], 'void',
                         ['pointer', 'pointer'], 'thiscall')(shP, lstP);

      if (styleSheet && styleSheet !== '0x0') {
        var onCreate = e['?OnCreate@esShapeBase@@QAEXPAVesStyleSheet@@@Z'];
        if (onCreate) {
          note('oncreate');
          new NativeFunction(onCreate, 'void', ['pointer', 'pointer'],
                             'thiscall')(shP, ptr(styleSheet));
        }
      }

      note('recalc');
      this.recalcShape(shP);

      if (canvas && canvas !== '0x0') {
        note('addItem');
        var a = this.addItem(canvas, shP, 1);
        if (a && a.error) {
          return { error: 'addItem: ' + a.error, steps: steps,
                   shape: shP.toString(), seg: seg.toString() };
        }
      }
      if (opts.pen !== undefined) {
        note('pen');
        shP.add(0x58).writeU32(opts.pen >>> 0);
      }
      this.recalcShape(shP);

      return {
        ok: true,
        shape: shP.toString(), seg: seg.toString(), list: lstP.toString(),
        cls: this.vtNameOf(shP.readPointer().toString()),
        segCls: this.vtNameOf(seg.readPointer().toString()),
        style: '0x' + shP.add(0x34).readU32().toString(16),
        pen: shP.add(0x58).readU32(),
        steps: steps
      };
    } catch (err) {
      return { error: 'makeLineShape[' + step + ']: ' + err, steps: steps };
    }
  },

  // Build a TRUE arc primitive: esShapePath { esSegList { esSegArc } }.
  // Same pipeline as makeCircleShape. Layout taken from eslib's ctor at
  // RVA 0x128290 (`??0esSegArc@@QAE@VPointF@Gdiplus@@MMMPAVMatrix@2@H@Z`):
  //   (PointF centre, float radius, float startAngle, float endAngle,
  //    Matrix*, int flags)
  //   -> +0x68 radius, +0x70 start, +0x74 end, +0x78/+0x7C centre,
  //      +0x80 mid angle, type word +0x04 = 0x4306, object size 0x98.
  // Angles are DEGREES; the ctor normalises them to 0..360.
  makeArcShape: function (cx, cy, r, startAngle, endAngle, flags) {
    try {
      var e = ensureExports();
      var opAddr = this.expOf('msvcrt.dll', '??2@YAPAXI@Z');
      if (!opAddr) return { error: 'operator new not found' };
      var opnew = new NativeFunction(ptr(opAddr), 'pointer', ['int'], 'sysv');
      var SEG = 0x98, LIST = 0x44, PATH = 0x74;

      var segP = opnew(SEG);
      new NativeFunction(e['?__autoclassinit2@esSegArc@@QAEXI@Z'], 'void',
                         ['pointer', 'int'], 'thiscall')(segP, SEG);
      new NativeFunction(
        e['??0esSegArc@@QAE@VPointF@Gdiplus@@MMMPAVMatrix@2@H@Z'], 'void',
        ['pointer', 'float', 'float', 'float', 'float', 'float', 'pointer', 'int'],
        'thiscall')(segP, cx, cy, r, startAngle, endAngle, ptr(0), flags || 0);
      if (segP.add(0x00).readPointer().isNull()) {
        return { error: 'esSegArc ctor produced no vtable' };
      }

      var lstP = opnew(LIST);
      new NativeFunction(e['?__autoclassinit2@esSegList@@QAEXI@Z'], 'void',
                         ['pointer', 'int'], 'thiscall')(lstP, LIST);
      new NativeFunction(e['??0esSegList@@QAE@XZ'], 'void',
                         ['pointer'], 'thiscall')(lstP);
      new NativeFunction(e['?AddSegObject@esSegList@@QAEXPAVesSeg@@H@Z'], 'void',
                         ['pointer', 'pointer', 'int'],
                         'thiscall')(lstP, segP, 1);

      var shP = opnew(PATH);
      new NativeFunction(e['?__autoclassinit2@esShapePath@@QAEXI@Z'], 'void',
                         ['pointer', 'int'], 'thiscall')(shP, PATH);
      new NativeFunction(e['??0esShapePath@@QAE@XZ'], 'void',
                         ['pointer'], 'thiscall')(shP);
      shP.add(0x34).writeU32(0x040700FF);
      new NativeFunction(e['?AddSegList@esShapePath@@QAEXPAVesSegList@@@Z'], 'void',
                         ['pointer', 'pointer'], 'thiscall')(shP, lstP);

      return { ok: true, shape: shP.toString(), seg: segP.toString(),
               list: lstP.toString() };
    } catch (err) {
      return { error: 'makeArcShape: ' + err };
    }
  },

  // Build the EE-native ANGLE MARK shape: esShapePath { esSegList { esSegArc } }
  // with the engine's dynamic type word 0x4307 (plain drawing arcs use 0x4306).
  // The native toolbar's angle marker is exactly this segment type; it stores
  // THREE points on the arc (+0x58 array, +0x5c = 3), which is what lets its
  // handles resize the radius and re-fit the sweep.
  //   cx,cy,r : arc centre and radius
  //   startRad,endRad : PAGE angles (atan2(dy,dx), y down) of the two rays
  makeNativeAngleShape: function (cx, cy, r, startRad, endRad) {
    try {
      var e = ensureExports();
      var opnew = new NativeFunction(ptr(this.expOf('msvcrt.dll', '??2@YAPAXI@Z')),
                                     'pointer', ['int'], 'sysv');
      var SEG = 0x98;
      var segP = opnew(SEG);
      new NativeFunction(e['?__autoclassinit2@esSegArc@@QAEXI@Z'], 'void',
                         ['pointer', 'int'], 'thiscall')(segP, SEG);
      new NativeFunction(e['??0esSegArc@@QAE@VzPoint@@G@Z'], 'void',
                         ['pointer', 'int', 'int', 'uint16'],
                         'thiscall')(segP, Math.round(cx), Math.round(cy), 0x4307);
      // Three arc points: start, mid, end (page angles, y-down).
      var arr = segP.add(0x58).readPointer();
      if (arr.isNull()) return { error: 'esSegArc ctor left +0x58 null' };
      var midRad = (startRad + endRad) / 2.0;
      var angs = [startRad, midRad, endRad];
      for (var i = 0; i < 3; i++) {
        arr.add(i * 8).writeS32(Math.round(cx + r * Math.cos(angs[i])));
        arr.add(i * 8 + 4).writeS32(Math.round(cy + r * Math.sin(angs[i])));
      }
      segP.add(0x68).writeFloat(r);
      segP.add(0x70).writeFloat(startRad + Math.PI / 2.0);
      segP.add(0x74).writeFloat(endRad + Math.PI / 2.0);
      segP.add(0x78).writeS32(Math.round(cx));
      segP.add(0x7c).writeS32(Math.round(cy));
      segP.add(0x6c).writeU32(1);
      segP.add(0x44).writeU32(0xB0000);

      var LIST = 0x44, PATH = 0x74;
      var lstP = opnew(LIST);
      new NativeFunction(e['?__autoclassinit2@esSegList@@QAEXI@Z'], 'void',
                         ['pointer', 'int'], 'thiscall')(lstP, LIST);
      new NativeFunction(e['??0esSegList@@QAE@XZ'], 'void',
                         ['pointer'], 'thiscall')(lstP);
      new NativeFunction(e['?AddSegObject@esSegList@@QAEXPAVesSeg@@H@Z'], 'void',
                         ['pointer', 'pointer', 'int'], 'thiscall')(lstP, segP, 1);

      var shP = opnew(PATH);
      new NativeFunction(e['?__autoclassinit2@esShapePath@@QAEXI@Z'], 'void',
                         ['pointer', 'int'], 'thiscall')(shP, PATH);
      new NativeFunction(e['??0esShapePath@@QAE@XZ'], 'void',
                         ['pointer'], 'thiscall')(shP);
      shP.add(0x34).writeU32(0x040700FF);
      new NativeFunction(e['?AddSegList@esShapePath@@QAEXPAVesSegList@@@Z'], 'void',
                         ['pointer', 'pointer'], 'thiscall')(shP, lstP);
      return { ok: true, shape: shP.toString(), seg: segP.toString(),
               list: lstP.toString() };
    } catch (err) { return { error: 'makeNativeAngleShape: ' + err }; }
  },

  // Read a list of signed 32-bit fields from one object.
  readInts: function (addr, offsets) {
    try {
      var p = ptr(addr), out = [];
      for (var i = 0; i < offsets.length; i++)
        out.push(p.add(offsets[i] | 0).readS32());
      return { ok: true, values: out };
    } catch (err) { return { error: 'readInts: ' + err }; }
  },

  // Apply the user's preferred native-axis style (2026-10-19):
  //   - x / y labels ON (esFormulaBox at +0x14c / +0x150)
  //   - tick numbers OFF (zero the tick arrays / counts / scale fields)
  //   - origin O label ON (the G=1,1-created box at +0x148)
  //   - arrow style 4, thinner than default (seg flags +0x10/+0x44/+0x13c)
  // Call AFTER the shape has been added to a canvas and recalculated once.
  styleAxisShape: function (shape, styleSheet) {
    try {
      var e = ensureExports();
      var sh = ptr(shape);
      var seg = sh.add(0x40).readPointer();
      var add = new NativeFunction(
        e['?AddOrRemoveTextBox@esSegAxis@@IAEHPAVesStyleSheet@@EHPAVesUndo@@@Z'],
        'int', ['pointer', 'pointer', 'int', 'int', 'pointer'], 'thiscall');
      var added = [add(seg, ptr(styleSheet), 1, 1, ptr(0)),
                   add(seg, ptr(styleSheet), 2, 1, ptr(0))];
      // Tick-number off + arrow style / width (values read off the user's
      // hand-styled native axis; see AGENTS.md 2026-10-19).
      [[0x10, 0x10], [0x44, 0x10000], [0x6c, 0], [0x78, 0],
       [0x104, 0], [0x110, 0], [0x12c, 0], [0x130, 0],
       [0x13c, 8], [0xec, 0], [0xf8, 0]].forEach(function (p) {
        seg.add(p[0]).writeU32(p[1]);
      });
      sh.add(0x10).writeU32(15);          // axis style id / arrow option
      sh.add(0x5c).writeU32(0x03040400);  // style word of the styled axis
      sh.add(0x58).writeU32(100);         // 0.25 mm pen (project default)
      var setp = new NativeFunction(e['?SetTextBoxPostion@esSegAxis@@IAEXH@Z'],
                                    'void', ['pointer', 'int'], 'thiscall');
      [0, 1, 2].forEach(function (k) { setp(seg, k); });
      var rec = this.recalcShape(shape);
      return { ok: true, shape: shape, seg: seg.toString(),
               added: added, recalc: rec };
    } catch (err) { return { error: 'styleAxisShape: ' + err }; }
  },

  // Native coordinate axis (Editer's own axis object).
  //   rect  = [x1,y1,x2,y2] content rectangle in page units
  //   origin= [ox,oy] page position of the mathematical origin
  //   gx,gy = axis-object flags (editor passes 0/0 for the default axis)
  // styleSheet is the document style sheet (caretContext().fontSheet).
  makeNativeAxisShape: function (rect, origin, gx, gy, styleSheet) {
    try {
      var e = ensureExports();
      var opnew = new NativeFunction(ptr(this.expOf('msvcrt.dll', '??2@YAPAXI@Z')),
                                     'pointer', ['int'], 'sysv');
      var ao = opnew(0x400);
      new NativeFunction(e['??0esAxisObj@@QAE@XZ'], 'void',
                         ['pointer'], 'thiscall')(ao);
      var rc = Memory.alloc(16);
      rc.add(0).writeS32(rect[0] | 0);
      rc.add(4).writeS32(rect[1] | 0);
      rc.add(8).writeS32(rect[2] | 0);
      rc.add(12).writeS32(rect[3] | 0);
      new NativeFunction(e['?InitSize@esAxisObj@@QAEXPAUtagRECT@@VzPoint@@H@Z'],
                         'void', ['pointer', 'pointer', 'int', 'int', 'int'],
                         'thiscall')(ao, rc, origin[0] | 0, origin[1] | 0, 1);
      var seg = opnew(0x16c);
      new NativeFunction(e['??0esSegAxis@@QAE@XZ'], 'void',
                         ['pointer'], 'thiscall')(seg);
      var editer = Process.getModuleByName('Editer.exe').base;
      seg.writePointer(editer.add(0x2921d4));
      var sh = opnew(0x60);
      new NativeFunction(e['??0esShapeCap@@QAE@XZ'], 'void',
                         ['pointer'], 'thiscall')(sh);
      sh.writePointer(editer.add(0x29210c));
      sh.add(0x40).writePointer(seg);
      seg.add(0x8).writePointer(sh);
      new NativeFunction(e['?SetParent@esObject@@QAEXPAV1@@Z'], 'void',
                         ['pointer', 'pointer'], 'thiscall')(seg, sh);
      new NativeFunction(e['?Initialize@esSegAxis@@QAEXPAVesStyleSheet@@PAVesAxisObj@@GG@Z'],
                         'void', ['pointer', 'pointer', 'pointer', 'int', 'int'],
                         'thiscall')(seg, ptr(styleSheet), ao, gx | 0, gy | 0);
      // Absolute placement: esSegAxis keeps its geometry relative to the
      // mathematical origin; the page offset lives in the segment's
      // Gdiplus::Matrix at +0x4c (identity after Initialize).
      var mp = seg.add(0x4c).readPointer();
      if (!mp.isNull()) {
        var setm = new NativeFunction(ptr(this.expOf('gdiplus.dll',
                       'GdipSetMatrixElements')), 'int',
                       ['pointer', 'float', 'float', 'float', 'float', 'float',
                        'float'], 'stdcall');
        setm(mp, 1, 0, 0, 1, origin[0] | 0, origin[1] | 0);
      }
      return { ok: true, shape: sh.toString(), seg: seg.toString(),
               axisObj: ao.toString() };
    } catch (err) { return { error: 'makeNativeAxisShape: ' + err }; }
  },

  // Rotated native right-angle marker.  The engine's own slanted right-angle
  // annotation is an esSegHVLine whose 3 points live in a LOCAL axis-aligned
  // frame and whose +0x4c Gdiplus::Matrix maps that frame onto the page.
  // The plain `??0esSegHVLine(POINT*,n,Matrix*)` ctor corrupts that member, so
  // build it the way the engine initialises a fresh object: default ctor
  // (which allocates the internal matrix), then write points/count and set
  // the matrix elements.
  //   points: local points, typically [[0,0],[s,0],[s,-s]]
  //   m11..m22,dx,dy: Gdiplus matrix elements (local -> page)
  makeHVLineMatrixShape: function (points, m11, m12, m21, m22, dx, dy) {
    try {
      var e = ensureExports();
      var opnew = new NativeFunction(ptr(this.expOf('msvcrt.dll', '??2@YAPAXI@Z')),
                                     'pointer', ['int'], 'sysv');
      var SEG = 0xC0, PATH = 0x74, LIST = 0x44;
      var segP = opnew(SEG);
      new NativeFunction(e['?__autoclassinit2@esSegHVLine@@QAEXI@Z'], 'void',
                         ['pointer', 'int'], 'thiscall')(segP, SEG);
      new NativeFunction(e['??0esSegHVLine@@QAE@XZ'], 'void',
                         ['pointer'], 'thiscall')(segP);
      var pts = ptr(opnew(points.length * 8));
      if (pts.isNull()) return { error: 'point array alloc failed' };
      for (var i = 0; i < points.length; i++) {
        pts.add(i * 8).writeS32(Math.round(points[i][0]));
        pts.add(i * 8 + 4).writeS32(Math.round(points[i][1]));
      }
      segP.add(0x58).writePointer(pts);
      segP.add(0x5c).writeU32(points.length);
      var mp = segP.add(0x4c).readPointer();
      if (mp.isNull()) return { error: 'esSegHVLine default ctor left +0x4c null' };
      var setm = new NativeFunction(ptr(this.expOf('gdiplus.dll',
                     'GdipSetMatrixElements')), 'int',
                     ['pointer', 'float', 'float', 'float', 'float', 'float', 'float'],
                     'stdcall');
      setm(mp, m11, m12, m21, m22, dx, dy);

      var lstP = opnew(LIST);
      new NativeFunction(e['?__autoclassinit2@esSegList@@QAEXI@Z'], 'void',
                         ['pointer', 'int'], 'thiscall')(lstP, LIST);
      new NativeFunction(e['??0esSegList@@QAE@XZ'], 'void',
                         ['pointer'], 'thiscall')(lstP);
      new NativeFunction(e['?AddSegObject@esSegList@@QAEXPAVesSeg@@H@Z'], 'void',
                         ['pointer', 'pointer', 'int'], 'thiscall')(lstP, segP, 1);

      var shP = opnew(PATH);
      new NativeFunction(e['?__autoclassinit2@esShapePath@@QAEXI@Z'], 'void',
                         ['pointer', 'int'], 'thiscall')(shP, PATH);
      new NativeFunction(e['??0esShapePath@@QAE@XZ'], 'void',
                         ['pointer'], 'thiscall')(shP);
      shP.add(0x34).writeU32(0x040700FF);
      new NativeFunction(e['?AddSegList@esShapePath@@QAEXPAVesSegList@@@Z'], 'void',
                         ['pointer', 'pointer'], 'thiscall')(shP, lstP);
      return { ok: true, shape: shP.toString(), seg: segP.toString(),
               list: lstP.toString(), matrix: mp.toString() };
    } catch (err) { return { error: 'makeHVLineMatrixShape: ' + err }; }
  },


  // (p0 -> p1 horizontal/vertical -> p2). The HV constraint is what keeps the
  // marker a square when the user drags its handles.
  makeHVLineShape: function (points, canvas, styleSheet) {
    try {
      var e = ensureExports();
      var opnew = new NativeFunction(ptr(this.expOf('msvcrt.dll', '??2@YAPAXI@Z')),
                                     'pointer', ['int'], 'sysv');
      var pts = Memory.alloc(points.length * 8);
      for (var i = 0; i < points.length; i++) {
        pts.add(i * 8).writeS32(Math.round(points[i][0]));
        pts.add(i * 8 + 4).writeS32(Math.round(points[i][1]));
      }
      var SEG = 0xC0, PATH = 0x74;
      var segP = opnew(SEG);
      new NativeFunction(e['?__autoclassinit2@esSegHVLine@@QAEXI@Z'], 'void',
                         ['pointer', 'int'], 'thiscall')(segP, SEG);
      new NativeFunction(e['??0esSegHVLine@@QAE@PAUtagPOINT@@HPAVMatrix@Gdiplus@@@Z'],
                         'void', ['pointer', 'pointer', 'int', 'pointer'],
                         'thiscall')(segP, pts, points.length, ptr(0));
      if (segP.add(0x00).readPointer().isNull()) {
        return { error: 'esSegHVLine ctor produced no vtable' };
      }
      var lstP = opnew(0x44);
      new NativeFunction(e['?__autoclassinit2@esSegList@@QAEXI@Z'], 'void',
                         ['pointer', 'int'], 'thiscall')(lstP, 0x44);
      new NativeFunction(e['??0esSegList@@QAE@XZ'], 'void',
                         ['pointer'], 'thiscall')(lstP);
      new NativeFunction(e['?AddSegObject@esSegList@@QAEXPAVesSeg@@H@Z'], 'void',
                         ['pointer', 'pointer', 'int'], 'thiscall')(lstP, segP, 1);
      var shP = opnew(PATH);
      new NativeFunction(e['?__autoclassinit2@esShapePath@@QAEXI@Z'], 'void',
                         ['pointer', 'int'], 'thiscall')(shP, PATH);
      new NativeFunction(e['??0esShapePath@@QAE@XZ'], 'void',
                         ['pointer'], 'thiscall')(shP);
      shP.add(0x34).writeU32(0x040700FF);
      new NativeFunction(e['?AddSegList@esShapePath@@QAEXPAVesSegList@@@Z'], 'void',
                         ['pointer', 'pointer'], 'thiscall')(shP, lstP);
      return { ok: true, shape: shP.toString(), seg: segP.toString(),
               list: lstP.toString() };
    } catch (err) { return { error: 'makeHVLineShape: ' + err }; }
  },


  //   canvas +0x38 = newest head, +0x34 = oldest tail
  //   shape  +0x44 = newer,       +0x48 = older
  unlinkShape: function (canvas, shape) {
    try {
      var c = ptr(canvas), s = ptr(shape);
      var newer = s.add(0x44).readPointer();
      var older = s.add(0x48).readPointer();
      var head = c.add(0x38);
      var tail = c.add(0x34);
      if (!newer.isNull()) newer.add(0x48).writePointer(older);
      else head.writePointer(older);
      if (!older.isNull()) older.add(0x44).writePointer(newer);
      else tail.writePointer(newer);
      s.add(0x44).writePointer(ptr(0));
      s.add(0x48).writePointer(ptr(0));
      return { ok: true, newer: newer.toString(), older: older.toString() };
    } catch (err) {
      return { error: 'unlinkShape: ' + err };
    }
  },

  // ---------------------------------------------------------------------
  // Canvas label, following the editor's own recipe (Editer.exe FUN_00426480)
  // combined with the canonical shape sequence in FUN_004842c0:
  //   construct -> OnCreate(styleSheet) -> RecalcLayout -> AddItem
  //
  //   shape = esShapeLine (0x5c)      style |= 0x4001007
  //   seg   = esSegLable  (0xd8)
  //           ctor(zPoint, zwstr, ulong, ushort fontIndex, ushort padding)
  //           -- the zwstr is passed BY VALUE: 3 stack dwords
  //              {buffer, length, capacity}. Passing a bare pointer instead
  //              leaves length 0 and the label silently renders nothing.
  //           Initialize(fontSheet) -> esEQLine::AppendString(seg+0x80, ...)
  //           -> Build(1) -> RecalcLayout
  //   shape+0x40 = seg ; esObject::SetParent(seg, shape)
  //
  // The AppendString call is essential: esSegLable::Draw inks the text with the
  // esEQLine embedded at seg+0x80, which neither the ctor nor Build populates.
  //
  // Every step is individually switchable so the caller can bisect a failure
  // without editing this file. All work happens in one JS frame.
  makeLabelShape: function (text, x, y, fontSheet, styleSheet, canvas, opts) {
    opts = opts || {};
    var on = function (name, dflt) {
      return opts[name] === undefined ? dflt : !!opts[name];
    };
    var steps = [];
    var step = 'init';
    var note = function (s) { steps.push(s); step = s; };
    try {
      var e = ensureExports();
      var opAddr = this.expOf('msvcrt.dll', '??2@YAPAXI@Z');
      var ctorW = this.expOf('zoro.dll', '??0zwstr@@QAE@PB_W@Z');
      var opnew = opAddr
        ? new NativeFunction(ptr(opAddr), 'pointer', ['int'], 'sysv') : null;
      if (!opnew || !ctorW) return { error: 'allocator or zwstr ctor missing' };

      var need = ['?__autoclassinit2@esSegLable@@QAEXI@Z',
                  '?Initialize@esSegLable@@QAEXPAVesFontSheet@@@Z',
                  '?Build@esSegLable@@MAEXH@Z',
                  '?RecalcLayout@esSegLable@@MAEXXZ',
                  '?__autoclassinit2@esShapeLine@@QAEXI@Z',
                  '??0esShapeLine@@QAE@XZ'];
      for (var i = 0; i < need.length; i++) {
        if (!e[need[i]]) return { error: 'export missing: ' + need[i] };
      }
      var segCtor = e['??0esSegLable@@QAE@VzPoint@@Vzwstr@@KGG@Z'];
      var segCtorDefault = e['??0esSegLable@@QAE@XZ'];

      // --- optional three-part text: [主体, 上标, 下标] ------------------
      // Editer.exe's 文字标注 dialog (resource strings @0x472e40..0x472f48:
      // "标注内容: 主体 / 上标 / 下标 / 分数形式") stores the label text as
      // THREE concatenated parts, and esSegLable::RecalcLayoutLable (0x3eb390)
      // renders them as: Part1 -> main EQLine text, Part2/Part3 -> a 0x48-byte
      // esTextItem with two boxes (ini codes 0x16000041 = 上标 only,
      // 0x16000081 = 下标 only, 0x160000c2 = both) -- i.e. the engine's own
      // superscript/subscript mechanism.  This is the only native way to get
      // "A" with a subscript "1" out of a label; the font slot cannot express it.
      var parts = null;
      if (opts.parts && opts.parts.length) {
        parts = [String(opts.parts[0] || ''), String(opts.parts[1] || ''),
                 String(opts.parts[2] || '')];
        text = parts.join('');
      }

      // --- scratch zwstr holding the text -------------------------------
      note('zwstr');
      var wbuf = Memory.alloc((text.length + 1) * 2);
      wbuf.writeUtf16String(text);
      var z = opnew(0x30);
      new NativeFunction(ptr(ctorW), 'void', ['pointer', 'pointer'],
                         'thiscall')(z, wbuf);
      var zdw = [z.readU32(), z.add(4).readU32(), z.add(8).readU32()];

      // --- text segment --------------------------------------------------
      note('seg-alloc');
      var seg = opnew(SEGLABEL_SIZE);
      new NativeFunction(e['?__autoclassinit2@esSegLable@@QAEXI@Z'], 'void',
                         ['pointer', 'int'], 'thiscall')(seg, SEGLABEL_SIZE);

      var ctorMode = opts.ctor || 'value';
      // Character counts. esSegLable's ctor does NOT treat its ulong as one
      // opaque "feature word": it unpacks the four bytes into
      //   byte0 -> +0x70  主体 (main text) char count
      //   byte1 -> +0x71  上标 (superscript) char count
      //   byte2 -> +0x72  下标 (subscript) char count
      //   byte3 -> +0x73  flags (0x80 = 数学化/math mode, 0x40 = 分数形式,
      //                   0x20 = margin pad, 0x10 = 标注点 dot, 0x08 = 边框)
      // and esSegLable::RecalcLayoutLable appends exactly byte0 characters
      // from the text buffer at +0x68 into the embedded esEQLine, then builds
      // the sup/sub boxes from the remaining parts.  Callers hand over a flags
      // template in opts.k (its low three bytes ignored); they are always
      // derived from the real text, or every multi-character label renders
      // only its first glyph / drops its sub- and superscript.
      var kTpl = (opts.k === undefined || opts.k === null)
        ? 0x80000000 : (opts.k >>> 0);
      var charCount = Math.min(255, String(text).length);
      var mainCount = Math.min(255, parts ? parts[0].length : String(text).length);
      var supCount = parts ? Math.min(255, parts[1].length) : 0;
      var subCount = parts ? Math.min(255, parts[2].length) : 0;
      var kWord = (((kTpl & 0xff000000) | (subCount << 16) |
                    (supCount << 8) | mainCount) >>> 0);
      if (ctorMode === 'default') {
        note('seg-ctor-default');
        if (!segCtorDefault) return { error: 'default esSegLable ctor missing' };
        new NativeFunction(segCtorDefault, 'void', ['pointer'],
                           'thiscall')(seg);
        // The default ctor leaves +0x70 zero ("no text"); set the counts the
        // way the 6-arg ctor would have.
        seg.add(0x70).writeU8(mainCount);
        seg.add(0x71).writeU8(supCount);
        seg.add(0x72).writeU8(subCount);
      } else {
        // zPoint (2 dwords) + zwstr (3 dwords) + ulong + ushort + ushort.
        // Declared as separate scalars so Frida lays them out on the stack
        // exactly as the by-value struct arguments expect.
        note('seg-ctor-value');
        if (!segCtor) return { error: 'esSegLable 6-arg ctor missing' };
        new NativeFunction(segCtor, 'void',
                           ['pointer', 'int', 'int', 'int', 'int', 'int',
                            'int', 'int', 'int'],
                           'thiscall')(seg, x, y, zdw[0], zdw[1], zdw[2],
                                       kWord, opts.g1 || 0, opts.g2 || 0);
      }
      if (seg.readPointer().isNull()) return { error: 'esSegLable ctor failed',
                                               steps: steps };

      if (on('initialize', true)) {
        note('seg-initialize');
        new NativeFunction(e['?Initialize@esSegLable@@QAEXPAVesFontSheet@@@Z'],
                           'void', ['pointer', 'pointer'],
                           'thiscall')(seg, ptr(fontSheet));
      }

      // Optional font index (+0x6e) and text padding (+0x6c). The 6-arg ctor
      // takes both as its last two by-value ushorts; passing 0 selects font
      // slot 0 rather than the document's current font.
      if (opts.fontIndex !== undefined && opts.fontIndex !== null) {
        note('seg-fontindex');
        seg.add(0x6e).writeU16(opts.fontIndex & 0xffff);
      }
      if (opts.padding !== undefined && opts.padding !== null) {
        seg.add(0x6c).writeU16(opts.padding & 0xffff);
      }

      if (on('build', true)) {
        note('seg-build');
        new NativeFunction(e['?Build@esSegLable@@MAEXH@Z'], 'void',
                           ['pointer', 'int'], 'thiscall')(seg, opts.buildArg || 1);
      }
      if (on('recalcSeg', true)) {
        note('seg-recalc');
        new NativeFunction(e['?RecalcLayout@esSegLable@@MAEXXZ'], 'void',
                           ['pointer'], 'thiscall')(seg);
      }

      // --- wrapper shape -------------------------------------------------
      note('shape-alloc');
      var shape = opnew(SHAPELINE_SIZE);
      new NativeFunction(e['?__autoclassinit2@esShapeLine@@QAEXI@Z'], 'void',
                         ['pointer', 'int'], 'thiscall')(shape, SHAPELINE_SIZE);
      note('shape-ctor');
      new NativeFunction(e['??0esShapeLine@@QAE@XZ'], 'void',
                         ['pointer'], 'thiscall')(shape);
      if (shape.readPointer().isNull()) return { error: 'esShapeLine ctor failed',
                                                 steps: steps };
      var style = shape.add(0x34).readU32() | STYLE_LABEL;
      shape.add(0x34).writeU32(style >>> 0);

      note('attach');
      shape.add(0x40).writePointer(ptr(seg));
      if (on('setParent', true)) {
        // eslib exports the non-virtual QAE mangling; keep UAE as a fallback
        // in case a different build exports the virtual form.
        var setParent = e['?SetParent@esObject@@QAEXPAV1@@Z']
                     || e['?SetParent@esObject@@UAEXPAV1@@Z'];
        if (setParent) {
          try {
            new NativeFunction(setParent, 'void', ['pointer', 'pointer'],
                               'thiscall')(seg, shape);
          } catch (err) { steps.push('setParent-err:' + err); }
        } else { steps.push('setParent-missing'); }
      }

      // Canonical step from FUN_004842c0: esShapeBase::OnCreate(styleSheet).
      if (on('onCreate', true) && styleSheet && styleSheet !== '0x0') {
        var onCreate = e['?OnCreate@esShapeBase@@QAEXPAVesStyleSheet@@@Z'];
        if (onCreate) {
          note('shape-oncreate');
          new NativeFunction(onCreate, 'void', ['pointer', 'pointer'],
                             'thiscall')(shape, ptr(styleSheet));
        } else { steps.push('onCreate-missing'); }
      } else if (on('onCreate', true)) {
        steps.push('onCreate-skipped(no stylesheet)');
      }

      if (on('recalcShape', true)) {
        note('shape-recalc-virt');
        var r = this.recalcShape(shape);
        if (r && r.error) steps.push('recalcShape-err:' + r.error);
      }

      if (on('addItem', true) && canvas && canvas !== '0x0') {
        note('addItem');
        var a = this.addItem(canvas, shape, 1);
        if (a && a.error) return { error: 'addItem: ' + a.error, steps: steps,
                                   shape: shape.toString(), seg: seg.toString() };
      }

      if (on('recalcAfterAdd', false)) {
        note('shape-recalc-after-add');
        this.recalcShape(shape);
      }

      // Settle the label's text onto its anchor, exactly what Editer.exe does
      // right after placing a label (FUN_00426900 -> esSegLable::HandMoveText
      // with flag 0).  Without this, +0x74 (text alignment) and +0x78/+0x7c
      // (text-offset floats) keep the ctor defaults, so the first drag re-lays
      // the text against a state the engine itself never produces -- the exact
      // "letter sits off / drag inks garbage" bug.  (0,0) is the fresh-label
      // settle: it centres the glyph on the anchor.  Disable with settle:false.
      if (on('settle', true)) {
        var hmt = e['?HandMoveText@esSegLable@@QAEHAAUtagPOINT@@H@Z'];
        if (hmt) {
          note('seg-settle');
          var spt = Memory.alloc(8);
          spt.writeS32(opts.settleX || 0);
          spt.add(4).writeS32(opts.settleY || 0);
          var sret = new NativeFunction(hmt, 'int',
                                        ['pointer', 'pointer', 'int'],
                                        'thiscall')(seg, spt, 0);
          if (on('settleRebuild', true)) {
            new NativeFunction(e['?Build@esSegLable@@MAEXH@Z'], 'void',
                               ['pointer', 'int'], 'thiscall')(seg, 1);
          }
          steps.push('seg-settle(ret=' + sret + ', +0x74=0x'
                     + seg.add(0x74).readU8().toString(16) + ')');
        } else { steps.push('settle-missing(HandMoveText)'); }
      }

      // THE step that makes a label visible: the segment ctor only copies the
      // string to +0x68 (a wchar_t*). What inks the glyph is the esEQLine
      // embedded at +0x80, and esSegLable::Draw only calls esEQLine::Draw on it.
      //
      // Whether the engine fills that line itself depends on the feature word
      // passed to the ctor: nonzero -> it does (and appending again would draw
      // the glyph twice); zero -> it does not, and the label stays blank.
      // So decide from the live object instead of guessing: append only when
      // the line is still empty. opts.appendText === false disables it, === true
      // forces it.
      if (opts.appendText !== false) {
        var append = e['?AppendString@esEQLine@@QAEXPB_WHPAVesFontSheet@@G@Z'];
        var lineCount = 0;
        try { lineCount = seg.add(0x80 + 0x30).readU32(); } catch (e2) { /* unreadable */ }
        if (lineCount === 0 || opts.appendText === true) {
          var textBuf = ctorMode === 'default' ? ptr(0) : seg.add(0x68).readPointer();
          if (append && !textBuf.isNull()) {
            note('eqline-append');
            new NativeFunction(append, 'void',
                               ['pointer', 'pointer', 'int', 'pointer', 'int'],
                               'thiscall')(seg.add(0x80), textBuf, text.length,
                                           ptr(fontSheet), opts.appendFlag || 0);
          } else {
            steps.push(append ? 'eqline-append-skipped(no text buffer)'
                              : 'eqline-append-export-missing');
          }
        } else {
          steps.push('eqline-engine-populated(' + lineCount + ' items)');
        }
      }

      // Match the engine's own labels: the embedded esEQLine's +0x04 high word
      // is 0xFFFF ("do not override -- keep the segment's own font").  Ours
      // come out 0x00000000, which reads as format index 0; the first paint
      // survives it, but any re-layout (dragging the letter) re-resolves the
      // font from it and inks garbage.  Low word is left untouched.
      if (opts.formatWord !== false) {
        var fw = seg.add(0x84).readU32();
        if ((fw >>> 16) !== 0xFFFF) {
          var nfw = (0xFFFF0000 | (fw & 0xFFFF)) >>> 0;
          seg.add(0x84).writeU32(nfw);
          steps.push('eqline-formatword(0x' + fw.toString(16) + '->0x'
                     + nfw.toString(16) + ')');
        }
      }

      return {
        ok: true,
        shape: shape.toString(),
        seg: seg.toString(),
        zwstr: z.toString(),
        zwstrDwords: zdw.map(function (w) { return '0x' + w.toString(16); }),
        style: '0x' + (style >>> 0).toString(16),
        steps: steps,
        box: {
          p1x: shape.add(0x14).readS32(), p1y: shape.add(0x18).readS32(),
          p2x: shape.add(0x1c).readS32(), p2y: shape.add(0x20).readS32(),
          left: shape.add(0x24).readS32(), top: shape.add(0x28).readS32(),
          right: shape.add(0x2c).readS32(), bottom: shape.add(0x30).readS32()
        },
        textAt: this.scanForText(seg, SEGLABEL_SIZE, text),
        segDump: this.hexdump(seg, 0x60)
      };
    } catch (err) {
      return { error: 'makeLabelShape[' + step + ']: ' + err, steps: steps };
    }
  },

  // Native EE "bold point" (加粗点, the editor's ` key).
  //
  // THE recipe is a single engine constructor:
  //   esShapeLine::esShapeLine(const tagPOINT& pt, ushort structureType, ulong flags)
  //     { esShapeBase::esShapeBase(this);
  //       *(vtbl*)this = esShapeLine::vftable;
  //       esPenInfo::esPenInfo(this + 0x50);
  //       esShapeLine::OnStructure(this, &pt, structureType, flags); }
  // Verified with structureType = 0x6001: the engine itself creates the
  // esSegPoint segment, sets the style word to 0x04000005 and lays the shape
  // out around the point (+/-200), and esShapeLine::RecalcLayout succeeds.
  //
  // Do NOT hand-roll it as operator_new + esShapeLine(void-ctor) + a manually
  // built esSegPoint, and do NOT call esSegPoint::Build(): the void ctor leaves
  // the shape's structure unset so every later RecalcLayout faults with
  // "access violation accessing 0x4".
  //
  // Then: optional re-size of the corner box, the 0.40 mm (160) pen -- applied
  // AFTER any canvas-wide 0.25 mm pass -- and a final recalc.
  makeDotShape: function (x, y, canvas, styleSheet, opts) {
    opts = opts || {};
    var steps = [];
    var step = 'init';
    var note = function (s) { steps.push(s); step = s; };
    try {
      var e = ensureExports();
      var opAddr = this.expOf('msvcrt.dll', '??2@YAPAXI@Z');
      var opnew = opAddr
        ? new NativeFunction(ptr(opAddr), 'pointer', ['int'], 'sysv') : null;
      if (!opnew) return { error: 'allocator missing' };
      var ctor = e['??0esShapeLine@@QAE@ABUtagPOINT@@GK@Z'];
      var autoInit = e['?__autoclassinit2@esShapeLine@@QAEXI@Z'];
      if (!ctor || !autoInit) {
        return { error: 'export missing: esShapeLine(tagPOINT,ushort,ulong)' };
      }
      var size = opts.size || 320;
      var pen = opts.pen === undefined ? 160 : opts.pen;
      var segType = opts.segType === undefined ? 0x6001 : (opts.segType | 0);

      note('point');
      var pt = Memory.alloc(8);
      pt.writeS32(x | 0);
      pt.add(4).writeS32(y | 0);

      note('shape-alloc');
      var shape = opnew(SHAPELINE_SIZE);
      new NativeFunction(autoInit, 'void', ['pointer', 'int'],
                         'thiscall')(shape, SHAPELINE_SIZE);

      note('shape-ctor(engine)');
      new NativeFunction(ctor, 'void',
                         ['pointer', 'pointer', 'int', 'int'],
                         'thiscall')(shape, pt, segType, opts.flags || 0);

      var seg = shape.add(0x40).readPointer();
      if (seg.isNull()) return { error: 'ctor left no segment', steps: steps };
      steps.push('seg=' + this.vtNameOf(seg.readPointer().toString()));

      // Optional exact corner box (a 320x320 box is what the toolbar's ` key
      // leaves behind).  The structure type's default is point +/- 200.
      if (opts.box !== false) {
        note('seg-box');
        seg.add(0x14).writeS32(x | 0);
        seg.add(0x18).writeS32(y | 0);
        seg.add(0x1c).writeS32((x + size) | 0);
        seg.add(0x20).writeS32((y + size) | 0);
      }

      if (styleSheet && styleSheet !== '0x0') {
        var onCreate = e['?OnCreate@esShapeBase@@QAEXPAVesStyleSheet@@@Z'];
        if (onCreate) {
          note('shape-oncreate');
          new NativeFunction(onCreate, 'void', ['pointer', 'pointer'],
                             'thiscall')(shape, ptr(styleSheet));
        }
      }

      note('shape-recalc');
      this.recalcShape(shape);

      if (canvas && canvas !== '0x0') {
        note('addItem');
        var a = this.addItem(canvas, shape, 1);
        if (a && a.error) {
          return { error: 'addItem: ' + a.error, steps: steps,
                   shape: shape.toString(), seg: seg.toString() };
        }
      }

      // AFTER the canvas-wide pen pass, so 0.25 mm does not win.
      note('pen');
      shape.add(0x58).writeU32(pen >>> 0);

      note('shape-recalc-final');
      this.recalcShape(shape);

      return {
        ok: true,
        shape: shape.toString(),
        seg: seg.toString(),
        style: '0x' + shape.add(0x34).readU32().toString(16),
        pen: pen, size: size, segType: '0x' + segType.toString(16),
        shapeCls: this.vtNameOf(shape.readPointer().toString()),
        segCls: this.vtNameOf(seg.readPointer().toString()),
        steps: steps,
        box: {
          p1x: shape.add(0x14).readS32(), p1y: shape.add(0x18).readS32(),
          p2x: shape.add(0x1c).readS32(), p2y: shape.add(0x20).readS32(),
          left: shape.add(0x24).readS32(), top: shape.add(0x28).readS32(),
          right: shape.add(0x2c).readS32(), bottom: shape.add(0x30).readS32()
        }
      };
    } catch (err) {
      return { error: 'makeDotShape[' + step + ']: ' + err, steps: steps };
    }
  },

  // Insert a canvas the way Space+G does, by calling the engine's own
  // esTextUI::InsertCanvas() on the *live* text UI.
  //
  // The reason this used to fail on every instance: the live esTextUI is not
  // reachable by scanning the heap for its vtable -- it hangs off the page list.
  // Ask the page list for it with esPageList::GetUI() first.
  //
  // esTextUI::InsertCanvas() also requires the UI to be bound to a text object
  // (esTextUI::IsValid() == *(int*)(this+0xdc) != 0), which is only true while
  // the caret is inside the document body; otherwise every candidate returns
  // null and it says so. This path only ever calls the engine's own routine,
  // so a refusal is harmless.
  //
  // LEGACY (2026-10): superseded by insertCanvasNative below (2-arg
  // InsertCanvas(ui, canvas, -1) paste channel, verified live). Not called by
  // the server anymore; kept for reference/probing only.
  newCanvas: function (pageList, uiAddr) {
    try {
      var e = ensureExports();
      var ctor = e['?InsertCanvas@esTextUI@@QAEPAVesCanvas@@XZ'];
      if (!ctor) return { error: 'InsertCanvas export missing' };
      var f = new NativeFunction(ctor, 'pointer', ['pointer'], 'thiscall');

      var order = [], seen = {};
      function add(p, why) {
        if (!p || p.isNull() || p.toInt32() < 0x10000) return;
        var k = p.toString();
        if (seen[k]) return;
        seen[k] = why;
        order.push({ ptr: p, why: why });
      }
      // The caret's own UI first: that is the one InsertCanvas works on and
      // the one whose page list receives the new canvas.  GetUI(pageList)
      // only answers for the page list that currently owns the caret, so it
      // is a poor primary source (it returned NULL for the ranked canvas'
      // page list while the live UI was bound to a different one).
      if (uiAddr && ptr(uiAddr).toInt32() > 0x10000) {
        add(ptr(uiAddr), 'explicit uiAddr');
      }
      var live = this.liveTextUI();
      if (live.ok) add(ptr(live.ui), 'liveTextUI (IsValid=1)');
      var fGetUI = e['?GetUI@esPageList@@QBEPAVesTextUI@@XZ'];
      if (pageList && fGetUI) {
        try {
          add(new NativeFunction(fGetUI, 'pointer', ['pointer'], 'thiscall')
              (ptr(pageList)), 'pageList.GetUI');
        } catch (e1) { /* page list has no UI */ }
      }
      var vt = e['??_7esTextUI@@6B@'];
      if (vt) {
        var hits = scanInstances(vt, 16);
        for (var i = 0; i < hits.length; i++) add(hits[i], 'heap scan');
      }

      // IsValid() gates the whole insertion, so report it per candidate.
      var fValid = e['?IsValid@esTextUI@@QBEHXZ'];
      var tried = [];
      for (var j = 0; j < order.length; j++) {
        var t = order[j].ptr, valid = null;
        try {
          valid = fValid ? new NativeFunction(fValid, 'int', ['pointer'],
                                              'thiscall')(t) : null;
        } catch (e2) { valid = 'err'; }
        if (!valid) {
          tried.push(order[j].why + ' ' + t.toString() + ' IsValid=0');
          continue;
        }
        var cv = null;
        try { cv = f(t); }
        catch (err2) { tried.push(order[j].why + ' ' + t.toString() + ':err'); continue; }
        if (cv !== null && !cv.isNull()) {
          var cc = this.caretCanvas();
          return { ok: true, textUI: t.toString(), source: order[j].why,
                   canvas: cv.toString(), caretCanvas: cc.ok ? cc.canvas : null,
                   embedder: cc.ok ? cc.embedder : null, tried: tried };
        }
        tried.push(order[j].why + ' ' + t.toString() + ' IsValid=1 but null');
      }
      return {
        ok: false,
        error: order.length
          ? 'InsertCanvas returned null on every candidate'
          : 'no esTextUI candidate found',
        hint: 'the text UI is only bound (IsValid) while the caret is inside '
            + 'the document body -- click into the page text in EduEditer and retry',
        tried: tried,
      };
    } catch (err) {
      return { error: 'newCanvas: ' + err };
    }
  },

  // ★ Native canvas insert — the Space+G replacement, reverse-engineered
  //   2026-10 from the editor's own paste command (esTextUI::PastData, the
  //   "paste an esCanvas" branch) and the OLE-insert command.
  //
  // The engine call that places a canvas into the text flow is the 2-arg
  // overload:
  //
  //   esTextUI::InsertCanvas(ui, canvas, flags)     RVA 0x48c980, flags = -1
  //
  // (Both editor callers pass -1 -- PastData and the OLE command; flags is
  // forwarded to esTextUI::OnPreInsert.) Inside it runs the full editor
  // insert: D2D text-line check -> OnPreInsert(ui, -1) -> GetInsertPos ->
  // operator_new(0x44) + esEmbedder(embedder, canvas) -> esText::
  // AddChrObj(text, embedder, pos, esObject::m_pUndo) -> text-line relayout
  // (vtbl+0x44(1)) -> canvas->flags(+0x4c) = 0x1000 -> esMainTable::AddCanvas
  // -> CancelSel; returns 1.
  //
  // The canvas object must exist before the call; PastData builds it with the
  // engine's own (w,h) constructor (default ctor + SetAsBorderRect(0,0,w,h),
  // border rect written at +0xc8, frameType bits 0x1000):
  //
  //   operator_new(0xe0) + __autoclassinit2 + ??0esCanvas@@QAE@HH@Z
  //
  // After the insert, PastData runs esCanvas::SetSelObj(canvas, NULL, 3)
  // (clear selection) and esCanvas::SetFocus(canvas). The Space+G command's
  // extra step (Editer.exe FUN_0047c250 -- activate the canvas' page and
  // scroll the view to it) is cosmetic and intentionally skipped.
  //
  // Why this replaces newCanvas() above: the no-arg overload
  // esTextUI::InsertCanvas(void) (0x48c6e0) also builds a canvas, but calling
  // it directly left the text UI half-settled in earlier live attempts (see
  // the notes on newCanvas/newCanvasByKey below). This path is what the app
  // itself runs for paste and OLE objects; notably it does not touch the
  // caret's DeleteSel machinery.
  //
  // The insert lands at the CURRENT CARET, so bind the caret first
  // (esTextUI::IsValid() == 1). opts.dryRun builds + measures the canvas but
  // stops before inserting (the object is leaked; safe, no document change).
  insertCanvasNative: function (uiAddr, w, h, opts) {
    var detail = {};
    try {
      opts = opts || {};
      var e = ensureExports();
      var need = {
        isValid: '?IsValid@esTextUI@@QBEHXZ',
        insert2: '?InsertCanvas@esTextUI@@QAEHPAVesCanvas@@H@Z',
        ctorWH: '??0esCanvas@@QAE@HH@Z',
        autoinit2: '?__autoclassinit2@esCanvas@@QAEXI@Z',
        setSelObj: '?SetSelObj@esCanvas@@QAEPAVesShapeBase@@PAV2@H@Z',
        setFocus: '?SetFocus@esCanvas@@QAEHXZ',
        getW: '?GetWidth@esCanvas@@QBEHXZ',
        getH: '?GetHeight@esCanvas@@QBEHXZ',
        frameType: '?GetFrameType@esCanvas@@QBEKXZ',
        vtCanvas: '??_7esCanvas@@6B@'
      };
      var F = {};
      for (var n in need) {
        var a = e[need[n]];
        if (!a) return { error: 'export missing: ' + need[n] };
        F[n] = a;
      }

      var ui = null;
      if (uiAddr && ptr(uiAddr).toInt32() > 0x10000) ui = ptr(uiAddr);
      if (!ui) {
        var live = this.liveTextUI();
        if (!live.ok) return { ok: false, error: live.error, hint: live.hint,
                               tried: live.tried };
        ui = ptr(live.ui);
      }
      var fValid = new NativeFunction(F.isValid, 'int', ['pointer'], 'thiscall');
      detail.textUI = ui.toString();
      detail.isValid = fValid(ui);
      if (detail.isValid !== 1) {
        return { ok: false, textUI: ui.toString(),
                 error: 'esTextUI::IsValid()==0 -- the caret is not inside the '
                      + 'document body; click once into the page text, then '
                      + 'retry' };
      }

      var W = (w === null || w === undefined) ? 61340 : (w | 0);
      var H = (h === null || h === undefined) ? 30670 : (h | 0);
      var opAddr = this.expOf('msvcrt.dll', '??2@YAPAXI@Z');
      if (!opAddr) return { error: 'operator new not found' };
      var opnew = new NativeFunction(ptr(opAddr), 'pointer', ['int'], 'sysv');
      var c = opnew(0xe0);
      new NativeFunction(F.autoinit2, 'void', ['pointer', 'int'],
                         'thiscall')(c, 0xe0);
      new NativeFunction(F.ctorWH, 'void', ['pointer', 'int', 'int'],
                         'thiscall')(c, W, H);
      detail.canvas = c.toString();
      var vtOk = c.readPointer().equals(F.vtCanvas);
      detail.vtableOk = vtOk;
      if (!vtOk) {
        return { ok: false, canvas: c.toString(),
                 error: 'esCanvas (w,h) ctor left the wrong vtable' };
      }
      detail.asked = { w: W, h: H };
      detail.measure = {
        w: new NativeFunction(F.getW, 'int', ['pointer'], 'thiscall')(c),
        h: new NativeFunction(F.getH, 'int', ['pointer'], 'thiscall')(c),
        frameType: new NativeFunction(F.frameType, 'int', ['pointer'],
                                      'thiscall')(c)
      };
      if (detail.measure.frameType !== 0x1000) {
        return { ok: false, canvas: c.toString(), measure: detail.measure,
                 error: 'unexpected frameType after ctor (want 0x1000)' };
      }
      if (opts.dryRun) {
        return { ok: true, dryRun: true, textUI: detail.textUI,
                 canvas: c.toString(), asked: detail.asked,
                 measure: detail.measure };
      }

      var r = new NativeFunction(F.insert2, 'int', ['pointer', 'pointer', 'int'],
                                 'thiscall')(ui, c, -1);
      detail.insertRet = r;
      if (r !== 1) {
        return { ok: false, textUI: ui.toString(), canvas: c.toString(),
                 error: 'esTextUI::InsertCanvas(canvas, -1) returned ' + r };
      }
      new NativeFunction(F.setSelObj, 'pointer', ['pointer', 'pointer', 'int'],
                         'thiscall')(c, ptr(0), 3);
      new NativeFunction(F.setFocus, 'int', ['pointer'], 'thiscall')(c);
      var cc = this.caretCanvas();
      return { ok: true, textUI: ui.toString(), canvas: c.toString(),
               asked: detail.asked, measure: detail.measure, insertRet: r,
               caretCanvas: cc };
    } catch (err) {
      return { error: 'insertCanvasNative: ' + err, detail: detail };
    }
  },

  // ---- editor-native canvas insert (2026-10-19) -------------------------
  // Set of laid-out canvases (frameType 0x1000 / any canvas with a non-zero
  // page rect). Used to diff before/after an editor-side insert.
  _canvasSet: function () {
    var out = {};
    try {
      var r = this.instances('??_7esCanvas@@6B@', 2000, 512);
      var list = r.addresses || [];
      for (var i = 0; i < list.length; i++) {
        var p = ptr(list[i]);
        var rect = null;
        try {
          rect = [p.add(0xc8).readS32(), p.add(0xcc).readS32(),
                  p.add(0xd0).readS32(), p.add(0xd4).readS32()];
        } catch (e2) { continue; }
        if (!rect || rect[2] <= 0 || rect[3] <= 0) continue;
        out[list[i]] = rect;
      }
    } catch (err) { /* ignore */ }
    return out;
  },

  // Locate the top-level Editer frame plus its largest AfxFrameOrView child
  // (the document view).
  _eeWindows: function () {
    var u32 = Process.getModuleByName('user32.dll');
    var map = {};
    u32.enumerateExports().forEach(function (x) { map[x.name] = x.address; });
    var EnumWindows = new NativeFunction(map.EnumWindows, 'int',
                                        ['pointer', 'pointer']);
    var EnumChildWindows = new NativeFunction(map.EnumChildWindows, 'int',
                                             ['pointer', 'pointer', 'pointer']);
    var GetWindowTextW = new NativeFunction(map.GetWindowTextW, 'int',
                                           ['pointer', 'pointer', 'int']);
    var GetClassNameW = new NativeFunction(map.GetClassNameW, 'int',
                                          ['pointer', 'pointer', 'int']);
    var GetWindowRect = new NativeFunction(map.GetWindowRect, 'int',
                                          ['pointer', 'pointer']);
    var frame = null, title = null;
    var cbWin = new NativeCallback(function (h, l) {
      try {
        var b = Memory.alloc(512);
        GetWindowTextW(h, b, 256);
        var t = b.readUtf16String();
        if (t.indexOf('Editer - [') === 0) { frame = ptr(h); title = t; }
      } catch (e) { /* ignore */ }
      return 1;
    }, 'int', ['pointer', 'pointer']);
    EnumWindows(cbWin, ptr(0));
    if (!frame) return { error: 'Editer frame window not found' };
    var view = null, best = 0;
    var cbChild = new NativeCallback(function (h, l) {
      try {
        var b = Memory.alloc(256);
        GetClassNameW(h, b, 128);
        if (b.readUtf16String().indexOf('AfxFrameOrView') !== 0) return 1;
        var r = Memory.alloc(16);
        GetWindowRect(h, r);
        var w = r.add(8).readS32() - r.readS32();
        var hh = r.add(12).readS32() - r.add(4).readS32();
        if (w * hh > best) { best = w * hh; view = ptr(h); }
      } catch (e) { /* ignore */ }
      return 1;
    }, 'int', ['pointer', 'pointer']);
    EnumChildWindows(frame, cbChild, ptr(0));
    return { frame: frame, view: view, title: title, map: map };
  },

  // Put Editer in the foreground and focus the document view (needed before
  // any keybd_event/mouse_event injection).
  _focusDoc: function (w) {
    var map = w.map;
    var GetForegroundWindow = new NativeFunction(map.GetForegroundWindow,
                                                 'pointer', []);
    var SetForegroundWindow = new NativeFunction(map.SetForegroundWindow, 'int',
                                                 ['pointer']);
    var SetFocusF = new NativeFunction(map.SetFocus, 'pointer', ['pointer']);
    var BringWindowToTop = new NativeFunction(map.BringWindowToTop, 'int',
                                              ['pointer']);
    var AttachThreadInput = new NativeFunction(map.AttachThreadInput, 'int',
                                              ['uint', 'uint', 'int']);
    var GWTPID = new NativeFunction(map.GetWindowThreadProcessId, 'uint',
                                    ['pointer', 'pointer']);
    var GetCurrentThreadId = new NativeFunction(
      Process.getModuleByName('kernel32.dll').getExportByName('GetCurrentThreadId'),
      'uint', []);
    var SleepF = new NativeFunction(
      Process.getModuleByName('kernel32.dll').getExportByName('Sleep'),
      'void', ['uint']);
    var fg = GetForegroundWindow();
    var fgT = GWTPID(fg, ptr(0));
    var myT = GetCurrentThreadId();
    var ok = AttachThreadInput(myT, fgT, 1);
    BringWindowToTop(w.frame);
    SetForegroundWindow(w.frame);
    SetFocusF(w.view);
    SleepF(150);
    return { attached: ok, fgThread: fgT, myThread: myT,
             foreground: GetForegroundWindow().toString() };
  },

  _unfocusThread: function (fgThread, myThread) {
    try {
      var u32 = Process.getModuleByName('user32.dll');
      var at = new NativeFunction(u32.getExportByName('AttachThreadInput'),
                                  'int', ['uint', 'uint', 'int']);
      at(myThread, fgThread, 0);
      return true;
    } catch (err) { return false; }
  },

  // Insert a canvas by driving the editor's OWN Space+G quick command with
  // real injected input. (2026-10-19: this is the ONLY insertion path whose
  // canvases can be deleted immediately without crashing the editor.)
  //
  // WHY: canvases created through insertCanvasNative() are attached to the
  // text run but never pass through the editor's private insert routine
  // (BeginUndoSet -> esCanvas ctor -> esMainTable::AddCanvas ->
  // esCanvasList::Append -> EndUndoSet -> esUndo::Add -> OnDocumentChange ->
  // SetFocus). Reproducing those calls by hand does NOT help -- the exact same
  // sequence was replayed and Delete still crashed. Only the editor's own
  // Space+G command produces canvases that survive Delete while unsaved.
  // Bonus: the editor marks the document modified, so Ctrl+S writes.
  //
  // Requires a bound caret (IsValid()==1) at the insert position; the canvas
  // lands at the caret. Returns the new canvas handle found by diffing the
  // laid-out canvas set before/after.
  insertCanvasByShortcut: function (opts) {
    opts = opts || {};
    var detail = {};
    try {
      var w = this._eeWindows();
      if (!w.frame) return { ok: false, error: w.error };
      if (!w.view) return { ok: false, error: 'document view not found' };
      detail.frame = w.frame.toString();
      detail.view = w.view.toString();
      detail.title = w.title;
      var e = ensureExports();
      var fValid = new NativeFunction(e['?IsValid@esTextUI@@QBEHXZ'], 'int',
                                      ['pointer'], 'thiscall');
      var live = this.liveTextUI();
      detail.liveUI = live.ui || null;
      if (live.ok && live.ui) {
        detail.isValid = fValid(ptr(live.ui));
      }
      var before = (opts.skipSnapshot ? null : this._canvasSet());
      detail.beforeCount = before ? Object.keys(before).length : null;
      var SleepF = new NativeFunction(
        Process.getModuleByName('kernel32.dll').getExportByName('Sleep'),
        'void', ['uint']);
      var keybd = new NativeFunction(w.map.keybd_event, 'void',
                                     ['uchar', 'uchar', 'uint', 'uint']);
      var f = this._focusDoc(w);
      detail.focus = f;
      if (opts.dryRun) {
        this._unfocusThread(f.fgThread, f.myThread);
        return { ok: true, dryRun: true, detail: detail };
      }
      keybd(0x20, 0x39, 0, 0);       // VK_SPACE down -- opens Space+<key> mode
      SleepF(150);
      keybd(0x47, 0x22, 0, 0);       // 'G' down
      SleepF(130);
      keybd(0x47, 0x22, 2, 0);       // 'G' up
      SleepF(100);
      keybd(0x20, 0x39, 2, 0);       // VK_SPACE up
      SleepF(opts.settleMs || 800);
      this._unfocusThread(f.fgThread, f.myThread);
      var after = this._canvasSet();
      var fresh = [];
      for (var k in after) {
        if (!before || !before[k]) fresh.push(k);
      }
      detail.afterCount = Object.keys(after).length;
      return { ok: fresh.length > 0, canvas: fresh.length ? fresh[0] : null,
               fresh: fresh, detail: detail };
    } catch (err) {
      return { ok: false, error: 'insertCanvasByShortcut: ' + err,
               detail: detail };
    }
  },

  // Click the document with real injected mouse input at SCREEN coordinates
  // (the usual way to re-bind the text caret after a canvas insert).
  clickDoc: function (x, y) {
    try {
      var w = this._eeWindows();
      if (!w.frame) return { ok: false, error: w.error };
      var f = this._focusDoc(w);
      var SleepF = new NativeFunction(
        Process.getModuleByName('kernel32.dll').getExportByName('Sleep'),
        'void', ['uint']);
      var SetCursorPos = new NativeFunction(w.map.SetCursorPos, 'int',
                                            ['int', 'int']);
      var mouse_event = new NativeFunction(w.map.mouse_event, 'void',
                                           ['uint', 'uint', 'uint', 'uint']);
      SetCursorPos(x | 0, y | 0);
      SleepF(60);
      mouse_event(0x0002, 0, 0, 0);   // LEFTDOWN
      SleepF(40);
      mouse_event(0x0004, 0, 0, 0);   // LEFTUP
      SleepF(250);
      this._unfocusThread(f.fgThread, f.myThread);
      var live = this.liveTextUI();
      return { ok: true, x: x, y: y, focus: f, liveUI: live.ui || null,
               isValid: live.ok && live.ui
                 ? new NativeFunction(ensureExports()['?IsValid@esTextUI@@QBEHXZ'],
                                      'int', ['pointer'], 'thiscall')(ptr(live.ui))
                 : null };
    } catch (err) {
      return { ok: false, error: 'clickDoc: ' + err };
    }
  },

  // ---- NATIVE SMOOTH CURVES (esSegBezier, type 0x4703) --------------------
  //
  // The engine's own path factory esShapePath::CreateFromPathData() DOES build
  // esSegBezier segments -- but only for one exact encoding, verified live
  // 2026-10-19 against a user-made EE "函数图象" sample:
  //
  //   * point types are GDI+ PathPointType bytes: 0x00 = start, 0x03 = cubic
  //     bezier control point, 0x80 = terminator;
  //   * the point list MUST end with a REPEATED copy of its last point and the
  //     types list must be exactly as long as the point list;
  //   * call it with n == points.length.
  //
  //   types [0,3,3,3] + 4 points            -> NULL (no repeated tail)
  //   types [0,3,3,3,0x80] + 5 points       -> esShapePath + esSegBezier ✓
  //   types [0,2,2,2,0x80]                  -> NULL (0x02 is not a path type)
  //   types [0,1,2,3]                       -> esSegGon (line path)
  //
  // `points` here are ON-CURVE samples; the cubic control points are derived
  // Catmull-Rom style (C1 = P1 + (P2-P0)/6, C2 = P2 - (P3-P1)/6) so the
  // resulting bezier passes through every sample.  This is the "手搓折线" fix:
  // the drawn object is a single native bezier path, not N line segments.
  makeBezierPathShape: function (points, closed) {
    try {
      var e = ensureExports();
      var addr = e['?CreateFromPathData@esShapePath@@SAPAV1@PAUtagPOINT@@PAEHH@Z'];
      if (!addr) return { error: 'CreateFromPathData export missing' };
      var v = [];
      for (var i0 = 0; i0 < points.length; i0++) {
        v.push([points[i0][0] | 0, points[i0][1] | 0]);
      }
      var n = v.length;
      if (n < 2) return { error: 'need at least 2 points' };
      var pts = [v[0]];
      var types = [0x00];
      for (var i = 0; i < n - 1; i++) {
        var p0 = v[Math.max(0, i - 1)];
        var p1 = v[i];
        var p2 = v[i + 1];
        var p3 = v[Math.min(n - 1, i + 2)];
        var c1 = [Math.round(p1[0] + (p2[0] - p0[0]) / 6),
                  Math.round(p1[1] + (p2[1] - p0[1]) / 6)];
        var c2 = [Math.round(p2[0] - (p3[0] - p1[0]) / 6),
                  Math.round(p2[1] - (p3[1] - p1[1]) / 6)];
        pts.push(c1, c2, p2);
        types.push(0x03, 0x03, 0x03);
      }
      pts.push([pts[pts.length - 1][0], pts[pts.length - 1][1]]);
      types.push(0x80);
      var pb = Memory.alloc(pts.length * 8);
      for (var j = 0; j < pts.length; j++) {
        pb.add(j * 8).writeS32(pts[j][0]);
        pb.add(j * 8 + 4).writeS32(pts[j][1]);
      }
      var tb = Memory.alloc(types.length);
      for (var k = 0; k < types.length; k++) tb.add(k).writeU8(types[k] & 0xff);
      var f = new NativeFunction(addr, 'pointer',
                                 ['pointer', 'pointer', 'int', 'int'], 'sysv');
      var shape = f(pb, tb, pts.length, closed ? 1 : 0);
      if (shape.isNull()) return { error: 'CreateFromPathData -> null' };
      return { ok: true, shape: shape.toString(), samples: n,
               ctrlPoints: pts.length };
    } catch (err) {
      return { error: 'makeBezierPathShape: ' + err };
    }
  },

  // Draw one or more smooth bezier curves onto a canvas.
  //   specs: [{ points: [[x,y],...], closed?: bool }]
  // Returns the created shapes; the caller runs the 0.25 mm pen pass itself
  // (setPenWidth) after all shapes are in, exactly like ee_draw_figure does.
  drawBezierCurves: function (canvas, specs) {
    var out = { ok: false, canvas: canvas, shapes: [], errors: [] };
    var self = this;
    try {
      var cv = ptr(canvas);
      (specs || []).forEach(function (sp, i) {
        try {
          var r = self.makeBezierPathShape(sp.points || sp, !!sp.closed);
          if (!r.ok) throw new Error(String(r.error));
          var a = self.addItem(cv, r.shape, 1);
          if (a && a.error) throw new Error(a.error);
          out.shapes.push({ shape: r.shape, samples: r.samples,
                            closed: !!sp.closed });
        } catch (err) {
          out.errors.push('curve[' + i + ']: ' + err);
        }
      });
      out.ok = out.errors.length === 0 && out.shapes.length > 0;
      return out;
    } catch (err) {
      return { ok: false, error: 'drawBezierCurves: ' + err };
    }
  },

  // Set the pen width of the given shapes only (used for the smooth curves:
  // they are created with the engine default 80 = 0.20 mm).
  setShapePen: function (shapes, pen) {
    var out = [];
    for (var i = 0; i < (shapes || []).length; i++) {
      try {
        var p = ptr(shapes[i]);
        p.add(0x58).writeS32(pen | 0);
        out.push({ shape: shapes[i], pen: pen | 0 });
      } catch (err) { out.push({ shape: shapes[i], error: String(err) }); }
    }
    return out;
  },

  // Build a native esSegBezier path shape from RAW cubic bezier CONTROL points.
  //
  // `ctrlPoints` is the flattened control polygon of a piecewise cubic bezier:
  //   [P0, C1, C2, P1, C3, C4, P2, ...]   (1 + 3*segments points)
  // This is EXACTLY the representation EE itself uses for a "函数图象" graph:
  // the user-made y=x^2 sample on the canvas is `esSegPath + esSegBezier` with
  // only 7 control points (2 cubic segments) -- see AGENTS.md.  Feeding a
  // densely Catmull-Rom'd chain instead makes the object carry hundreds of
  // knots, which reads as "折线" to the user (feedback 2026-10-19), so the
  // fitting happens on the Python side and this RPC takes the fitted control
  // polygon verbatim.
  makeBezierShapeFromControlPoints: function (ctrlPoints, closed) {
    try {
      var e = ensureExports();
      var addr = e['?CreateFromPathData@esShapePath@@SAPAV1@PAUtagPOINT@@PAEHH@Z'];
      if (!addr) return { error: 'CreateFromPathData export missing' };
      var c = ctrlPoints || [];
      if (c.length < 4 || (c.length - 1) % 3 !== 0) {
        return { error: 'control points must be 1+3k, got ' + c.length };
      }
      var pts = [];
      var types = [];
      for (var i = 0; i < c.length; i++) {
        pts.push([c[i][0] | 0, c[i][1] | 0]);
        types.push(i === 0 ? 0x00 : 0x03);
      }
      pts.push([pts[pts.length - 1][0], pts[pts.length - 1][1]]);
      types.push(0x80);
      var pb = Memory.alloc(pts.length * 8);
      for (var j = 0; j < pts.length; j++) {
        pb.add(j * 8).writeS32(pts[j][0]);
        pb.add(j * 8 + 4).writeS32(pts[j][1]);
      }
      var tb = Memory.alloc(types.length);
      for (var k = 0; k < types.length; k++) tb.add(k).writeU8(types[k] & 0xff);
      var f = new NativeFunction(addr, 'pointer',
                                 ['pointer', 'pointer', 'int', 'int'], 'sysv');
      var shape = f(pb, tb, pts.length, closed ? 1 : 0);
      if (shape.isNull()) return { error: 'CreateFromPathData -> null' };
      return { ok: true, shape: shape.toString(), segments: (c.length - 1) / 3 };
    } catch (err) {
      return { error: 'makeBezierShapeFromControlPoints: ' + err };
    }
  },

  // Draw raw-control-point beziers onto a canvas (see above).
  //   specs: [{ ctrl: [[x,y],...], closed?: bool }]
  drawBezierControlCurves: function (canvas, specs) {
    var out = { ok: false, canvas: canvas, shapes: [], errors: [] };
    var self = this;
    try {
      var cv = ptr(canvas);
      (specs || []).forEach(function (sp, i) {
        try {
          var r = self.makeBezierShapeFromControlPoints(sp.ctrl, !!sp.closed);
          if (!r.ok) throw new Error(String(r.error));
          var a = self.addItem(cv, r.shape, 1);
          if (a && a.error) throw new Error(a.error);
          out.shapes.push({ shape: r.shape, segments: r.segments });
        } catch (err) {
          out.errors.push('curve[' + i + ']: ' + err);
        }
      });
      out.ok = out.errors.length === 0 && out.shapes.length > 0;
      return out;
    } catch (err) {
      return { ok: false, error: 'drawBezierControlCurves: ' + err };
    }
  },

  // Draw one saved canvas spec (analysis/specs/nb/*.canvas.json) onto a live
  // canvas in ONE round-trip: sampled polylines/arcs, optional fills, bold
  // dots, labels and the native coordinate axis.  Spec coordinates are already
  // final canvas units (the specs were built for a 61340x30670 canvas and fit
  // inside the editor's default canvas as well).
  //
  // opts: { styleSheet, fontSheet, fontIndex, padding, pen }
  drawCanvasSpec: function (specPath, canvasAddr, opts) {
    opts = opts || {};
    var out = { ok: false, canvas: canvasAddr, paths: [], labels: [],
                errors: [] };
    var self = this;
    try {
      var spec = JSON.parse(File.readAllText(specPath));
      var cv = ptr(canvasAddr);
      var sheet = opts.styleSheet;
      var fontSheet = opts.fontSheet || sheet;
      var fontIndex = (opts.fontIndex === 0 || opts.fontIndex)
        ? opts.fontIndex : 11;
      var pad = opts.padding || 400;
      var pen = opts.pen || 100;
      if (!sheet) return { ok: false, error: 'styleSheet required' };

      function poly(pts, closed) {
        var v = pts.map(function (p) { return [p[0] | 0, p[1] | 0]; });
        var n = v.length;
        if (n < 2) throw new Error('need >=2 points');
        var arr = v.concat([closed ? v[0] : v[n - 1]]);
        var types = [0x00];
        for (var i = 1; i < n; i++) types.push(0x01);
        types.push(0x80);
        var r = self.createPath(arr, types, closed ? 1 : 0);
        var shape = r && (r.ret || r.shape);
        if (!shape || shape === '0x0') {
          throw new Error('createPath -> ' + JSON.stringify(r));
        }
        var a = self.addItem(cv, shape, 1);
        if (a && a.error) throw new Error('addItem: ' + a.error);
        return shape;
      }

      // 1) native axis first, so the figure draws on top of it
      if (spec.axis) {
        try {
          var ax = spec.axis;
          var axs = self.makeNativeAxisShape(
            ax.rect, ax.origin,
            ax.visible_x === 0 ? 0 : (ax.visible_x || 1),
            ax.visible_y === 0 ? 0 : (ax.visible_y || 1), fontSheet);
          if (!axs || !axs.shape) throw new Error('axis -> ' + JSON.stringify(axs));
          self.addItem(cv, axs.shape, 1);
          self.recalcShape(axs.shape);
          self.styleAxisShape(axs.shape, fontSheet);
          out.axis = { shape: axs.shape, seg: axs.seg || null };
        } catch (eAx) { out.errors.push('axis: ' + eAx); }
      }

      // 2) plain paths (optionally filled / dashed)
      (spec.paths || []).forEach(function (it, i) {
        try {
          var closed = it.close === undefined ? it.points.length > 2
                                              : !!it.close;
          var shape = poly(it.points, closed);
          var rec = { shape: shape, n: it.points.length, closed: closed };
          if (it.fill) {
            var want = it.fill;
            var color = want === 'dark' ? 0xA0A0A0 : 0xCACACA;
            var br = self.setSolidBrush(shape, color);
            rec.fill = { color: '0x' + color.toString(16),
                         brush: br && br.brush, filled: br && br.filled };
            if (!br || !br.ok) out.errors.push('fill[' + i + ']: ' + JSON.stringify(br));
          }
          if (it.dash) {
            // esPenInfo+0x04 == 3 -> real dashed pen
            self.writeI32(ptr(shape).add(0x54), 3);
            rec.dash = 3;
          }
          out.paths.push(rec);
        } catch (eP) { out.errors.push('path[' + i + ']: ' + eP); }
      });

      // 3) sampled arcs / curves (pre-sampled point lists in the spec)
      function emitSampled(list, tag) {
        (list || []).forEach(function (it, i) {
          try {
            var pts = it.points || it;
            var shape = poly(pts, false);
            out.paths.push({ shape: shape, n: pts.length, sample: tag });
          } catch (eS) { out.errors.push(tag + '[' + i + ']: ' + eS); }
        });
      }
      emitSampled(spec.arcs, 'arc');
      emitSampled(spec.curves, 'curve');

      // 4) bold dots (engine-built, 0.40 mm; setPenWidth skips them)
      (spec.dots || []).forEach(function (d, i) {
        try {
          var x = d[0] | 0, y = d[1] | 0;
          var size = d.length > 2 ? (d[2] | 0) : 320;
          var r = self.makeDotShape(x, y, cv, fontSheet,
                                    { size: size, pen: 160 });
          if (!r || !r.ok) throw new Error(JSON.stringify(r));
          out.paths.push({ shape: r.shape, dot: size });
        } catch (eD) { out.errors.push('dot[' + i + ']: ' + eD); }
      });

      // 5) labels (math word baked in at creation via canvas-wide style pass)
      //    makeLabelShape() ALREADY attaches the shape to `canvas` -- adding it
      //    a second time collapses the canvas shape chain to that one shape
      //    (verified live: count 3 -> 1 after the duplicate addItem).
      (spec.labels || []).forEach(function (it, i) {
        try {
          var r = self.makeLabelShape(String(it.text), it.x | 0, it.y | 0,
                                      fontSheet, sheet, cv,
                                      { fontIndex: fontIndex, padding: pad });
          if (!r || !r.ok) throw new Error(JSON.stringify(r));
          out.labels.push({ text: it.text, shape: r.shape });
        } catch (eL) { out.errors.push('label[' + i + ']: ' + eL); }
      });

      // 6) uniform 0.25 mm pen, then the canvas-wide label style (math italic)
      var pr = self.setPenWidth(cv, pen);
      out.pen = { ok: pr && pr.ok, value: pen };
      if (out.labels.length) {
        var ls = self.setLableStyle(cv, { fontIndex: fontIndex, margin: pad,
                                          math: 1 });
        out.labelStyle = { ok: ls && ls.ok, labels: ls && ls.labels };
      }
      self.redrawAll();
      out.ok = out.errors.length === 0;
      return out;
    } catch (err) {
      return { ok: false, error: 'drawCanvasSpec: ' + err, out: out };
    }
  },

  // Insert a canvas the way the USER does: post the editor's own Space+G key
  // sequence to the document window.
  //
  // LEGACY (2026-10): superseded by insertCanvasByShortcut above (preferred).
  // The old newCanvasByKey below posts WM_KEYDOWN only; it types 'g' instead of
  // inserting because the quick command needs REAL keybd_event input.
  // History: the raw NO-ARG esTextUI::InsertCanvas() export (0x48c6e0) must
  // never be called -- it bypasses the editor's insert/settle/relayout path
  // and half-breaks the text UI (OnKeyDown returns 0 for every key, caret
  // rect becomes paragraph-tall), then the process dies. The 2-arg overload
  // (ui, canvas, -1) with an engine-built esCanvas DOES go through the proper
  // paste path and is the verified native route (see insertCanvasNative).
  //
  // PostMessage (not SendInput) so no focus is needed and the mouse is free.
  newCanvasByKey: function (hwnd, vk, vkMod) {
    try {
      var user32 = Process.findModuleByName('user32.dll');
      if (!user32) return { error: 'user32.dll not loaded' };
      var pPost = user32.findExportByName('PostMessageW');
      if (!pPost) return { error: 'PostMessageW not found' };
      var Post = new NativeFunction(pPost, 'int',
                                    ['pointer', 'uint', 'pointer', 'pointer'], 'stdcall');
      var h = ptr(hwnd);
      var fn = vkMod === undefined ? 0x47 : vkMod;    // 'G' by default
      var mk = function (scan, up, rep) {
        return ptr(((up ? 0xc0000000 : 0) | (rep << 16) | (scan << 0)) >>> 0);
      };
      var sent = [];
      var spaceScan = 0x39, gScan = 0x22;
      Post(h, 0x0100, ptr(0x20), mk(spaceScan, false, 1));   sent.push('space-down');
      Post(h, 0x0101, ptr(0x20), mk(spaceScan, true, 1));    sent.push('space-up');
      Post(h, 0x0100, ptr(fn), mk(gScan, false, 1));         sent.push('g-down');
      Post(h, 0x0101, ptr(fn), mk(gScan, true, 1));          sent.push('g-up');
      return { ok: true, hwnd: ptr(hwnd).toString(), sent: sent };
    } catch (err) {
      return { error: 'newCanvasByKey: ' + err };
    }
  },

  // The page list + font sheet that own the live caret.  esTextUI::GetOwner()
  // returns the page list, and esPageList::GetStyleSheet() (misleading name)
  // returns that document's esFontSheet -- the object a label's +0xd4 must
  // point at.  Used to give a caret-canvas (one not reachable through
  // GetActiveCanvas) the right font sheet.
  caretContext: function () {
    try {
      var e = ensureExports();
      var live = this.liveTextUI();
      if (!live.ok) return live;
      var ui = ptr(live.ui);
      var out = { ok: true, ui: live.ui };
      var fOwner = e['?GetOwner@esTextUI@@QBEPAVesObject@@XZ'];
      if (fOwner) {
        var pl = new NativeFunction(fOwner, 'pointer', ['pointer'],
                                    'thiscall')(ui);
        out.pageList = pl.isNull() ? null : pl.toString();
        var fStyle = e['?GetStyleSheet@esPageList@@QAEPAVesStyleSheet@@XZ'];
        if (fStyle && !pl.isNull()) {
          var fs = new NativeFunction(fStyle, 'pointer', ['pointer'],
                                      'thiscall')(pl);
          out.fontSheet = fs.isNull() ? null : fs.toString();
        }
      }
      return out;
    } catch (err) { return { error: 'caretContext: ' + err }; }
  },

  // The canvas anchored at the caret: esTextUI::GetBefEmbeder() returns the
  // esEmbedder sitting just before the caret, and that embedder stores its
  // esCanvas at +0x38 (verified live: the pointer there carries the
  // ??_7esCanvas@@6B@ vtable).  This is the canvas a fresh InsertCanvas just
  // landed on, and therefore the one to draw on right after ee_goto_problem
  // with insert=true -- the page-list GetActiveCanvas() does NOT report it.
  caretCanvas: function () {
    try {
      var e = ensureExports();
      var live = this.liveTextUI();
      if (!live.ok) return live;
      var ui = ptr(live.ui);
      var fA = e['?GetBefEmbeder@esTextUI@@QAEPAVesEmbedder@@XZ'];
      if (!fA) return { error: 'GetBefEmbeder export missing' };
      var emb = new NativeFunction(fA, 'pointer', ['pointer'], 'thiscall')(ui);
      if (emb.isNull()) {
        return { ok: true, ui: live.ui, embedder: null, canvas: null,
                 note: 'no canvas is anchored at the caret' };
      }
      var vtCanvas = e['??_7esCanvas@@6B@'].toString();
      var found = null;
      for (var off = 0; off < 0x80 && !found; off += 4) {
        var v;
        try { v = emb.add(off).readU32(); } catch (e2) { continue; }
        if (v <= 0x10000 || v >= 0x7fffffff) continue;
        var t;
        try { t = ptr(v).readPointer().toString(); } catch (e3) { continue; }
        if (t === vtCanvas) found = ptr(v);
      }
      return { ok: true, ui: live.ui, embedder: emb.toString(),
               canvas: found ? found.toString() : null };
    } catch (err) { return { error: 'caretCanvas: ' + err }; }
  },

  // Call an arbitrary address with an explicit ABI (no implicit `this`).
  calladdr: function (addr, retType, argTypes, args, abi) {
    var f;
    try {
      f = new NativeFunction(ptr(addr), retType, argTypes || [], abi || 'cdecl');
    } catch (err) {
      return { error: 'NativeFunction: ' + err };
    }
    var argv = (args || []).map(toPtr);
    try {
      var r = f.apply(null, argv);
      return { ok: true, ret: numOrPtr(r) };
    } catch (err) {
      return { error: 'invoke: ' + err };
    }
  },

  // Force the process's top-level windows to repaint.
  redrawAll: function () {
    try {
      var u32 = Process.getModuleByName('user32.dll');
      var map = {};
      u32.enumerateExports().forEach(function (e) { map[e.name] = e.address; });
      var EnumWindows = new NativeFunction(map.EnumWindows, 'int', ['pointer', 'pointer']);
      var GetWTPID = new NativeFunction(map.GetWindowThreadProcessId, 'uint',
                                        ['pointer', 'pointer']);
      var InvalidateRect = new NativeFunction(map.InvalidateRect, 'int',
                                              ['pointer', 'pointer', 'int']);
      var UpdateWindow = map.UpdateWindow
        ? new NativeFunction(map.UpdateWindow, 'int', ['pointer']) : null;
      var pid = Process.id;
      var n = 0;
      var cb = new NativeCallback(function (hwnd, lparam) {
        try {
          var out = Memory.alloc(4);
          GetWTPID(hwnd, out);
          if (out.readU32() === pid) {
            InvalidateRect(hwnd, ptr(0), 1);
            if (UpdateWindow) UpdateWindow(hwnd);
            n++;
          }
        } catch (e) { /* ignore */ }
        return 1;
      }, 'int', ['pointer', 'pointer']);
      EnumWindows(cb, ptr(0));
      return { ok: true, windows: n };
    } catch (err) {
      return { error: String(err) };
    }
  },

  // ---- draw-path tracing -------------------------------------------------
  // Attach Interceptor hooks along the draw chain so a missing glyph can be
  // localised precisely: is Draw reached at all, is the class Render reached,
  // is the child segment's Draw reached, and what did IsVisible decide.
  // Bounded ring buffer; no target memory is written.
  traceDraw: function (enable) {
    var self = this;
    if (!this._hits) this._hits = [];
    if (this._hooks) {
      this._hooks.forEach(function (h) { try { h.detach(); } catch (e) {} });
      this._hooks = null;
    }
    if (enable === false) return { ok: true, attached: [], detached: true };
    var e = ensureExports();
    var specs = [
      ['ShapeBase::Draw', '?Draw@esShapeBase@@UAEXPAVesRender@@@Z'],
      ['ShapePath::Render', '?Render@esShapePath@@MAEXPAVesRender@@@Z'],
      ['ShapeLine::Render', '?Render@esShapeLine@@MAEXPAVesRender@@@Z'],
      ['ShapeBase::GetLineList', '?GetLineList@esShapeBase@@UBEXPAVesLineList@@K@Z'],
      ['ShapePath::GetLineList', '?GetLineList@esShapePath@@UBEXPAVesLineList@@K@Z'],
      ['SegLable::Draw',
       '?Draw@esSegLable@@UAEXPAVesRender@@PAUtag_DRAWPARAM@@PBVMatrix@Gdiplus@@@Z'],
      ['Render::IsVisible', '?IsVisible@esRender@@QAEHPBUtagRECT@@@Z']
    ];
    var attached = [];
    var hooks = [];
    specs.forEach(function (s) {
      var addr = e[s[1]];
      if (!addr) return;
      try {
        var h = Interceptor.attach(addr, {
          onEnter: function (args) {
            var rec = { fn: s[0] };
            try { rec.obj = this.context.ecx.toString(); } catch (e2) {}
            try { rec.arg0 = args[0].toString(); } catch (e2) {}
            try {
              if (self._hits.length > 8000) self._hits.shift();
              self._hits.push(rec);
            } catch (e2) {}
            this._rec = rec;
          },
          onLeave: function (retval) {
            try {
              if (this._rec) this._rec.ret = retval.toInt32();
            } catch (e2) { /* void or unavailable */ }
          }
        });
        hooks.push(h);
        attached.push(s[0]);
      } catch (e2) { /* skip unhookable target */ }
    });
    this._hooks = hooks;
    return { ok: true, attached: attached };
  },

  traceLog: function (clear) {
    var out = this._hits || [];
    if (clear) this._hits = [];
    return { count: out.length, hits: out };
  },

  // ---- caret navigation -------------------------------------------------
  //
  // Verified live (Editer.exe + the 镇海区 exam paper .wsd):
  //   * The bound esTextUI is found by scanning for ??_7esTextUI@@6B@ and
  //     keeping the instance whose IsValid() == 1.
  //   * esTextUI::SetCaretToSafePosition() puts the caret on the first
  //     paragraph of the document and clears any selection.
  //   * esTextUI::OnKeyDown(VK_DOWN, 0) walks the caret forward one visual
  //     line at a time through the whole document, auto-scrolling the view.
  //   * esTextUI::GetCaretOwner() returns the *paragraph* (esPara) the caret
  //     sits in -- the export name says esTextLine, the object is an esPara.
  //   * esPara::GetContents(zwstr&, 0) returns that paragraph's text, and
  //     esPara::GetNextVisible() walks the paragraphs in document order.
  //
  // So "put the caret on question N" is: go to the top, then step down until
  // the paragraph under the caret contains the question's opening text.

  liveTextUI: function () {
    try {
      var e = ensureExports();
      var vt = e['??_7esTextUI@@6B@'];
      if (!vt) return { error: 'esTextUI vtable export missing' };
      var fValid = e['?IsValid@esTextUI@@QBEHXZ'];
      var fn = fValid ? new NativeFunction(fValid, 'int', ['pointer'],
                                           'thiscall') : null;
      var hits = scanInstances(vt, 32), tried = [];
      for (var i = 0; i < hits.length; i++) {
        var v = null;
        try { v = fn ? fn(hits[i]) : null; } catch (e1) { v = 'err'; }
        tried.push(hits[i].toString() + ' IsValid=' + v);
        if (v === 1) {
          return { ok: true, ui: hits[i].toString(),
                   source: 'heap scan (IsValid=1)', tried: tried };
        }
      }
      return { ok: false, tried: tried,
               error: 'no bound esTextUI: the text caret is not inside the '
                    + 'document body. Click once into the page text in '
                    + 'EduEditer, then retry.' };
    } catch (err) { return { error: 'liveTextUI: ' + err }; }
  },

  // Everything the caret needs, resolved in one frame.
  _caretApi: function () {
    if (this._apiCache) return this._apiCache;
    var e = ensureExports();
    var need = {
      owner: '?GetCaretOwner@esTextUI@@QBEPAVesTextLine@@XZ',
      rect: '?GetCaretRect@esTextUI@@QAEHPAUtagRECT@@@Z',
      key: '?OnKeyDown@esTextUI@@QAEHIH@Z',
      safe: '?SetCaretToSafePosition@esTextUI@@QAEXXZ',
      contents: '?GetContents@esPara@@QAEXAAVzwstr@@H@Z',
      next: '?GetNextVisible@esPara@@QBEPAV1@XZ',
      prev: '?GetPrevVisible@esPara@@QBEPAV1@XZ'
    };
    var out = {};
    for (var k in need) {
      var a = e[need[k]];
      if (!a) return { error: 'export missing: ' + need[k] };
      out[k] = a;
    }
    out.fOwner = new NativeFunction(out.owner, 'pointer', ['pointer'], 'thiscall');
    out.fRect = new NativeFunction(out.rect, 'int', ['pointer', 'pointer'], 'thiscall');
    out.fKey = new NativeFunction(out.key, 'int', ['pointer', 'uint', 'int'], 'thiscall');
    out.fSafe = new NativeFunction(out.safe, 'void', ['pointer'], 'thiscall');
    out.fGet = new NativeFunction(out.contents, 'void',
                                  ['pointer', 'pointer', 'int'], 'thiscall');
    out.fNext = new NativeFunction(out.next, 'pointer', ['pointer'], 'thiscall');
    out.fPrev = new NativeFunction(out.prev, 'pointer', ['pointer'], 'thiscall');
    this._apiCache = out;
    return out;
  },

  paraText: function (p) {
    try {
      var api = this._caretApi();
      if (api.error) return '';
      var z = Memory.alloc(0x40);
      for (var k = 0; k < 0x40; k += 4) z.add(k).writeU32(0);
      api.fGet(ptr(p), z, 0);
      var s = z.readU32();
      return (s > 0x10000 && s < 0x7fffffff) ? ptr(s).readUtf16String(400) : '';
    } catch (err) { return ''; }
  },

  // ---- paragraph helpers -------------------------------------------------
  // `paraText` above passes a real zwstr and lets the engine destruct it, which
  // MUTATES the paragraph.  For bulk reads use a NULL zwstr: GetContents writes
  // nothing when the out-parameter is null, so this is a pure read.
  paraRead: function (p) {
    try {
      var api = this._caretApi();
      if (api.error) return null;
      var z = Memory.alloc(0x40);
      for (var k = 0; k < 0x40; k += 4) z.add(k).writeU32(0);
      api.fGet(ptr(p), z, 0);
      var s = z.readU32();
      var t = (s > 0x10000 && s < 0x7fffffff) ? ptr(s).readUtf16String(4000) : '';
      // A NULL zwstr can leave the engine's temp buffer in place; the string is
      // still owned by the paragraph until the next call, so copy it out now.
      return t;
    } catch (err) { return null; }
  },

  // Walk GetPrevVisible from the caret (or an explicit paragraph) towards the
  // document start.  This is the only way to reach the stem when the caret sits
  // in an empty paragraph at the END of a question.
  prevParagraphs: function (max, fromPara) {
    try {
      var api = this._caretApi();
      if (api.error) return { error: api.error };
      var live = this.liveTextUI();
      if (!live.ok) return live;
      var ui = ptr(live.ui);
      var p = fromPara ? ptr(fromPara) : api.fOwner(ui);
      var out = [], seen = {}, cap = max || 200;
      while (!p.isNull() && out.length < cap) {
        var k = p.toString();
        if (seen[k]) { out.push({ addr: k, cycle: true }); break; }
        seen[k] = 1;
        out.push({ addr: k, text: this.paraRead(p) });
        p = api.fPrev(p);
      }
      return { ok: true, ui: live.ui, count: out.length, paras: out };
    } catch (err) { return { error: 'prevParagraphs: ' + err }; }
  },

  // Dump up to `max` paragraphs in DOCUMENT ORDER by first walking back to the
  // start (GetPrevVisible chain), then walking forward.  Reading the chain
  // twice also survives a caret that sits in a paragraph with a broken forward
  // link.  `filter` keeps only paragraphs whose text contains that substring.
  // `uiAddr` targets a specific esTextUI; without it the FIRST IsValid=1
  // instance is used, which is often the wrong document (several documents are
  // usually open at once).
  allParagraphs: function (max, filter, uiAddr) {
    try {
      var api = this._caretApi();
      if (api.error) return { error: api.error };
      var ui;
      if (uiAddr) {
        ui = ptr(uiAddr);
      } else {
        var live = this.liveTextUI();
        if (!live.ok) return live;
        ui = ptr(live.ui);
      }
      var uiStr = ui.toString();
      var cap = max || 2000;
      var p = api.fOwner(ui), seen = {}, first = p, guard = 0;
      while (!p.isNull() && guard < cap) {
        var k = p.toString();
        if (seen[k]) break;
        seen[k] = 1; first = p; guard++;
        var q = api.fPrev(p);
        if (q.isNull()) break;
        p = q;
      }
      var backSteps = guard;
      var out = [], seen2 = {}, f = first, g = 0;
      while (!f.isNull() && g < cap) {
        var k2 = f.toString();
        if (seen2[k2]) break;
        seen2[k2] = 1;
        var t = this.paraRead(f) || '';
        if (!filter || t.indexOf(filter) >= 0) out.push({ addr: k2, text: t });
        g++;
        var n = api.fNext(f);
        if (n.isNull()) break;
        f = n;
      }
      return { ok: true, ui: uiStr, backSteps: backSteps, count: out.length,
               truncated: g >= cap, paras: out };
    } catch (err) { return { error: 'allParagraphs: ' + err }; }
  },

  // The paragraphs of the document in order, starting from the caret's own
  // paragraph and following esPara::GetNextVisible().
  readParagraphs: function (max) {
    try {
      var api = this._caretApi();
      if (api.error) return { error: api.error };
      var live = this.liveTextUI();
      if (!live.ok) return live;
      var ui = ptr(live.ui);
      var p = api.fOwner(ui), out = [], seen = {};
      var cap = max || 400;
      while (!p.isNull() && out.length < cap) {
        var k = p.toString();
        if (seen[k]) { out.push({ addr: k, cycle: true }); break; }
        seen[k] = 1;
        out.push({ addr: k, text: this.paraText(p) });
        p = api.fNext(p);
      }
      return { ok: true, ui: live.ui, count: out.length, paras: out };
    } catch (err) { return { error: 'readParagraphs: ' + err }; }
  },

  // The document's first paragraph.  There is no exported "go to start":
  // SetCaretToSafePosition() only clamps the caret to a valid position (it
  // left the caret at the document END when it was already there), VK_HOME and
  // VK_PRIOR are not handled (OnKeyDown returns 0).  VK_UP is handled, so walk
  // up until the caret stops moving for a few presses.
  gotoTop: function (maxSteps, uiAddr) {
    try {
      var api = this._caretApi();
      if (api.error) return { error: api.error };
      var live;
      if (uiAddr) { live = { ok: true, ui: String(uiAddr) }; }
      else {
        live = this.liveTextUI();
        if (!live.ok) return live;
      }
      var ui = ptr(live.ui);
      var cap = maxSteps || 600, steps = 0, last = null, stalls = 0;
      for (;;) {
        var p = api.fOwner(ui);
        var r = Memory.alloc(16);
        api.fRect(ui, r);
        var key = p.toString() + '|' + r.readS32() + ',' + r.add(4).readS32();
        if (key === last) { stalls++; } else { stalls = 0; last = key; }
        if (stalls >= 3 || steps >= cap) break;
        if (!api.fKey(ui, 0x26 /* VK_UP */, 0)) break;
        steps++;
      }
      var p2 = api.fOwner(ui);
      return { ok: true, ui: live.ui, steps: steps, para: p2.toString(),
               text: this.paraText(p2) };
    } catch (err) { return { error: 'gotoTop: ' + err }; }
  },

  // Move the caret to the first paragraph (walking forward from the top of the
  // document) whose text contains `anchor`.  This is what replaces "user,
  // please click the caret onto question N".
  gotoText: function (anchor, maxSteps, fromSafe, uiAddr) {
    try {
      var api = this._caretApi();
      if (api.error) return { error: api.error };
      var live;
      if (uiAddr) { live = { ok: true, ui: String(uiAddr) }; }
      else {
        live = this.liveTextUI();
        if (!live.ok) return live;
      }
      var ui = ptr(live.ui);
      var want = String(anchor);
      if (!want) return { error: 'gotoText: empty anchor' };
      var top = null;
      if (fromSafe !== false) {
        top = this.gotoTop(undefined, uiAddr);
        if (!top.ok) return top;
      }
      var steps = 0, hist = [], last = null, stalls = 0;
      var cap = maxSteps || 600;
      for (;;) {
        var p = api.fOwner(ui);
        var t = p.isNull() ? '' : this.paraText(p);
        var key = p.toString() + '|' + t.slice(0, 24);
        if (t.indexOf(want) >= 0) {
          var r = Memory.alloc(16);
          api.fRect(ui, r);
          return { ok: true, ui: live.ui, steps: steps, para: p.toString(),
                   text: t, topSteps: top ? top.steps : null,
                   caretRect: [r.readS32(), r.add(4).readS32(),
                               r.add(8).readS32(), r.add(12).readS32()],
                   hist: hist };
        }
        if (steps >= cap) {
          return { ok: false, error: 'anchor not found within ' + cap + ' steps',
                   steps: steps, lastText: t, lastPara: p.toString(), hist: hist };
        }
        if (key === last) { stalls++; } else { stalls = 0; last = key; }
        if (stalls >= 12) {
          return { ok: false, error: 'caret stopped moving at step ' + steps,
                   steps: steps, lastText: t, lastPara: p.toString(), hist: hist };
        }
        var ret = api.fKey(ui, 0x28 /* VK_DOWN */, 0);
        if (!ret) {
          return { ok: false, error: 'OnKeyDown(VK_DOWN) returned 0',
                   steps: steps, lastText: t, lastPara: p.toString(), hist: hist };
        }
        if (hist.length < 8) hist.push(t.slice(0, 28));
        steps++;
      }
    } catch (err) { return { error: 'gotoText: ' + err }; }
  },

  // Where is the caret right now?
  caretWhere: function () {
    try {
      var api = this._caretApi();
      if (api.error) return { error: api.error };
      var live = this.liveTextUI();
      if (!live.ok) return live;
      var ui = ptr(live.ui);
      var r = Memory.alloc(16);
      var ok = api.fRect(ui, r);
      var p = api.fOwner(ui);
      return { ok: true, ui: live.ui, rectOk: ok,
               rect: [r.readS32(), r.add(4).readS32(), r.add(8).readS32(),
                      r.add(12).readS32()],
               para: p.isNull() ? null : p.toString(),
               text: p.isNull() ? null : this.paraText(p) };
    } catch (err) { return { error: 'caretWhere: ' + err }; }
  },

  // =====================================================================
  // Caret / text-position machinery  (analysis/figures-progress.md §7)
  //
  // Goal: put the text caret on a chosen paragraph so the engine's own
  // esTextUI::InsertCanvas() drops the canvas where the figure belongs,
  // instead of asking the user to click there first.
  //
  // Facts established live:
  //   * Page lists have their own esTextUI (esPageList::GetUI), but GetUI
  //     returns NULL unless that UI is bound to a text object
  //     (esTextUI::IsValid() == *(int*)(this+0xdc) != 0), which is only true
  //     while the caret is inside that document's body.
  //   * A plain vtable scan of `rw-` ranges DOES find the live UI, so the
  //     heap scan + IsValid() filter is a reliable fallback.
  // =====================================================================

  // Escape hatch: run a snippet inside the agent so a new engine call can be
  // tried without editing this file and restarting the MCP server.  The
  // snippet runs with the module helpers in scope (ensureExports, ptr,
  // scanInstances, hexdump, ...) and must end with a return statement.
  scratch: function (src) {
    try {
      var r = eval('(function(){' + String(src) + '\n})()');
      if (r === null || r === undefined) return { ok: true, ret: null };
      if (typeof r === 'object' || typeof r === 'string' || typeof r === 'number'
          || typeof r === 'boolean') {
        return { ok: true, ret: r };
      }
      return { ok: true, ret: String(r) };
    } catch (err) {
      return { ok: false, error: String(err),
               stack: (err && err.stack) ? String(err.stack) : null };
    }
  },

  // One row per esTextUI instance: vtable check, IsValid, style sheet, owner,
  // view rect, scroll offset, current caret rect and caret owner line.
  textUIs: function (max) {
    try {
      var e = ensureExports();
      var vt = e['??_7esTextUI@@6B@'];
      if (!vt) return { error: 'esTextUI vtable export missing' };
      var fValid = e['?IsValid@esTextUI@@QBEHXZ'];
      var fAble = e['?IsAbleToInput@esTextUI@@QAEHI@Z'];
      var fOwner = e['?GetOwner@esTextUI@@QBEPAVesObject@@XZ'];
      var fOwnerType = e['?GetOwnerType@esTextUI@@QBEGXZ'];
      var fPage = e['?GetActivePage@esTextUI@@QAEHXZ'];
      var fCaretLine = e['?GetCaretOwner@esTextUI@@QBEPAVesTextLine@@XZ'];
      var fCaretRect = e['?GetCaretRect@esTextUI@@QAEHPAUtagRECT@@@Z'];
      var fCheckShow = e['?CheckShowCaret@esTextUI@@QBEHXZ'];
      var fSheet = e['?GetSheet@esTextUI@@QBEPAVesStyleSheet@@XZ'];
      var fUiRect = e['?GetUiRect@esTextUI@@QAE?AUtagRECT@@XZ'];
      var fGetUI = e['?GetUI@esPageList@@QBEPAVesTextUI@@XZ'];

      // Which page list claims each UI (the authoritative binding).
      var claimed = {};
      var plVt = e['??_7esPageList@@6B@'];
      if (plVt && fGetUI) {
        var pls = scanInstances(plVt, 32);
        for (var i = 0; i < pls.length; i++) {
          try {
            var u = new NativeFunction(fGetUI, 'pointer', ['pointer'],
                                       'thiscall')(pls[i]);
            if (u && !u.isNull()) claimed[u.toString()] = pls[i].toString();
          } catch (e1) { /* list has no UI */ }
        }
      }

      var hits = scanInstances(vt, max || 32);
      var out = [];
      for (var j = 0; j < hits.length; j++) {
        var t = hits[j], row = { addr: t.toString() };
        row.pageListOwningIt = claimed[row.addr] || null;
        try { row.isValid = fValid ? new NativeFunction(fValid, 'int', ['pointer'], 'thiscall')(t) : null; } catch (e2) { row.isValid = 'err'; }
        try { row.ableToInput = fAble ? new NativeFunction(fAble, 'int', ['pointer', 'int'], 'thiscall')(t, 1) : null; } catch (e3) { row.ableToInput = 'err'; }
        try { row.sheet = fSheet ? fSheet(t).toString() : null; } catch (e4) { row.sheet = 'err'; }
        try { row.sheetField = t.add(0x1e0).readPointer().toString(); } catch (e5) { row.sheetField = 'err'; }
        try { row.owner = fOwner ? fOwner(t).toString() : null; } catch (e6) { row.owner = 'err'; }
        try { row.ownerType = fOwnerType ? fOwnerType(t) : null; } catch (e7) { row.ownerType = 'err'; }
        try { row.activePage = fPage ? fPage(t) : null; } catch (e8) { row.activePage = 'err'; }
        try { row.checkShowCaret = fCheckShow ? fCheckShow(t) : null; } catch (e9) { row.checkShowCaret = 'err'; }
        try {
          var ln = fCaretLine ? fCaretLine(t) : null;
          row.caretLine = (ln && !ln.isNull()) ? ln.toString() : null;
        } catch (e10) { row.caretLine = 'err'; }
        try {
          var r = Memory.alloc(16);
          var ok = fCaretRect ? new NativeFunction(fCaretRect, 'int', ['pointer', 'pointer'], 'thiscall')(t, r) : null;
          row.caretRect = ok ? { ok: ok, l: r.readS32(), t: r.add(4).readS32(),
                                 r: r.add(8).readS32(), b: r.add(12).readS32() } : { ok: ok };
        } catch (e11) { row.caretRect = 'err'; }
        try {
          if (fUiRect) {
            var q = Memory.alloc(16);
            new NativeFunction(fUiRect, 'pointer', ['pointer', 'pointer'], 'thiscall')(t, q);
            row.uiRect = { l: q.readS32(), t: q.add(4).readS32(),
                           r: q.add(8).readS32(), b: q.add(12).readS32() };
          }
        } catch (e12) { row.uiRect = 'err'; }
        out.push(row);
      }
      return { ok: true, count: out.length, items: out };
    } catch (err) { return { error: 'textUIs: ' + err }; }
  },

  // Every esPageList instance with its document, style sheet, its own UI and
  // every canvas it hands out, so "which page list is the live document" is
  // answerable instead of assumed.
  pageLists: function () {
    try {
      var e = ensureExports();
      var vt = e['??_7esPageList@@6B@'];
      if (!vt) return { error: 'esPageList vtable export missing' };
      var fGetUI = e['?GetUI@esPageList@@QBEPAVesTextUI@@XZ'];
      var fDocA = e['?GetDocument@esPageList@@QBEPAVesBaseDoc@@XZ'];
      var fStyleA = e['?GetStyleSheet@esPageList@@QAEPAVesStyleSheet@@XZ'];
      var fCanvasA = e['?GetActiveCanvas@esPageList@@QBEPAVesCanvas@@H@Z'];
      var fWA = e['?GetWidth@esCanvas@@QBEHXZ'];
      var fHA = e['?GetHeight@esCanvas@@QBEHXZ'];
      var fDoc = fDocA ? new NativeFunction(fDocA, 'pointer', ['pointer'], 'thiscall') : null;
      var fStyle = fStyleA ? new NativeFunction(fStyleA, 'pointer', ['pointer'], 'thiscall') : null;
      var fCanvas = fCanvasA ? new NativeFunction(fCanvasA, 'pointer', ['pointer', 'int'], 'thiscall') : null;
      var fW = fWA ? new NativeFunction(fWA, 'int', ['pointer'], 'thiscall') : null;
      var fH = fHA ? new NativeFunction(fHA, 'int', ['pointer'], 'thiscall') : null;
      var fValidA = e['?IsValid@esTextUI@@QBEHXZ'];
      var fValid = fValidA ? new NativeFunction(fValidA, 'int', ['pointer'], 'thiscall') : null;

      var pls = scanInstances(vt, 32), out = [];
      for (var i = 0; i < pls.length; i++) {
        var row = { pageList: pls[i].toString(), index: i };
        try { row.doc = fDoc ? fDoc(pls[i]).toString() : null; } catch (e1) { row.doc = null; }
        try { row.styleSheet = fStyle ? fStyle(pls[i]).toString() : null; } catch (e2) { row.styleSheet = null; }
        var ui = null;
        try { ui = fGetUI ? new NativeFunction(fGetUI, 'pointer', ['pointer'], 'thiscall')(pls[i]) : null; }
        catch (e3) { ui = null; }
        row.ui = (ui && !ui.isNull()) ? ui.toString() : null;
        if (row.ui) {
          try { row.uiIsValid = fValid ? new NativeFunction(fValid, 'int', ['pointer'], 'thiscall')(ui) : null; }
          catch (e4) { row.uiIsValid = 'err'; }
          try { row.uiSheet = ui.add(0x1e0).readPointer().toString(); } catch (e5) { row.uiSheet = 'err'; }
        }
        row.canvases = [];
        for (var n = 0; n < 8; n++) {
          var cv = null;
          try { cv = fCanvas ? fCanvas(pls[i], n) : null; } catch (e6) { break; }
          if (!cv || cv.isNull()) break;
          var c = { slot: n, canvas: cv.toString() };
          try { c.width = fW ? fW(cv) : null; } catch (e7) { c.width = null; }
          try { c.height = fH ? fH(cv) : null; } catch (e8) { c.height = null; }
          try {
            var sc = this.shapeCount(cv);
            c.shapes = sc.ok ? sc.count : null;
          } catch (e9) { c.shapes = null; }
          row.canvases.push(c);
        }
        out.push(row);
      }
      return { ok: true, count: out.length, items: out };
    } catch (err) { return { error: 'pageLists: ' + err }; }
  },

  readU32: function (addr) {
    try { return ptr(addr).readU32(); } catch (err) { return null; }
  },

  readStr: function (addr, isWide) {
    try {
      return isWide ? ptr(addr).readUtf16String(256) : ptr(addr).readCString(256);
    } catch (err) { return '<err ' + err + '>'; }
  },

  // Carve every embedded PNG out of the live process into `outDir` on disk.
  // The document keeps its images as literal PNG byte runs in the heap, so this
  // recovers the paper's own figures without needing the .wsd on disk.
  // Image bytes never cross the RPC boundary -- only the manifest does.
  // Boundaries are found by scanning for the signature and the IEND sentinel,
  // exactly like tools/find_wsd_by_png.py does on disk; the harvested bytes are
  // then validated by PIL on the host side.
  carvePngs: function (outDir, minBytes) {
    try {
      var SIG = '89 50 4e 47 0d 0a 1a 0a';
      var IEND = '49 45 4e 44 ae 42 60 82';
      var min = minBytes || 300;
      var ranges = [];
      Process.enumerateRanges('r--').forEach(function (r) {
        if (r.size < 64 || r.size > 256 * 1024 * 1024) return;
        ranges.push(r);
      });
      var found = [];
      var dbg = { sigHits: 0, noIend: 0, tooSmall: 0 };
      ranges.forEach(function (r) {
        var rEnd = r.base.add(r.size);
        var cur = r.base, guard = 0;
        while (guard++ < 40000) {
          var left = rEnd.sub(cur).toInt32();
          if (left <= 16) break;
          var m;
          try { m = Memory.scanSync(cur, left, SIG); }
          catch (e) { break; }
          if (!m || m.length === 0) break;
          var hit = m[0].address;
          cur = hit.add(8);
          dbg.sigHits++;
          var want = rEnd.sub(hit).toInt32();
          if (want < 16) { dbg.noIend++; continue; }
          var e;
          try { e = Memory.scanSync(hit, want, IEND); }
          catch (err) { dbg.noIend++; continue; }
          if (!e || e.length === 0) { dbg.noIend++; continue; }
          var total = e[0].address.add(8).sub(hit).toInt32();
          if (total < min) { dbg.tooSmall++; continue; }
          var w = 0, h = 0;
          try {
            if (hit.add(12).readU32() === 0x52444849) {   // 'IHDR' little-endian
              w = hit.add(16).readU32();
              h = hit.add(20).readU32();
            }
          } catch (e2) { /* leave 0x0 */ }
          found.push({ addr: hit, len: total, w: w, h: h });
        }
      });
      var seen = {}, files = [];
      for (var i = 0; i < found.length; i++) {
        var f = found[i];
        var key = f.addr.toString() + ':' + f.len;
        if (seen[key]) continue;
        seen[key] = 1;
        var name = 'p_' + f.addr.toString().replace('0x', '') + '_' + f.w + 'x' + f.h + '.png';
        var rec = { name: name, addr: f.addr.toString(), bytes: f.len, w: f.w, h: f.h };
        try {
          var fh = new File(outDir + '\\' + name, 'wb');
          fh.write(f.addr.readByteArray(f.len));
          fh.flush();
          fh.close();
        } catch (e) { rec.error = String(e); }
        files.push(rec);
      }
      files.sort(function (a, b) { return a.addr < b.addr ? -1 : (a.addr > b.addr ? 1 : 0); });
      return { ok: true, scannedRanges: ranges.length, dbg: dbg, count: files.length, files: files };
    } catch (err) {
      return { ok: false, error: 'carvePngs: ' + err };
    }
  }
};
