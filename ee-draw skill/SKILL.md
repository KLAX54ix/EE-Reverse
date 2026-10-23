---
name: ee-draw
description: Draw and edit vector figures inside an EduEditer (EE) document through the ee-draw MCP (Frida bridge into Editer.exe). Use whenever the task involves EduEditer, a .wsd exam paper, redrawing textbook/geometry figures, coordinate axes, letter labels, or any ee_* tool. Carries the mandatory pre-flight checks, the project's fixed drawing conventions, and the pitfalls that previously produced garbled labels, wrong stroke weights, polygon-looking circles and misplaced canvases.
whenToUse: The user mentions EduEditer/EE, a .wsd file, redrawing figures in an exam paper, geometry labels/axes, or any ee_* tool.
---

# Drawing figures in EduEditer (EE) through the ee-draw MCP

## 0. Read this first — 先读配方，别重新发明

- **`D:\EE Reverse\analysis\figures-progress.md` 的 §1–§6 是配方总表，动手前必须逐条读。**
  加粗点、虚线、填充、标注 formatWord、坐标轴这些都已经在里面记过；不读就会重复犯同样的错
  （本 skill 的约定表只是索引，细节以那份日志为准）。
- `D:\EE Reverse\notes\` — 早期逆向笔记（对象布局）。

Architecture: `Editer.exe` (x86 MFC) + `eslib.dll` (16123 exports). A Frida bridge
(`D:\EE Reverse\bridge\ee_bridge.js`) is injected into Editer.exe and driven by the MCP server
`D:\EE Reverse\mcp-server\ee_mcp_server.py` (serverName `ee-draw`).

Units: **1 canvas unit = 1/400 mm.** A fresh inserted canvas is about **61340 x 30670**.

### 0.1 Element → tool matrix (use this, don't improvise)

| Figure element | Use | Notes |
|---|---|---|
| straight line / polyline / polygon / rectangle | `ee_draw_figure.paths` (one call for the whole figure) | canvas-wide 0.25 mm pass; `close:true` for polygons |
| dashed line | `paths[].dash = true` | real pen style (`esPenInfo+0x04 = 3`), NOT a cut-up polyline |
| filled region | `paths[].fill = true` (light) / `"dark"` (dark grey) | must check the returned `fill.filled == true` (GetBrush non-null) |
| circle | `ee_draw_circle` | native `esSegCircel`; server 0.3.0 defaults to 0.25 mm (old builds drew 0.20 mm) |
| arc / angle mark | `ee_draw_angle_mark` (`right` reliable; `arc`/`double` = native arc, can silently fail on some canvases) or sampled `arcs[]` | if it must appear, sample it |
| parabola / function graph | `ee_draw_figure.curves[]` (quadratic sampler) or a dense polyline | **NEVER** native Bézier/Curve |
| coordinate axis | **native `ee_draw_axis`** (`esShapeCap` 0x320B + `esSegAxis` 0x5006, built via `esAxisObj::InitSize` + `esSegAxis::Initialize`) | hand-drawn lines only if the tool/host is unavailable |
| labels / letters | `ee_draw_figure.labels[]` (auto font resolution) | multi-char OK; `sup`/`sub` supported; font slot is per-document |
| bold point (加粗点) | `ee_draw_figure.dots[[x,y],...]` | engine ctor; 0.40 mm; never fake with a tiny polygon |
| everything | **one figure = one `ee_draw_figure` call** | then one audit pass; do not iterate by adding shapes to a live figure |

### 0.2 Mandatory gates BEFORE showing a figure to the user

1. `python tools/check_spec.py <your-spec.json>` — constraint residuals (equal lengths,
   exact angles, collinearity, on-segment). FAIL ⇒ fix geometry, don't draw.
2. `ee_audit_canvas` (server 0.3.0) — stroke width / label format word `0xffff0003` /
   non-zero label char count / sane label box / `GetBrush` ownership. FAIL ⇒ redraw the canvas.
3. Spot checks: `fill.filled == true`, `errors == []`, label bbox visible (with padding=400 a
   single letter's shape box measured 3134×3480; a garbled label blows up to ~12000–17000+ wide).
4. Only then ask the user to look. Do not ask the user to catch mechanical mistakes.

### 0.5 Failure playbook (symptom → cause → action)

| Symptom | Most likely cause | Action |
|---|---|---|
| canvas tints, no object can be selected | shape chain corrupted (native Bézier, delete/unlink, `SetBrush(NULL)`, hand-built object) | close document **without saving**, reopen; redraw whole canvas |
| letters garbled / label box ~17000 wide | wrong font slot, `+0x70` truncated, or EQLine format word not `0xffff0003` | recreate labels with a valid slot; run audit |
| fill missing though fields look right | shape owns no brush (old scalar recipe) | `SetSolidBrush` + verify `GetBrush() != 0` |
| bold dots become thin ticks | a canvas-wide pen pass overwrote their 160 | fixed in bridge (skips 0x6001); keep dots in the same figure call |
| circle looks like a polygon | sampled-polyline fallback used | use `ee_draw_circle` (native `esSegCircel`) |
| arc invisible | native `esSegArc` silently failed on this canvas | use sampled `arcs[]` or `ee_draw_angle_mark` right-angle |
| axis invisible | `esSegAxis` now renders through `ee_draw_axis`; if it fails, fall back to lines + V arrowheads + labels |
| canvas inserted in the middle of the stem | `gotoText` stopped at the stem's end, where an **inline formula image** makes `bef()` non-null, so the "bef != 0 ⇒ after figure" test fired too early | **Ctrl+Z cleanly removes the just-inserted canvas** (verified 2026-10-19; engine objects survive) — no need to close the document. Then walk **until the current paragraph text is empty**, and only there test `bef()` / press `VK_RIGHT`. |
| `gotoText` stops with `OnKeyDown(VK_DOWN) returned 0` | it hit a canvas you already inserted; keyboard navigation cannot cross an inserted canvas block | click a text line **below** that canvas with `tools/click_doc.ps1 <shotX> <shotY>`, then `gotoText` the next anchor; do not walk from the old question. |
| every `ee_new_canvas` fails with `IsValid=0` | focus is on a canvas (insert/click) or the shell | click once into page text (or run `click_doc.ps1`), then retry; do not guess a UI handle |
| user says "centroid is wrong" twice | they may be testing with the **perpendicular-bisector** tool (intersection = circumcenter, the circle centre), not the **median** tool (intersection = centroid) | place the centroid dot at the median intersection, and in the reply give both points: centroid G = (A+B+C)/3; circumcenter O = circle centre. Do not move G to O. |

### 0.3 Forbidden recipes (red lines — violating these has corrupted canvases/documents)

- **Native `esSegBezier` (0x4703) / `esSegCurve` (0x4708): forbidden.** The Bézier left the
  shape chain corrupted (canvas tints, no object can be selected); `esSegCurve` is a dynamic
  function object, not a static curve, and its `AddPoint` fails. Use sampled polylines.
- **Native coordinate axis: use `ee_draw_axis`.** It creates `esShapeCap` (type 0x320B, size 0x60,
  Editer vtable base+0x29210c) + `esSegAxis` (type 0x5006, size 0x16C, Editer vtable base+0x2921d4).
  Recipe: default-construct both, set `shape+0x40=seg` + `esObject::SetParent(seg,shape)`, build an
  `esAxisObj` with `??0esAxisObj@@QAE@XZ`, call `InitSize(RECT*, VzPoint origin, 1)` (mode 1 = page
  units), then `esSegAxis::Initialize(seg, styleSheet, axisObj, G1, G2)`, `addItem` + `recalc`.
  **Pass G1=G2=1, not 0/0.** With 0/0 the engine creates no `esFormulaBox` label object
  (`seg+0x148 == 0`) and the axis renders only bare tick strokes — the user's "图形旁边多了一堆短线".
  With 1/1, `seg+0x148` is an `esFormulaBox` and the tick numbers/labels get drawn.
  **User's final axis style (2026-10-19, default for all future axes):** after addItem + first recalc,
  call `AddOrRemoveTextBox(seg, styleSheet, 1, 1, NULL)` and `(..., 2, 1, NULL)` to create the
  x / y label boxes (`+0x14c` / `+0x150`); `+0x148` is the origin **O** box already made by G=1,1.
  Turn tick numbers/strokes off: `seg+0x6c=0`, `+0x78=0`, `+0x104=0`, `+0x110=0`, `+0x12c=0`,
  `+0x130=0`, `+0xec=0`, `+0xf8=0`. Arrow style 4 / thinner: `seg+0x10=0x10`, `seg+0x44=0x10000`,
  `seg+0x13c=8`, `shape+0x10=15`, `shape+0x5c=0x03040400`, `shape+0x58=100` (0.25mm).
  Then `SetTextBoxPostion(seg, 0/1/2)` and recalc. Wrapped as bridge `styleAxisShape(shape, styleSheet)`
  and called automatically by `ee_draw_axis`.
  **Absolute placement:** after Initialize and before addItem/recalc, set the segment's
  `+0x4c` Gdiplus matrix translation to `origin` (`GdipSetMatrixElements(m,1,0,0,1,ox,oy)`).
  Without this the axis draws near canvas (0,0) while the figure sits at 20000+ units — the
  "figure is not inside the axis" symptom. After recalc the shape/seg bbox and `seg+0x34` axis
  points become page-absolute (e.g. rect [14100,6440,39400,24040], origin [24000,17000] →
  axes `(24000,24040)-(24000,6440)` and `(14100,17000)-(39400,17000)`).
  Tool params: `rect` [x1,y1,x2,y2], `origin` [ox,oy]; `visible_x`/`visible_y` default to 1
  (these are the two G flags).
  Do not byte-clone axes (partial render).
- **Never hand-assemble shapes** (`operator_new` + default ctor + manual links) and `addItem`
  them — only objects from the engine's own constructors.
- **Never hand-draw an angle mark / right-angle square with `paths`.** Use
  `ee_draw_angle_mark` (now backed by the engine's own annotation objects):
  - angle: `esSegArc` with **type word 0x4307** and 3 control points (`+0x58` array, `+0x5c=3`;
    arc start/mid/end). Plain drawing arcs are type 0x4306 and have no control points.
  - right angle: `esSegHVLine` (type 0x4704) built from 3 points. For a **slanted** right angle
    the 3 points are **local INSET square corners** `[(s,0),(s,-s),(0,-s)]` (do NOT start at the
    vertex: that makes one arm lie on the angle's own side) and the segment's `+0x4c`
    Gdiplus::Matrix maps that local frame to the page (`col1 = u`, `col2 = -v`, translation = vertex).
    Create it as: default ctor `??0esSegHVLine@@QAE@XZ` (allocates the internal matrix), write
    an engine-allocated point array to `+0x58` / count to `+0x5c`, then
    `GdipSetMatrixElements(seg+0x4c, m11,m12,m21,m22,dx,dy)`.
    **Do NOT** call the ctor overload `(POINT*, n, Matrix*)`: it corrupts `+0x4c` and
    `RecalcLayout` returns INT_MIN garbage boxes. Bridge RPCs:
    `makeHVLineMatrixShape(points,m11,m12,m21,m22,dx,dy)` (slanted) and
    `makeNativeAngleShape(...)` (angle). Add the returned shape, then set `shape+0x58=100`.
  A 3-point `paths` entry defaults to `close:true` and adds a diagonal (old Q7 defect).
- **Never delete/unlink an existing object** (`ee_delete_shape` is a last-resort experiment
  switch). Redraw the whole canvas instead. **Embedded canvases cannot be removed with
  `esCanvas::SetSelObj` + `DeleteSel`** (live test: `SetSelObj` returns 0, `DeleteSel` → system
  error); the safe path is to ask the user to select the canvas in the page and press Delete, then
  re-insert the corrected one. A wrong canvas inserted in the stem can instead be undone with
  **Ctrl+Z** (clean, verified 2026-10-19).
- **Never `SetBrush(shape, NULL)`** to "unfill" — it breaks the shape chain.
- **Never write `+0x70/+0x71/+0x72`** on a label segment: those are per-part CHARACTER COUNTS,
  not checkboxes. The 数学化 flag is bit7 of `+0x73`. (Writing `+0x70 = 1` truncated every
  multi-character label to its first glyph on the next relayout; fixed in the bridge 2026-10-18.)
- **A canvas-wide pen pass must never touch bold dots** — their 0.40 mm pen IS their size.
  (Fixed in the bridge 2026-10-18: `setPenWidth` now skips seg type `0x6001`.)

### 0.4 Experience protocol — the case library (this is how experience is transferred)

The skill is the router, not the encyclopedia. Per-figure experience lives in
`D:\EE Reverse\analysis\cases\`:

- **Before drawing:** classify the figure type, read `analysis/cases/index.md`, then read the
  1–3 nearest case cards. Reuse their constraint/derivation pattern — do not re-derive from scratch.
- **After drawing:** append a case card using `analysis/cases/README.md` template: constraints
  extracted from the stem, free parameters, derivation formulas, numeric residuals, final spec
  JSON path, tool calls, verification output, and negative lessons.
- **Every user correction** becomes three things in the same turn: (a) a failure-playbook line,
  (b) a checker if it is mechanically checkable, (c) a case card marked as a negative example.
- The user never has to transcribe experience; the agent records it after each figure.

---

## 1. FIXED PROJECT CONVENTIONS (user-decided — do not "improve" these)

| Item | Value | Note |
|---|---|---|
| Stroke width | **`pen_mm = 0.25`** (engine value **100**) | The user's established standard. **Do NOT try to match the original PNG's raster line thickness by scaling it up** — that produced a wrong 0.65mm(260) and was rejected. |
| Letter/point labels | label margin `padding = 400` (1.00 mm), `math = 1`, font slot = a valid **Times New Roman italic** slot of *this* document | ~五号 |
| **加粗点 (bold point)** | **`ee_draw_figure` 的 `dots:[[x,y],...]`**；底层必须用**引擎自己的构造函数** `esShapeLine::esShapeLine(const tagPOINT& pt, ushort structureType, ulong flags)`，`structureType = 0x6001` | 这一个调用就够：引擎自己建 `esSegPoint` 段、自己把样式字写成 `0x04000005`、自己按点布局。**三条禁忌**：① 不要用多边形/十字凑；② 不要 `operator_new` + `esShapeLine(void)` + 手搓 `esSegPoint`；③ 不要调 `esSegPoint::Build()`。②③ 会让 `RecalcLayout` 永久抛 `access violation accessing 0x4`，**而且这种半成品留在画布上会在重绘时把 Editer 直接搞崩**（2026-10 已发生一次，未保存内容全丢）。笔宽 160(0.40mm) 要在画布级 0.25mm 之后写。 |
| Circle | **native `ee_draw_circle`** | Sampled-polyline circles look **discontinuous** — rejected. `ee_draw_circle` makes a real `esSegCircel`. |
| **Fill / shading** | **You must call the engine API**: `esShapePath::SetSolidBrush(COLORREF)` (light grey `0xCACACA`, dark grey `0xA0A0A0`), then `recalcShape`. Bridge RPC = `setSolidBrush`; server = `paths[].fill` (`true` / `"dark"`). **Verify with `esShapePath::GetBrush()` — non-null means it is really filled** (`0x0` = not filled, even when every scalar field matches a filled shape). | **Two wrong recipes were tried and both left the figure completely unfilled**: ① `shape+0x38 = 12`; ② `shape+0x10 = 12` + `shape+0x38` shade. Those fields *do* end up identical to a shape made with the editor's fill tool, but the shape still owns no brush, so the renderer never fills it — and the read-back looks correct, which makes the mistake very convincing. |
| Where the canvas goes | **at the END of the question, AFTER the original figure** | so it can be compared with the paper's own image. **Never** drop a canvas into the middle of the question text. |
| 坐标轴 | **原生 `ee_draw_axis`**：`esShapeCap`(0x320B/0x60) + `esSegAxis`(0x5006/0x16C)，默认构造 + `esAxisObj::InitSize` + `esSegAxis::Initialize` + addItem/recalc；参数 `rect`=[x1,y1,x2,y2]、`origin`=[ox,oy] |
| 函数图象 | **FORBIDDEN — do not use native Bézier/Curve.** `esSegBezier` (0x4703) corrupts the shape chain (canvas tints, nothing selectable); `esSegCurve` (0x4708) is a DYNAMIC function object with four evaluator pointers at `seg+0x70..0x7C`, not a static curve, and its `AddPoint` fails. **Use `ee_draw_figure.curves[]` (quadratic sampler) or a dense polyline** — 题10 图2 verified max deviation 2.07 canvas units (0.005 mm) with 56 samples. |

### `esSegAxis` (0x5006) field layout — read off the user's own axis (2026-02)

| offset | meaning |
|---|---|
| `seg+0x4` | `0x5006` (type id) |
| `seg+0x14/+0x18` → `+0x1c/+0x20` | **axis extent** (x1,y1)-(x2,y2) |
| `seg+0x24..+0x30` | outer box, extent padded by 100 |
| **`seg+0x70/+0x74`** | **x tick pair (spacing, scale)** — observed `10, 10000` |
| **`seg+0x78`** | observed `0` |
| **`seg+0x7c/+0x80`** | **y tick pair** — observed `10, 10000` |
| `shape+0x4` | **`0x320B`** — the axis has its **own shape class** (a plain path is `0x330F`) |
| `shape+0x34` | style word **`0x040700B7`** (a plain line is `0x040700FF`) |

### EE's own "function graph" is a DYNAMIC object — not a plain path

Drawing a function inside an axis produces a shape that **looks** like an `esShapePath`
(`shape+0x4 == 0x330F`, style `0x040700FF`) but whose seg is a dynamic object:
`seg+0x4 == 0x1DA4703` (**not** a seg type id) and `seg+0x70..0x7C` holds **four code
pointers into eslib** — i.e. it carries its own evaluator, which is why it can be dragged
and re-parameterised in the canvas. Do **not** mistake it for a normal path. For **redrawing static figures**, do **NOT** use
`esSegCurve` (0x4708) either — it is not a static curve and its construction path fails;
use `ee_draw_figure.curves[]` (quadratic sampler) or a dense polyline. Native Bézier/Curve is a
forbidden recipe (see §0.3).

### Complete `esSeg::Create(typeId)` table (measured by scanning, 2026-02)

```js
// Method: call ?Create@esSeg@@SAPAV1@G@Z (stdcall, ushort) and read the returned
// object's vtable name from +0x0.  Invalid ids return null (safe -- it does not
// crash).  Every seg shares the same skeleton:
//   +0x4 = type id, +0x14..+0x30 = geometry, +0x4C = style object ptr, +0xC = 1
```
| id | class | | id | class |
|---|---|---|---|---|
| 0x4087 | esSegStar | | **0x4C0E** | **esSegGonFace (filled polygon)** |
| **0x4281** | **esSegRect** | | **0x5001** | esSegSimpleAxis |
| 0x4282 | esSegArc90 | | 0x5002/03 | esSegSimpleSingleAxis |
| 0x4283 | esSegRoundRect | | **0x5004** | **esSegArrowLines** |
| **0x4284** | **esSegCircel (true circle)** | | 0x5005 | esSegGlow |
| **0x4286** | **esSegPolygon (regular N-gon)** | | **0x5006** | **esSegAxis (coordinate axis)** |
| 0x42C1 / 0x4306 / 0x4307 | esSegArc | | 0x6001 | esSegPoint |
| 0x4488 / 0x4489 | esSegWall / esSegPipe | | 0x6003 | esSegCircels |
| 0x410B/0C / 0x410D | esSegSpring / esSegCoil | | 0x6004 | esSegSectionLine |
| **0x4701** | **esSegLine** | | 0x6005 | esSegSurface |
| **0x4702** | **esSegGon** | | 0x6006 | esSegText |
| 0x4703 | esSegBezier | | 0x6007 | esSegRuler |
| 0x4704 | esSegHVLine | | 0x6009 | esSegArcRuler |
| 0x4705 | esSegRoundLine | | 0x600A/B | esSegRulerTextA/B |
| **0x4708** | **esSegCurve** | | **0x600D** | **esSegLable** |
| 0x480F | esSegArcFace | | 0x600E | esSegMatchMan |
| 0x4A8A | esSegEllipseEx | | 0x6010 | esSegBond |
| 0x7101 | esCtrlPoint | | 0x7102+ | esCtrlLineMove / XYAny / Scale / Rotate / Dot / Gon / Bezier … |

(Dynamic-geometry control points are 0x7101..0x710D.)

---

## 2. MANDATORY pre-flight (every session, before drawing)

1. `ee_status` — confirms pid + eslib base. ("script has been destroyed" just means the Editer
   process restarted; call again, the server re-attaches.)
2. `ee_diag {op:"modules", args:{filter:"Editer"}}` — Editer.exe base (has been `0x930000` every
   time, but never assume; RVAs are computed against it).
3. **Font slots are PER DOCUMENT — the most repeated mistake.**
   - `ee_diag {op:"call", args:{name:"js:return rpc.exports.caretContext();"}}` → `fontSheet`.
   - `ee_diag {op:"fontlist", args:{sheet:"<fontSheet>", max_slot:40, size_pt:10.5}}` → the slots
     that actually exist **in this document**. Use only those. Reusing a slot number remembered
     from another document/open makes the engine resolve an empty font and **every letter turns to
     garbage** (tell-tale: a label's shape box grows from ~1100 to ~17000+ units wide).
   - **Slot NUMBERS are not stable across a save/reopen.** EE remaps them by font identity on
     load (observed: a live label on slot 16 = `Times New Roman` italic came back on slot **14**
     after save+reopen, while `FS Math Type` italic stayed on 10). So never reuse a remembered
     number — every session, re-run `fontlist` and pick by **face name + italic**, not by index.
   - A paper with no `Times New Roman` slot usually has a `FS Math Type` italic slot — but note the
     sheet **grows on demand**: after math-mode labels have been laid out (or a font lookup ran),
     new slots appear. Prefer a genuine `Times New Roman` italic slot for A/B/C/P letters;
     `FS Math Type` italic is the fallback. Mixing the two in one figure makes the letters visibly
     inconsistent (the engine can also re-resolve a single letter's slot on its own).
   - The font slot is baked into the label's embedded EQLine at creation: changing `+0x6e` later
     does **not** re-ink the glyph, and forcing a rebuild re-appends to the EQLine (garbage). Pick
     the right slot **before** creating the labels.
4. **Caret must be bound** (`esTextUI::IsValid()==1`, i.e. the caret is inside the document body)
   for `ee_goto_text` / `ee_goto_problem` / `ee_new_canvas`. If every candidate reports
   `IsValid=0`, **ask the user to click once into the page text** — never guess. Note: right after
   a canvas insert the editor moves focus onto that new canvas, so `IsValid` dropping to 0 then is
   normal (not breakage) — re-bind before the next insert.

---

## 3. Per-figure workflow

```
# 1) put the caret on the question
ee_goto_text {anchor:"<unique substring of the question stem>"}

