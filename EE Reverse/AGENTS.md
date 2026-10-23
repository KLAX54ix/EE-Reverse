# AGENTS.md — EE (EduEditer) 插图重画项目

逆向 EduEditer，把试卷 `.wsd` 里的插图重画成**原生矢量对象**。通过 Frida 桥（`Editer.exe`）
驱动的 `ee-draw` MCP 操作。**本文件每次会话自动注入；完整手册见 skill `ee-draw`
（`C:\Users\84184\.dsh\skills\ee-draw\SKILL.md`），进度见
[`analysis/figures-progress.md`](analysis/figures-progress.md)。**

> 开工前先 `skill {name:"ee-draw"}`；若目录里没有该 skill，直接读上面的路径。
> **并且必须先逐条读 `analysis/figures-progress.md` §1–§6 的配方**（加粗点/虚线/填充/formatWord/
> 坐标轴都在里面）——不读就会重复犯同样的错。
> **画新题前读 `analysis/cases/index.md`（按图型检索 1–3 张案例卡）；画完必须写回案例卡**
> （模板见 `analysis/cases/README.md`）。用户只纠正/验收，经验由 agent 每题外置。

## 新会话开工（重要，避免从零摸索）

- **工作目录必须是 `D:\EE Reverse`**，本文件才会自动注入；换目录就等于丢掉全部项目记忆。
- **MCP 不用点名**：同一 DSH 实例里 `ee-draw` 工具会自动可用；连不上是配置问题，不是提示词问题。
- **skill 要显式点名**：新会话即使看到本文件，也应先 `skill {name:"ee-draw"}`；
  否则可能不加载配方、重新踩坑。
- 新会话**不继承**当前画布句柄、视图位置、剪贴板、Editer 临时状态；
  开工先让用户 **Ctrl+S**，再 `ee_status` 确认 Editer 在跑，重新定位题目。
- 启动语可直接复制：
  ```text
  在 D:\EE Reverse 工作。先读 AGENTS.md，调用 skill ee-draw，
  再读 analysis/figures-progress.md 和对应案例卡。用 ee-draw MCP 画第 X 题；
  先 ee_status 确认 Editer 在跑，按原图+题干约束构造，画完 ee_audit_canvas + 写案例卡。
  坐标轴用 ee_draw_axis（已默认 x/y 标注、无刻度数字、保留 O、样式4细箭头）。
  ```

## 画图的根本方法：**约束式构造**，不是照抄像素

