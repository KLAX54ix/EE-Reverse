#!/usr/bin/env python3
"""EduEditer (EE) MCP server — lets an agent draw precise vector figures.

Transport: stdio JSON-RPC 2.0 (MCP). No third-party dependencies.

Runtime model
-------------
The server attaches to a running Editer.exe via Frida and calls the engine
(eslib.dll) directly:

  esShapePath::CreateFromPathData(POINT*, uchar* types, int count, int close)
      -> operator_new(0x74) + esShapePath() ctor + segment list
  esCanvas::AddItem(canvas, shape, flags)
      -> intrusive list insert into the active canvas

Both were confirmed by static decompilation (Ghidra headless project
D:\\EE Reverse\\analysis\\ghidra-proj) and by live instrumentation of the
editor's own drawing operations.

Coordinates are EE internal page units. In the reference document
(八下四边形分类汇编.wsd) one drawn figure used X 10454..34454, Y 8012..25412,
so page units are roughly 1/100 mm.

Canvas selection
----------------
A document can expose several page lists and therefore several "active"
canvases (templates, other views). Picking the first one found was
order-dependent and could draw into a canvas nobody is looking at. Selection is
now ranked (most shapes, then widest) and every tool accepts an explicit
`canvas` handle; `ee_canvases` shows the full ranking.
"""
import json
import math
import sys
import threading
import traceback

sys.path.insert(0, r"D:\EE Reverse\bridge")

import frida  # noqa: E402

TARGET = "Editer.exe"
BRIDGE = r"D:\EE Reverse\bridge\ee_bridge.js"

VT_PAGELIST = "??_7esPageList@@6B@"
VT_CANVAS = "??_7esCanvas@@6B@"

CREATE_FROM_PATH_DATA = "?CreateFromPathData@esShapePath@@SAPAV1@PAUtagPOINT@@PAEHH@Z"
ADD_ITEM = "?AddItem@esCanvas@@QAEXPAVesShapeBase@@H@Z"
GET_ACTIVE_CANVAS = "?GetActiveCanvas@esPageList@@QBEPAVesCanvas@@H@Z"
GET_WIDTH = "?GetWidth@esCanvas@@QBEHXZ"
GET_HEIGHT = "?GetHeight@esCanvas@@QBEHXZ"
GET_FRAME_RECT = "?GetFrameRect@esCanvas@@QAEABVzRect@@XZ"

T_START, T_LINE, T_BEZIER, T_CLOSE = 0x00, 0x01, 0x03, 0x80
CIRCLE_TOOL_ID = 0x4284       # esSegCircel +0x04 on a tool-drawn circle
CANVAS_HEAD = 0x38          # esCanvas + 0x38 -> newest shape
SHAPE_NEXT = 0x48           # esShapeBase + 0x48 -> older shape

KAPPA = 0.5522847498307936

# Project-fixed stroke width.  Engine unit is 1/400 mm, so 0.25 mm == 100.
# The engine's own default is 80 (0.20 mm), which is why every standalone
# primitive must set its pen explicitly (verified live 2026-10-18: a freshly
# drawn esSegCircel had shape+0x58 == 80 until a canvas-wide pass changed it).
PEN_MM_DEFAULT = 0.25


def pen_value(mm=None, default_mm=PEN_MM_DEFAULT):
    """Convert millimetres to the engine's esPenInfo width (1/400 mm)."""
    return int(round(float(default_mm if mm is None else mm) * 400))

# Default flags byte for the segment ctor's `ulong` (bits 24..31).  The four
# bytes of that word are per-part CHARACTER COUNTS (0x70/0x71/0x72) plus a
# flags byte at +0x73; the bridge derives byte0 from the real text length, so
# this constant only supplies the flags: 0x80 = math mode (数学化).  A nonzero
# main-text count makes the engine populate the embedded esEQLine itself;
# with 0 it does not and the label renders nothing unless the text is
# appended manually.
DEFAULT_LABEL_FEATURE = 0x80000001

# 镇海区九年级期末数学试卷: question id -> distinctive text anchor in the
# paragraph that owns the figure.  Anchors are substrings of the in-memory
# paragraph text (esPara::GetContents), which carries EE's list numbers, e.g.
# "6. 如图，在平面直角坐标系中，△ABC与△DEF是以原点O为位似中心的位似图形…".
PROBLEM_ANCHORS = {
    "选择5": "在Rt△ABC中，∠C=90°",
    "选择6": "位似图形",
    "选择8": "莱洛三角形",
    "选择9": "AD是斜边BC上的中线",
    "选择10": "正八边形",
    "填空5": "⊙O的内接三角形",
    "填空6": "AC=DC=BD",
    "解答1": "点D是AC的中点",
    "解答3": "正方形网格",
    "解答5": "AD是⊙O的直径",
    "解答6": "光线从空气射入玻璃",
    "解答8": "四边形ABCD内接于⊙O",
}

# Bisection presets for the label pipeline: each key turns one verified step on
# or off so a rendering failure can be localised without editing the bridge.
LABEL_VARIANTS = {
    "full": {},
    "no-append": {"appendText": False},
    "no-oncreate": {"onCreate": False},
    "no-recalc": {"recalcShape": False},
    "no-build": {"build": False},
    "no-initialize": {"initialize": False},
    "no-recalc-after-add": {"recalcShape": False, "recalcAfterAdd": True},
    "minimal": {"build": False, "recalcSeg": False, "onCreate": False,
                "recalcShape": False},
    "default-ctor": {"ctor": "default"},
}


class EEError(Exception):
    pass