# 2) move it PAST the paper's own figure, to the end of the question block
#    (see "placing the canvas" below)

# 3) insert the canvas there, then draw the whole figure in one call
ee_new_canvas            # native engine insert (no keyboard); optional {w, h}
ee_draw_figure {canvas, paths, arcs, labels, pen_mm:0.25, font_index:<valid slot>, padding:400, math:1}
ee_redraw
```

### Placing the canvas (the part that was wrong before)
The paper's own figure is an embedded object sitting **after** the question text (usually in the
empty paragraph between the stem and the `A. B. C. D.` options). Steps:

1. `ee_goto_text(anchor)` → the caret lands in the question paragraph.
2. Press `VK_DOWN` (`OnKeyDown(0x28)`) **until the current paragraph's text is empty**
   (`readParagraphs(1).paras[0].text === ""`). Do **not** use a non-null
   `GetBefEmbeder()` as the "past the figure" test while still in the stem: inline formula
   images make it non-null there, and inserting then puts the canvas **inside the stem**
   (the 2026-10-19 Q16 mistake). `VK_END` (`0x23`) is **not handled** by this engine — do not use it.
3. In that empty paragraph, read `GetBefEmbeder()`; if it is null, press `VK_RIGHT` (`0x27`)
   until it returns the paper's original-figure canvas (then the caret is immediately after it).
   If `VK_DOWN` hits `OnKeyDown ... returned 0`, the caret is blocked by a canvas you already
   inserted — click a text line **below** it (`tools/click_doc.ps1`) and start again.
4. Only after that, if you still are not sure, dump the surrounding paragraphs (`readParagraphs`)
   and verify that the paragraph before the caret is the (image) paragraph and the paragraph after
   it starts with `A.` — only then insert. Inserting in the middle of the stem is the failure the
   user called out.

**Raster-derived coordinates:** points recovered from a PNG (e.g. `meas-fig*.json` `model_points`)
may already be in **image orientation (y down)**. Before using them, test one invariant from the
stem (perpendicularity / midpoint / given ratio) numerically; if it fails, try the un-rotated /
y-flipped variant. 2026-10-19 Q15: the model points were already image-oriented; rotating them by
+30° broke `CD ⟂ AO` and hid `AB = 2·OD`.

**Recovery:** an accidentally inserted canvas can be removed with a single **Ctrl+Z** — verified
2026-10-19: the wrong Q16 canvas vanished, the paragraph structure returned to
「题干 → 空图段 → 大题标题」, and all previously drawn canvases kept their shapes. You do **not**
need to close the document and redo everything.

**Native insert, verified 2026-10.** `ee_new_canvas` no longer simulates Space+G. It builds the
canvas with the engine's own constructor (`??0esCanvas@@QAE@HH@Z` = default ctor +
`SetAsBorderRect(0,0,w,h)` → frame type `0x1000`) and calls the 2-arg
`esTextUI::InsertCanvas(ui, canvas, -1)` (0x48c980 — the editor's own paste/OLE channel), then
`SetSelObj(canvas,NULL,3)` + `SetFocus(canvas)`. Default size 61340x30670; `ee_new_canvas` accepts
optional `w`/`h`. After the insert the focus moves to the new canvas, so `IsValid()` dropping to 0
right after is **normal** (same as the old keyboard flow) — click back into the page text (or ask
the user) before inserting the next canvas. Do NOT call the no-arg `esTextUI::InsertCanvas()`
overload (0x48c6e0) directly: it half-breaks the textUI and eventually crashes the process.

`ee_draw_figure` takes one spec and does the whole figure in one engine round-trip:
- `paths:  [{points:[[x,y],...], close:bool, dash:bool, fill:bool}]`
- `arcs:   [{cx, cy, r, a0, a1, steps}]` — sampled arcs (quadratic/CAD curves); **for circles use
  `ee_draw_circle` instead**.
- `curves: [{sx, sy, ox, oy, cx, cy, h, x0, x1, steps}]` — parabola sampler for function graphs.
- `labels: [{text, x, y}]` — anchor is the text's placement point.

Native primitives that work and should be preferred:
`ee_draw_circle`, `ee_draw_line`, `ee_draw_polygon`, `ee_draw_polyline`, `ee_draw_rect`,
`ee_draw_arc`, `ee_draw_label`, `ee_draw_angle_mark`.

---

## 4. Matching the original figure

### 4.0 Construct from the problem's constraints — do NOT trace pixels

**This is the rule the user cares about most.** Tracing pixel coordinates produces figures that are
provably wrong: for 题2 the stem says `AB=BC=AC` (equilateral), but a pixel trace gave sides
21982 / 21919 / **21685** — 1.35 % short on one side, and "D on AB, E on BC" floated visibly off the
lines. Instead:

1. **Extract the mathematical constraints from the question text first.**
   (题2 = equilateral + F is the midpoint of AC + ∠DFE = 60° + D∈AB, E∈BC.)
2. **Keep only the minimal free parameters** (usually two points plus scale/orientation) and *derive*
   everything else:
   - third vertex of an equilateral triangle: `A = B + Rot(∓60°)·(C−B)`
   - midpoint: `F = (C+A)/2`
   - ray ∩ side: solve `F + t·d = A + s·(B−A)`; check `s ∈ [0,1]` to prove the hit is on the
     **segment**, not on its extension
   - an angle: take the bisector direction measured from the original, then spread `±θ/2` so the
     angle is exact
3. **Verify numerically before drawing** (a few lines of Python):
   - lengths that must be equal: spread < 0.01 % (the residual is just integer rounding to canvas
     units — 1 unit = 1/400 mm, invisible)
   - angles that must be exact (60°): error < 0.01°
   - points that must be collinear: distance to the line < 1 unit
4. Only *free* quantities the problem does not constrain (orientation, overall scale, where along a
   side an unconstrained point sits) may be measured from the raster.

EE's own construction tools live on the 绘图 ribbon tab (基本图形 palette, which includes an angle
tool, plus 动态几何). `esSegPolygon` has `ctor(zPoint, int sideCount)` — sideCount 3 being an
equilateral triangle — but it is **not** in `esSeg::Create`'s dispatch table, so a programmatic
entry point still has to be found; until then draw with exact `ee_draw_figure` coordinates.

### 4.1 Extracting the free parameters from the raster

The originals are PNGs pasted into the .wsd. Extract and inspect them first:

```
python tools/extract_wsd_images.py "<paper>.wsd" captures/<paper>-figs   # carves every PNG
```
Read a figure with `read_image` (needs an image-capable model; if the tool reports the model
cannot take images, say so plainly and ask the user — do not guess geometry).

Geometry helpers (pure Pillow+numpy, in `D:\EE Reverse\tools\`):
| script | purpose |
|---|---|
| `fig_ascii.py <png> [cols] [frac]` | block-summed ASCII art — structure for a text-only model |
| `fig_lines.py <png>` | Hough transform → dominant lines |
| `fig_intersect.py <png> [n]` | pairwise line intersections filtered to ink → vertices |
| `fig_grid.py <png> <out> [step]` | overlay a labelled coordinate grid |
| `fig_crop.py <png> <out> x0 y0 x1 y1 [step] [zoom]` | zoom a region with a grid → exact coords |
| `fig_render.py <spec.json> <out>` | render your own spec next to the original for a diff |
| `fig_verts2.py <png> 't,r' ...` | refine each Hough line by total least squares and print every in-figure **intersection** |

**Get vertices from LINE INTERSECTIONS, never by eyeballing a grid.** Reading a grid by eye is off by
5-10 px, and any point that must lie ON a side (e.g. "D is on AB, E is on BC") visibly floats off the
line once the document is zoomed — the user caught exactly this. Pipeline:
`fig_lines.py` → the (theta, rho) peaks; `fig_verts2.py <png> <peaks...>` → refined lines + exact
intersections. Then **prove it numerically**: substitute every "should be collinear" point into its
line and check the distance is only tens of units (1 unit = 1/400 mm); a shared vertex must also come
out identical from both of its lines (that is how you know the fit is right).

To fix an already-drawn figure: `esSegGon` stores only the bounding box in the segment, so line
endpoints cannot be patched in place — **do not unlink anything**; plan the whole canvas again
and redraw it on a fresh canvas (iron rule 1). Label anchors are the CENTRE of the text box
(`seg+0x14..+0x20`), so a moved vertex also needs its label moved.

Use them to get **geometry** (vertex positions, proportions) — not to re-derive the stroke weight,
which is fixed at 0.25mm (§1).

---

## 5. Verification loop

1. **Label sanity (automatic tell).** Two checks with `ee_list_shapes` / a field read:
   - shape box: with `padding=400` a single letter measured **3134×3480** units (2026-10-18
     live: A=3134, AB=4217, ABC=5354 wide); a garbled label blows up to **~12000–17000+**.
   - the embedded EQLine's format word (`seg+0x84`) must be **`0xffff0003`**. If the high 16 bits
     are `0x0000` the engine treats it as "format index 0": it draws once, then **any re-layout
     parses it with the wrong format and inks garbage**. (The bridge writes this automatically —
     verify, don't assume.)
   - settled fields: `+0x74 = 0x54`, `+0x73 = 0x84`, `+0x78/+0x7c ≈ 0.5`.
2. Geometry: `fig_render.py` your spec next to the original PNG and compare.
3. **Canvas census (focus-free):** `python bridge\audit_canvases.py list` — of the ~565 objects
   carrying the esCanvas vtable, only ones with a non-zero `+0xc8` rect are real; ours are
   `frameType==0x1000` + 61340x30670. Do not trust the `ee_canvases` ranking (ghosts rank in).
4. `ee_redraw`. Capture pixels only when necessary:
   `powershell -NoProfile -ExecutionPolicy Bypass -File tools\capture_window.ps1 -ProcessName Editer -OutDir captures -Tag <tag>`
   **Capturing restores+foregrounds the window and STEALS FOCUS, which unbinds the caret** — after a
   capture you normally must ask the user to click back into the document. `PrintWindow` bitmaps can
   also be stale. Prefer the geometry checks above.

---

## 6. Iron rules

1. **Create and draw only. NEVER unlink/delete any object — not even one you just created.**
   `unlinkShape` does not repair the neighbour links and has bricked canvases twice; the recovery
   is always **close the document without saving and reopen** (the disk copy is the last clean
   state), then redraw the whole canvas. A half-built shape left on a live canvas makes Editer.exe
   **crash on the next repaint** and takes every unsaved canvas with it; therefore never put an
   unfinished object on a live canvas — probe on a throwaway (unembedded) canvas first.
2. **Do not repeatedly create+delete labels on one canvas** — the engine freezes (Not Responding).
   Settle the geometry first, then draw once.
3. **Ctrl+S before every batch.** Reopening the document loses everything unsaved; a process restart
   loses all in-memory canvases.
4. Object recipes recovered from the editor itself:
   - **Label**: `esShapeLine` (0x5C) wrapper + `esSegLable` (0xD8) seg, `style |= 0x04001007`,
     `Initialize(seg, fontSheet)` (required, else the text is empty), shape+0x40 = seg, `SetParent`,
     `AddItem`, then **`HandMoveText(seg,(0,0),0)` + `Build(seg,1)` to settle** — omitting the
     settle leaves +0x74/+0x78/+0x7c at ctor defaults and the letter sits off / inks garbage on the
     first drag. (Settled: +0x74=0x54, +0x78=+0x7c=0.5, +0x73=0x84.)
   - **Dashed line**: `esPenInfo+0x04 = 3` (`shape+0x54 = 3`) — exposed as `paths[].dash`.
   - **Filled shape**: **must call `esShapePath::SetSolidBrush(COLORREF)`** (`0xCACACA` light,
     `0xA0A0A0` dark), exposed as `paths[].fill` (`true` / `"dark"`), then `recalcShape`.
     **Verify `GetBrush() != 0`** — the scalar `shape+0x10 = 12` + `shape+0x38` shade recipe is
     WRONG: it leaves no brush and the shape renders completely unfilled (two wrong recipes
     were tried; read-back still looks identical to a filled shape). 2026-10-18 live check:
     `fill` returned `brush:0x8408e70, filled:true`.
   - **Label fields**: font slot `+0x6e`, margin `+0x6c`, text `+0x68`,
     **character count `+0x70`** (per part: main/+0x70, 标注点/+0x71, 边框/+0x72),
     **flags `+0x73` (bit7 = 数学化)**, font sheet `+0xd4`.
     **Never write `+0x70..+0x72` as style checkboxes** — that is the multi-char truncation
     bug fixed in the bridge 2026-10-18. `math` only sets bit7 of `+0x73`.
   - **Stroke width**: `shape+0x58` is the embedded `esPenInfo` width for **every** shape
     (80 = 0.20 mm engine default, 100 = 0.25 mm project, 160 = 0.40 mm bold dot).
     Standalone primitives must set it explicitly; `draw_figure` does one canvas-wide pass.
   - **Arrowheads**: no native API found — two short lines forming a V. (`esSegArrowLines`
     0x5004 exists but its 16 functions are still undecompiled; candidate for a native upgrade.)
5. `ee_diag {op:"call", args:{name:"js: ..."}}` evaluates JS inside the bridge — the fastest way to
   read object fields. Frida 17 removed `Module.getExportByName`; use `Module.getGlobalExportByName`.

---

## 7. Iteration discipline (required by the user)

**Every correction the user makes must be folded back into this file (and
`D:\EE Reverse\AGENTS.md` for the short always-on version) in the same turn it is made.** Record:
what was wrong, what the correct convention is, and how to verify it. Do not wait to be asked, and
do not leave the correction only in the conversation.

---

## 8. Bridge / server edits
- Edit `bridge/ee_bridge.js` only. To reload it live, force the Frida session to reset:
  `ee_diag {op:"poke", args:{addr:"0x0", value:1}}` — this deliberately writes to address 0,
  the bridge's uncaught `writeI32` fault makes the server drop the session, and the next call
  re-attaches and re-reads the file (verified 2026-10-18; the tool call itself returns an error).
  Safer alternative: touch address 0 only when you accept losing the session; engine objects survive.
- Edit `mcp-server/ee_mcp_server.py`: a real MCP-server restart is required (an already-running
  server keeps the old code/schema). Tool surface is now **23 tools** (added `ee_audit_canvas`
 and `ee_draw_axis`,
  version 0.3.0). If the host manages the server, restart it before relying on new schema.
- Only one Frida client may attach at a time. A reset/re-attach is cheap; don't run a second server.
- Ghidra 12.1.4 in `D:\EE Reverse\tools\ghidra_12.1.4_PUBLIC`, `JAVA_HOME=D:\java`. If its
  LaunchSupport JDK check fails under a sandbox, bootstrap directly with
  `-Djava.system.class.loader=ghidra.GhidraClassLoader ... ghidra.app.util.headless.AnalyzeHeadless`.
