'use strict';
// EE engine call recorder — passive Interceptor hooks on eslib.dll exports.
// Sends one message per intercepted call. Never modifies arguments or returns.

var MOD = 'eslib.dll';
var EXP = {};
var m = Process.findModuleByName(MOD);
if (m) m.enumerateExports().forEach(function (e) { EXP[e.name] = e.address; });

// [mangled name, label, number of stack args after `this`]
var TARGETS = [
  ['?AddItem@esCanvas@@QAEXPAVesShapeBase@@H@Z', 'esCanvas::AddItem', 2],
  ['?Insert@esCanvas@@UAEXPAVesObject@@0H@Z', 'esCanvas::Insert', 3],
  ['?CreateObject@esPageList@@UBEPAVesObject@@G@Z', 'esPageList::CreateObject', 1],
  ['?CreateObject@esObject@@UBEPAV1@G@Z', 'esObject::CreateObject', 1],
  ['?CreateObject@esShapeBase@@UBEPAVesObject@@G@Z', 'esShapeBase::CreateObject', 1],
  ['?CreateObject@esSegList@@UBEPAVesObject@@G@Z', 'esSegList::CreateObject', 1],
  ['?CreateObject@esContainer@@UBEPAVesObject@@G@Z', 'esContainer::CreateObject', 1],
  ['?CreateObject@esCanvasList@@UBEPAVesObject@@G@Z', 'esCanvasList::CreateObject', 1],
  ['?Initialize@esShapeCreator@@QAEHH@Z', 'esShapeCreator::Initialize', 1],
  ['?GetCreateType@esShapeCreator@@QBEGXZ', 'esShapeCreator::GetCreateType', 0],
  ['?SetCreateInfo@esShapeCreator@@QAEXPAVesSnapManager@@ABVesPenInfo@@K@Z',
   'esShapeCreator::SetCreateInfo(pen,ulong)', 3],
  ['?SetCreateInfo@esShapeCreator@@QAEXPAVesSnapManager@@ABVesPenInfo@@PAVesShapeBase@@G@Z',
   'esShapeCreator::SetCreateInfo(pen,shape,ushort)', 4],
  ['?OnInitializeProcess@esDrawingModifier@@QAEPAVesShapeList@@XZ',
   'esDrawingModifier::OnInitializeProcess', 0],
  ['?OnEndProcess@esDrawingModifier@@QAEHIH@Z',
   'esDrawingModifier::OnEndProcess', 2],
  ['?OnMouseMove@esDrawingModifier@@QAEHPAVesSnapManager@@I@Z',
   'esDrawingModifier::OnMouseMove', 2],
  ['?OnInitializeProcess@esDrawingModifier@@QAEPAVesShapeList@@XZ',
   'esDrawingModifier::OnInitializeProcess2', 0],
  ['?SnapPoint@esDrawingModifier@@QAEHPAVesSnapManager@@@Z',
   'esDrawingModifier::SnapPoint', 1],
  ['?GetShapeList@esCanvas@@QAEPAVesShapeList@@XZ',
   'esCanvas::GetShapeList', 0],
  ['?ClearCreateInfo@esShapeCreator@@QAEXXZ',
   'esShapeCreator::ClearCreateInfo', 0]
];

var installed = [];

TARGETS.forEach(function (t, idx) {
  var name = t[0], label = t[1], nargs = t[2];
  var addr = EXP[name];
  if (!addr) {
    installed.push({ i: idx, label: label, hooked: false, reason: 'export not found' });
    return;
  }
  try {
    Interceptor.attach(addr, {
      onEnter: function (args) {
        var rec = { k: 'call', label: label, self: args[0].toString(), a: [] };
        for (var i = 1; i <= nargs; i++) rec.a.push(args[i].toString());
        send(rec);
      }
    });
    installed.push({ i: idx, label: label, hooked: true, addr: addr.toString() });
  } catch (e) {
    installed.push({ i: idx, label: label, hooked: false, reason: String(e) });
  }
});

send({ k: 'install', at: Date.now(), installed: installed });

rpc.exports = {
  status: function () { return installed; },
  ping: function () { return 'alive'; }
};