class EEGateway:
    """One long-lived Frida session against Editer.exe."""

    def __init__(self):
        self._lock = threading.Lock()
        self.dev = None
        self.session = None
        self.script = None
        self._canvas = None
        self._ctx = None

    # ---------- lifecycle ----------
    def _attach(self):
        if self.script is not None:
            return
        self.dev = frida.get_local_device()
        try:
            self.session = self.dev.attach(TARGET)
        except Exception as exc:
            raise EEError(
                f"cannot attach to {TARGET}: {exc}. Start EduEditer "
                f"(Editer.exe) with a document open, then retry."
            )
        with open(BRIDGE, "r", encoding="utf-8") as fh:
            src = fh.read()
        self.script = self.session.create_script(src)
        self.script.on("message", self._on_message)
        self.script.load()
        self._canvas = None
        self._ctx = None

    @staticmethod
    def _on_message(msg, data):
        if msg.get("type") == "error":
            print(f"[ee] script error: {msg.get('description')}", file=sys.stderr)

    def _rpc(self, name, *args):
        self._attach()
        try:
            return getattr(self.script.exports_sync, name)(*args)
        except Exception as exc:
            # session died: drop it so the next call re-attaches
            self.reset()
            raise EEError(f"EE session lost during {name}: {exc}")

    def reset(self):
        try:
            if self.script:
                self.script.unload()
        except Exception:
            pass
        try:
            if self.session:
                self.session.detach()
        except Exception:
            pass
        self.script = None
        self.session = None
        self._canvas = None
        self._ctx = None

    # ---------- primitives ----------
    def info(self):
        return self._rpc("info")

    # ---------- canvas selection ----------
    @staticmethod
    def _rank(rows):
        """Best candidate first: most shapes, then widest, then earliest."""
        def key(r):
            sh = r.get("shapes") or 0
            w = r.get("width") or 0
            return (-sh, -w, r.get("index", 0))
        return sorted(rows, key=key)

    def canvas_candidates(self):
        """Every page list's active canvas, deduped and ranked best-first."""
        res = self._rpc("canvasCandidates")
        if res.get("error"):
            raise EEError("canvasCandidates: " + str(res["error"]))
        rows = [r for r in res.get("candidates", []) if r.get("canvas")]
        best = {}
        for r in rows:
            cur = best.get(r["canvas"])
            if cur is None or self._rank([r, cur])[0] is r:
                best[r["canvas"]] = r
        ranked = self._rank(list(best.values()))
        return ranked, res

    def canvas(self, explicit=None, refresh=False):
        """Resolve the canvas to draw on.

        Always re-resolved: the active canvas changes whenever the user inserts
        one (or ee_new_canvas does), and a stale pointer silently draws into
        nothing. `explicit` (a handle from ee_list_shapes/ee_canvases) wins.
        """
        if explicit:
            handle = explicit if isinstance(explicit, str) else hex(int(explicit))
            if not handle.startswith("0x"):
                handle = hex(int(handle, 16))
            self._canvas = handle
            self._ctx = None
            return handle

        ranked, _raw = self.canvas_candidates()
        if not ranked:
            self._canvas = None
            self._ctx = None
            raise EEError("no active canvas found in the open document — call "
                          "ee_new_canvas to insert one first")
        win = ranked[0]
        self._canvas = win["canvas"]
        self._ctx = win
        return win["canvas"]

    def canvas_report(self):
        """Ranking plus which candidate wins, for auditing and debugging."""
        ranked, raw = self.canvas_candidates()
        return {
            "chosen": ranked[0]["canvas"] if ranked else None,
            "ranked": ranked,
            "pageLists": raw.get("pageLists"),
        }

    def label_context(self, canvas=None, face=None, italic=None,
                      size_hint=None):
        """Resolve (canvas, pageList, styleSheet, fontSheet) for a new label."""
        ranked, raw = self.canvas_candidates()
        if not ranked:
            raise EEError("no active canvas found; insert one with ee_new_canvas")
        row = None
        if canvas:
            for r in ranked:
                if r["canvas"].lower() == str(canvas).lower():
                    row = r
                    break
            if row is None:
                row = {"canvas": canvas, "styleSheet": None, "pageList": None}
        else:
            row = ranked[0]

        style_sheet = row.get("styleSheet")

        # esPageList::GetStyleSheet() (misleading name) returns the document's
        # esFontSheet -- the exact object a label's +0xd4 must hold, and the
        # same object that doubles as the style sheet (esFontSheet::GetStyleSheet
        # returns `this`).  So take it as the font sheet directly instead of the
        # old heap-scan "first font sheet with a style sheet", which landed on a
        # TEMPLATE sheet and made labels measure/render with the wrong font.
        chosen_fs = None
        reason = None
        if style_sheet and style_sheet != "0x0":
            chosen_fs = style_sheet
            reason = "pageList.GetStyleSheet"
        else:
            # Canvas not reachable through GetActiveCanvas (e.g. the fresh
            # caret canvas after ee_goto_problem insert=true): take the live
            # text UI's owning page list instead.
            cc = self._rpc("caretContext")
            if cc.get("ok") and cc.get("fontSheet") and cc["fontSheet"] != "0x0":
                chosen_fs = cc["fontSheet"]
                style_sheet = chosen_fs
                reason = "caretContext(pageList=" + str(cc.get("pageList")) + ")"
            else:
                chosen_fs = "0x0"
                reason = "none found"

        self._canvas = row["canvas"]
        self._ctx = row

        # Letter style lives in the segment's font slot (+0x6e). Read it off an
        # existing label so new letters match the document (its math slot is
        # typically the italic one). 0 means "no label to copy" -> upright.
        detected = self._rpc("labelFontIndex", row["canvas"])
        font_index = detected.get("fontIndex")
        if detected.get("ok"):
            src = "existing label " + str(detected.get("seg"))
        else:
            # No label anywhere on this canvas: ask the DOCUMENT's font sheet
            # which slot is the wanted face (default: Times New Roman italic
            # 五号, i.e. EE's "AY" annotation style).  Slot numbers are
            # document-local, so this is what makes label drawing portable
            # across documents without touching EE's UI.
            src = "none (default 0)"
            want_face = face or "Times New Roman"
            want_italic = True if italic is None else bool(italic)
            got = self.resolve_font_slot(chosen_fs, want_face,
                                         want_italic, size_hint)
            if got:
                font_index = got.get("slot")
                src = ("font sheet: slot %s = %s italic=%s size=%s"
                       % (got.get("slot"), got.get("name"),
                          got.get("italic"), got.get("size")))
            elif face or italic is not None:
                src = ("font sheet: no match for %r italic=%s"
                       % (want_face, want_italic))
        return {
            "canvas": row["canvas"],
            "pageList": row.get("pageList"),
            "styleSheet": style_sheet,
            "fontSheet": chosen_fs,
            "fontSheetReason": reason,
            "detectedFontIndex": font_index,
            "detectedPadding": detected.get("padding"),
            "fontIndexSource": src,
            "candidates": ranked,
        }

    def resolve_font_slot(self, sheet, face, italic=None, size_hint=None):
        """Find the font-sheet slot whose face matches `face` (see ee_fonts).

        The slot list is document-local; esFont::GetFontName/IsItalic/GetFontSize
        answer it from the live engine.  size_hint (1/100 pt, 1050 = 五号) is a
        preference, not a filter: without an exact size match the lowest
        matching slot wins.
        """
        if not sheet or sheet == "0x0":
            return None
        r = self._rpc("fontList", sheet, 63, 10.5)
        if not r.get("ok"):
            return None
        cands = []
        for f in r.get("fonts", []):
            name = f.get("name") or ""
            if name.lower() != str(face).lower():
                continue
            if italic is not None and bool(f.get("italic")) != bool(italic):
                continue
            cands.append(f)
        if not cands:
            return None
        if size_hint is not None:
            exact = [f for f in cands if f.get("size") == size_hint]
            if exact:
                cands = exact
        return min(cands, key=lambda f: f.get("slot", 0))

    def list_fonts(self, canvas=None, max_slot=63, size_pt=10.5):
        """All fonts in the document's font sheet with their slot numbers."""
        ctx = self.label_context(canvas)
        sheet = ctx["fontSheet"]
        r = self._rpc("fontList", sheet, int(max_slot), float(size_pt))
        out = {"canvas": ctx["canvas"], "sheet": sheet,
               "reason": ctx["fontSheetReason"],
               "stoppedAtRepeat": r.get("stoppedAtRepeat"),
               "fonts": r.get("fonts")}
        if r.get("error"):
            out["error"] = r["error"]
        return out

    def create_path(self, points, types, close):
        return self._rpc("createPath", points, types, 1 if close else 0)

    def add_item(self, shape, canvas=None, flags=1):
        return self._rpc("addItem", canvas or self.canvas(), shape, flags)

    def redraw(self):
        return self._rpc("redrawAll")

    def read_i32(self, addr):
        return self._rpc("readI32", addr)

    def read_ptr(self, addr):
        try:
            return self._rpc("readU32", addr)
        except Exception:
            return None

    # ---------- geometry ----------
    def geometry(self, shape):
        """Recompute and read back a shape's cached geometry.

        Dispatches RecalcLayout through the object's own vtable: esShapeLine's
        +0x64 is esShapeBase::RecalcLayout, so calling the esShapePath export on
        it would read past the end of a 0x5c-byte allocation.
        """
        r = self._rpc("recalcShape", shape)
        base = int(shape, 16)
        vals = {n: self.read_i32(hex(base + o)) for n, o in (
            ("p1x", 0x14), ("p1y", 0x18), ("p2x", 0x1C), ("p2y", 0x20),
            ("left", 0x24), ("top", 0x28), ("right", 0x2C), ("bottom", 0x30),
            ("style", 0x34))}
        vals["_recalc"] = r
        return vals

    def set_shape_pen(self, shape, pen):
        """Set ONE shape's stroke width (embedded esPenInfo at shape+0x58).

        Unit is 1/400 mm: 0.20mm = 80 (engine default), 0.25mm = 100 (project
        convention), bold-dot 0.40mm = 160.  Standalone primitives use this;
        `draw_figure` instead performs one canvas-wide pass via setPenWidth
        (which the bridge now makes skip bold dots so their 160 survives).
        """
        if pen is None or not shape:
            return None
        return self._rpc("writeI32", hex(int(shape, 16) + 0x58), int(pen))

    # ---------- high level ----------
    def _emit(self, pts, types, close, canvas=None, verify=True):
        r = self.create_path(pts, types, close)
        if r.get("error"):
            raise EEError(r["error"])
        shape = r.get("ret")
        if not shape or shape == "0x0":
            raise EEError("CreateFromPathData returned null "
                          "(check point/type array shape)")
        cv = canvas or self.canvas()
        a = self.add_item(shape, cv)
        if a.get("error"):
            raise EEError(a["error"])
        out = {"shape": shape, "canvas": cv}
        if verify:
            out["geometry"] = self.geometry(shape)
        return out

    def line(self, x1, y1, x2, y2, canvas=None, pen=None):
        return self.polygon([(x1, y1), (x2, y2)], closed=False, canvas=canvas,
                            pen=pen)

    def polygon(self, points, closed=True, canvas=None, pen=None):
        """Build a path the way EE's own parser expects.

        Verified against eslib.dll's esShapePath::CreateFromPathData:
          * one 0x01 entry emits one segment;
          * an explicit 0x80 terminator entry is REQUIRED or the factory
            destroys the object and returns null;
          * with close=0 the 0x80 entry flushes the segment list without
            closing it (open polyline/line); with close=1 it also adds the
            closing edge;
          * the points array must be as long as the types array, so the path
            repeats its last vertex (open) or its first vertex (closed).
        """
        v = [(int(x), int(y)) for x, y in points]
        n = len(v)
        if n < 2:
            raise EEError("need at least 2 points")
        pts = v + [v[0] if closed else v[-1]]
        types = [T_START] + [T_LINE] * (n - 1) + [T_CLOSE]
        out = self._emit(pts, types, 1 if closed else 0, canvas)
        if pen is not None:
            self.set_shape_pen(out["shape"], pen)
            out["pen"] = int(pen)
        return out

    def rect(self, x1, y1, x2, y2, canvas=None, pen=None):
        return self.polygon([(x1, y1), (x2, y1), (x2, y2), (x1, y2)], True,
                            canvas, pen=pen)

    def circle(self, cx, cy, r, canvas=None, segments=72, pen=None):
        """Draw a TRUE circle using EE's own esSegCircel primitive.

        Verified against a circle the editor's circle tool drew: the resulting
        segment carries the circle tool id 0x4284, a radius float at +0x68 and
        the centre at +0x70/+0x74. Falls back to a dense closed polygon (using
        only the already-verified path) if the primitive cannot be built.
        """
        import math
        cx, cy, r = int(cx), int(cy), int(r)
        cv = canvas or self.canvas()
        res = self._rpc("makeCircleShape", float(cx), float(cy), float(r),
                        math.pi / 2, CIRCLE_TOOL_ID)
        if res.get("ok") and res.get("shape"):
            a = self.add_item(res["shape"], cv)
            if not a.get("error"):
                out = {"shape": res["shape"], "canvas": cv,
                       "geometry": self.geometry(res["shape"]),
                       "primitive": "esSegCircel (native circle)"}
                if pen is not None:
                    self.set_shape_pen(res["shape"], pen)
                    out["pen"] = int(pen)
                return out

        k = int(round(r * KAPPA))
        ring = [
            (cx + r, cy), (cx + r, cy + k), (cx + k, cy + r), (cx, cy + r),
            (cx - k, cy + r), (cx - r, cy + k), (cx - r, cy),
            (cx - r, cy - k), (cx - k, cy - r), (cx, cy - r),
            (cx + k, cy - r), (cx + r, cy - k), (cx + r, cy),
        ]
        pts = [(cx + r, cy)] + ring
        types = [T_START] + ([T_START, T_START, T_BEZIER] * 4) + [T_CLOSE]
        try:
            out = self._emit(pts, types, 1, cv)
            out["primitive"] = "bezier path"
            if pen is not None:
                self.set_shape_pen(out["shape"], pen)
                out["pen"] = int(pen)
            return out
        except EEError:
            pass
        poly = [(int(round(cx + r * math.cos(2 * math.pi * i / segments))),
                 int(round(cy + r * math.sin(2 * math.pi * i / segments))))
                for i in range(segments)]
        out = self.polygon(poly, closed=True, canvas=cv, pen=pen)
        out["primitive"] = f"closed {segments}-gon (fallback)"
        out["note"] = f"native circle failed: {res.get('error')}"
        return out

    def label(self, text, x, y, canvas=None, font_sheet=None,
              style_sheet=None, variant="full", opts=None,
              font_index=None, padding=None, style_flags=None,
              font_face=None, font_italic=None):
        """Draw a letter/word label using the editor's own label recipe.

        Recipe source: Editer.exe FUN_00426480 (label insert), FUN_004842c0
        (canonical shape sequence construct -> OnCreate(styleSheet) ->
        RecalcLayout -> AddItem) and esSegLable::Draw / esSegLable::Build.

        The decisive step is esEQLine::AppendString on the esEQLine embedded at
        seg+0x80: that line is what esSegLable::Draw actually inks, and neither
        the segment ctor nor Build fills it.  The ctor's `ulong` carries the
        per-part CHARACTER COUNTS (the bridge derives byte0 from the text
        itself) plus a flags byte; the font is chosen solely by the font slot
        (+0x6e, see ee_fonts / font_face).
        """
        ctx = self.label_context(canvas, face=font_face, italic=font_italic)
        cv = ctx["canvas"]
        fs = font_sheet or ctx["fontSheet"]
        ss = style_sheet or ctx["styleSheet"]
        if variant not in LABEL_VARIANTS:
            raise EEError(f"unknown variant {variant!r}; "
                          f"known: {sorted(LABEL_VARIANTS)}")
        options = dict(LABEL_VARIANTS[variant])
        options.update(opts or {})

        # Feature word: editor-like by default, so the engine builds the text.
        if "k" not in options:
            options["k"] = int(DEFAULT_LABEL_FEATURE
                              if style_flags is None else style_flags)
        # Font slot: match the document's own letters unless overridden.
        if font_index is None:
            font_index = ctx.get("detectedFontIndex")
        if font_index is not None:
            options["fontIndex"] = int(font_index)
        if padding is None:
            padding = ctx.get("detectedPadding")
        if padding is not None:
            options["padding"] = int(padding)

        res = self._rpc("makeLabelShape", str(text), int(x), int(y),
                        fs, ss, cv, options)
        out = {
            "canvas": cv,
            "fontSheet": fs,
            "styleSheet": ss,
            "fontSheetReason": ctx["fontSheetReason"],
            "fontIndex": font_index,
            "fontIndexSource": ctx.get("fontIndexSource"),
            "variant": variant,
            "options": options,
            "result": res,
        }
        if res.get("ok"):
            out["shape"] = res.get("shape")
            out["geometry"] = self.geometry(res["shape"])
        return out

    # ---------- batch: one call draws one whole figure ----------
    #
    # FILLING: a shape renders filled only once it OWNS A BRUSH, created by
    # esShapePath::SetSolidBrush(COLORREF).  The scalar fields (+0x10 = 12 fill
    # flag, +0x38 = shade) are NOT sufficient: a figure drawn with them and
    # recalculated twice came out completely unfilled, and GetBrush() stayed 0.
    # Ground truth = a shape the editor's own fill tool produced, where
    # GetBrush() is non-null.
    FILL_LIGHT = 0xCACACA     # the light grey of the shading in the originals
    FILL_DARK = 0xA0A0A0      # the darker grey (e.g. the FKGH region of 题6)

    def draw_figure(self, spec, canvas=None):
        """Draw a complete textbook figure in ONE engine round-trip.

        Every constant here was recovered from the live editor (see
        notes/02-next-steps.md 3.9):
          * pen width is esPenInfo+0x08, in 1/400 mm  ->  0.25mm == 100;
          * a label's font slot is esSegLable+0x6e and its margin +0x6c, also
            1/400 mm -> 1.00mm == 400;
          * FILLING requires esShapePath::SetSolidBrush(COLORREF) -- only then
            does the shape own a brush and render filled.  The scalar fields
            (+0x10 flag, +0x38 shade) are NOT sufficient (two wrong recipes,
            both left GetBrush() == 0 and the figure completely unfilled);
          * a label's text is baked into the embedded esEQLine at creation, so
            the font slot must be right BEFORE makeLabelShape runs.
        """
        cv = canvas or self.canvas()
        pen = int(round(float(spec.get("pen_mm", 0.25)) * 400))
        font_index = spec.get("font_index")
        padding = spec.get("padding")
        out = {"canvas": cv, "penValue": pen, "paths": [], "labels": [],
               "errors": []}

        for i, it in enumerate(spec.get("paths", [])):
            try:
                pts = [(int(round(float(x))), int(round(float(y))))
                       for x, y in it["points"]]
                closed = bool(it.get("close", len(pts) > 2))
                r = self.polygon(pts, closed=closed, canvas=cv)
                rec = {"shape": r["shape"], "closed": closed, "n": len(pts)}
                if it.get("dash"):
                    # A real dashed line: esPenInfo+0x04 is the line style
                    # (0 = solid, 3 = dashed), verified by writing it on the
                    # editor's own dashed sample and watching it turn solid.
                    self._rpc("writeI32", hex(int(r["shape"], 16) + 0x54), 3)
                    rec["dash"] = 3
                if it.get("fill"):
                    # THE fill mechanism: a shape only renders filled once it
                    # owns a brush, and esShapePath::SetSolidBrush(COLORREF)
                    # creates it.  The scalar fields (+0x10 flag, +0x38 shade)
                    # are NOT sufficient -- writing them and recalculating left
                    # GetBrush() == 0 and the figure came out completely
                    # unfilled, twice.  Verified against a shape the user's own
                    # fill tool produced: GetBrush() is non-null only there.
                    want = it.get("fill")
                    color = self.FILL_DARK if want == "dark" else self.FILL_LIGHT
                    br = self._rpc("setSolidBrush", r["shape"], color)
                    rec["fill"] = {"color": "0x%06x" % color,
                                   "brush": br.get("brush"),
                                   "filled": br.get("filled")}
                    if not br.get("ok"):
                        out["errors"].append("fill[%d]: %s" % (i, br))
                out["paths"].append(rec)
            except Exception as exc:
                out["errors"].append("path[%d]: %s" % (i, exc))

        # Circular arcs: NATIVE esSegArc first (exact, ONE object).  The old
        # implementation sampled 128 points into a polyline -- that is exactly
        # the "折线手搓" the user rejected on 2026-10-19.  The native primitive
        # is verified working (ee_draw_arc; the 慈溪 Q7 alpha arc used it), so
        # use it here; only if it fails does this fall back to a dense polyline
        # (a figure must never be silently incomplete).
        for i, it in enumerate(spec.get("arcs", [])):
            try:
                cx, cy = float(it["cx"]), float(it["cy"])
                r = float(it["r"])
                a0, a1 = float(it["a0"]), float(it["a1"])
                try:
                    res = self.arc(cx, cy, r, a0, a1,
                                   major=bool(it.get("major")), canvas=cv,
                                   pen=pen)
                    out["paths"].append({"shape": res["shape"],
                                         "arc": [a0, a1],
                                         "primitive": "esSegArc"})
                except Exception as native_exc:
                    n = int(it.get("steps", 96))
                    pts = []
                    for k in range(n + 1):
                        a = math.radians(a0 + (a1 - a0) * k / n)
                        pts.append((int(round(cx + r * math.cos(a))),
                                    int(round(cy + r * math.sin(a)))))
                    rr = self.polygon(pts, closed=False, canvas=cv)
                    out["paths"].append({"shape": rr["shape"],
                                         "arc": [a0, a1],
                                         "fallback": str(native_exc)})
            except Exception as exc:
                out["errors"].append("arc[%d]: %s" % (i, exc))

        # Sampled curves: NATIVE esSegBezier (ONE smooth object per curve),
        # never a polyline.  A quad entry evaluates y = h*(x-cx)^2 + cy in
        # FIGURE units and maps it with origin (ox, oy) and scale (sx, sy)
        # into canvas units.  The on-curve samples are converted to cubic
        # bezier control points by the bridge (Catmull-Rom), then handed to
        # the engine's own path factory, so the canvas holds a single
        # esSegBezier (type 0x4703) path -- verified 2026-10-19.
        def _emit_bezier(canvas_pts, closed, tag, extra=None):
            """Draw on-curve samples as ONE native esSegBezier path.

            The samples are first fitted with Schneider's algorithm
            (tools/bezier_fit.py) so the object carries only a handful of
            control points -- exactly like EE's own 函数图象 object (the user's
            y=x^2 sample has 7 control points = 2 cubic segments).  A densely
            Catmull-Rom'd chain renders fine but its hundreds of knots read as
            "折线" to the user (2026-10-19 feedback), so fitting is the default.
            """
            pts_f = [(float(x), float(y)) for x, y in canvas_pts]
            bez = None
            try:
                from bezier_fit import fit_bezier
                ctrl = fit_bezier(pts_f, tol=1.2)
                bez = self._rpc("drawBezierControlCurves", cv,
                                [{"ctrl": [[int(round(x)), int(round(y))]
                                           for x, y in ctrl],
                                  "closed": bool(closed)}])
                if bez.get("ok"):
                    extra = dict(extra or {})
                    extra["segments"] = (len(ctrl) - 1) // 3
            except Exception:
                bez = None
            if not (bez and bez.get("ok")):
                pts_i = [[int(round(x)), int(round(y))] for x, y in pts_f]
                bez = self._rpc("drawBezierCurves", cv,
                                [{"points": pts_i, "closed": bool(closed)}])
            rec = {"curve": tag, "primitive": "esSegBezier",
                   "samples": len(pts_f)}
            if extra:
                rec.update(extra)
            if bez.get("ok") and bez.get("shapes"):
                for sh in bez["shapes"]:
                    r2 = dict(rec)
                    r2["shape"] = sh.get("shape")
                    out["paths"].append(r2)
            else:
                rr = self.polygon([(int(round(x)), int(round(y)))
                                   for x, y in pts_f], closed=False,
                                  canvas=cv)
                rec["shape"] = rr["shape"]
                rec["fallback"] = bez.get("error") or "bezier failed"
                out["paths"].append(rec)

        for i, it in enumerate(spec.get("curves", [])):
            try:
                sx, sy = float(it["sx"]), float(it["sy"])
                ox, oy = float(it["ox"]), float(it["oy"])
                cx = float(it.get("cx", 0.0))
                cy = float(it.get("cy", 0.0))
                h = float(it.get("h", 1.0))
                x0, x1 = float(it["x0"]), float(it["x1"])
                n = int(it.get("steps", 60))
                pts = []
                for k in range(n + 1):
                    x = x0 + (x1 - x0) * k / n
                    y = h * (x - cx) ** 2 + cy
                    pts.append((ox + x * sx, oy - y * sy))
                _emit_bezier(pts, False, "quad", {"points": len(pts)})
            except Exception as exc:
                out["errors"].append("curve[%d]: %s" % (i, exc))

        # Explicit native bezier polylines in CANVAS coordinates: the points
        # are on-curve samples; the bridge fits cubic control points.
        for i, it in enumerate(spec.get("beziers", [])):
            try:
                pts = it["points"]
                if len(pts) >= 2:
                    _emit_bezier(pts, it.get("closed", False), "bezier")
            except Exception as exc:
                out["errors"].append("bezier[%d]: %s" % (i, exc))

        labels = spec.get("labels") or []
        if labels:
            ctx = self.label_context(cv, face=spec.get("font_face"),
                                     italic=spec.get("font_italic"))
            for i, it in enumerate(labels):
                try:
                    fs = it.get("font_sheet") or ctx["fontSheet"]
                    ss = it.get("style_sheet") or ctx["styleSheet"]
                    # 'full', i.e. WITH esSegLable::Initialize.  Initialize is
                    # what actually inks the text into the embedded esEQLine --
                    # skipping it (the 'no-initialize' variant) produced a label
                    # with a single EMPTY item, so the letter silently vanished.
                    # Initialize appends twice, so the item count is pinned to 1
                    # right after creation (see below); that combination gives
                    # one correct glyph and no trailing garbage.
                    options = dict(LABEL_VARIANTS[it.get("variant", "full")])
                    fi = it.get("font_index", font_index)
                    if fi is None:
                        fi = ctx.get("detectedFontIndex")
                    if fi is not None:
                        options["fontIndex"] = int(fi)
                    # The ctor's ulong is NOT a feature word: its bytes are the
                    # per-part CHARACTER COUNTS (byte0 = main text, byte1/2 =
                    # 标注点/边框 suffixes) plus a flags byte (byte3, 0x80 =
                    # math mode).  The bridge overwrites byte0 with the real
                    # text length; callers only supply the flags template.
                    # The label font lives exclusively in the font slot
                    # (+0x6e) -- putting the slot into the k word lands in the
                    # +0x72 suffix count and makes RecalcLayoutLable append
                    # garbage glyphs.
                    if "k" in it:
                        options["k"] = int(it["k"])
                    else:
                        options["k"] = int(DEFAULT_LABEL_FEATURE)
                    pad = it.get("padding", padding)
                    if pad is None:
                        pad = ctx.get("detectedPadding")
                    if pad is not None:
                        options["padding"] = int(pad)
                    # Three-part label text: 主体 / 上标 / 下标.  This is the
                    # editor's own label model (文字标注 dialog: "标注内容:
                    # 主体 上标 下标 分数形式"); esSegLable::RecalcLayoutLable
                    # builds the superscript/subscript boxes from parts 2/3.
                    # The plain AppendString path cannot express them.
                    txt = str(it["text"])
                    sup = str(it.get("sup") or "")
                    sub = str(it.get("sub") or "")
                    if sup or sub:
                        options["parts"] = [txt, sup, sub]
                    r = self._rpc("makeLabelShape", txt,
                                  int(it["x"]), int(it["y"]), fs, ss, cv, options)
                    out["labels"].append({"text": txt + (("^" + sup) if sup else "")
                                          + (("_" + sub) if sub else ""),
                                          "shape": r.get("shape"),
                                          "ok": bool(r.get("ok"))})
                    # Post-create fixes on the embedded esEQLine, both read off
                    # labels the ENGINE itself made (the paper's inline labels):
                    #   +0x30 item count -> 1, because the engine's own text
                    #         population leaves a second item that inks as a run
                    #         of garbage glyphs (and takes part in layout, so the
                    #         letter also sits off-centre);
                    #   +0x04 high word -> 0xFFFF, i.e. "do not override, use the
                    #         segment's own font".  Ours came out 0x00000000, which
                    #         reads as format index 0; the first paint survives it
                    #         but any re-layout (dragging the letter) re-resolves
                    #         the font from it and spews garbage.
                    seg = r.get("seg")
                    if seg:
                        h = int(seg, 16)
                        # Post-create fix on the embedded esEQLine, read off
                        # labels the ENGINE itself made (the paper's inline
                        # labels): +0x04 high word -> 0xFFFF, i.e. "do not
                        # override, use the segment's own font".  Ours came
                        # out 0x00000000, which reads as format index 0; the
                        # first paint survives it but any re-layout re-resolves
                        # the font from it and spews garbage.
                        #
                        # (Do NOT touch +0xB0 anymore: EQLine+0x30 is the
                        # per-character item count and esText draws exactly
                        # that many items -- forcing it to 1 truncated every
                        # multi-character label to its first glyph.  It was a
                        # workaround for the old k-word encoding, which made
                        # the engine append a garbage suffix run; the bridge
                        # now derives the real char count from the text.)
                        cur = self._rpc("readU32", hex(h + 0x84)) or 0
                        if (cur >> 16) != 0xFFFF:
                            self._rpc("writeI32", hex(h + 0x84),
                                      0xFFFF0000 | (cur & 0xFFFF))
                        # Editer.exe settles a fresh label with HandMoveText
                        # right after building it (FUN_00426900), but the POINT
                        # it passes matters: (0,0) immediately inks garbage, so
                        # this stays OFF unless the caller asks for it, and then
                        # it uses the label's own canvas position.
                        if spec.get("hand_move"):
                            hm = self._rpc("handMoveText", seg,
                                           int(it.get("x", 0)),
                                           int(it.get("y", 0)), 1)
                            hm2 = self._rpc("handMoveText", seg,
                                            int(it.get("x", 0)),
                                            int(it.get("y", 0)), 0)
                            if not spec.get("quiet"):
                                out["handmove"] = [hm, hm2]
                    if not r.get("ok"):
                        out["errors"].append("label[%d]: %r" % (i, r))
                except Exception as exc:
                    out["errors"].append("label[%d]: %s" % (i, exc))

        if spec.get("apply_pen", True):
            penres = self._rpc("setPenWidth", cv, pen)
            out["pen"] = ({"ok": penres.get("ok"), "value": pen,
                           "shapes": len(penres.get("items") or [])}
                          if spec.get("quiet") else penres)

        # Bold dots (加粗点).  Built by the ENGINE'S OWN constructor
        # esShapeLine::esShapeLine(const tagPOINT&, ushort 0x6001, ulong), which
        # creates the esSegPoint segment, sets the style word to 0x04000005 and
        # lays the shape out around the point.  Hand-building an esShapePath (or
        # even an esShapeLine + manual esSegPoint) renders a thick STROKE -- i.e.
        # a short line, not a dot -- and/or leaves a structure RecalcLayout
        # cannot lay out.  Created AFTER the pen pass so the global 0.25 mm width
        # does not overwrite their 0.40 mm (160) pen.
        dot_specs = spec.get("dots") or []
        if dot_specs:
            dctx = self.label_context(cv, face=spec.get("font_face"),
                                      italic=spec.get("font_italic"))
            for i, d in enumerate(dot_specs):
                try:
                    x, y = int(d[0]), int(d[1])
                    size = int(d[2]) if len(d) > 2 else 320
                    res = self._rpc("makeDotShape", x, y, cv,
                                    dctx["styleSheet"],
                                    {"size": size, "pen": 160})
                    if res.get("ok"):
                        out["paths"].append({"shape": res["shape"],
                                             "seg": res.get("seg"),
                                             "dot": size,
                                             "style": res.get("style")})
                    else:
                        out["errors"].append("dot[%d]: %s"
                                             % (i, res.get("error")))
                except Exception as exc:
                    out["errors"].append("dot[%d]: %s" % (i, exc))

        o = {}
        if font_index is not None:
            o["fontIndex"] = int(font_index)
        if padding is not None:
            o["margin"] = int(padding)
        if spec.get("math") is not None:
            o["math"] = int(spec["math"])
        if o and spec.get("apply_lable_style", True):
            # rebuild MUST stay off here.  The labels were created with the
            # right font slot already, and esSegLable::Build re-appends to the
            # embedded esEQLine -- which is what duplicated its item list
            # (count 2 instead of 1) and inked a run of garbage glyphs.
            o["rebuild"] = False
            lsres = self._rpc("setLableStyle", cv, o)
            out["lablestyle"] = ({"ok": lsres.get("ok"), "applied": o,
                                  "labels": lsres.get("labels")}
                                 if spec.get("quiet") else lsres)
        return out

    def arc(self, cx, cy, r, start_deg, end_deg, major=False, canvas=None,
            pen=None):
        """Draw a TRUE arc using EE's own esSegArc primitive.

        Verified against eslib's ctor (RVA 0x128290):
        `(PointF centre, float radius, float startAngle, float endAngle,
          Matrix*, int flags)` storing radius at +0x68, start at +0x70, end at
        +0x74, type word 0x4306, object size 0x98. Same esSegList + esShapePath
        wrapper as the circle primitive.

        Two non-obvious details, all three confirmed against the live engine by
        reading back the arc's control points:
          * the angles are RADIANS -- the ctor runs them through
            epNormalAngle360P(x), which is just `x mod 2*pi` (feeding 45
            degrees un-converted stores 45 mod 2*pi = 1.017703);
          * the engine's 0 degree direction points UP the page, i.e.
            engine_angle = page_angle + 90, where page angles are the usual
            atan2(dy, dx) with y growing downward;
          * it sweeps NEGATIVELY from the first angle to the second, so the
            upper bound of the interval must be passed first.
        """
        import math
        cv = canvas or self.canvas()
        sweep = (float(end_deg) - float(start_deg) + 180.0) % 360.0 - 180.0
        if major:
            sweep += -360.0 if sweep > 0 else 360.0
        lo = min(float(start_deg), float(start_deg) + sweep)
        hi = max(float(start_deg), float(start_deg) + sweep)
        res = self._rpc("makeArcShape", float(int(cx)), float(int(cy)),
                        float(int(r)),
                        math.radians(hi + 90.0), math.radians(lo + 90.0), None)
        if not res.get("ok"):
            raise EEError("makeArcShape: " + str(res.get("error")))
        a = self.add_item(res["shape"], cv)
        if a.get("error"):
            raise EEError(a["error"])
        if pen is not None:
            self.set_shape_pen(res["shape"], pen)
        return {"shape": res["shape"], "canvas": cv, "seg": res.get("seg"),
                "geometry": self.geometry(res["shape"]),
                "arc_deg": [lo, hi], "sweep_deg": abs(sweep),
                "pen": pen,
                "primitive": "esSegArc (native arc)"}

    def angle_mark(self, vertex, point_a, point_b, kind="right", size=None,
                   canvas=None, pen=None):
        """Mark the angle at `vertex` between the rays to `point_a`/`point_b`.

        kind="right"  the EE-native right-angle marker (esSegHVLine, 3 points)
        kind="arc"    the EE-native angle marker (esSegArc type 0x4307)
        kind="double" two concentric native angle markers

        These are the engine's own annotation objects: dragging their handles
        changes the radius, but the segment type keeps the marker's shape and
        re-fits the sweep to the two rays.
        `size` is the mark's arm length (right) or radius (arcs), in page units.
        """
        import math
        vx, vy = int(vertex[0]), int(vertex[1])
        ax, ay = int(point_a[0]), int(point_a[1])
        bx, by = int(point_b[0]), int(point_b[1])
        ux, uy = ax - vx, ay - vy
        wx, wy = bx - vx, by - vy
        lu, lw = math.hypot(ux, uy), math.hypot(wx, wy)
        if lu == 0 or lw == 0:
            raise EEError("vertex must differ from both ray points")
        ux, uy = ux / lu, uy / lu
        wx, wy = wx / lw, wy / lw
        cv = canvas or self.canvas()
        p = int(pen if pen is not None else 100)

        def _add(res):
            if not res.get("ok"):
                raise EEError(f"native marker: {res.get('error')}")
            a = self.add_item(res["shape"], cv)
            if a.get("error"):
                raise EEError("native marker addItem: " + str(a["error"]))
            self.set_shape_pen(res["shape"], p)
            return res

        if kind == "right":
            s = int(size or 800)
            # Native slanted right-angle marker: local 3 points + a Gdiplus
            # matrix that rotates the local frame onto the two rays.  Keeping
            # the points axis-aligned in the LOCAL frame is what makes the HV
            # constraint hold when the marker is dragged.
            # Local 3 points are the INSET square corners: s along each ray,
            # not starting at the vertex (starting at the vertex makes one arm
            # overlap the angle's own side and the mark looks like a single line).
            res = self._rpc("makeHVLineMatrixShape",
                            [[s, 0], [s, -s], [0, -s]],
                            ux, uy, -wx, -wy, vx, vy)
            _add(res)
            return {"shape": res["shape"], "seg": res.get("seg"),
                    "canvas": cv, "mark": "EE-native slanted right-angle marker",
                    "primitive": "esSegHVLine + Gdiplus matrix", "arm": s,
                    "pen": p}

        # Orient the sweep to the interior (minor) angle between the two rays.
        a1 = math.degrees(math.atan2(uy, ux))
        a2 = math.degrees(math.atan2(wy, wx))
        sweep = (a2 - a1) % 360.0
        if sweep > 180.0:
            sweep -= 360.0
        lo = min(a1, a1 + sweep)
        hi = max(a1, a1 + sweep)

        def native_arc(radius):
            res = self._rpc(
                "makeNativeAngleShape", float(vx), float(vy), float(radius),
                math.radians(lo), math.radians(hi))
            _add(res)
            return {"shape": res["shape"], "seg": res.get("seg"),
                    "radius": radius}

        if kind == "arc":
            r = int(size or 1600)
            out = native_arc(r)
            out.update({"canvas": cv, "mark": "EE-native angle marker",
                        "primitive": "esSegArc type 0x4307",
                        "start_deg": a1, "sweep_deg": sweep, "pen": p})
            return out

        if kind == "double":
            r = int(size or 1600)
            gap = max(200, int(r * 0.35))
            first = native_arc(r)
            second = native_arc(r + gap)
            return {"mark": "double native angle marker", "radius": r,
                    "gap": gap, "start_deg": a1, "sweep_deg": sweep,
                    "shapes": [first, second], "pen": p}

        raise EEError(f"unknown angle mark kind {kind!r}; "
                      f"use right, arc or double")

    def draw_axis(self, rect, origin, visible_x=1, visible_y=1,
                  canvas=None, pen=None):
        """Draw the editor's own native coordinate axis (esShapeCap + esSegAxis).

        `rect` = [x1,y1,x2,y2] content rectangle in page units.
        `origin` = [ox,oy] page position of the mathematical origin.
        The engine builds ranges, ticks and labels from esAxisObj via
        esSegAxis::Initialize; both the content rect and the origin are needed.
        Returns the created shape/segment handles and the computed range.
        """
        cv = canvas or self.canvas()
        ctx = self.label_context(cv)
        fs = ctx["fontSheet"]
        r = [int(v) for v in rect]
        o = [int(v) for v in origin]
        if len(r) != 4:
            raise EEError("rect must be [x1,y1,x2,y2]")
        if len(o) != 2:
            raise EEError("origin must be [ox,oy]")
        res = self._rpc("makeNativeAxisShape", r, o,
                        int(visible_x), int(visible_y), fs)
        if not res.get("ok"):
            raise EEError("makeNativeAxisShape: " + str(res.get("error")))
        a = self.add_item(res["shape"], cv)
        if a.get("error"):
            raise EEError("axis addItem: " + str(a["error"]))
        rec = self._rpc("recalcShape", res["shape"])
        # User's preferred axis style (2026-10-19): x/y labels on, tick numbers
        # off, origin O label on, arrow style 4 / thinner.  Must run after the
        # first recalc, because it adds the x/y label boxes and zeroes tick data.
        sty = self._rpc("styleAxisShape", res["shape"], fs)
        if not sty.get("ok"):
            raise EEError("axis styleAxisShape: " + str(sty.get("error")))
        if pen is not None:
            self.set_shape_pen(res["shape"], int(pen))
        rng = self._rpc("readInts", res["seg"],
                        [0x14, 0x18, 0x1c, 0x20])
        return {"shape": res["shape"], "seg": res.get("seg"),
                "axisObj": res.get("axisObj"), "canvas": cv,
                "rect": r, "origin": o, "range": rng.get("values"),
                "pen": pen,
                "primitive": "esShapeCap(0x320B) + esSegAxis(0x5006)",
                "recalc": rec}

    def draw_function(self, expr, x_range, origin, scale, canvas=None,
                      y_range=None, samples=260, pen=None, dash=False,
                      expr_y=None):
        """Plot y = f(x) as a NATIVE smooth curve (esSegBezier 0x4703).

        This is the "函数图象" capability the user asked for (2026-10-19): give
        it a formula and a coordinate mapping and the canvas receives ONE
        native bezier path per continuous branch -- no hand-sampled polylines.

        The engine's own 函数图象 tool also ends up as an esShapePath whose
        segment is an esSegBezier (verified on a user-made sample), so this is
        the same object kind, only the expression evaluation happens here.

        Parameters
        ----------
        expr    : formula string in `x`, Python syntax. Allowed names:
                  sin, cos, tan, asin, acos, atan, sinh, cosh, tanh, sqrt,
                  abs, log, exp, floor, ceil, pi, e.  e.g. "36/x", "x**2-2*x",
                  "2*sin(x)", "1/(x-1)".
        x_range : [x0, x1] in MODEL units.
        origin  : [ox, oy] canvas position of the model origin (0,0).
        scale   : canvas units per model unit (same for x and y; y is up).
        y_range : optional [y0, y1] model clip -- values outside are treated as
                  asymptote breaks (so 1/x does not shoot to infinity).
        samples : on-curve sample count per branch (default 260; the bridge
                  turns them into cubic bezier control points).
        expr_y  : optional; if given, expr is x(y) and the curve is drawn from
                  y_range instead (useful for x = 1/y style graphs).
        """
        cv = canvas or self.canvas()
        import ast
        import math as _m

        ns = {
            "sin": _m.sin, "cos": _m.cos, "tan": _m.tan,
            "asin": _m.asin, "acos": _m.acos, "atan": _m.atan,
            "sinh": _m.sinh, "cosh": _m.cosh, "tanh": _m.tanh,
            "sqrt": _m.sqrt, "abs": abs, "log": _m.log, "exp": _m.exp,
            "floor": _m.floor, "ceil": _m.ceil,
            "pi": _m.pi, "e": _m.e,
        }

        def _check(node):
            for sub in ast.walk(node):
                if isinstance(sub, ast.Name) and sub.id not in ns and sub.id != "x":
                    raise EEError("draw_function: unknown name %r" % sub.id)
                if isinstance(sub, (ast.Import, ast.ImportFrom, ast.Lambda)):
                    raise EEError("draw_function: unsupported syntax")
            return node

        def math_is_bad(v):
            return v != v or v in (float("inf"), float("-inf"))

        # A Call is allowed only for the whitelisted function names.
        tree = _check(ast.parse(expr, mode="eval"))

        def f(xv):
            local = dict(ns)
            local["x"] = xv
            return float(eval(compile(tree, "<expr>", "eval"), {"__builtins__": {}},
                              local))

        yy = None
        if expr_y:
            yy = _check(ast.parse(expr_y, mode="eval"))

        ox, oy = float(origin[0]), float(origin[1])
        sc = float(scale)
        x0, x1 = float(x_range[0]), float(x_range[1])
        if x1 == x0:
            raise EEError("x_range must be non-degenerate")
        if yy is not None:
            if not y_range:
                raise EEError("expr_y needs y_range")
            y0, y1 = float(y_range[0]), float(y_range[1])
        else:
            y0 = float(y_range[0]) if y_range else None
            y1 = float(y_range[1]) if y_range else None

        # --- ADAPTIVE canvas-space sampling -----------------------------------
        # Uniform-x sampling looks like a polyline exactly where it matters:
        # on a hyperbola the steep end has huge dy for one x step, so the
        # chords are long and the "smooth" bezier inherits visible corners
        # (user feed-back 2026-10-19: "反比例函数还是折线").  Instead step in
        # parameter space by a FIXED CANVAS-SPACE distance (12 units ~ 0.03 mm),
        # so every chord is short no matter how steep the curve is.
        target_px = 12.0
        max_pts = max(64, int(samples))
        span = (y1 - y0) if yy is not None else (x1 - x0)

        def eval_t(t):
            if yy is not None:
                local = dict(ns)
                local["y"] = t
                try:
                    xv = float(eval(compile(yy, "<expr_y>", "eval"),
                                    {"__builtins__": {}}, local))
                except Exception:
                    return None
                return (xv, t)
            try:
                return (t, f(t))
            except Exception:
                return None

        def valid(pt):
            if pt is None:
                return False
            px, py = pt
            if math_is_bad(px) or math_is_bad(py):
                return False
            if yy is not None:
                if y0 is not None and y1 is not None:
                    if py < min(y0, y1) or py > max(y0, y1):
                        return False
                if px < min(x0, x1) or px > max(x0, x1):
                    return False
            else:
                if y0 is not None and y1 is not None:
                    if py < min(y0, y1) or py > max(y0, y1):
                        return False
            return True

        def canvas_grad(t, pt):
            """|d(canvas point)/dt| in page units per model unit."""
            h = abs(span) * 1e-6 if span else 1e-6
            q = eval_t(t + h)
            if q is None:
                return 0.0
            return ((q[0] - pt[0]) ** 2 + (q[1] - pt[1]) ** 2) ** 0.5 * sc / h

        branches = []
        cur = []
        prev = None
        t = x0 if yy is None else y0
        t_end = x1 if yy is None else y1
        dirn = 1.0 if t_end >= t else -1.0
        guard = 0
        while (t - t_end) * dirn < 0 and guard < max_pts * 40 and len(cur) < max_pts:
            guard += 1
            pt = eval_t(t)
            step = None
            if valid(pt):
                g = canvas_grad(t, pt)
                if g > 1e-9:
                    step = target_px / g
                else:
                    step = abs(span)
                # jump guard: a pole shows up as a huge canvas jump
                if prev is not None:
                    jd = ((pt[0] - prev[0]) ** 2 + (pt[1] - prev[1]) ** 2) ** 0.5 * sc
                    if jd > target_px * 12:
                        step = None
            if step is None:
                if len(cur) >= 2:
                    branches.append(cur)
                cur = []
                prev = None
                # advance a little and retry (skip the singular point)
                t += dirn * abs(span) * 1e-3
                continue
            cur.append(pt)
            prev = pt
            step = min(step, abs(t_end - t))
            step = max(step, abs(span) * 1e-9)
            t += dirn * step
        if len(cur) >= 2:
            branches.append(cur)

        out = {"canvas": cv, "expr": expr, "branches": [], "errors": []}
        pen_v = int(round(float(pen if pen is not None else 100)))
        for bi, br in enumerate(branches):
            cpts = [(ox + px * sc, oy - py * sc) for px, py in br]
            ctrl = None
            try:
                from bezier_fit import fit_bezier
                ctrl = fit_bezier(cpts, tol=1.2)
            except Exception:
                ctrl = None
            if ctrl is not None:
                bez = self._rpc("drawBezierControlCurves", cv,
                                [{"ctrl": [[int(round(x)), int(round(y))]
                                           for x, y in ctrl], "closed": False}])
                segs = (len(ctrl) - 1) // 3
            else:
                bez = self._rpc("drawBezierCurves", cv,
                                [{"points": [[int(round(x)), int(round(y))]
                                             for x, y in cpts], "closed": False}])
                segs = None
            if not bez.get("ok") or not bez.get("shapes"):
                out["errors"].append("branch[%d]: %s" % (bi, bez.get("error")))
                continue
            shp = bez["shapes"][0]["shape"]
            rec = {"shape": shp, "points": len(br),
                   "primitive": "esSegBezier",
                   "x_range": [br[0][0], br[-1][0]]}
            if segs is not None:
                rec["segments"] = segs
            out["branches"].append(rec)
            if dash:
                self._rpc("writeI32", hex(int(shp, 16) + 0x54), 3)
                rec["dash"] = 3
        if branches:
            pr = self._rpc("setPenWidth", cv, pen_v)
            out["pen"] = {"ok": pr.get("ok"), "value": pen_v}
        out["curveCount"] = len(out["branches"])
        return out

    def new_canvas(self, w=None, h=None):
        """Insert a canvas at the text caret through the engine's own embed
        routine: esTextUI::InsertCanvas(canvas, -1).

        Reverse-engineered 2026-10 from the editor's paste command
        (esTextUI::PastData): build the canvas with the engine's (w,h)
        constructor, embed it at the caret with flags=-1, then
        SetSelObj(NULL,3) + SetFocus. No keyboard simulation is involved.
        The canvas defaults to 61340 x 30670 (the size a Space+G canvas used
        to get). The caret must be bound to the document body in EduEditer
        (esTextUI::IsValid() == 1); on refusal, click into the page text and
        retry. Returns {"ok": true, "canvas": ...} or an error object.
        """
        self._ctx = None
        return self._rpc("insertCanvasNative", None, w, h, {})

    def goto_problem(self, qid, insert=False):
        """Put the text caret onto question `qid` (选择5 / 填空6 / 解答3 …) or a
        literal text anchor, walking the document automatically.  With
        insert=True also insert a canvas at the caret and report it."""
        anchor = PROBLEM_ANCHORS.get(str(qid), str(qid))
        res = self._rpc("gotoText", anchor)
        self._ctx = None
        out = {"anchor": anchor, "goto": res}
        if insert and res.get("ok"):
            nc = self._rpc("insertCanvasNative", res.get("ui"), None, None, {})
            out["canvas"] = nc
        return out

    def goto_text(self, anchor):
        return self._rpc("gotoText", str(anchor))

    def caret_canvas(self):
        return self._rpc("caretCanvas")

    def delete_shape(self, shape, canvas=None, confirm_dangerous=False):
        """Unlink a shape from the active canvas.

        DISABLED by default on purpose: unlinkShape leaves the neighbouring
        links broken, which bricks the canvas (objects stop responding; some
        cases garble). The project rule is: never delete — redraw the whole
        canvas. Kept only behind confirm_dangerous=True for throwaway-canvas
        experiments.
        """
        if not confirm_dangerous:
            raise EEError(
                "ee_delete_shape is disabled: deleting shapes has bricked "
                "canvases in this project (unlinkShape leaves dangling links). "
                "Redraw the whole canvas instead. Pass confirm_dangerous=true "
                "only for a deliberate throwaway-canvas experiment."
            )
        cv = canvas or self.canvas()
        res = self._rpc("unlinkShape", cv, shape)
        if res.get("error"):
            raise EEError(res["error"])
        return {"deleted": shape, "canvas": cv, "links": res}

    def canvas_bounds(self, canvas=None):
        """Page extent of the active canvas, so callers can stay inside it."""
        cv = canvas or self.canvas()
        w = self._rpc("call", GET_WIDTH, "int", [], cv, [], "thiscall").get("ret")
        h = self._rpc("call", GET_HEIGHT, "int", [], cv, [], "thiscall").get("ret")
        out = {"canvas": cv, "width": w, "height": h}
        r = self._rpc("call", GET_FRAME_RECT, "pointer", [], cv, [], "thiscall")
        p = r.get("ret")
        if p and p != "0x0":
            base = int(p, 16)
            out["frame_rect"] = [self.read_i32(hex(base + i * 4))
                                 for i in range(4)]
        return out

    def list_shapes(self, limit=200, canvas=None):
        """Walk the canvas list. Only objects whose vtable is a known eslib
        class are treated as esShapePath; anything else (the editor can host
        app-level classes from Editer.exe) is reported but NOT probed, since
        calling shape methods on a foreign object would corrupt state."""
        cv = int(canvas or self.canvas(), 16)
        info = self.info()
        eslib_base = int(info["eslibBase"], 16)
        eslib_end = eslib_base + int(info["eslibSize"])
        head = self.read_ptr(hex(cv + CANVAS_HEAD))
        shapes = []
        seen = set()
        while head and head not in seen and len(shapes) < limit:
            seen.add(head)
            addr = hex(head)
            vt = self.read_ptr(addr)
            entry = {"shape": addr, "vtable": hex(vt) if vt else None}
            if vt:
                entry["class"] = self._rpc("vtNameOf", hex(vt))
            if vt and eslib_base <= vt < eslib_end:
                entry["geometry"] = self.geometry(addr)
            else:
                entry["note"] = ("object class is not in eslib; not probed")
                entry["head"] = self._rpc("hexdump", addr, 48)
            shapes.append(entry)
            nxt = self.read_ptr(hex(head + SHAPE_NEXT))
            head = nxt if nxt and nxt > 0x10000 else None
        return shapes

    def audit_canvas(self, canvas=None, expected_pen=100, limit=200):
        """Read-only self-check of a canvas we drew: the mechanical half of the
        project's verification gates.

        Checks per shape:
          * stroke width shape+0x58 == expected_pen (default 100 = 0.25mm),
            except bold dots (seg type 0x6001) which must keep 160 (0.40mm);
          * labels (seg type 0x600D): character count +0x70 > 0, EQLine format
            word +0x84 == 0xffff0003, shape box width in a sane range
            (400..12000; a garbled label blows up to ~17000+);
          * esShapePath shapes: report SetSolidBrush ownership via GetBrush()
            (non-null = really filled).
        It cannot judge whether the geometry is *correct* -- that is what
        tools/check_spec.py (constraint residuals) is for.
        """
        cv = canvas or self.canvas()
        shapes = self.list_shapes(limit=limit, canvas=cv)
        rows, failures = [], []
        for s in shapes:
            addr = s.get("shape")
            if not addr:
                continue
            base = int(addr, 16)
            pen = self.read_i32(hex(base + 0x58))
            pen = None if pen is None else pen & 0xffffffff
            seg = self.read_ptr(hex(base + 0x40))
            seg_type = None
            if seg:
                v = self.read_i32(hex(seg + 0x04))
                seg_type = None if v is None else v & 0xffff
            row = {"shape": addr, "class": s.get("class"),
                   "pen": pen, "segType": (None if seg_type is None
                                           else hex(seg_type))}
            geo = s.get("geometry") or {}
            width = None
            height = None
            if geo.get("right") is not None and geo.get("left") is not None:
                width = int(geo["right"]) - int(geo["left"])
                height = int(geo["bottom"]) - int(geo["top"])
                row["box"] = [width, height]

            if seg_type == 0x6001:                      # bold dot
                row["kind"] = "dot"
                if pen != 160:
                    failures.append({"shape": addr, "kind": "dot",
                                     "reason": "dot pen %r != 160" % (pen,)})
            elif seg_type == 0x600D:                    # label
                row["kind"] = "label"
                fmt = self.read_i32(hex(seg + 0x84))
                chars = self.read_i32(hex(seg + 0x70))
                fmt = None if fmt is None else fmt & 0xffffffff
                chars = None if chars is None else chars & 0xff
                row["formatWord"] = None if fmt is None else hex(fmt)
                row["charCount"] = chars
                if fmt != 0xffff0003:
                    failures.append({"shape": addr, "kind": "label",
                                     "reason": "formatWord %r != 0xffff0003"
                                               % (row["formatWord"],)})
                if not chars:
                    failures.append({"shape": addr, "kind": "label",
                                     "reason": "charCount == 0"})
                if width is not None and (width < 400 or width > 12000):
                    failures.append({"shape": addr, "kind": "label",
                                     "reason": "label box width %d out of "
                                               "400..12000" % width})
                if pen not in (None, expected_pen):
                    failures.append({"shape": addr, "kind": "label",
                                     "reason": "label pen %r != %d"
                                               % (pen, expected_pen)})
            else:
                row["kind"] = "shape"
                if pen is not None and pen != expected_pen:
                    failures.append({"shape": addr, "kind": "shape",
                                     "reason": "pen %r != %d"
                                               % (pen, expected_pen)})
            if "esShapePath" in (s.get("class") or ""):
                b = self._rpc("getBrush", addr)
                row["brush"] = b.get("brush")
                row["filled"] = bool(b.get("filled"))
            rows.append(row)
        return {"canvas": cv, "count": len(rows), "expectedPen": expected_pen,
                "pass": not failures, "failures": failures, "shapes": rows}

    # ---------- diagnostics ----------
    def diag(self, op, args):
        args = args or {}
        if op == "canvases":
            return self.canvas_report()
        if op == "fontsheets":
            return self._rpc("fontSheets")
        if op == "hexdump":
            return self._rpc("hexdump", args["addr"], int(args.get("len", 64)))
        if op == "readu32":
            return {"addr": args["addr"], "value": self._rpc("readU32", args["addr"])}
        if op == "readstr":
            return self._rpc("readStr", args["addr"], bool(args.get("wide")))
        if op == "vtname":
            return {"addr": args["addr"],
                    "name": self._rpc("vtNameOf", args["addr"])}
        if op == "vtslots":
            return self._vt_slots(args["addr"], int(args.get("count", 32)))
        if op == "zwstr":
            return self._rpc("zwstrProbe", str(args.get("text", "A")))
        if op == "scantext":
            return self._rpc("scanForText", args["addr"], int(args.get("len", 256)),
                             str(args["text"]))
        if op == "shapecount":
            return self._rpc("shapeCount", args["canvas"],
                             int(args.get("limit", 4000)))
        if op == "recalc":
            return self._rpc("recalcShape", args["shape"])
        if op == "names":
            return self._rpc("names", str(args.get("pattern", "")),
                             int(args.get("limit", 200)))
        if op == "expaddr":
            return {"name": args["name"],
                    "addr": self._rpc("expaddr", args["name"])}
        if op == "call":
            # Invoke an export with an explicit `this` and argument list.
            return self._rpc("call", args["name"], args.get("ret", "pointer"),
                             args.get("argTypes", []), args.get("selfPtr"),
                             args.get("args", []), args.get("abi", "thiscall"))
        if op == "callvirt":
            return self._rpc("callVirt", args["obj"], int(args["slot"], 0)
                             if isinstance(args["slot"], str) else int(args["slot"]),
                             args.get("ret", "pointer"),
                             args.get("argTypes", []), args.get("args", []))
        if op == "readframe":
            return self._rpc("readU32", args["addr"])
        if op == "trace":
            return self._rpc("traceDraw", args.get("enable", True))
        if op == "tracelog":
            from collections import Counter
            raw = self._rpc("traceLog", bool(args.get("clear")))
            hits = raw.get("hits", []) or []
            per_fn = Counter(h.get("fn") for h in hits)
            obj = args.get("obj")
            if obj:
                hits = [h for h in hits
                        if str(h.get("obj", "")).lower() == str(obj).lower()]
            shown = hits[:int(args.get("limit", 200))]
            return {"total": raw.get("count"), "perFn": dict(per_fn),
                    "matchedObjects": len(hits), "hits": shown}
        if op == "createcanvas":
            # doc=None only MEASURES a canvas; passing a doc would register it
            # and is known to kill Editer.exe, so it stays opt-in.
            return self._rpc("createCanvas", args.get("doc"), args.get("typeId"),
                             bool(args.get("confirmDangerous")))
        if op == "insertprobe":
            # Why does esTextUI::InsertCanvas() yield nothing? Walks the same
            # precondition chain the engine walks and reports each step.
            return self._rpc("canvasInsertProbe", args.get("pageList"))
        if op == "newcanvas":
            return self._rpc("insertCanvasNative", args.get("ui"), args.get("w"),
                             args.get("h"), {})
        if op == "penwidth":
            # Stroke width for every primitive on a canvas.  The value is the
            # engine's own unit: 1/400 mm -> 0.25mm == 100 (EE's UI confirms:
            # 80 shows as 0.20mm, 25 shows as 0.06mm).
            return self._rpc("setPenWidth", args.get("canvas") or self.canvas(),
                             int(args.get("value", 100)))
        if op == "lablestyle":
            # The 文字标注 dialog's parameters, applied to every label segment.
            # margin is 1/400 mm (so 1.00mm == 400); the font slot encodes
            # 字体+样式(斜体)+大小 together.
            o = {k: v for k, v in args.items() if k != "canvas"}
            return self._rpc("setLableStyle", args.get("canvas") or self.canvas(), o)
        if op == "poke":
            # Write one 32-bit value.  Used for style words, which have no
            # exported setter -- the label's 文字标注 dialog writes them the
            # same way.  Callers are responsible for the address.
            return {"addr": args["addr"],
                    "value": self._rpc("writeI32", args["addr"], int(args["value"])),
                    "readback": hex(self._rpc("readU32", args["addr"]) or 0)}
        if op == "caret":
            # Resolves the LIVE text UI on its own (explicit addr > pageList
            # GetUI > heap scan filtered by IsValid).  Passing a pageList whose
            # caret is not bound is no longer fatal.
            return self._rpc("caretInfo", args.get("pageList"),
                             args.get("ui"))
        if op == "textuis":
            return self._rpc("textUIs", int(args.get("max", 32)))
        if op == "pagelists":
            return self._rpc("pageLists")
        if op == "scratch":
            # Escape hatch: evaluate a snippet inside the Frida agent with the
            # module helpers in scope.  Use it to try engine calls before
            # wiring them into a real operation.
            return self._rpc("scratch", str(args.get("src", "")))
        if op == "handmove":
            return self._rpc("handMoveText", str(args["seg"]),
                             int(args.get("dx", 0)), int(args.get("dy", 0)),
                             int(args.get("flag", 1)))
        if op == "modules":
            return self._rpc("modules", args.get("filter"))
        if op == "allcanvases":
            # Every esCanvas in the process, not just the ones the page walk
            # reaches.  Reports each canvas' shape count and the label count, so
            # a stale canvas left over from an earlier (broken) batch is visible.
            r = self._rpc("instances", "??_7esCanvas@@6B@",
                          int(args.get("max", 40)), 64)
            out = []
            for a in (r.get("addresses") or []):
                row = {"canvas": a}
                try:
                    sc = self._rpc("shapeCount", a)
                    row["shapes"] = sc.get("count") if sc.get("ok") else None
                    row["firstVtables"] = sc.get("firstVtables")
                    ls = self._rpc("setLableStyle", a, {})
                    row["labels"] = ls.get("labels")
                    row["bad"] = sum(
                        1 for it in (ls.get("items") or [])
                        if self._rpc("readU32",
                                     hex(int(it["seg"], 16) + 0xB0)) != 1)
                    if not ls.get("labels"):
                        continue          # only canvases that hold labels
                except Exception as exc:
                    row["error"] = str(exc)
                out.append(row)
            return {"count": r.get("count"), "withLabels": len(out),
                    "canvases": out}
        if op == "dellables":
            # Bulk-remove labels from a canvas (optionally only those whose
            # +0x6e font slot differs from `font`), so a bad batch can be
            # replaced without a round trip per shape.
            cvh = str(args.get("canvas") or self.canvas())
            want = args.get("font")
            items = []
            if args.get("shapes"):
                items = [{"shape": s} for s in args["shapes"]]
            else:
                ls = self._rpc("setLableStyle", cvh, {})
                for it in (ls.get("items") or []):
                    if want is None or it.get("before", {}).get("font") == want:
                        items.append({"shape": it.get("shape")})
            done = []
            for it in items:
                try:
                    self._rpc("unlinkShape", it["shape"])
                    done.append(it["shape"])
                except Exception as exc:
                    done.append("%s FAILED %s" % (it["shape"], exc))
            return {"canvas": cvh, "removed": len(done), "shapes": done}
        if op == "alllables":
            # Every esSegLable in the process, with its own text.  This finds
            # labels that live in a canvas the page-list walk cannot reach.
            r = self._rpc("instances", "??_7esSegLable@@6B@",
                          int(args.get("max", 80)), 64)
            out = []
            for a in (r.get("addresses") or []):
                b = int(a, 16)
                rec = {"seg": a}
                try:
                    rec["margin"] = self._rpc("readU32", hex(b + 0x6c)) & 0xffff
                    rec["font"] = self._rpc("readU32", hex(b + 0x6e)) & 0xffff
                    rec["len"] = self._rpc("readU32", hex(b + 0x70)) & 0xff
                    rec["f73"] = (self._rpc("readU32", hex(b + 0x70)) >> 24) & 0xff
                    tp = self._rpc("readU32", hex(b + 0x68))
                    rec["textPtr"] = hex(tp or 0)
                    if tp:
                        rec["text"] = self._rpc("readStr", hex(tp), True)
                except Exception as exc:
                    rec["error"] = str(exc)
                out.append(rec)
            return {"count": r.get("count"), "items": out}
        if op == "fontlist":
            # Which slot in this document's font sheet is which face?
            sheet = args.get("sheet")
            if not sheet:
                rep = self.canvas_report()
                ranked = rep.get("ranked") or [{}]
                sheet = ranked[0].get("styleSheet")
            return self._rpc("fontList", sheet, int(args.get("max_slot", 60)),
                             float(args.get("size_pt", 10.5)))
        if op == "fontslot":
            # Probe: which slot does (字体, 样式) such as ("Times New Roman",
            # "斜体") resolve to in this document's font sheet?
            sheet = args.get("sheet")
            if not sheet:
                rep = self.canvas_report()
                sheet = (rep.get("ranked") or [{}])[0].get("styleSheet")
            return self._rpc("fontSlot", sheet,
                             str(args.get("face", "Times New Roman")),
                             str(args.get("style", "斜体")))
        raise EEError(f"unknown diag op {op!r}")

    def _vt_slots(self, addr, count):
        """Dump a vtable's slots and name each target from the export table."""
        base = int(addr, 16)
        out = []
        for i in range(count):
            slot = i * 4
            fn = self._rpc("readU32", hex(base + slot))
            if fn is None:
                break
            name = None
            if fn:
                name = self._rpc("vtNameOf", hex(fn))
            out.append({"slot": f"0x{slot:03x}", "fn": hex(fn) if fn else None,
                        "name": name})
        return {"vtable": addr, "slots": out}


