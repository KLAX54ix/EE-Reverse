'use strict';
// EE circle/arc construction recorder — captures how the editor builds a
// circle or arc, including constructor arguments and new-object pointers.

var MOD = 'eslib.dll';
var EXP = {};
var m = Process.findModuleByName(MOD);
if (m) m.enumerateExports().forEach(function (e) { EXP[e.name] = e.address; });

function regs(ctx) {
  return {
    eax: ctx.eax.toString(), ebx: ctx.ebx.toString(),
    ecx: ctx.ecx.toString(), edx: ctx.edx.toString(),
    esi: ctx.esi.toString(), edi: ctx.edi.toString(),
    esp: ctx.esp.toString()
  };
}

function stackDump(ctx, n) {
  var out = [];
  try {
    for (var i = 0; i < n; i++) {
      out.push(ctx.esp.add(4 + i * 4).readPointer().toString());
    }
  } catch (e) { out.push('<err>'); }
  return out;
}

// float reinterpretation of stack slots, to read PointF / radius / angles
function stackFloats(ctx, n) {
  var out = [];
  try {
    for (var i = 0; i < n; i++) {
      var raw = ctx.esp.add(4 + i * 4).readU32();
      var buf = Memory.alloc(4);
      buf.writeU32(raw);
      out.push(Number(buf.readFloat().toFixed(4)));
    }
  } catch (e) { out.push(null); }
  return out;
}

var TARGETS = [
  ['??0esSegArc@@QAE@VPointF@Gdiplus@@MMMPAVMatrix@2@H@Z', 'esSegArc(PointF,r,?,?,Matrix*,int)', 8],
  ['??0esSegArc@@QAE@VPointF@Gdiplus@@MMPAVMatrix@2@@Z', 'esSegArc(PointF,r,?,Matrix*)', 8],
  ['??0esSegArc@@QAE@VzPoint@@G@Z', 'esSegArc(zPoint,ushort)', 2],
  ['??0esSegArc@@QAE@G@Z', 'esSegArc(ushort)', 1],
  ['??0esSegArcBase@@QAE@XZ', 'esSegArcBase()', 0],
  ['??0esSegArcBase@@QAE@G@Z', 'esSegArcBase(ushort)', 1],
  ['??0esSegArcBase@@QAE@VzPoint@@G@Z', 'esSegArcBase(zPoint,ushort)', 2],
  ['??0esSegList@@QAE@XZ', 'esSegList()', 0],
  ['??0esSegList@@QAE@PAUtagPOINT@@PAEHH@Z', 'esSegList(pts,types,int)', 3],
  ['??0esShapePath@@QAE@XZ', 'esShapePath()', 0],
  ['??0esShapePath@@QAE@PAUtagPOINT@@PAEH@Z', 'esShapePath(pts,types)', 2],
  ['??0esShapePath@@QAE@PAVesSnapManager@@GK@Z', 'esShapePath(snap,ushort,ulong)', 3],
  ['?AddSegList@esShapePath@@QAEXPAVesSegList@@@Z', 'ShapePath::AddSegList', 1],
  ['?AddSegObject@esShapePath@@QAEXPAVesSeg@@H@Z', 'ShapePath::AddSegObject', 2],
  ['?AddSegObject@esSegList@@QAEXPAVesSeg@@H@Z', 'SegList::AddSegObject', 2],
  ['?BuildArc@esSegArcBase@@IAEXVzPoint@@MMMH@Z', 'SegArcBase::BuildArc(center,f,f,f,int)', 5],
  ['?Initialize@esShapeCreator@@QAEHH@Z', 'ShapeCreator::Initialize(toolId)', 1],
  ['?AddItem@esCanvas@@QAEXPAVesShapeBase@@H@Z', 'Canvas::AddItem(shape,flags)', 2]
];

var installed = [];

TARGETS.forEach(function (t) {
  var name = t[0], label = t[1], nargs = t[2];
  var addr = EXP[name];
  if (!addr) {
    installed.push({ label: label, hooked: false, reason: 'export not found' });
    return;
  }
  try {
    Interceptor.attach(addr, {
      onEnter: function (args) {
        this._rec = {
          k: 'call', label: label,
          thisPtr: this.context.ecx.toString(),
          regs: regs(this.context),
          stack: stackDump(this.context, nargs),
          floats: stackFloats(this.context, nargs)
        };
      },
      onLeave: function (retval) {
        var rec = this._rec;
        rec.ret = retval.toString();
        send(rec);
      }
    });
    installed.push({ label: label, hooked: true, addr: addr.toString() });
  } catch (e) {
    installed.push({ label: label, hooked: false, reason: String(e) });
  }
});

send({ k: 'install', installed: installed });
rpc.exports = { status: function () { return installed; } };
