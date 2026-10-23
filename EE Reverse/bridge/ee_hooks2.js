'use strict';
// EE drawing-path recorder v2 — full ia32 register + stack context.
// On ia32 Frida's Interceptor `args` are the STACK arguments; `this` lives in
// ECX for __thiscall, so both are captured explicitly here.

var MOD = 'eslib.dll';
var EXP = {};
var m = Process.findModuleByName(MOD);
if (m) m.enumerateExports().forEach(function (e) { EXP[e.name] = e.address; });

function stackDump(ctx, n) {
  var out = [];
  try {
    for (var i = 0; i < n; i++) {
      out.push(ctx.esp.add(4 + i * 4).readPointer().toString());
    }
  } catch (e) { out.push('<err>'); }
  return out;
}

function regs(ctx) {
  return {
    eax: ctx.eax.toString(), ebx: ctx.ebx.toString(),
    ecx: ctx.ecx.toString(), edx: ctx.edx.toString(),
    esi: ctx.esi.toString(), edi: ctx.edi.toString(),
    esp: ctx.esp.toString(), ebp: ctx.ebp.toString()
  };
}

// [mangled, label, wantReturn]
var TARGETS = [
  ['?Initialize@esShapeCreator@@QAEHH@Z', 'ShapeCreator::Initialize(H)', true],
  ['?ClearCreateInfo@esShapeCreator@@QAEXXZ', 'ShapeCreator::ClearCreateInfo()', false],
  ['?GetCreateType@esShapeCreator@@QBEGXZ', 'ShapeCreator::GetCreateType()', true],
  ['?SetCreateInfo@esShapeCreator@@QAEXPAVesSnapManager@@ABVesPenInfo@@K@Z',
   'ShapeCreator::SetCreateInfo(pen,ulong)', false],
  ['?SetCreateInfo@esShapeCreator@@QAEXPAVesSnapManager@@ABVesPenInfo@@PAVesShapeBase@@G@Z',
   'ShapeCreator::SetCreateInfo(pen,shape,ushort)', false],
  ['?AddItem@esCanvas@@QAEXPAVesShapeBase@@H@Z', 'Canvas::AddItem(shape,int)', false],
  ['?Insert@esCanvas@@UAEXPAVesObject@@0H@Z', 'Canvas::Insert(obj,obj,int)', false],
  ['?GetShapeList@esCanvas@@QAEPAVesShapeList@@XZ', 'Canvas::GetShapeList()', true],
  ['?GetCount@esShapeList@@QBEHXZ', 'ShapeList::GetCount()', true]
];

var installed = [];

TARGETS.forEach(function (t) {
  var name = t[0], label = t[1], wantRet = t[2];
  var addr = EXP[name];
  if (!addr) {
    installed.push({ label: label, hooked: false, reason: 'export not found' });
    return;
  }
  try {
    Interceptor.attach(addr, {
      onEnter: function (args) {
        this._rec = { k: 'call', label: label, regs: regs(this.context),
                      stack: stackDump(this.context, 6) };
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