GW = EEGateway()


# --------------------------------------------------------------------------
# MCP tool definitions
# --------------------------------------------------------------------------
CANVAS_PROP = {"type": "string",
               "description": "optional canvas handle; defaults to the ranked "
                              "active canvas (see ee_canvases)"}
PEN_PROP = {"type": "number", "default": PEN_MM_DEFAULT,
            "description": "stroke width in mm; the project convention is 0.25 "
                           "(engine unit 1/400 mm, so 0.25mm == 100)"}

TOOLS = [
    {
        "name": "ee_status",
        "description": "Report the EduEditer connection state: process id, "
                       "eslib.dll base address, export count and the active canvas.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "ee_canvases",
        "description": "List every candidate drawing canvas (one per page list) "
                       "with its shape count and size, best candidate first, and "
                       "say which one is currently chosen. Use this when drawing "
                       "appears to land somewhere invisible.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "ee_fonts",
        "description": "List the open document's font slots: face name, italic/"
                       "bold/size (1/100 pt, 1050 = 五号) per slot. Font slots "
                       "are document-local — use this to pick font_index for "
                       "ee_draw_label / ee_draw_figure, or rely on their "
                       "automatic font_face resolution.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "canvas": CANVAS_PROP,
                "max_slot": {"type": "integer", "default": 63,
                             "description": "highest slot to probe"},
                "size_pt": {"type": "number", "default": 10.5,
                            "description": "pt size passed to esFontSheet::GetFont"},
            },
        },
    },
    {
        "name": "ee_new_canvas",
        "description": "Insert a new drawing canvas into the open document at "
                       "the text caret, through the engine's own insert routine "
                       "(esTextUI::InsertCanvas(canvas, -1) — the channel the "
                       "editor's paste command uses; no keyboard simulation). "
                       "It only works while EduEditer's text caret is inside the "
                       "document body (esTextUI::IsValid() must be 1); if it "
                       "reports a refusal, click into the page text and retry.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "w": {"type": "integer",
                      "description": "canvas width in 1/400 mm (default 61340)"},
                "h": {"type": "integer",
                      "description": "canvas height in 1/400 mm (default 30670)"},
            },
        },
    },
    {
        "name": "ee_draw_line",
        "description": "Draw an open straight line segment on the active EE canvas. "
                       "pen_mm defaults to the project's fixed 0.25 mm (engine "
                       "default is 0.20 mm, so this is not a no-op).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "x1": {"type": "integer"}, "y1": {"type": "integer"},
                "x2": {"type": "integer"}, "y2": {"type": "integer"},
                "pen_mm": PEN_PROP,
                "canvas": CANVAS_PROP,
            },
            "required": ["x1", "y1", "x2", "y2"],
        },
    },
    {
        "name": "ee_draw_polyline",
        "description": "Draw an open polyline through the given points.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "points": {"type": "array", "items": {"type": "array",
                           "items": {"type": "integer"}, "minItems": 2,
                           "maxItems": 2}},
                "pen_mm": PEN_PROP,
                "canvas": CANVAS_PROP,
            },
            "required": ["points"],
        },
    },
    {
        "name": "ee_draw_polygon",
        "description": "Draw a closed polygon (triangle, quadrilateral, ...) "
                       "through the given vertices.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "points": {"type": "array", "items": {"type": "array",
                           "items": {"type": "integer"}, "minItems": 2,
                           "maxItems": 2}},
                "pen_mm": PEN_PROP,
                "canvas": CANVAS_PROP,
            },
            "required": ["points"],
        },
    },
    {
        "name": "ee_draw_rect",
        "description": "Draw a rectangle from two opposite corners.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "x1": {"type": "integer"}, "y1": {"type": "integer"},
                "x2": {"type": "integer"}, "y2": {"type": "integer"},
                "pen_mm": PEN_PROP,
                "canvas": CANVAS_PROP,
            },
            "required": ["x1", "y1", "x2", "y2"],
        },
    },
    {
        "name": "ee_draw_circle",
        "description": "Draw a circle as a TRUE esSegCircel primitive (falls "
                       "back to a closed path). The engine's own default pen is "
                       "0.20 mm; this tool applies the project's 0.25 mm unless "
                       "pen_mm is given.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "cx": {"type": "integer"}, "cy": {"type": "integer"},
                "r": {"type": "integer"},
                "pen_mm": PEN_PROP,
                "canvas": CANVAS_PROP,
            },
            "required": ["cx", "cy", "r"],
        },
    },
    {
        "name": "ee_draw_label",
        "description": "Place a text label (a letter such as A/B/C, or a short "
                       "word) on the canvas at page coordinates, using the "
                       "editor's own label recipe (esShapeLine wrapper + "
                       "esSegLable text segment). Use variant to bisect a "
                       "rendering problem; defaults to the full verified recipe.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "label text, e.g. \"A\""},
                "x": {"type": "integer"}, "y": {"type": "integer"},
                "canvas": CANVAS_PROP,
                "variant": {"type": "string", "enum": sorted(LABEL_VARIANTS),
                            "description": "pipeline preset to run"},
                "font_sheet": {"type": "string",
                               "description": "override the auto-picked esFontSheet"},
                "style_sheet": {"type": "string",
                                "description": "override the auto-picked esStyleSheet"},
                "font_index": {"type": "integer",
                               "description": "font slot for the segment (+0x6e); "
                                              "0 selects slot 0 rather than the "
                                              "document's current font. Omit to "
                                              "auto-resolve (existing label, "
                                              "else font_face lookup)"},
                "font_face": {"type": "string",
                              "description": "face to resolve when no existing "
                                             "label provides a slot, e.g. "
                                             "\"Times New Roman\" (default) or "
                                             "\"宋体\"; see ee_fonts"},
                "font_italic": {"type": "boolean",
                                "description": "italic flag for font_face "
                                               "resolution (default true)"},
                "padding": {"type": "integer",
                            "description": "label text padding (+0x6c)"},
                "sup": {"type": "string",
                        "description": "superscript part (3-part label model); "
                                       "use with sub for x^2 / fractions"},
                "sub": {"type": "string",
                        "description": "subscript part (3-part label model)"},
                "style_flags": {"type": "integer",
                                "description": "label feature word passed to the "
                                               "segment ctor (esSegLable "
                                               "GetLableFreature); controls label "
                                               "styling such as italic"},
            },
            "required": ["text", "x", "y"],
        },
    },
    {
        "name": "ee_draw_figure",
        "description": "Draw a WHOLE figure in one call: polylines/polygons, "
                       "sampled curves/arcs, bold dots and letters, then one "
                       "canvas-wide 0.25 mm pen pass and one label style pass. "
                       "Coordinates are canvas units (1 unit = 1/400 mm, so "
                       "0.25mm pen = 100 and a 5cm figure = 20000 units). "
                       "paths[].dash = real dashed pen; paths[].fill = true "
                       "(light grey) or \"dark\" (dark grey), implemented with "
                       "esShapePath::SetSolidBrush and verified via GetBrush; "
                       "curves[] = quadratic sampler; arcs[] = sampled arcs "
                       "(the native arc silently fails on some canvases); "
                       "dots[] = engine-built 0.40 mm bold points; labels[] "
                       "support sup/sub. NEVER use native esSegBezier/Curve or "
                       "esSegAxis: the Bezier corrupts the shape chain and the "
                       "axis does not render -- see the project iron rules.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "canvas": CANVAS_PROP,
                "pen_mm": {"type": "number", "default": 0.25,
                           "description": "stroke width in mm for every shape"},
                "font_index": {"type": "integer",
                               "description": "label font slot (+0x6e); omit to "
                                              "inherit the document's own labels"},
                "font_face": {"type": "string",
                              "description": "face to resolve when the canvas "
                                             "has no labels yet, e.g. \"Times "
                                             "New Roman\" (default) or \"宋体\"; "
                                             "see ee_fonts"},
                "font_italic": {"type": "boolean",
                                "description": "italic flag for font_face "
                                               "resolution (default true)"},
                "padding": {"type": "integer",
                            "description": "label margin (+0x6c) in 1/400 mm; "
                                           "1.00mm = 400"},
                "math": {"type": "integer", "default": 1,
                         "description": "数学化 flag. It is bit7 of the label "
                                        "segment's +0x73 flags word; it does "
                                        "NOT touch +0x70..+0x72 (those are the "
                                        "per-part CHARACTER COUNTS -- writing "
                                        "them truncated multi-character labels, "
                                        "fixed in the bridge 2026-10-18)."},
                "paths": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "points": {"type": "array",
                                       "items": {"type": "array",
                                                 "items": {"type": "number"},
                                                 "minItems": 2, "maxItems": 2}},
                            "close": {"type": "boolean",
                                      "description": "default: closed when >2 points"},
                            "dash": {"type": "boolean",
                                     "description": "true = real dashed pen "
                                                    "(esPenInfo+0x04 = 3), not "
                                                    "a cut-up polyline"},
                            "fill": {
                                "anyOf": [{"type": "boolean"},
                                          {"type": "string", "enum": ["dark"]}],
                                "description": "true = light grey, \"dark\" = "
                                               "dark grey. Implemented with "
                                               "SetSolidBrush; a shape really "
                                               "renders filled only when "
                                               "GetBrush() != 0, so the "
                                               "returned 'fill.filled' must be "
                                               "true."},
                        },
                        "required": ["points"],
                    },
                },
                "curves": {
                    "type": "array",
                    "description": "quadratic sampler: y = h*(x-cx)^2+cy in "
                                   "figure units, mapped by origin/scale into "
                                   "canvas units. Use this (or a dense "
                                   "polyline) for parabolas, never the native "
                                   "Bezier/Curve.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "sx": {"type": "number"},
                            "sy": {"type": "number"},
                            "ox": {"type": "number"},
                            "oy": {"type": "number"},
                            "cx": {"type": "number", "default": 0},
                            "cy": {"type": "number", "default": 0},
                            "h": {"type": "number", "default": 1},
                            "x0": {"type": "number"},
                            "x1": {"type": "number"},
                            "steps": {"type": "integer", "default": 60},
                        },
                        "required": ["sx", "sy", "ox", "oy", "x0", "x1"],
                    },
                },
                "arcs": {
                    "type": "array",
                    "description": "sampled circular arcs emitted as exact "
                                   "polylines; angles in degrees, clockwise.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "cx": {"type": "number"},
                            "cy": {"type": "number"},
                            "r": {"type": "number"},
                            "a0": {"type": "number"},
                            "a1": {"type": "number"},
                            "steps": {"type": "integer", "default": 48},
                        },
                        "required": ["cx", "cy", "r", "a0", "a1"],
                    },
                },
                "dots": {
                    "type": "array",
                    "description": "bold points (加粗点), 0.40 mm: each item is "
                                   "[x, y] or [x, y, size]; built by the "
                                   "engine's own esShapeLine(pt, 0x6001, ...) "
                                   "constructor. Do NOT fake them with a tiny "
                                   "polygon.",
                    "items": {"type": "array",
                              "items": {"type": "number"},
                              "minItems": 2, "maxItems": 3},
                },
                "labels": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "text": {"type": "string"},
                            "x": {"type": "number"},
                            "y": {"type": "number"},
                            "sup": {"type": "string",
                                    "description": "superscript part"},
                            "sub": {"type": "string",
                                    "description": "subscript part"},
                            "font_index": {"type": "integer",
                                           "description": "per-label font slot"},
                            "font_sheet": {"type": "string"},
                            "style_sheet": {"type": "string"},
                            "variant": {"type": "string",
                                        "enum": sorted(LABEL_VARIANTS)},
                            "padding": {"type": "integer"},
                            "k": {"type": "integer",
                                  "description": "ctor flags template; the "
                                                 "bridge derives the character "
                                                 "counts itself"},
                        },
                        "required": ["text", "x", "y"],
                    },
                },
            },
        },
    },
    {
        "name": "ee_draw_arc",
        "description": "Draw a TRUE circular arc (esSegArc primitive) centred on "
                       "(cx, cy) from start_deg to end_deg, measured in degrees "
                       "clockwise from the +x axis.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "cx": {"type": "integer"}, "cy": {"type": "integer"},
                "r": {"type": "integer"},
                "start_deg": {"type": "number"},
                "end_deg": {"type": "number"},
                "major": {"type": "boolean", "default": False,
                          "description": "take the long way round instead of the "
                                         "minor arc"},
                "pen_mm": PEN_PROP,
                "canvas": CANVAS_PROP,
            },
            "required": ["cx", "cy", "r", "start_deg", "end_deg"],
        },
    },
    {
        "name": "ee_draw_angle_mark",
        "description": "Mark the angle at a vertex between two rays: 'right' draws "
                       "the small square used for 90-degree angles, 'arc' draws an "
                       "esSegArc across the angle, 'double' draws two concentric "
                       "arcs (the equal-angle convention). Points are page "
                       "coordinates; `size` is the arm length or radius.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "vertex": {"type": "array", "items": {"type": "integer"},
                           "minItems": 2, "maxItems": 2,
                           "description": "the angle's vertex [x, y]"},
                "point_a": {"type": "array", "items": {"type": "integer"},
                            "minItems": 2, "maxItems": 2,
                            "description": "a point on the first ray"},
                "point_b": {"type": "array", "items": {"type": "integer"},
                            "minItems": 2, "maxItems": 2,
                            "description": "a point on the second ray"},
                "kind": {"type": "string", "enum": ["right", "arc", "double"],
                         "default": "right"},
                "size": {"type": "integer",
                         "description": "arm length (right) or radius (arcs)"},
                "pen_mm": PEN_PROP,
                "canvas": CANVAS_PROP,
            },
            "required": ["vertex", "point_a", "point_b"],
        },
    },
    {
        "name": "ee_draw_axis",
        "description": "Draw the editor's own native coordinate axis "
                       "(esShapeCap 0x320B + esSegAxis 0x5006). `rect` is the "
                       "axis content rectangle [x1,y1,x2,y2] in page units and "
                       "`origin` is the page position of the mathematical "
                       "origin [ox,oy]. The engine derives ranges, tick marks "
                       "and labels through esSegAxis::Initialize.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "rect": {"type": "array", "items": {"type": "integer"},
                         "minItems": 4, "maxItems": 4,
                         "description": "[x1,y1,x2,y2] content rectangle"},
                "origin": {"type": "array", "items": {"type": "integer"},
                           "minItems": 2, "maxItems": 2,
                           "description": "[ox,oy] page position of the math origin"},
                "visible_x": {"type": "integer", "default": 1},
                "visible_y": {"type": "integer", "default": 1},
                "pen_mm": PEN_PROP,
                "canvas": CANVAS_PROP,
            },
            "required": ["rect", "origin"],
        },
    },
    {
        "name": "ee_draw_function",
        "description": "Plot y = f(x) as the editor's NATIVE smooth curve "
                       "(esSegBezier 0x4703, one object per continuous branch) "
                       "instead of a hand-sampled polyline -- the '函数图象' "
                       "capability. Give the formula in `x` plus the model->page "
                       "mapping: `origin` = page position of the model origin, "
                       "`scale` = page units per model unit (y axis points up). "
                       "Asymptotes/poles are split into separate branches "
                       "automatically (use `y_range` to bound steep parts). "
                       "Draw the axis first with ee_draw_axis for a complete "
                       "function-graph figure.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "expr": {"type": "string",
                         "description": "formula in x, e.g. '36/x' or 'x**2-2*x' "
                                        "(sin/cos/tan/sqrt/abs/log/exp/pi allowed)"},
                "x_range": {"type": "array", "items": {"type": "number"},
                            "minItems": 2, "maxItems": 2,
                            "description": "[x0,x1] in MODEL units"},
                "origin": {"type": "array", "items": {"type": "number"},
                           "minItems": 2, "maxItems": 2,
                           "description": "[ox,oy] page position of model (0,0)"},
                "scale": {"type": "number",
                          "description": "page units per model unit (y up)"},
                "y_range": {"type": "array", "items": {"type": "number"},
                            "minItems": 2, "maxItems": 2,
                            "description": "optional [y0,y1] model clip; values "
                                           "outside break the curve"},
                "samples": {"type": "integer", "default": 260},
                "pen_mm": PEN_PROP,
                "dash": {"type": "boolean", "default": False},
                "canvas": CANVAS_PROP,
            },
            "required": ["expr", "x_range", "origin", "scale"],
        },
    },
    {
        "name": "ee_canvas_bounds",
        "description": "Report the active canvas extent (width, height and the "
                       "frame rectangle in page units). Draw inside this area — "
                       "geometry placed outside it is clipped until the canvas "
                       "is enlarged.",
        "inputSchema": {"type": "object",
                        "properties": {"canvas": CANVAS_PROP}},
    },
    {
        "name": "ee_list_shapes",
        "description": "List the vector shapes on the active canvas with their "
                       "cached geometry (bounding box and anchor points).",
        "inputSchema": {
            "type": "object",
            "properties": {"limit": {"type": "integer", "default": 100},
                           "canvas": CANVAS_PROP},
        },
    },
    {
        "name": "ee_audit_canvas",
        "description": "Read-only self-check of a canvas we drew: stroke width "
                       "== 0.25 mm (bold dots must stay 0.40 mm), label EQLine "
                       "format word == 0xffff0003, non-zero label char count, "
                       "sane label box, and GetBrush() ownership for filled "
                       "paths. Run this BEFORE showing a figure to the user. "
                       "It cannot judge geometry correctness -- use "
                       "tools/check_spec.py for the constraint residuals.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "canvas": CANVAS_PROP,
                "expected_pen": {"type": "integer", "default": 100,
                                 "description": "engine pen width (1/400 mm); "
                                                "0.25mm == 100"},
                "limit": {"type": "integer", "default": 200},
            },
        },
    },
    {
        "name": "ee_delete_shape",
        "description": "DANGEROUS — disabled by default. unlinkShape does NOT "
                       "repair the neighbouring list links in this engine; "
                       "deleting a shape has bricked canvases (objects stop "
                       "responding, canvas garbles). The project rule is to "
                       "redraw the whole canvas instead of deleting anything. "
                       "Only for a deliberate throwaway-canvas experiment: "
                       "pass confirm_dangerous=true.",
        "inputSchema": {
            "type": "object",
            "properties": {"shape": {"type": "string",
                                     "description": "shape handle, e.g. 0x971fd48"},
                           "canvas": CANVAS_PROP,
                           "confirm_dangerous": {"type": "boolean",
                                                 "default": False}},
            "required": ["shape"],
        },
    },
    {
        "name": "ee_redraw",
        "description": "Force the editor windows to repaint so new geometry "
                       "becomes visible.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "ee_goto_problem",
        "description": "Move EduEditer's text caret onto a question, "
                       "automatically (no manual click): pass a question id "
                       "such as 选择5 / 填空6 / 解答3, or any text anchor.  "
                       "The caret walks paragraph-by-paragraph to the first "
                       "match.  With insert:true it also inserts a drawing "
                       "canvas at that spot and reports the canvas handle to "
                       "draw on.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "q": {"type": "string",
                      "description": "question id (选择5/填空6/解答3) or a "
                                     "literal text anchor"},
                "insert": {"type": "boolean",
                           "description": "also insert a canvas at the caret"},
            },
            "required": ["q"],
        },
    },
    {
        "name": "ee_goto_text",
        "description": "Move the text caret to the first paragraph containing "
                       "the given substring.",
        "inputSchema": {
            "type": "object",
            "properties": {"anchor": {"type": "string"}},
            "required": ["anchor"],
        },
    },
    {
        "name": "ee_caret_canvas",
        "description": "Report the canvas anchored at the text caret (the one a "
                       "fresh InsertCanvas landed on). Use after ee_goto_problem "
                       "with insert:true to get the canvas to draw into.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "ee_diag",
        "description": "Read-only introspection inside Editer.exe: object memory, "
                       "vtable slot resolution, canvas ranking, font sheets, "
                       "zwstr layout, and where a string landed in an object. "
                       "Operations: canvases, fontsheets, hexdump, readu32, "
                       "readstr, vtname, vtslots, zwstr, scantext, shapecount, "
                       "recalc, names, expaddr, call, callvirt, trace, tracelog.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "op": {"type": "string"},
                "args": {"type": "object"},
            },
            "required": ["op"],
        },
    },
]


