# 阶段 2 队列（自底向上反编译）— 依赖序

> 约定：每批 = 一类（1–3 个关系紧的类）。规范来源优先取"单拷贝"模块（zoro）；
> 逐模块实例化的模板（zArray/zArrayBase/zList/zItem/zTypedMap）以 zoro 规范为基准，
> 其它模块的同名实例**做函数体等价核验**（大小+字节比对/抽样反编译），不重复出规格。
> 台账进度写入 `ledger/status-overrides.csv`；每批完成后更新本文件的 [x] 与 RE-STATUS.md。

## Tier 0 — zoro.dll 基础类型（批次 1–3 完成后暂停；当前优先 eslib 绘图核心 → 见 Tier 3）

| # | 目标 | 函数量 | 状态 |
|---|---|---|---|
| 0.1 | `zStringTemplate<char,ansi>/<wchar_t,unicode>` | 117 | ✅ 2026-10-17（spec: pseudo/zoro/zStringTemplate.md；L4 差分待做） |
| 0.2 | `zstr`/`zStringItem`/`zStringList`（遗留 ANSI 串族） | 24 | ✅ 2026-10-17（并入 zstr-legacy.md，含 zItem/zList<zStringItem> 实例） |
| 0.3 | `zwstr`/`zWstrArray`/`zWstrList`/`zWSharedString`（宽串族） | 58 | ✅ 2026-10-17（zstr-legacy.md；Q1–Q6 怪癖入册；待命名：FUN_10028e01/1000a130/1001c230） |
| 0.4 | `zMemory`（分配器身份核实：何时用 zrt_new/free/malloc） | 30 | ✅ 2026-10-17（并入 zserial.md；分配混用第三例：realloc/zrt_new/free） |
| 0.5 | `zStream` + `zFileSerializer` + `zFile`（序列化原语 → 直接服务 S4） | 65 | ✅ 2026-10-17（zserial.md；含变长长度编码格式） |
| 0.6 | **`zArchive`**（.wsd 序列化核心 → S4 关键） | 10 | ✅ 2026-10-17（zserial.md；双基接口 zStream/zBaseBuffer 已定） |
| 0.7 | `zArrayBase`/`zArray`/`zList`/`zItem`/`zDataItem`（容器；zoro 规范 43/12/31/15） | ~101 | ⬜ |
| 0.8 | `zRectTempl`/`zRect`/`zSize`（几何基元） | ~82 | ⬜ |
| 0.9 | `zXml*` 家族（Document/Element/Attribute/Node/Text/Comment/XmlString/Base） | 198 | ⬜ |
| 0.10 | `zTime`/`zThread`/`zThreadManager`/`zSharedMemory`（基建） | ~72 | ⬜ |
| 0.11 | `zSHA512`/`zEncoder`（编码/杂凑） | 30 | ⬜ |
| 0.12 | `zipArchive`/`zipFileItem`（zip 通道） | 31 | ⬜ |
| 0.13 | `sqDatabase`/`sqQuery`/`sqRecord`（内嵌 SQL 层，低优先级） | ~61 | ⬜ |
| 0.14 | zoro 剩余无名（551 个 `(none)`）普查：区分 CRT/三方/自研 | 551 | ⬜ |

## Tier 1 — eglib.dll 基础（绘图/GUI 底座）

| # | 目标 | 函数量 | 状态 |
|---|---|---|---|
| 1.1 | `eg_graphics::egGraphics`/`egPath`/`egPen`/`egBrush`/`egFont`/`egTransfromer`/`egSource` | ~240 | ⬜ |
| 1.2 | `eg_gui::GDC`/`egMemDC`/`egBmpDC`/`GBitmap`/`GPen`/`GBrush`/`GRgn` | ~140 | ⬜ |
| 1.3 | `eg_gi::*`（gradient/bitmap brush 族，疑似 D2D 封装） | ~100 | ⬜ |
| 1.4 | 低优先：`eg_pdf::*`（PDF 导出）、`eg_jpeg::CxImageJPG`（JPEG 解码，疑三方改）、`egMd5`/`egImgID` | ~180 | ⬜ |

## Tier 2 — eulib.dll 基础

| # | 目标 | 函数量 | 状态 |
|---|---|---|---|
| 2.1 | 容器实例拷贝核验：`zArrayBase<int>`/`zArray<*>...`（对 zoro 规范） | ~54 | ⬜ |
| 2.2 | `xRegistry`/`xItem`/`xBaseControlPanel` 等框架基类 | ~110 | ⬜ |
| 2.3 | UI 控件族（xTreeView/xToolbar*/xDialog/xMDIFrameWnd/xVisualManager…）→ 服务 Editer UI 层 | ~900 | ⬜ 排后 |

## Tier 3 — eslib.dll 叶子 → 核心（**当前重点**，用户 2026-10-17 指示优先）

> 批序（已议定）：基座 ✅ → 样式/笔刷 ✅ → seg 叶族 1/2 ✅ → seg 叶族 2/2（弧族）✅ → 标注 ✅ → 轴/曲线 ✅ → shape 族 ✅ → 画布核 ✅ → 文本排版 → 容器核验。

