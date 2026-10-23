'use strict';
// EE text/label creation recorder — captures how the editor builds a canvas
// letter or text box, including the extra initialisation the ctor omits.

var MOD = 'eslib.dll';
var EXP = {};
var m = Process.findModuleByName(MOD);
if (m) m.enumerateExports().forEach(function (e) { EXP[e.name] = e.address; });

function regs(ctx) {
  return { ecx: ctx.ecx.toString(), edx: ctx.edx.toString(),
           eax: ctx.eax.toString(), esp: ctx.esp.toString() };
}
function stackDump(ctx, n) {
  var out = [];
  try { for (var i = 0; i < n; i++) out.push(ctx.esp.add(4 + i * 4).readPointer().toString()); }
  catch (e) { out.push('<err>'); }
  return out;
}

var TARGETS = [
  ['??0esSegText@@QAE@VzPoint@@@Z', 'esSegText(zPoint)', 2],
  ['??0esSegText@@QAE@XZ', 'esSegText()', 0],
  ['?OnCreate@esSegText@@UAEXPAVesStyleSheet@@@Z', 'esSegText::OnCreate', 1],
  ['??0esSegTextBox@@QAE@VzPoint@@G@Z', 'esSegTextBox(zPoint,ushort)', 3],
  ['?CreateTextBox@esSegTextBox@@QAEXPAVesStyleSheet@@E@Z', 'esSegTextBox::CreateTextBox', 2],
  ['??0esSegLable@@QAE@VzPoint@@Vzwstr@@KGG@Z', 'esSegLable(zPoint,zwstr,...)', 6],
  ['??0esSegLable@@QAE@XZ', 'esSegLable()', 0],
  ['?Initialize@esSegLable@@QAEXPAVesFontSheet@@@Z', 'esSegLable::Initialize', 1],
  ['??0esSegFormulaBox@@QAE@XZ', 'esSegFormulaBox()', 0],
  ['?InitializeEqbox@esSegFormulaBox@@QAEXPAVesStyleSheet@@H@Z', 'FormulaBox::InitializeEqbox', 2],
  ['?AddSegObject@esShapePath@@QAEXPAVesSeg@@H@Z', 'ShapePath::AddSegObject', 2],
  ['?AddSegObject@esSegList@@QAEXPAVesSeg@@H@Z', 'SegList::AddSegObject', 2],
  ['?AddSegList@esShapePath@@QAEXPAVesSegList@@@Z', 'ShapePath::AddSegList', 1],
  ['?Initialize@esShapeCreator@@QAEHH@Z', 'ShapeCreator::Initialize(toolId)', 1],
  ['?AddItem@esCanvas@@QAEXPAVesShapeBase@@H@Z', 'Canvas::AddItem(shape,flags)', 2],
  ['?InsertText@esTextUI@@QAEXPB_WIH@Z', 'TextUI::InsertText', 3]
];

var installed = [];
TARGETS.forEach(function (t) {
  var name = t[0], label = t[1], nargs = t[2];
  var addr = EXP[name];
  if (!addr) { installed.push({ label: label, hooked: false, reason: 'export not found' }); return; }
  try {
    Interceptor.attach(addr, {
      onEnter: function (args) {
        this._rec = { k: 'call', label: label, thisPtr: this.context.ecx.toString(),
                      regs: regs(this.context), stack: stackDump(this.context, nargs) };
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
