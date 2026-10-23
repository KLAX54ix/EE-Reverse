// EE runtime probe #3 — resolve the live accessor chain with real calls.
// Only non-virtual member getters are called (QB... mangling), so a wrong
// `this` returns garbage rather than executing an arbitrary virtual slot.

var MOD = 'eslib.dll';

var NAMES = {
  base_GetActiveCanvas: '?GetActiveCanvas@esBaseDoc@@QBEPAVesCanvas@@XZ',
  pageList_GetDocument: '?GetDocument@esPageList@@QBEPAVesBaseDoc@@XZ',
  pageList_GetCanvasList: '?GetCanvasList@esPageList@@QBEPAVesCanvasList@@XZ',
  canvas_GetActive: '?GetActive@esCanvas@@QBEPAVesShapeBase@@XZ',
  canvas_AddItem: '?AddItem@esCanvas@@QAEXPAVesShapeBase@@H@Z',
  pageList_CreateObject: '?CreateObject@esPageList@@UBEPAVesObject@@G@Z',
  pageList_CreatePage: '?CreatePage@esPageList@@SAPAVesDocPage@@G@Z',
  doc_GetActiveUndoObj: '?GetActiveUndoObj@esDocument@@QAEPAVesUndo@@H@Z'
};

function resolve() {
  var out = {};
  var mod = Process.findModuleByName(MOD);
  var byName = {};
  if (mod) {
    mod.enumerateExports().forEach(function (e) { byName[e.name] = e.address; });
  }
  Object.keys(NAMES).forEach(function (k) {
    var a = byName[NAMES[k]];
    out[k] = a ? a.toString() : null;
  });
  return out;
}

setImmediate(function () {
  var addrs = resolve();
  send({ kind: 'export_addrs', addrs: addrs });

  var DOCS = ['0x91c8f80', '0x91d9890'];
  var LISTS = ['0x91c9c80', '0x91d1610', '0x91da590', '0xa99ac88', '0xaa793d8'];
  var CANVASES = ['0x1286040', '0x1286128', '0x1286210', '0x92cbfc0', '0x92cc0a8'];

  function tryCall(label, addr, retType, argTypes, self, args, abi) {
    var res = { kind: 'call', fn: label, self: self, ret: null, err: null };
    try {
      var f = new NativeFunction(ptr(addr), retType, argTypes, abi || 'thiscall');
      var r = f.apply(null, [ptr(self)].concat(args || []));
      res.ret = r === null || r === undefined ? null : r.toString();
    } catch (e) {
      res.err = String(e);
    }
    send(res);
    return res.ret;
  }

  // Does esDocument expose GetActiveCanvas directly (i.e. derive from esBaseDoc)?
  if (addrs.base_GetActiveCanvas) {
    DOCS.forEach(function (d) {
      tryCall('esBaseDoc::GetActiveCanvas', addrs.base_GetActiveCanvas,
              'pointer', ['pointer'], d);
    });
    LISTS.forEach(function (l) {
      tryCall('esBaseDoc::GetActiveCanvas(on pageList)', addrs.base_GetActiveCanvas,
              'pointer', ['pointer'], l);
    });
  }

  // pageList -> document
  var docsFromLists = {};
  if (addrs.pageList_GetDocument) {
    LISTS.forEach(function (l) {
      docsFromLists[l] = tryCall('esPageList::GetDocument',
                                 addrs.pageList_GetDocument, 'pointer',
                                 ['pointer'], l);
    });
  }

  // document/backpointer -> pageList  (try GetDocument on documents too)
  if (addrs.pageList_GetDocument) {
    DOCS.forEach(function (d) {
      tryCall('esPageList::GetDocument(on doc)', addrs.pageList_GetDocument,
              'pointer', ['pointer'], d);
    });
  }

  // canvas -> active shape
  if (addrs.canvas_GetActive) {
    CANVASES.forEach(function (c) {
      tryCall('esCanvas::GetActive', addrs.canvas_GetActive, 'pointer',
              ['pointer'], c);
    });
  }

  send({ kind: 'done' });
});