def call_tool(name, args):
    if name == "ee_status":
        info = GW.info()
        try:
            canvas = GW.canvas(refresh=True)
        except EEError as exc:
            canvas = f"<{exc}>"
        return {"process": info, "active_canvas": canvas}

    if name == "ee_canvases":
        return GW.canvas_report()

    if name == "ee_new_canvas":
        return GW.new_canvas(args.get("w"), args.get("h"))

    cv = args.get("canvas")
    # Standalone primitives get the project's fixed 0.25 mm by default; the
    # engine's own default is 0.20 mm, so this must be applied explicitly.
    pen = pen_value(args.get("pen_mm"))

    if name == "ee_draw_line":
        return GW.line(args["x1"], args["y1"], args["x2"], args["y2"],
                       canvas=cv, pen=pen)

    if name == "ee_draw_polyline":
        return GW.polygon(args["points"], closed=False, canvas=cv, pen=pen)

    if name == "ee_draw_polygon":
        return GW.polygon(args["points"], closed=True, canvas=cv, pen=pen)

    if name == "ee_draw_rect":
        return GW.rect(args["x1"], args["y1"], args["x2"], args["y2"],
                       canvas=cv, pen=pen)

    if name == "ee_draw_circle":
        return GW.circle(args["cx"], args["cy"], args["r"], canvas=cv,
                         pen=pen)

    if name == "ee_draw_label":
        opts = {}
        if args.get("sup") or args.get("sub"):
            opts["parts"] = [str(args["text"]), str(args.get("sup") or ""),
                             str(args.get("sub") or "")]
        return GW.label(str(args["text"]), int(args["x"]), int(args["y"]),
                        canvas=cv, font_sheet=args.get("font_sheet"),
                        style_sheet=args.get("style_sheet"),
                        variant=args.get("variant", "full"),
                        font_index=args.get("font_index"),
                        padding=args.get("padding"),
                        style_flags=args.get("style_flags"),
                        font_face=args.get("font_face"),
                        font_italic=args.get("font_italic"),
                        opts=opts or None)

    if name == "ee_fonts":
        return GW.list_fonts(canvas=cv,
                             max_slot=int(args.get("max_slot", 63)),
                             size_pt=float(args.get("size_pt", 10.5)))

    if name == "ee_draw_figure":
        return GW.draw_figure(args, canvas=cv)

    if name == "ee_draw_arc":
        return GW.arc(args["cx"], args["cy"], args["r"],
                      args["start_deg"], args["end_deg"],
                      major=bool(args.get("major")), canvas=cv, pen=pen)

    if name == "ee_draw_angle_mark":
        return GW.angle_mark(args["vertex"], args["point_a"], args["point_b"],
                             kind=args.get("kind", "right"),
                             size=args.get("size"), canvas=cv, pen=pen)

    if name == "ee_draw_axis":
        return GW.draw_axis(args["rect"], args["origin"],
                            visible_x=int(args.get("visible_x", 1)),
                            visible_y=int(args.get("visible_y", 1)),
                            canvas=cv, pen=pen)

    if name == "ee_draw_function":
        return GW.draw_function(args["expr"], args["x_range"], args["origin"],
                                args["scale"], canvas=cv,
                                y_range=args.get("y_range"),
                                samples=int(args.get("samples", 260)),
                                pen=pen, dash=bool(args.get("dash")),
                                expr_y=args.get("expr_y"))

    if name == "ee_canvas_bounds":
        return GW.canvas_bounds(canvas=cv)

    if name == "ee_list_shapes":
        return {"shapes": GW.list_shapes(int(args.get("limit", 100)),
                                         canvas=cv)}

    if name == "ee_audit_canvas":
        return GW.audit_canvas(canvas=cv,
                               expected_pen=int(args.get("expected_pen", 100)),
                               limit=int(args.get("limit", 200)))

    if name == "ee_delete_shape":
        return GW.delete_shape(str(args["shape"]), canvas=cv,
                               confirm_dangerous=bool(args.get("confirm_dangerous")))

    if name == "ee_redraw":
        return GW.redraw()

    if name == "ee_goto_problem":
        return GW.goto_problem(args.get("q"), insert=bool(args.get("insert")))

    if name == "ee_goto_text":
        return GW.goto_text(args["anchor"])

    if name == "ee_caret_canvas":
        return GW.caret_canvas()

    if name == "ee_diag":
        return GW.diag(str(args["op"]), args.get("args"))

    raise EEError(f"unknown tool {name}")