**不要用像素坐标硬算。** 用户已明确指出：题2 明说是等边三角形，我照抄像素画出来三边
21982/21919/**21685**（差 1.35%），一眼就是错的。正确流程：

1. **从题干文字提取数学约束**（必做第一步）。例：题2 = `AB=BC=AC`（等边）+ `F 是 AC 中点`
   + `∠DFE=60°` + `D∈AB, E∈BC`。
2. **只保留最少的自由参数**（通常 2 个点 + 尺度/朝向），其余全部**推导**：
   - 等边第三点：`A = B + Rot(∓60°)·(C−B)`
   - 中点：`F = (C+A)/2`
   - 射线与边的交点：解 `F + t·d = A + s·(B−A)` 的二元一次方程组（同时得到 s，用于确认交点
     落在**线段**上而不在延长线上）
   - 角度：先取原图量到的**角平分线方向**，再按 `±θ/2` 摊开，保证角度精确
3. **落笔前先数值自检**（Python 一行就能算）：
   - 该相等的边长之差应 < 0.01%（余量是画布整数化 1 单位 = 0.0025mm，看不见）
   - 该精确的角度（如 60°）误差应 < 0.01°
   - 该共线的点，到直线的距离应 < 1 单位
4. 只有**角度/朝向/比例**这类"题面没规定"的自由量，才允许从原图量取。

EE 侧的原生工具（绘图选项卡 → 基本图形 / 动态几何）用于人工作图；程序侧目前仍以
`ee_draw_figure` 的精确坐标为准。想用单个三角形对象而非三条线，可研究 `esSegPolygon`
（有 `ctor(zPoint, int 边数)`，但**不在 `esSeg::Create` 的分发表里**，需要另找构造入口）。

## 本项目固定约定（用户定的，不要擅自"优化"）

| 项目 | 值 |
|---|---|
| 线宽 | **`pen_mm = 0.25`**（引擎值 **100**）。**不要**照原位图的栅格线宽去放大（曾错误改成 0.65mm/260，被否） |
| 标注 | `padding = 400`、`math = 1`、字体槽优先选**本档真实存在的 `Times New Roman` 斜体槽**（没有才退回 `FS Math Type` 斜体）。槽在创建时烘进 EQLine，之后再改 `+0x6e` 不会重绘 |
| **加粗点** | **用 `ee_draw_figure` 的 `dots:[[x,y],...]`**；底层必须走**引擎自己的构造函数** `esShapeLine::esShapeLine(const tagPOINT&, ushort 0x6001, ulong)`（它自己建 `esSegPoint`、自己写样式字 `0x04000005`）。**禁用**：多边形凑、`operator_new`+`esShapeLine(void)`+手搓段、`esSegPoint::Build()` —— 后两者让 `RecalcLayout` 永久崩，且**半成品留在画布上重绘会把 Editer 搞崩** |
| 圆 | **用原生 `ee_draw_circle`**。折线逼近的圆看起来**不连续**，被否 |
| **填充** | **必须调用引擎 API**：`esShapePath::SetSolidBrush(COLORREF)`（浅灰 `0xCACACA`、深灰 `0xA0A0A0`），写完 `recalcShape`。桥里是 `setSolidBrush`，服务端是 `paths[].fill`（`true` / `"dark"`）。<br>**验证方法（关键）**：`esShapePath::GetBrush()` —— **非空才是真填上了**（`0x0` = 没填充，标量字段全对也没用）。<br>**两版错误配方**（都试过、都没填上）：① `shape+0x38 = 12`；② `shape+0x10 = 12` + `shape+0x38` 灰阶。这些字段会**看起来**和"用填充工具画出来的图形"一致，但图形本人没有 brush，渲染器就不填 |
| 画布位置 | **放在题干末尾、原图之后**，与卷子自带图片形成对照。**绝不要插在题干文字中间** |
| 坐标轴 | **原生 `ee_draw_axis`**（`esShapeCap` 0x320B + `esSegAxis` 0x5006）。**默认样式（用户 2026-10-19 定）**：x/y 标注、**无刻度数字/短线**、保留原点 O、箭头样式 4、线宽 0.25mm（比默认细）。绝对位置由段 `+0x4c` 的 Gdiplus 矩阵平移到 `origin`，否则会画在画布左上角 |

## 每次开工必做（三条，都是踩坑换来的）

1. `ee_status` + `ee_diag {op:"modules", args:{filter:"Editer"}}` 取 Editer.exe 基址。
2. **字体槽是「每个文档 + 每次打开」都变的 —— 最高频错误。**
   `caretContext` 拿 `fontSheet` → `ee_diag {op:"fontlist", args:{sheet, max_slot:40}}`，
   **按「字体名 + 斜体」挑，不要记槽号**（实测：`Times New Roman` 斜体 16 → 保存重开后变 **14**，
   而 `FS Math Type` 斜体一直是 10）。用不存在的槽号 → 引擎取到空字体 → **整张图字母全糊**
   （症状：字母包围盒由 ~1100 变成 ~17000+）。字母优先 `Times New Roman` 斜体槽，没有才用
   `FS Math Type` 斜体；同图内别混用。
3. **光标必须绑定在正文里**（`IsValid()==1`）才能 `ee_goto_text` / `ee_new_canvas`。
   全报 `IsValid=0` 就**请用户点一下页面文字**，不要猜。
   （插完画布后焦点转到画布、`IsValid` 掉 0 属正常，也要先点回正文才能插下一张。）

## 放画布的正确姿势（已实测跑通，2026-10）

卷子每道题的实际结构是固定三段：**[题干段落] → [空段落，内含原图 canvas] → [选项段落]**。
所以插画布 = 把光标停在**原图那个嵌入对象之后**（光标定位仍用键盘走位）：

```js
var ui = '<liveTextUI>';                       // caretContext().ui
var fKey = new NativeFunction(Module.getGlobalExportByName('?OnKeyDown@esTextUI@@QAEHIH@Z'),
                              'int', ['pointer','int','int'], 'thiscall');   // (vk, rep)
var fBef = new NativeFunction(Module.getGlobalExportByName('?GetBefEmbeder@esTextUI@@QAEPAVesEmbedder@@XZ'),
                              'pointer', ['pointer'], 'thiscall');
function bef(){ var e = fBef(ptr(ui)); return e.isNull()?null:e.add(0x38).readPointer().toString(); }
rpc.exports.gotoText('<题干片段>');            // 光标落到题干段
while (bef() !== '<该题原图的 canvas 句柄>') fKey(ptr(ui), 0x28, 0);   // VK_DOWN 逐行走
rpc.exports.insertCanvasNative(ui);             // 引擎原生插入（见下），插在光标处 = 原图之后 ✓
```

**★ 2026-10 起：插画布走引擎原生通道 `insertCanvasNative`（已验证），不再用键盘空格+G。**
配方（= 编辑器自己的"粘贴画布"通道，与 PastData/OLE 同一入口）：

```
canvas = operator_new(0xe0) + __autoclassinit2@esCanvas + ??0esCanvas@@QAE@HH@Z(0,0,w,h)
         // 默认构造 + SetAsBorderRect(0,0,w,h)；frameType 写入 0x1000；默认 w=61340 h=30670
检查：GetWidth/GetHeight==w/h、GetFrameType()==0x1000、vtable==esCanvas（@0x64cc600c）
esTextUI::InsertCanvas(ui, canvas, -1)   // @0x48c980（两参重载），返回 1 = 成功
esCanvas::SetSelObj(canvas, NULL, 3)     // 清选（@0x1d5b00）
esCanvas::SetFocus(canvas)               // @0x1d20e0
// 编辑器命令 FUN_0046dff0 里多出的 FUN_0047c250 只是"激活页+视图滚动居中"（cosmetic），可跳过
```

- 行为实测：插入后**焦点转到画布**，`IsValid()` 变 0 属**正常**（与键盘流程一致，不是坏掉）；
  要连续插下一张，先点回正文重新绑定光标（`IsValid()==1` 才可插）。
- 持久化实测（2026-10）：Ctrl+S → 关闭文档 → **重启 Editer 进程** → 重开 It-test.wsd，
  三张画布全部存活（`frameType==0x1000`、图形链 1/8/8 与保存前一致、标注盒宽 2741–3482 无乱码）。
- 刚插入时 `GetWidth/GetHeight` 读 0（未布局），布局后读回 61340×30670。
- `ee_new_canvas` 已切到此通道，可传 `w`/`h`；服务端 `new_canvas(w,h)` → RPC `insertCanvasNative`；
  探针 `bridge/probe_native_insert.py`（status/dry/insert）。
- 注意：**无参旧重载** `esTextUI::InsertCanvas()` @0x48c6e0 已弃用（直调会让 textUI 半坏，见铁律）。

- **`OnKeyDown` 不是 RPC**，必须按上面的 mangled name 直接调；`VK_DOWN(0x28)`/`VK_LEFT(0x25)`/`VK_RIGHT(0x27)`
  有效，而 **`VK_END(0x23)`/`VK_DELETE(0x2E)`/`VK_BACK(0x08)` 一律返回 0（不处理）**，
  所以删嵌入对象不能靠键盘模拟。
- 原图的 canvas 句柄可以从 `ee_canvases` 或逐行走时打印 `bef()` 得到；一题的题干段通常占 4 个视觉行。

**光标停在题干中间就插画布 = 错误**（用户已明确指出）。若已经插错，见下条"删除"。

## 焦点：所有 shell 命令都会解绑光标

EE 一失去焦点 `esTextUI::IsValid()` 就变 0，`gotoText`/`ee_new_canvas` 全部失效。而**每次跑 pwsh 都会抢焦点**。所以：
- 光标操作要**成串做完**，中间不要插 shell；
- 每次跑完 shell（含截图、IDA、Python）**先重新点一下文档正文**：
  `powershell.exe -NoProfile -ExecutionPolicy Bypass -File tools\click_doc.ps1 <shotX> <shotY>`
  （该脚本把截图坐标换算成屏幕坐标后点一下；窗口矩形与 PrintWindow 截图尺寸一致）。
- **点击点必须落在「正文文字行」上**：如果当前视图正好停在一张画布里，点下去只会把光标放进画布，
  光标依旧不绑正文。这种情况先让用户点一下文字/滚动一下，再继续。
- `tools/zoom_doc.ps1` 里的 Ctrl+滚轮 **不可靠**（实测没稳定改变缩放，反而移动了视图），别指望它。
- **光标会在每画完一张图后自己掉**（**插入画布后焦点转到画布** → `IsValid()` 变 0，属引擎正常行为，
  与键盘流程一致，不是故障），实测**连续画两张图就必然要重新绑定一次**。
  所以现实节奏是：**每题一次「截图 → 滚动找文字行 → 点击」**。
  连续走位只在同一题内可靠（`gotoText` 会失败时，就用「从当前光标往下走 + 比对 `bef()`」的方式定位）。
- `gotoText` 的 anchor **必须和段落文字逐字一致**（用 dump 出来的原文片段）；失败时它返回 `ok:false`
  且光标不动——**此时千万不要接着 `ee_new_canvas`**，否则会在错误位置插出一个空画布
  （已经犯过一次，只能请用户在页面上选中删掉）。

## 铁律

- **绝对不要移除画布上的对象 —— 连自己刚建的也不要**（2026-02 连栽两次）。
  `ee_delete_shape`(unlinkShape) 实测**修不好双向链表的邻居指针**：两次调用后返回的
  `newer/older` 都是 `0x0`，紧接着**整张画布就坏了** —— 症状是"画布微微变色、所有对象点不动、用不了"。
  两次事故：① 题6 删自己建的填充多边形 → 画布 `shapes` 直接变 0；② 题10 删自己建的 9 点折线 → 同样坏。
  **画错了就整体重画那张画布，不要试图删掉某一个对象。** 恢复办法永远是：
  **关文档不保存 + 重新打开**（磁盘上是上次保存的干净状态）。
- **绝不要把手工拼装的对象挂进画布**（2026-02 血的教训）。即使是"字段全对"的对象也不行：
  我手工 `operator_new(0x200)` + 默认构造 + `sh+0x40 = seg` 造出的 `esShapeCap`，
  **类型字 `0x320B`、样式字 `0x04000030` 都和真轴逐位一致、也没崩进程**，
  但 `addItem` 是按 `esShapePath` 的布局去写链接字段的 → **整条图形链被写坏 → 画布上所有对象都点不动**
  （和 `SetBrush(NULL)` 那次同类故障）。恢复办法：**关文档时不保存、重新打开**（磁盘上是上次保存的干净状态）。
  **只允许挂"引擎自己的构造函数造出来的对象"**（`esShapeLine(pt,type,flags)`、`esSeg::Create`+标准包装流程）。
  手工拼装的对象只能**离线看字段**，永远不要 `addItem`。
- **只新建、只画。** 绝不删已有对象（悬空指针 → 满屏乱码）。只删**本次自己刚建**的。
- **不要 `SetBrush(shape, NULL)` 去"取消填充"**：实测把整张画布的图形链打断了（24 个对象全部消失，
  画布对象还在但 `shapes=0`）。要改填充就**删掉重画**，或者用编辑器的填充工具。
- **不要手改笔刷对象内部的字段**（尤其 `+0x40`，那是个指针）：改了之后 FKGH 的笔刷就再也 `SetBrush`
  不动（返回 system error）。
- **同一画布不要反复建删标注** —— 引擎会卡死。先想清几何，再一次画完。
- **★ 2026-10 事故：连崩三次，真因是"把 bogus 指针喂给引擎"**（实测修正版）
  1. **`esTextUI::InsertCanvas()` 的「无参重载」@0x48c6e0 不要用**。它返回画布句柄、看着成功，
     但**不是编辑器自己的插入通道**：textUI 当场坏掉（`OnKeyDown` 从此恒返回 0、
     光标矩形变成整段高），随后进程崩溃。插画布要用**两参重载** `InsertCanvas(ui, canvas, -1)` @0x48c980
     + 引擎自建 `esCanvas`（= `insertCanvasNative`，走编辑器"粘贴画布"通道，**2026-10 已验证**：
     insertRet=1、画布可画、textUI 保持健康；见"放画布的正确姿势"）。
  2. **`fontSheet` / `styleSheet` 必须取对字段**。实测对照：
     - ✅ `caretContext().fontSheet` == `pageLists()[].styleSheet`（页面表 `+0x38`）——**可用**
     - ❌ `pageLists()[].ui`（页面表 `+0x40`，即 **ui 句柄**）——**不可用**：
       `makeLabelShape` 会在 `seg-build` 抛 `access violation accessing 0x68`
     - ❌ 文档重启/重开后从上一次会话记住的 `styleSheet`/`fontSheet` —— **陈旧指针**
   喂 bogus 指针的后果不是"报错就算"，而是**留下半成品对象；它一旦挂上画布，
   下一次重绘就把进程带走**（不挂画布时只是失败、进程能活，已实测）。
  3. **已实测澄清（推翻早前的猜测）**：在废纸画布上**一次调用连建 11 个对象**
     （1 曲线 + 6 直线 + 5 标注）+ 随后 `redrawAll()`，**全部成功、进程存活**
     （`shapes=11`，`redraw windows=11`）。所以**"批量"本身不是崩溃原因**，
     前提是每个句柄都有效。`redrawAll()` 单独调也安全。
  4. 保命纪律：**每次动手前 Ctrl+S**；崩溃后可查
     `D:\educationeditor\EduEditer\Backup\bk55_*.tmp`（最近的那个就是当前文档的自动备份）。
- 批量前先让用户 **Ctrl+S**；文档重开/进程重启会丢未保存内容。
- **截图会抢焦点并让光标解绑**（`PrintWindow` 还可能是旧位图）。优先几何自检：
  单个五号字母的**字形盒**约 1100×1480 单位；但 shape 包围盒还含 padding——
  2026-10-18 实测 `padding=400` 时：A=3134×3480、AB=4217×3480、ABC=5354×3480，
  所以**明显 >12000 宽**才是文字糊了；
  另查标注内嵌 EQLine 的格式字（`seg+0x84`）必须是 **`0xffff0003`**（高 16 位为 0 会"首次能画、
  一重排就乱码"）。
- 单位：**1 单位 = 1/400 mm**。

## 常用流程

```
（先用 click_doc.ps1 把光标点回正文）
gotoText(题干片段) → VK_DOWN 走到「bef()==该题原图 canvas」   # 仅光标定位用键盘走位
ee_new_canvas                                                 # 原生插入（默认 61340×30670，可传 w/h）
ee_draw_figure {canvas, paths, dots, labels, pen_mm:0.25, font_index:<Times New Roman 斜体槽>, padding:400, math:1}
ee_draw_circle {canvas, cx, cy, r}   # 服务端 0.3.0 起默认 0.25mm；旧版默认 80，需手工 +0x58=100
ee_redraw
```
- 圆**必须**用 `ee_draw_circle`（`esSegCircel`）；虚线 `paths[].dash=true`；填充 `paths[].fill=true`；
  加粗点用 `dots`。
- 审计画布用 `bridge/audit_canvases.py`（`list` / 显式句柄两模式）：进程里有 **500+ 个带 esCanvas
  vtable 的幽灵对象**（rect 全 0，多半是 undo/缓存），**只有 `+0xc8` rect 非零的才是真画布**；
  我们新建的画布特征 = `frameType==0x1000` + 61340×30670。**别信 `ee_canvases` 排名**（幽灵会被排进来）。
- 原图提取与几何测量脚本在 `tools/`：`extract_wsd_images.py`、`fig_sheet.py`（43 张图的联络表，
  用来按内容对题——**PNG 顺序≠题目顺序**）、`fig_ascii / fig_lines / fig_intersect / fig_grid /
  fig_crop / fig_render.py`。

### 取顶点必须用「直线拟合求交」，不能靠肉眼读网格

肉眼从网格读点会有 5~10px 误差；凡是**必须落在某条边上的点**（如"D 在 AB 上、E 在 BC 上"）
放大后一眼就看出脱离了边线（用户已指出一次）。正确做法：

```
① fig_lines.py <png>                       # Hough 拿到每条线的 (theta, rho)
② fig_verts2.py <png> '29.25,228' '150,-196' ...   # 对每条线做总体最小二乘细化，再两两求交
```
`fig_verts2.py` 会打印细化后的 (theta,rho) 和**所有落在图内的交点**，直接取用即可。
拿到后**必须数值自检**：把每个"应当共线"的点代入直线算距离，应 < 几十个单位（1 单位=1/400mm）。

## 原生曲线 / 坐标轴（2026-02 逆向结果）

**静态曲线 `esSegBezier` (0x4703) —— ★ 2026-10 实测【禁用】，改手搓折线**

> **结论：不要用原生贝塞尔曲线。** 它的每个单点检查都过，但**挂上活画布后把图形链写坏**
> —— 症状正是用户描述的"**画布变色、所有对象点不动**"（和 `unlinkShape` / `SetBrush(NULL)`
> 同一类故障）。用户已明确指示：**改为土方法、手搓，不用原生的**。
>
> 通过的检查（说明"检查通过"≠"能用"）：
> `esSeg::Create(0x4703)` 返回非空 → 7 个控制点由 `??0esSegBezier@@QAE@PAUtagPOINT@@H@Z`
> 存回 `seg+0x58`(数组) / `seg+0x5C`(个数) → `steps` 里**有** `oncreate` →
> 二次→三次升阶数值误差 **2.4e-14** → `addItem` 返回成功。**然后画布就坏了。**
>
> **✅ 现在用这个（已验证）**：抛物线/曲线用**加密折线**走 `ee_draw_figure` 的 `paths`。
> 例：题10 图2 用 56 个采样点（0.1 单位一段），相对真抛物线最大偏差
> **2.07 画布单位 = 0.005 mm**，肉眼不可见，且用的是最稳的 `esSegGon`+`esShapePath` 通道。
> 生成脚本：`tools/bl_q10_fig2_polyline.py`（含数值自检）。
>
> 下面保留原生曲线的结构资料，**仅作离线参考，不要再挂画布**。
```
esSeg::Create(0x4703)                                   # 建贝塞尔段
??0esSegBezier@@QAE@PAUtagPOINT@@H@Z(点数组, 个数)        # 喂控制点（n 段三次贝塞尔要 3n+1 个点）
   -> 点存到 seg+0x58(数组指针) / seg+0x5C(个数)，引擎自动算采样点到 +0xD8 起
esSegList(0x44) -> esShapePath(0x74) -> OnCreate(styleSheet) -> recalc -> addItem
```
- **`styleSheet` 必须传**（本文档查 `ee_canvases` 的 `styleSheet` 字段，**不要猜、不要用 canvasCandidates 乱取**），
  否则 `OnCreate` 那一步不会执行、样式字写不上、`shape+0x34` 会是画布指针或 0
  —— **这种对象挂上去就会把画布搞坏（闪退/点不动）**。2026-02 因此又坏过一次。
- **挂画布前的唯一硬判据**：返回的 `steps` 里**必须有 `oncreate`**，且样式字 `0x04xxxxxx`。
  **没有 `oncreate` 就绝对不要 addItem**（宁可这次不画）。三次事故的共同点：
  ①轴的包装类不对(样式字=画布指针) ②手工拼装的轴(链接字段写坏) ③曲线 styleSheet=0x0(没有 oncreate)。
- 桥里已实现：`makeCurveShape(points, canvas, styleSheet)`。
- ⚠️ **想"换掉"画布上已有的曲线时，不要删旧的** —— 见铁律第一条。正确做法：
  **把整张画布的对象重新规划好，一次画完**（或者整张画布重画）。
  抛物线用**二次→三次升阶**表示是**精确**的：三点定出 `y = A(x−h)² + k`，在顶点处切成两段，
  `C1 = P0 + ⅔(P1−P0)`、`C2 = P2 + ⅔(P1−P2)`，共 7 个控制点。
- **`esSegCurve` (0x4708) 不是静态曲线**，它是**动态函数图象**类：seg `+0x70..0x7C` 是 4 个求值函数指针，
  和用户用 EE 函数工具画的 y=x² **完全一致**，其 `AddPoint` 静默失败。画插图别用它。

**坐标轴 `esSegAxis` (0x5006) —— 2026-02 旧结构资料【已作废，不要再按此挂画布】**

> ✅ 坐标轴现在直接用 **`ee_draw_axis`**，新配方见本文档后面的
> 「2026-10-19 坐标轴逆向」以及 skill `ee-draw`：`esShapeCap` 0x320B + `esSegAxis` 0x5006，
> 默认构造 + Editer vtable + `esAxisObj::InitSize` + `Initialize(G1=G2=1)` + 段 `+0x4c` 矩阵平移
> + addItem/recalc + `styleAxisShape`。当时“禁止挂画布”的结论是因为缺了矩阵 / G 标志 /
> 标签盒，不是对象本身不能挂。
> 下面 2026-02 的 `esSeg::Create(0x5006)` 手工配方**已作废**，仅保留字段布局参考。
```js
// 1) 段：直接 Create，写范围和刻度
var seg = esSeg::Create(0x5006);            // esSegAxis
seg+0x14/0x18/0x1c/0x20 = 范围(x1,y1,x2,y2)；+0x24..+0x30 = 外扩100
seg+0x70/0x74 = x刻度(间距,比例)；+0x78 = 0；+0x7c/0x80 = y刻度    // 实测 10,10000
// 2) 包装：必须用 esShapeCap（不是 esShapePath！）
var sh = operator_new(0x200);
__autoclassinit2@esShapeCap(sh, 0x200);
??0esShapeCap@@QAE@XZ(sh);                  // 默认构造，无需 snap manager
sh+0x40 = seg;                              // 关键：esShapeCap 的 +0x40 直接就是段（不是 seg list）
// 3) 写样式字 + 挂画布
OnCreate@esShapeBase(sh, styleSheet);
recalcShape(sh); addItem(sh, canvas);
```
**验收标准（挂画布前必须满足）**：
- `shape+0x4 == 0x320B`（和你手画的轴一致）
- `shape+0x34` 是**样式字**（`0x04xxxxxx`，实测 `0x04000030`），**不是画布指针**
- `shape+0x40` 读回等于那个 esSegAxis

**失败教训**：
- 套 `esShapePath` → 样式字写不上、**addItem 后重绘崩进程**（2026-02 崩过一次）。
- `esShapeCap(snapMgr, 0x5006, 0)` 这个带类型的构造函数**不能直接调**：传 NULL 崩在 `+0x74`，
  传自造的空 snap manager 崩在 `+0x8` —— 它需要编辑器里**活的** snap manager。**用默认构造 + 手工挂段绕过** ✓
- **类名怎么解**：读 vtable 的 RTTI —— `vt[-1]` → COL → `COL+0xC` → TypeDescriptor → `+0x8` 就是类名
  （这个方法通用，以后遇到不明对象都用它）。

## 2026-10-18 活体审计（废纸画布）+ MCP 0.3.0

**方法：废纸画布**（不污染试卷）：`ee_diag {op:"createcanvas", args:{typeId:0x2020}}` 造一张
未嵌入文档的 esCanvas（0x0 尺寸也够用），把返回句柄传给 `ee_draw_figure`/`ee_draw_circle`，
就能在内存里画并读回字段；画完不挂文档、不保存。实测 fill/dash/dots/多字符 label/圆 全部可造。

**实测结论（本轮修复依据）**：
- `shape+0x58` 是所有 shape 的**笔宽字段**（= 内嵌 esPenInfo+0x08）：引擎默认 80(0.20mm)、
  项目 100(0.25mm)、加粗点 160(0.40mm)。单独调 `ee_draw_circle` 得到 80；服务端 0.3.0 起
  单原语默认写 100，不再需要手工 `+0x58=100`。
- **标签 `+0x70` 是主体字符数，不是"数学化"**：旧 `setLableStyle` 把 math 写进 +0x70，
  实测 ABC 3→1、AB 2→1（下一次 RecalcLayoutLable 把多字符截成首字形）。已修：math 只写
  `+0x73` bit7，+0x70/+0x71/+0x72 一概不碰（桥 2026-10-18）。验证：新造 ABC 经 math=1 后
  `+0x70` 仍 3、`+0x73=0x84`。
- **`setPenWidth` 会覆盖加粗点**（实测量到 before=160 after=100）。已修：按段类型 `0x6001`
  跳过；复测 dot 保留 160。
- 填充实测 brush 非空（`GetBrush=0x8408e70`, filled=true）；虚线 `+0x54=3`；EQLine 格式字
  `0xffff0003`；圆段类型 `0x4284`。
- **桥热重载已验证**：`ee_diag {op:"poke", args:{addr:"0x0", value:1}}` 故意写 0 地址，触发
  `writeI32` 未捕获异常 → 服务端 reset 会话；下一次调用重新加载 `ee_bridge.js`（本轮实测，
  工具调用本身会报错，属正常）。新桥 RPC `getBrush` 已上线。
- **MCP 服务端 0.3.0（已改、未重启）**：23 个工具（新增 `ee_audit_canvas`、`ee_draw_axis`）；`ee_draw_figure`
  schema 补齐 `dots/dash/curves/arcs`、label `sup/sub`、`fill:"dark"`；单原语增加 `pen_mm`
  （默认 0.25）；`ee_draw_label` 支持 sup/sub；删掉 schema 里的旧填充配方。**当前会话仍跑旧
  服务端，新 schema/工具要重启 MCP 才生效**。
- 标签包围盒实测（padding=400）：A=3134×3480、AB=4217×3480、ABC=5354×3480。

## 2026-10-19 批量画图（慈溪 Q7/Q9/Q13/Q15/Q16）

- 五张图已画并自检：Q7 `0x6850ee8`（14 shapes）、Q9 `0x6850668`（8）、Q13 `0x68527b8`（11）、
  Q15 `0x6850b58`（11）、Q16 `0x68577e8`（9）；`check_spec` 全 PASS（q7/q9/q13/q15/q16），
  `ee_audit_canvas` 全 PASS。案例卡：`analysis/cases/2026-cixi-batch2.md`。
- **插画布闸门（重要修正）**：`gotoText` 停在题干末尾时，题干里的 **inline 公式图**会让
  `GetBefEmbeder()` 非空；这时直接插入会把画布插进**题干中间**（Q16 首插踩过）。
  正确做法：按 `VK_DOWN` 直到 `readParagraphs(1).paras[0].text == ""`，再在该空段落检查
  `bef()` / 按 `VK_RIGHT` 找到原图 canvas，然后插入。`VK_END` 不受支持，别用。
- **误插可用 Ctrl+Z 干净撤销**（2026-10-19 实测：撤销后段落结构恢复、其余已画画布形状无损）。
  不必关文档重来。
- **`gotoText` 不能跨过已插入的画布**（`VK_DOWN` 返回 0）：从下方文字重新点一下再 gotoText。
- 批量画多题：每画完一题焦点转到画布，下一次插入前必须用鼠标点正文（`tools/click_doc.ps1`），
  否则 `ee_new_canvas` 报所有 `IsValid=0`。
- **2026-10-19 修正重画**（用户删除旧画布后）：Q7 新画布 `0x2fe2fe8`（14 shapes，α 弧 = 原生
  `esSegArc` 0x4306、F 直角 = `ee_draw_angle_mark(kind:"right")` 不闭合）、Q9 `0x1fac1a8`
  （9，A 角改为与原图一致的 -58°，重心 G=(32120,17265) 加 0x6001 实心点；中垂线交点 O 是外心，
  不是重心）、Q15 `0x1434ac0`（12，改用 image-orientation 的 model_points：
  CD·AD=0、AB=12000、OD=6000，D 处原生直角标记）、Q16 `0x1efc1a8`（9，精确模型整体旋转到
  **AB 严格水平**：A(38000,26619)/B(22000,26619)/C(23000,15000)/D(32000,3381)/E(26000,17324)，
  不再用 Kabsch/任意角度；C 处原生直角标记）。
  **“整体歪”时先摆正一个基准边（水平/竖直），再按该边旋转；不要拿噪声栅格做 Kabsch 硬拟合。**
  **角度/直角标记一律用 `ee_draw_angle_mark`；`paths` 3 点默认 close 会多一条斜边。**
  `meas-fig*.json` 的 model_points 可能已是图像坐标，先做不变量数值自检再映射。
- **嵌入画布不能由程序删**（`SetSelObj`+`DeleteSel` 实测 system error）；只能请用户在页面上选中
  画布按 Delete，或对误插画布 Ctrl+Z 撤销。

## 2026-10-19 EE 原生角度/直角标记（用户样本逆向）

用户手画样本（文档末尾画布）逆向结果：

- **角度标记** = `esShapePath` + `esSegArc`，但段类型字是 **0x4307**（普通画弧是 0x4306）。
  动态标记的关键是 **3 个控制点**：`+0x5c = 3`，`+0x58` 指向 3 个 `tagPOINT`（弧起点/中点/终点）。
  构造：`esSegArc::ctor(VzPoint 中心, ushort 0x4307)`（0x128110）→ 写 +0x58 三点 →
  `+0x68` 半径、`+0x70/+0x74` 起止角（弧度，= page angle + 90°）、`+0x6c=1`、`+0x44=0xB0000`。
- **直角标记** = `esShapePath` + **`esSegHVLine`（类型 0x4704）**，ctor
  `esSegHVLine(tagPOINT*, int n, Matrix*)`（0x11ac50）传 3 个点（角顶点两侧的 L 形）。
  HV 约束保证拖动时保持直角、只改大小。
- 桥新增 RPC（2026-10-19）：
  - `makeNativeAngleShape(cx,cy,r,startPageRad,endPageRad)`
  - `makeHVLineShape(points)`（points = [[x,y],[x,y],[x,y]]）
  两者返回 `{shape,seg}`；调用方 `addItem` + `shape+0x58=100` 设笔宽。
- 服务端 `angle_mark` 已改为调用上面两个原生 RPC（`kind:"right"`→HVLine，`arc/double`→0x4307），
  2026-10-19 已随 MCP 重启生效。
- **斜放的直角（2026-10-19 修正）**：`esSegHVLine` 的 H/V 约束在**局部坐标系**里才成立。
  原生样本是 3 个局部点 `[(s,0),(s,-s),(0,-s)]`（**内缩**方形两角，不能含顶点，否则一条臂会和
  角的边重合、看起来只有一条线）+ 段 `+0x4c` 的 `Gdiplus::Matrix`（局部→页面）：
  矩阵 `m11..m22` 取两条单位边方向 `u`、`v`（`col1=u`, `col2=-v`），`dx,dy` 取顶点。
  **千万不要用** `??0esSegHVLine@@QAE@PAUtagPOINT@@HPAVMatrix@@@Z` 直接传矩阵——它会把
  `+0x4c` 的矩阵成员写坏，`RecalcLayout` 得到 `INT_MIN` 垃圾包围盒。
  正确配方：`operator new(0xC0)` + `__autoclassinit2` + **默认构造 `??0esSegHVLine@@QAE@XZ`**
  （默认构造会自己分配好内部矩阵）→ 用引擎分配器给点数组，写 `+0x58` 指针 / `+0x5c=3`
  → `GdipSetMatrixElements(seg+0x4c, m11,m12,m21,m22,dx,dy)` → 包 `esShapePath`。
  桥 RPC：`makeHVLineMatrixShape(points, m11,m12,m21,m22,dx,dy)`。服务端 `kind:"right"`
  已改用它（任意斜角都正常，拖动只改大小、保持直角）。
- 角度标记 `esSegArc` 0x4307 用 3 个控制点表示，不含页面 H/V 约束，斜角度同样自适应；
  不需要矩阵。

## 2026-10-19 坐标轴逆向（文末样本）

用户在文末画布画了一个原生坐标轴样本。逆向结果：

- **原生坐标轴对象 = `esShapeCap`（类型字 `0x320B`，大小 `0x60`）+ `esSegAxis`（类型字 `0x5006`，大小 `0x16C`）**。
  但这两个对象用的是 **Editer.exe 里的 vtable 副本**，不是 eslib 的：
  - shape vtable = `Editer.base + 0x29210c`（样本 `0xcb210c`），class `.?AVesShapeCap@@`
  - seg   vtable = `Editer.base + 0x2921d4`（样本 `0xcb21d4`），class `.?AVesSegAxis@@`
  - 样本 shape：`+0x8`=canvas，`+0x10`=23，`+0x34`=样式字 `0x040700B7`，`+0x40`=seg，
    `+0x58`=笔宽，`+0x5c`=0x03040400；字段到 `+0x5c` 为止（对象只有 0x60）。
  - 样本 seg：`+0x8`=shape，`+0x14..0x20`=(x1,y1,x2,y2)，`+0x24..0x30`=外扩 100 的矩形，
    `+0x34`=4 点数组（箭头/轴端点），`+0x38`=4，`+0x58`=3 点数组，`+0x5c`=3，
    `+0x70/0x74`=x 刻度(10,10000)，`+0x78/0x7c/0x80`=y 刻度，`+0x84`=0x500190 …
- **Editer 里的创建函数在 `Editer.base + 0x842c0`（样本 `0xaa42c0`）**。关键调用：
  ```
  seg = new(0x16C); ??0esSegAxis@@QAE@XZ(seg); seg.vtable = Editer.base+0x2921d4
  sh  = new(0x60);  ??0esShapeCap@@QAE@XZ(sh);  sh.vtable = Editer.base+0x29210c
  sh+0x40 = seg; esObject::SetParent(seg, sh)
  esSegAxis::Initialize(seg, styleSheet, axisObj, G, G)   // 0x3fd4c0，必需非空 axisObj
  penInfo.CopyTo(...); AddItem(canvas, sh, 1)
  ```
- **✅ 2026-10-19 已打通**：`esAxisObj` 用默认构造 + `InitSize(RECT*, VzPoint origin, 1)`
  （mode=1 表示 rect/origin 直接是页面单位；`+0x68/+0x6c`=原点，`+0x70..+0x7c`=内容矩形），
  再 `esSegAxis::Initialize(seg, styleSheet, axisObj, G, G)`，最后 **addItem + recalc**。
  recalc 时引擎会把 seg 的 `+0x14..0x20` 算成**相对原点的范围**并生成刻度/控制点/标签；
  例：rect=(30000,8000,40000,16000)、origin=(30000,16000) → range=(0,-8000,10000,0)。
  已在页面坐标 (30000,8000)-(40000,16000) 处实测画出竖轴/横轴/刻度（文末声明左侧可见）。
  桥 RPC `makeNativeAxisShape(rect, origin, gx, gy, styleSheet)`；服务端工具 `ee_draw_axis`
  （`rect`、`origin`，可选 `visible_x/visible_y`、`pen_mm`）。**当前 MCP 是旧进程，需重启后新工具才生效**；
  未重启期间可直接 `ee_diag call js` 调桥 RPC 验证。
- **★ 坐标轴绝对定位（2026-10-19 用户反馈“图形没有画在坐标轴里”后修复）**：
  `esSegAxis` 的几何最初是相对原点的；页面绝对位置在段 **`+0x4c` 的 Gdiplus::Matrix** 里
  （默认 identity）。必须在 `Initialize` 之后、`addItem/recalc` 之前用
  `GdipSetMatrixElements(seg+0x4c, 1,0,0,1, originX, originY)` 把局部原点平移到页面原点。
  否则轴会画在画布 (0,0) 附近，而三角形在 2 万多单位处，看起来就是“图形不在坐标轴里”。
  正确设置后 recalc 会把 `shape+0x14..0x20`、`seg+0x14..0x20` 和 `seg+0x34` 轴点数组
  全部转成**页面绝对坐标**（例：rect=[14100,6440,39400,24040]、origin=[24000,17000] →
  shape bbox 与 seg range 均为 [14100,6440,39400,24040]；轴点数组为
  `(24000,24040)-(24000,6440)`、`(14100,17000)-(39400,17000)`）。
  桥 RPC 已内置这一步。
- **★ 刻度标签 / “一堆短线”修复（2026-10-19）**：`Initialize(seg, styleSheet, axisObj, G1, G2)`
  的两个 `G` 是轴功能标志。`G1=G2=0` 时**不创建 `esFormulaBox` 标签对象**（`seg+0x148=0`），
  画出来只有光秃秃的刻度短线——用户看到的就是“图形旁边多了一堆短线”。
  必须传 **`G1=1, G2=1`**：`seg+0x148 = esFormulaBox`（RTTI 验证），引擎才会画数字/刻度标签。
  `G` 组合实测：`(0,0)/(1,0)` → `+0x148=0`；`(1,1)/(0,1)` → `+0x148=esFormulaBox`；
  `(2,2)` → `+0x14c` 另一个对象。服务端 `ee_draw_axis` 的 `visible_x/visible_y` 默认已改成 1。
- **★ 用户最终轴样式（2026-10-19 用户手工改好，作为以后默认）**：
  在 `G=1,1` + 绝对矩阵的轴上，`addItem`/首次 `Recalc` 之后执行：
  1. `AddOrRemoveTextBox(seg, styleSheet, 1, 1, NULL)` → 创建 **x 标签框**（`+0x14c`）
     `AddOrRemoveTextBox(seg, styleSheet, 2, 1, NULL)` → 创建 **y 标签框**（`+0x150`）
     （`kind 0` 的 `+0x148` 是 `G=1,1` 已有的 **原点 O 标签框**，不要再加）
  2. 关刻度数字/短线（写 0）：`seg +0x6c/+0x78`、`+0x104/+0x110`、`+0x12c/+0x130`、
     `+0xec/+0xf8`（后两个是刻度数组指针）
  3. 箭头样式 4 / 较细：`seg+0x10=0x10`、`seg+0x44=0x10000`、`seg+0x13c=8`；
     `shape+0x10=15`、`shape+0x5c=0x03040400`、`shape+0x58=100`（0.25mm）
  4. 依次 `SetTextBoxPostion(seg, 0/1/2)`，再 `Recalc`。
  实测结果与用户手工轴逐字段一致：`+0x148/+0x14c/+0x150` 标签框 bounds 分别为
  原点 (-1664,400,-400,1980)、x 轴右端 (14134,100,15066,1680)、y 轴顶端
  (-1273,-10550,-400,-8970)（相对数学原点）。
  桥已封装 `styleAxisShape(shape, styleSheet)`；服务端 `ee_draw_axis` 在首次 recalc 后自动调用，
  以后画轴默认就是这个样式。
- **字节级克隆样本对象可以 addItem（不崩），但只画出部分轴（横轴），竖轴/标签不跟着走**；
  不要用这个当最终方案。
- 可行但需要人工/剪贴板：选中样本轴 → Ctrl+C → 目标画布 Ctrl+V（编辑器自己的深拷贝，
  子对象/标签/样式完整）。当前键盘粘贴未成功（焦点不在画布），后续可做成工具步骤。
- 用户样本画布在文末，可保留作模板；测试时往样本画布加过 3 个克隆轴，删样本画布即可清掉。

## 迭代纪律

**用户每提一条纠正，必须在同一轮里整理进本文件与 skill `ee-draw`**（写明：错在哪、正确约定、怎么验证），
不要只留在对话里。

## 改桥/服务端

- 只改 `bridge/ee_bridge.js`。热重载：`ee_diag {op:"poke", args:{addr:"0x0", value:1}}`（故意写 0
  地址让会话 reset，下一次调用重新读文件；2026-10-18 验证）。
- 改 `mcp-server/ee_mcp_server.py`：必须重启 MCP 进程（命令见 skill；当前为 0.3.0 / 23 tools，含 `ee_draw_axis`）。
  已运行的会话不会自动加载新 schema。

## 2026-10-19 深夜：删除闪退 / 保存不写盘 / 画布插入 —— 最终结论（★必读）

1. **铁律补充：永不点删除。** 用户 2026-10-19 明确指示：“以后如果让你干活的话，注意不点删除就可以了”。
   实测 6 次：在 EduEditer 里 Delete 一张**尚未经历「保存 → 关闭 → 重开」**的画布（哪怕刚由编辑器自己的
   空格+G 插入、哪怕补过 AddCanvas/Append/undo 注册）**都会闪退**。删形状同理。
   - 误插画布 → 立即 **Ctrl+Z**（安全）；
   - 确实要删 → **先保存 → 关闭文档 → 重开 → 再删**（已验证安全：空白画布、已保存带图形画布都正常）；
   - 画完的图不要删；不满意就重画一张新画布，旧的不动。
2. **保存不写盘的真相：编辑器只把“已修改”的文档写盘。** 桥插入的画布/画的形状**不会置 dirty**，
   于是 Ctrl+S 静默跳过、关闭也不提示保存 → 内容全丢（本批 6 图就是这样丢的）。
   - 标脏：编辑器内的真实操作会自动标脏（用户按空格+G 插画布、输入字符等）；桥操作不会。
   - 我方可程序化保存：`SendMessage(frame, WM_COMMAND, 0xE103, 0)`（0xE103 = ID_FILE_SAVE，
     从 Editer.exe 的 RT_ACCELERATOR 表 table 1119 解出 Ctrl+S→0xE103）。实测能写盘（413616 字节含 36 个对象）。
   - **验收必须看文件时间戳/大小**（`Get-Item *.wsd | Length,LastWriteTime`），不要相信“已保存”的口头结论。
3. **插入画布的最可靠方式 = 请用户按 空格+G**（编辑器自己的命令：画布可立即删除、自动标脏、走私有插入例程）。
   桥的 `insertCanvasNative`（operator_new + ctor + InsertCanvas + SetFocus）插的画布**不能立即删**；
   手工补注册（BeginUndoSet→AddCanvas→Append→EndUndoSet→OnDocumentChange→SetFocus）实测**仍然崩**，
   不要再走这条路做“修复”。
4. 桥新增 RPC（`bridge/ee_bridge.js`，2026-10-19）：`insertCanvasByShortcut`（真实 keybd_event 注入驱动
   空格+G，能成功但会抢焦点、偶发把编辑器搞卡）、`clickDoc`（注入鼠标点击重绑光标，单次可用）、
   `drawCanvasSpec`（按 spec 一键画整图；**实测会死锁，禁用**）、`_canvasSet/_eeWindows/_focusDoc` 辅助。
   **输入注入类操作一律少用**：连续多次注入焦点/点击会把 Editer 卡死（实测两次）。
5. 不要用 `ee_diag {op:"poke"}` 热重载做实验：实测重置会话后出现进程消失/卡死，期间丢失未保存内容。
   改桥宁可用“新建文档+冷启动”验证。
6. `makeLabelShape` **内部已把 shape 挂到 canvas**，调用方不要再 `addItem`：重复挂会让画布形状链
   **塌缩成只剩 1 个 shape**（实测 count 3→1）。服务端 `draw_figure` 是对的；桥内自写循环时注意。
7. **本批实际结果（2026-10-19 22:11）**：`九下期中选择压轴题.wsd` 磁盘为 **410733 字节 / 21:38:52**，
   已回到接近原卷（我画的两张图 Q5/多选6 及 Q4 均未保留）；Editer 进程已关闭。
   剩余 Q1/Q2/Q3/Q4 四张图**未完成**，下次重做时按上面 1–6 条执行，画完程序化保存后用时间戳验收。

## 2026-10-19 深夜：原生函数图象 / 原生曲线打通（★ 取代“折线手搓”）

用户指出：反比例函数、圆/圆弧不该用大量折线手搓，要求用“坐标轴的原生函数功能（输入解析式出图）”。
逆向结果（活体样本 + 引擎工厂实验，全部 2026-10-19 实测）：

### 1. EE 自己的“函数图象”产物是什么

用户在文末画布用「函数图象（输入解析式）」画 y=x² 后，画布上新增对象 =
**`esShapePath`（type 字 `0x330f`，Editer 里的 vtable 副本 `Editer.base+0x292044`）
+ `esSegBezier`（type `0x4703`，Editer vtable `Editer.base+0x291e54`）**。
即：EE 的函数图象最终就是**一条原生贝塞尔曲线**（一个对象），不是动态求值对象。
（对话框里同时会出现一个**未挂画布**的 `esSegCurve`(0x4708) 预览对象——
它的 `AddPoint` 实测恒返回 0/无效，`esSegCurve` 不要用来画图。）

### 2. 用引擎自己的路径工厂直接造原生贝塞尔（★关键配方）

`esShapePath::CreateFromPathData(points, types, n, close)` **支持贝塞尔**，但只接受一种编码：

| 编码 | 结果 |
|---|---|
| `types=[0,3,3,3]` + 4 点 | **NULL**（没有重复尾点） |
| `types=[0,2,2,2,0x80]` | **NULL**（0x02 不是路径类型） |
| `types=[0,1,2,3]` | `esSegGon`（折线） |
| **`types=[0,3,3,3,0x80]` + 5 点（末尾重复最后一点）** | **`esSegBezier` ✓** |
| 同上但 `close=0` | 同样得到 `esSegBezier` ✓（开放曲线） |

规则：`types` 用 GDI+ `PathPointType`：`0x00`=起点、`0x03`=三次贝塞尔控制点、`0x80`=终止；
**点数组末尾必须重复最后一个点**，`types` 长度 == 点数组长度，`n = points.length`。

### 3. 采样点 → 控制点（Catmull-Rom）

给定 on-curve 采样点列 P0..Pk（每个都落在曲线上），每段生成：
`C1 = P1 + (P2−P0)/6`、`C2 = P2 − (P3−P1)/6`（端点用自身替代 P0/P3），
得到 `1 + 3k` 个控制点 + 末尾重复点 + `types=[0,3,...,0x80]` → 一条原生平滑曲线。
实测：40 段抛物线 = 1 个 `esSegBezier` 对象，`ee_audit_canvas` PASS，box 正确。

### 4. 原生圆弧（esSegArc 0x4306）

`ee_draw_arc` 直接可用（已有工具）。角度是 **page 角**（atan2(dy,dx)，y 向下）：
**上半圆 = `start_deg=0, end_deg=180`**（工具内部换成 arc_deg [-180,0]）；
`start=180,end=360` 会得到**下半圆**。半圆/圆弧一律用它，不要再采样折线。

### 5. 桥/服务端新增能力（已改代码）

- 桥 RPC（`bridge/ee_bridge.js`，热重载后生效）：
  - `makeBezierPathShape(points, closed)` → `{shape, samples, ctrlPoints}`（Engine 工厂造 bezier path）
  - `drawBezierCurves(canvas, [{points, closed}])` → `{shapes, errors}`（末端做 addItem）
  - `setShapePen(shapes, pen)`（只改给定 shape 的笔宽）
- 服务端（`mcp-server/ee_mcp_server.py`，**需重启 MCP 才生效**）：
  - 新工具 **`ee_draw_function`**：`expr`（x 的表达式，如 `36/x`、`x**2-2*x`）+ `x_range`
    + `origin`（模型原点在页面上的位置）+ `scale`（页面单位/模型单位）
    + 可选 `y_range`（渐近线裁剪）、`samples`、`pen_mm`、`dash`；
    自动按极点/无穷断开分支，每条连续分支 = **一个原生 bezier 对象**。
  - `ee_draw_figure` 的 `arcs` 改为**先走原生 esSegArc**（失败才回退折线）；
    `curves`（二次函数采样）改为**原生 bezier**；新增顶层 `beziers: [{points, closed}]`
    （画布坐标的 on-curve 采样点）。
  - 旧的 `paths`/`dots`/`labels`/`fill`/`dash` 语义不变。

### 6. 验证状态

- 试画（用户文末样本画布 0xa4c2500）：原生轴 + `y=1/x` 原生 bezier（box 24600×10755，
  segType 0x4703，pen 100）+ 原生半圆弧（segType 0x4306，pen 100）→ 审计通过。
- **仍待做一次 save → close → reopen 验收**：确认原生 bezier/arc 落盘/重开后不崩
  （2026-02 曾有“手搓 bezier 挂画布后图形链损坏”的记录；这次是引擎工厂产物，风险低但必须验一次）。
- 当前 MCP 进程仍是旧代码：`ee_draw_function` 等新工具要等下次重启 MCP 才出现在工具列表；
  眼下可直接用 `ee_diag {op:"call"}` 调桥 RPC 画，或重启服务端后再用工具。

### 7. ★ 关键修正（2026-10-19 用户两次反馈后）：控制点要“少而准”，用拟合而不是密集插值

用户看完第一版演示说“反比例函数还是折线”“这次你只用了更多的折线”。原因不是对象类型错
（它确实是 `esSegBezier`），而是**控制点太多**：EE 自己的“函数图象”样例如 `y=x²` 只有
**7 个控制点 / 2 段三次贝塞尔**（实测：`shape=esShapePath(0x330f)`，`seg=esSegBezier`，
`seg+0x5c=7`，点列为 `P0,C1,C2,P1,C3,C4,P2`）；我第一版用 Catmull-Rom 把 143–601 个
采样点全塞成控制点，EE 里看起来就是一串密集折线。

**正确做法：先密采样，再用 Schneider 拟合算法压成尽量少的贝塞尔段**：
`tools/bezier_fit.py`（= `mcp-server/bezier_fit.py`，同一份代码）：
- `fit_bezier(points, tol=1.2)` → 返回扁平控制多边形 `[P0,C1,C2,P1,C3,C4,P2,...]`（长度 1+3n）；
- 内部：弦长参数化 → 最小二乘求 C1/C2 → **Newton 重参数化两次**（不加重参数化会多出 3–5 倍段数，
  实测 1/4 圆从 21 段降到 4 段）→ 误差超过 `tol` 就在最大误差点二分递归；
- `tol` 单位是画布单位（1 单位 = 1/400 mm），`1.2` ≈ 0.003 mm，肉眼不可见。
- 实测：`y=1/x`（x 0.55–3.4，3000 单位/单位）→ **5 段 / 16 个控制点**；
  1/4 圆 → 4 段、径向误差 0.85 单位。

**桥新增两个 RPC（原生控制点直通，不做 Catmull-Rom）**：
- `makeBezierShapeFromControlPoints(ctrl, closed)`：`ctrl` = 扁平控制多边形（1+3n）；
- `drawBezierControlCurves(canvas, [{ctrl, closed}])`：造 + addItem。
（原来的 `makeBezierPathShape(points, closed)` / `drawBezierCurves` 仍保留，只适合演示/兜底。）

**服务端已改用拟合**：`ee_draw_function` 的每条分支、`ee_draw_figure` 的 `curves`/`beziers`
都先 `fit_bezier` 再走 `drawBezierControlCurves`（导入失败才退回 Catmull-Rom/折线）。
辅助脚本 `tools/make_curve_json.py <out.json> <expr> <x0> <x1> <ox> <oy> <scale> [tol]`
可直接生成“拟合好的控制点 JSON”，供 `File.readAllText` + `drawBezierControlCurves` 现场画。

### 8. EE「函数曲线」面板逆向（2026-10-19 深夜，未完成自动化）

EE 的原生函数图象入口：**绘图选项卡 → 「坐标轴和曲线」→ 函数曲线面板**（一个**非模态 #32770 对话框**，
不是模态框）。用户提示：面板预览里的**虚线框 = 可见区域/取值窗口**，图落在框外就“取不到”。

面板控件 id（用 `tools/ee_funcdlg.py dump` / `ee_win_tree.ps1` 读出，实测）：

| id | 类型 | 含义 |
|---|---|---|
| 5690 | Edit(多行) | `Y(x) =` 公式 |
| 5691 | Edit | 常量定义 |
| 5046 | Button(勾选) | 使用自定义变量域（勾上后 5000/5001 才可用） |
| 5000 / 5001 | Edit | 从 / 至（定义域，单位为数学单位） |
| 5047 | Button(勾选) | 输出为曲线对象（**不勾**才是原生函数图象，与轴联动） |
| 5832 | Button | 生成曲线 |
| 1 / 2 | Button | 确定 / 取消 |

**经验（重要）**：
1. 生成/插入**绑定在“画布编辑态”**：先点画布进入编辑，再打开面板，生成的图才会落到该画布；
   在后台（画布未激活）点「生成曲线」只会更新面板预览，画布链不新增对象（实测多次）。
2. **跨进程写不进去**：`WM_SETTEXT` 返回 0、`SetWindowTextW`/`WM_CHAR`（即使 AttachThreadInput+SetFocus）
   都改不了这些 Edit（MFC 只认真实键盘输入）。`tools/ee_funcgen.py` / `ee_dlg_type.py` 因此只能
   **读状态/点按钮**，不能填表。**结论：这一步必须由用户在面板里手动输入**。
3. 生成时若定义域没设好，曲线整体落在虚线框外 → 画布上什么都看不到（用户实测）。
4. EE 生成的函数图象对象：`esShapePath`(type 0x330f, Editer vtable 0x812044) + `esSegBezier`(0x4703)，
   且 **shape+0x44/+0x48 保存其坐标轴对象引用**（拖轴/缩放轴时图会联动）；这是 Es 编辑器私有类，
   eslib 工厂造不出来（`CreateObject(0x330f)` → system error），所以**不能用贝塞尔精确冒充**。
5. 原生半圆/圆弧没问题：`ee_draw_arc`（esSegArc 0x4306）用户已验收“半圆没问题”。