| # | 目标 | 函数量 | 状态 |
|---|---|---|---|
| 3.0 | `esSegBase`/`esSeg`/`esSegList`/`esSegObj`/`esSegItem(s)`/`esSegGemotry`（S1 基座；76 项类型字工厂表） | 147 | ✅ 2026-10-17（spec: pseudo/eslib/esSeg-base.md；Q1–Q10 + ILT 折叠表） |
| 3.1 | `esStyleSheet`/`esPenInfo`/`esBrushInfo`（S1 样式/笔/刷；`esSeg::Draw`→`esPenInfo::CreatePen` 入口） | 149 | ✅ 2026-10-17（spec: pseudo/eslib/esStyleSheet.md；19 子表布局/SFlags/序列化 §4/Q1–Q12） |
| 3.2 | seg 叶族 1/2：`esSegGon`/`esSegLine`/`esSegCircel`/`esSegPoint`/`esSegRect`/`esSegRectEx`/`esSegRoundRect`（S1） | 174 | ✅ 2026-10-17（spec: pseudo/eslib/esSeg-leaf.md；类型头 types/esSeg-leaf.h；Q-gon-1..3/Q-rect-1..2/Q-RoundRect-1..2/Q-circel-1..2/Q-point-1..3） |
| 3.2b | seg 叶族 2/2（弧族）：`esSegLines`/`esSegArcBase`/`esSegArc`/`esSegArc90`/`esSegCircels`/`esSegArcFace`/`esSegGonFace`/`esSegEllipseEx`（S1） | 142 | ✅ 2026-10-17（spec: pseudo/eslib/esSeg-arc.md；类型头 types/esSeg-arc.h；Q-lines-1/Q-arcbase-1..4/Q-arc-1..2/Q-arc90-1/Q-circels-1/Q-arcface-1..2/Q-gonface-1..2/Q-ellipseex-1） |
| 3.3 | `esSegLable` 全链 + `esLableBox` + `esLableBoxEx`（S5；动态侧 k-字模型作差分基准） | 72（62+Ex 10） | ✅ 2026-10-17（spec: pseudo/eslib/esSeg-lable.md；类型头 types/esSeg-lable.h；Q-lable-1..10/Q-lablebox-1..6/Q-lableboxex-1..2；undo 0xa01/0xa0a/0xa0b/0xa0f/0xa10/0xa11/0xa12） |
| 3.4 | `esSegAxis`(0x5006)/`esSegCurve`(0x4708)/`esSegBezier`(0x4703)（S6；解释"渲染坏"根因） | 112 | ✅ 2026-10-17（spec: pseudo/eslib/esSeg-axis.md；类型头 types/esSeg-axis.h；含 esSegSimpleAxis/esSegSimpleSingleAxis/esSegFreeBezier；Q-axis-1..9/Q-bez-1..9/Q-sax-1..8；undo 0xb11/0xc21..0xc54/0xf2dc..0xf2ef） |
| 3.5 | `esShapeBase`/`esShapePath`/`esShapeLine`/`esShapeCap`/`esShapeGroup`…（S1） | 253 | ✅ 2026-10-17（spec: pseudo/eslib/esShape.md；类型头 types/esShape.h；含 §4.1 重段型表/§6 撤销码；Q-shape-15..23；undo 0x502/0x50d/0x520..0x523/0x601/0x602/0x804/0xf006/0xf0b..0xf2f1） |
| 3.6 | `esCanvas`/`esEmbedder`（S3 画布核；含撤销 Undo/Undata 码表、变换三通道、边框点协议、导出族、自毁协议） | 269（245+24） | ✅ 2026-10-17（spec: pseudo/eslib/esCanvas.md；类型头 types/esCanvas.h；269/269 机检；Q-canvas-1..30；undo 0x202/0x204..0x212/0x216/0x209/0x20a/0x20b/0x20e/0x210/0x511f/0x523/0xf005/0xf006/0xf2f1） |
| 3.6b | `esPageList`/`esCanvasList`/`esCanvasState`（S3 页面/列表层） | 152（101+37+14） | ⬜ |
| 3.7 | `esTextUI`/`esPara`/`esTextLine`/`esEQLine`/`esFormulaBox`（S2） | — | ⬜ |
| 3.8 | 容器实例核验（zArrayBase 73/zList 37/zItem 20/zTypedMap 17） | 147 | ⬜ |

## Tier 4 — Editer.exe UI/文档层（S7）

| # | 目标 | 状态 |
|---|---|---|
| 4.1 | 调用面普查（导入表 × eslib/eulib/zoro/eglib 导出名对齐） | ⬜ |
| 4.2 | 命令层 `xCommandParameters`/`esStage::ExecuteCommand` → 命令 ID 表 | ⬜ |
| 4.3 | 文档/视图/存盘（.wsd 打开保存路径） | ⬜ |

## 横切任务

- [ ] 容器拷贝等价核验工具（比较同名函数跨模块字节/大小；写入 ledger notes）
- [ ] 将已完成布局类写入 Ghidra 结构体并套用（zStringTemplate 12B 优先）
- [ ] L4 差分框架设计：`tools/verify/`（zoro 类可用 Frida 调 zoro 导出直接对拍）
- [x] 命名回写通道：`tools\ghidra-scripts\RenameList.java`（csv → USER_DEFINED；已跑通 7 个 `zrt_*`，含重导回流台账）
- [x] status-overrides 机制：`ledger\status-overrides.csv` + re_ledger `overrides_valid` check（1,635/1,635 = zStringTemplate 117 + zrt 7 + zstr 88 + zserial 105 + esSeg 基座 147 + esStyleSheet/笔/刷 149 + esSeg 叶族 174 + 弧族 142 + 标注族 72 + 轴/曲线族 112 + 形状核族 253 + 画布核族 269；幂等已验）