# --------------------------------------------------------------------------
# Minimal MCP stdio JSON-RPC loop
# --------------------------------------------------------------------------
PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "ee-draw", "version": "0.3.0"}


def send(obj):
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def respond(mid, result=None, error=None):
    msg = {"jsonrpc": "2.0", "id": mid}
    if error is not None:
        msg["error"] = error
    else:
        msg["result"] = result
    send(msg)


def handle(req):
    method = req.get("method")
    mid = req.get("id")
    params = req.get("params") or {}

    if method == "initialize":
        respond(mid, {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": SERVER_INFO,
        })
        return
    if method in ("notifications/initialized", "initialized"):
        return
    if method == "tools/list":
        respond(mid, {"tools": TOOLS})
        return
    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments") or {}
        try:
            result = call_tool(name, args)
            text = json.dumps(result, ensure_ascii=False, indent=2)
            respond(mid, {"content": [{"type": "text", "text": text}],
                          "isError": False})
        except Exception as exc:
            detail = f"{type(exc).__name__}: {exc}"
            respond(mid, {"content": [{"type": "text",
                                       "text": detail + "\n" + traceback.format_exc()}],
                          "isError": True})
        return
    if method in ("ping",):
        respond(mid, {})
        return
    if mid is not None:
        respond(mid, error={"code": -32601, "message": f"method not found: {method}"})


def main():
    # MCP stdio framing is UTF-8; Windows defaults pipes to the ANSI code page.
    try:
        sys.stdout.reconfigure(encoding="utf-8", newline="\n")
        sys.stdin.reconfigure(encoding="utf-8")
    except Exception:
        pass
    print("[ee-draw] EE MCP server ready (stdio)", file=sys.stderr)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except Exception:
            continue
        handle(req)
    return 0


if __name__ == "__main__":
    sys.exit(main())
