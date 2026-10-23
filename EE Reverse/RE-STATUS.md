# RE-STATUS — EduEditer 逆向工程状态板

> 更新：2026-10-17 · 本轮变化：**阶段 2 第十一批完成**（eslib 画布核族 269 个：esCanvas 245 · esEmbedder 24）——S3 画布/嵌入打通：撤销分发 Undo/Undata 码表-码翻转对（0x202 · 0x204..0x207 · 0x208 · 0x20e · 0x210 · 0x212 · 0x216 · 0x209 · 0x20a↔0x20b · 0x214↔0x215 · 0x523 · 0xf005↔0xf006 · 0xf2f1 · 0x511f）+ 变换三通道（Graphics 平移+矩阵合并 / egGraphics TranslateTransform+Multiply / GDC 克隆+epModifyDeviceTransfrom；ToExternal 内→外 / ToInternal 求逆） + 边框点差分流（AddBorderPoint 0x20a · DelBorderPoint 0x20b · 轮廓 undo 0x209）+ 导出族（skip 0x7000 · min-101 · dotmap=esShapeLine(pt,0x6001) · 无 alpha 褪白）+ 嵌链插入语义（AddItem 头插 vs Insert 反向）+ 宿主映射（host+0x40 vs +0x81）+ 自毁协议（EraseSelectedItems ▸ 0xf2f1）；产出 `analysis\pseudo\eslib\esCanvas.md` + `analysis\types\esCanvas.h`（269 RVA 机检全对齐 OK 269/269）；status-overrides **1635/1635** 应用、幂等复验；台账 113,883 行不变，5 项 checks 全 PASS；基线本轮复验 ALL-MATCH（5/5）
> 每轮工作循环：读本板 → 校验基线哈希（`tools\re_baseline_verify.ps1`）→ 取"下一步"第一条 → 只推进一类 → 落盘 → 回填"变化"列

## 0. 基线（不可变契约）

**状态：✅ ALL-MATCH（5/5，2026-10-17 12:01 复验；证据：`analysis\RE-BASELINE.json`）**

| id | 目标 | 大小 (B) | sha256 | 状态 |
|---|---|---|---|---|
| T1 | Editer.exe | 5,383,168 | 3B12A439…EE2D8 | ✅ MATCH |
| T2 | eslib.dll | 7,273,984 | 3AD0831A…3FA0F | ✅ MATCH |
| T3 | eulib.dll | 1,065,984 | ECA35D2C…37075E | ✅ MATCH |
| T4 | zoro.dll | 284,672 | 1B06570B…15C22 | ✅ MATCH |
| T5 | eglib.dll | 765,952 | D826FCB7…C7EC0 | ✅ MATCH |

- 复验命令：`powershell.exe -NoProfile -ExecutionPolicy Bypass -File "D:\EE Reverse\tools\re_baseline_verify.ps1"`（幂等；退出码 0=全对，2=异常）
- **不匹配协议**：本行改记 **BASELINE-MISMATCH** → 既有结论全部降级 stale → 停止深挖，等用户重新确认基线。
- B 类（第三方：ffmpeg 系列/SDL2/sqlite3/zip/zlib/运行时库等）：只识别 + 分层标 `external`，不逐函数反编译。

## 1. 分层验收指标（L1–L5）

| 层 | 口径 | 已完成 | 分母 | 状态 |
|---|---|---|---|---|
| **L1 清单** | 每个函数/导出/虚表/字符串引用全登记进台账 | ✅ 100%：函数 68,737 + 导出 21,801 + 字符串 39,143 + 虚表 5,645 + xrefs 全量回填 | 同左 | ✅（5 项 checks 全 PASS，含 overrides_valid） |
| **L2 归属** | 每函数归属到类/模块；每导出落类 | 模块 100%（113,883 行全带模块）；导出 demangle 21,801/21,801；类 21,751 | 44,463 具名函数 | 🟡 48.9%（owner_class 非空口径重算；批次 1 回写 +7；批次 7–8 复测 21,751 不变——新族 owner 已在 L1 demangle 计入；剩余增长依赖命名回写） |
| L3 类型 | 跨模块核心类字段布局表（analysis\types\*.h） | 11（zStringTemplate 12B · 遗留字符串族 6 类 · 序列化栈 6 类 · esSeg 基座 7 类 + 76 类型字 · 样式/笔/刷 3 类 + SFlags/刷类型码 · seg 叶族 7 类 + 交互模式族 · 弧族 8 类 + 三点定圆/弧拆分/环带 · 标注族 3 类 + 三段文本/位置码/布置族 · 轴/曲线族 6 类 + 3n+1 控制点/刻度模型 · 形状核族 5 类 + 段表链/刷-液-亮三件套/组矩阵层/组工厂尺寸表 · 画布核族 2 类 + 撤销-重做码翻转对/变换三通道/边框点差分流） | S1–S7+基础类 | 🟡 起步（`zStringTemplate.h`、`zstr-legacy.h`、`zserial.h`、`esSeg-base.h`、`esStyleSheet.h`、`esSeg-leaf.h`、`esSeg-arc.h`、`esSeg-lable.h`、`esSeg-axis.h`、`esShape.h`、`esCanvas.h`） |
| L4 行为 | 核心子系统差分验证规格（tools\verify） | **0** | S1–S7 | ⬜ 未开始 |
| L5 未知 | Residual-Unknown 台账（RE-UNKNOWNS.md）与 L1 对齐 | **0** | — | ⬜ 未开始 |

判定：L1–L2 必须 100%；L3–L4 核心子系统 100%；L5 须与 L1 对得上。

## 2. 核心子系统矩阵（S1–S7）

| 子系统 | 关键对象 | L1/L2 | L3 | L4 | 备注 |
|---|---|---|---|---|---|
| S1 绘图对象模型 | esShapePath/esSeg*/esStyleSheet/esPenInfo | 🟡 | 🟡 基座 147 + 样式/笔/刷 149 + seg 叶族 174 + 弧族 142 + 标注族 72 + 轴/曲线族 112 + 形状核族 253 | ⬜ | esSeg 基座 + esStyleSheet/esPenInfo/esBrushInfo + 叶段族 7 类 + 弧族 8 类 + 标注族 3 类 + 轴/曲线族 6 类已入库（字段布局/交互吸附族/弧拆分/三点定圆/环带/三段文本/布置族/两臂基点轴模型/3n+1 控制点/撤销码）；形状核族（esShapeBase/Line/Cap/Path/Group）已入库（段表链/填充刷-液-亮三件套/重段型表/组矩阵层/组工厂尺寸表/Q-shape-15..23）；seg 叶族全部完成；动态侧观察作线索 |
| S2 文本排版 | esTextUI/esPara/esTextLine/esEQLine/esFormulaBox | ⬜ | ⬜ | ⬜ | 同上（标注/EQLine 行为已实测观察） |
| S3 画布与嵌入 | esCanvas/esEmbedder/esPageList | 🟡 | 🟡 画布核族 269（esCanvas 245 + esEmbedder 24） | ⬜ | esCanvas/esEmbedder 已入库（撤销分发 Undo/Undata 码表-码翻转对/变换三通道 Graphics/egGraphics/GDC/边框点协议/导出族阈值/宿主映射 host+0x40 vs +0x81/自毁协议 Q-canvas-1..30）；余 esPageList/esCanvasList/esCanvasState（152）→ 队列 3.6b；动态侧 bridge 画布操作事故即差分验证用例 |
| S4 .wsd 文档格式 | 序列化/zArchive/字体表/存盘撤销 | ⬜ | ⬜ | ⬜ | recon\wsd_probe.py 有初步结构结论；**zserial 规格已入库**（zStream/zBaseBuffer/zMemory/zArchive/zFile/zFileSerializer + 字符串变长编码 + zMemory::Serialize 盘格式），余：字体表/存盘/撤销 |
| S5 标注与公式 | esSegLable ctor/Initialize/Build/RecalcLayout | 🟡 | 🟡 标注族 72（三段文本/属性组 0xa00/位置码/布置族） | ⬜ | 标注族已入库（esSegLable + esLableBox/Ex；Q-lable-*/Q-lablebox-* 待 L4 差分）；余 esDS_HV/esScriber/esFormulaBox 文本项（3.7）；动态侧 k-字模型等观察可作验证规格（步骤 4） |
| S6 坐标轴与曲线 | esSegAxis 0x5006 / esSegCurve 0x4708（/0x4703） | 🟡 | 🟡 轴/曲线族 112（esSegAxis 36 · Bezier 28 · SimpleAxis 17 · SimpleSingleAxis 13 · Curve 9 · FreeBezier 9） | ⬜ | 轴/曲线族已入库（两臂基点 + RevX/RevY 置换 + 三角波刻度 + 3 标签盒 + 3n+1 贝塞尔 + Catmull-Rom 升级 + 随手画采样 + 刻度尺三级刻度长 + Q-axis/Q-bez/Q-sax）；动态侧"渲染坏"的事故即差分验证用例（原生 Bezier 挂画布坏链与 0x8123 毒哨兵对照） |
| S7 模块边界 | Editer ↔ eslib/eulib/zoro/eglib 调用面 | ⬜ | ⬜ | ⬜ | Editer.exe 无导出；靠 Ghidra 函数 + 导入面 |

## 3. 现有资产（★ 一律视为"线索"，挂上 evidence 并入 ledger 后才升级为"结论"）

- `recon\*_exports.txt`：eslib 16,123 / eulib 3,305 / zoro 1,536 / eglib 837 条导出（line 数=条目+2 行头；对账完成）
- **`ledger\`（L1 台账，re_ledger.py 幂等生成）**：`ledger.csv` **113,883 行**（68,737 函数 + 1,472 独立导出 + 38,803 字符串 + 4,871 虚表）、`exports.csv` 21,801 条（合并 20,329、独立 1,472）、`functions.csv` 68,737 条、`unresolved-mangling.csv` **0 条**、`manifest.json`（26 个输入哈希 + 统计 + 5 项 checks 全 PASS）
- 本轮新工具：`tools\re_ledger.py`、`tools\ghidra-scripts\ExportFunctions.java`、**`ExportSupplement.java`**（xrefs/调用边/字符串/虚表一次导出）、**`DemangleList.java`**（全量 demangle）、`tools\re_baseline_verify.ps1`；补充数据在 `ledger\raw\`（5×3 + demangled.csv）
- 阶段 2 新资产（2026-10-17）：`ledger\status-overrides.csv`（**1635 条**：zStringTemplate 117 + zrt_* 助手 7 + 遗留字符串族 88 + 序列化栈 105 + esSeg 基座 147 + esStyleSheet/笔/刷 149 + seg 叶族 174 + 弧族 142 + 标注族 72 + 轴/曲线族 112 + 形状核族 253 + 画布核族 269；re_ledger 第 5 项 check `overrides_valid`）· `tools\ghidra-scripts\RenameList.java`（批量改名回写 Ghidra，csv 在 `analysis\renames\`）· `analysis\pseudo\zoro\`：zStringTemplate.decomp.txt（117）· zrt-helpers.decomp.txt（7 助手）· zstr-legacy.decomp.txt（88）· zserial.decomp.txt（105） + 规格 md ×3 + `analysis\types\` 类型头 ×3 · **`analysis\pseudo\eslib\`：esSeg-base.decomp.txt（147）+ esStyleSheet.decomp.txt（149）+ esSeg-leaf.decomp.txt（174）+ esSeg-arc.decomp.txt（142）+ esSeg-lable.decomp.txt（72）+ esSeg-axis.decomp.txt（112）+ esShape.decomp.txt（253）+ **esCanvas.decomp.txt（269）+ 规格 md ×8 + `analysis\types\`（esSeg-base.h / esStyleSheet.h / esSeg-leaf.h / esSeg-arc.h / esSeg-lable.h / esSeg-axis.h / esShape.h / esCanvas.h）（S1 基座 + 样式/笔/刷 + seg 叶族 1/2 + 弧族 2/2 + 标注族 S5 + 轴/曲线族 S6 + 形状核族 S1 + 画布核族 S3）** · 队列 `analysis\phase2-queue.md` · 盘点 `analysis\phase2-inventory-base.txt`
- `recon\analyse_exports.py` / `peinfo.py` / `probe.py` / `wsd_probe.py`：现成解析脚本
- Ghidra：`analysis\ghidra-proj\`（**EEediter / EEeslib / EEeulib / EEzoro / EEeglib 五工程全部已分析**）；脚本 `tools\ghidra-scripts\`（DumpDecomp / FindVtableCtor / SymAddr / **ExportFunctions / ExportSupplement / DemangleList**）
- `analysis\decomp-*.txt`（14 件 ≈57k 行反编译线索）、`EP_*`/`note*.txt` 等既有笔记
- 文档：AGENTS.md（铁律）· notes\00/01/02 · analysis\figures-progress.md（动态行为观察库）
- 动态桥：bridge\ee_bridge.js + mcp-server\ee_mcp_server.py（ee-draw MCP，可做差分验证）
- 工具环境：Ghidra 12.1.4（`tools\ghidra_12.1.4_PUBLIC\support\analyzeHeadless.bat`），JAVA_HOME=`D:\java`；REA MCP（serverName `rea`）作静态交叉核对

## 4. L1 台账执行计划 — 状态与下一步

**已完成（2026-10-17，1 轮）**：A1 `ExportFunctions.java` ✅ → A2 EEeslib/EEediter 导出 ✅ → A3 EEeulib/EEzoro/EEeglib 导入+导出 ✅ → B1 `re_ledger.py`（checks 全 PASS、幂等已验）✅ → B2 本板回填 ✅

**产出**：`ledger\ledger.csv` 70,209 行 = 68,737 函数 + 1,472 独立导出；导出 21,801 条 = 合并进函数 20,329（含 2,975 条同址多名别名） + 独立 1,472（vtable 774 / data 698）；thunk 2,315；未解 mangle 5（全为函数内 local-static，`unresolved-mangling.csv` 单列 triage）；**无任何"导出函数在 Ghidra 中缺函数"的缺口**（standalone function-like = 0）。

**L1 收尾（2026-10-17 第二轮，全部完成 ✅）**：
1. ✅ `ExportSupplement.java`（合并原 1–3 项）：xrefs 68,737/68,737 回填（total 调用边 187,768 条落 `*_callees.csv`）、字符串 39,143、虚表扫描 5,645（**774 个导出虚表 100% 匹配**）→ `ledger\raw\`。
2. ✅ 字符串行入台账（`#str`：38,803 新增 + 340 合并进既有 data 行）。
3. ✅ 非导出虚表入台账（`#vt`：4,871 新增；条目数 + 前 6 函数 RVA 入 notes）。
4. ✅ `DemangleList.java`：21,801/21,801 demangle 成功（0 失败）；5 条 local-static 结构解析提类（BD2DMatrix / zTypedMap / zStringTemplate）→ unresolved **0**。

**阶段 2 第一批（2026-10-17，zStringTemplate）✅**：
1. ✅ 反编译 117/117（char 61 + wchar 56）→ `analysis\pseudo\zoro\zStringTemplate.decomp.txt`；布局 +0x00 data/+0x04 len/+0x08 cap（字符数、含 NUL 槽）已定，与 zBuffer 同布局（ILT 折叠）。
2. ✅ 7 个 zoro 运行时助手身份确认（zrt_strlenA/strcmp/stricmp/strstr/strchr/wcslen/new）→ `RenameList.java` 回写 Ghidra → 重导 `zoro_functions.csv` → 回流台账（7 行）。
3. ✅ `status-overrides.csv` 机制：117+7 条 status=decompiled，`overrides_valid` PASS，124/124 应用；幂等复跑 skip 通过。
4. ✅ 规格/类型/队列落盘：`analysis\pseudo\zoro\zStringTemplate.md`、`analysis\types\zStringTemplate.h`、`analysis\phase2-queue.md`（Tier 0.1 [x]）。
   遗留（本类收尾项）：Q1–Q4 怪癖（SetAt 置 len=1 / Trim* 只去 1 空格 / ctor NULL+p 复位 len / new+free 混用）待 L4 差分；Ghidra 结构体套用待做。

**阶段 2 第二批（2026-10-17，遗留字符串族 0.2/0.3）✅**：
1. ✅ 反编译 88/88（zstr 15 · zwstr 18 · zWSharedString 6 · zWstrArray 12 · zWstrList 22 · zStringItem/zStringList 9 · 模板实例 6）→ `analysis\pseudo\zoro\zstr-legacy.decomp.txt`。
2. ✅ 结构结论：zstr/zwstr=zStringTemplate 薄子类；zWSharedString=refcount 缓冲（8B 对象，vptr+buffer）；zWstrArray=zTypedPtrArray<wchar_t> 派生（虚表 dtor/Add/Insert/SetAt）；zWstrList=zSection 锁 + 侵入式双向链表（节点 20B=zwstr+next+prev，+0x14 哨兵）；zStringItem=zItem 派生（0x18B，CRT malloc，无 cap）。
3. ✅ 6 处怪癖入册（wide 截断转换/cap=len、ANSI 单字符丢失、free 混用、Load 末段、SetAt 无锁、Find 忽略起点）+ 3 个待命名助手清单（FUN_10028e01=疑 operator delete、FUN_1000a130=std::string::length、FUN_1001c230=链表节点构造）。
4. ✅ 规格/类型落盘：`analysis\pseudo\zoro\zstr-legacy.md`、`analysis\types\zstr-legacy.h`；status-overrides 212/212；幂等 skip 复验。
   新线索：Editer.exe 存在 `ZORO.DLL::zWstrArray::Add/Insert/SetAt` 导入 thunk（RVA 0x2542d8 等 3 个）→ Editer 直接虚调该容器，S7 调用面普查时用。

**阶段 2 第三批（2026-10-17，序列化栈 0.4/0.5/0.6）✅**：
1. ✅ 反编译 105/105（zMemory 30 · zStream 34 · zFile 18 · zFileSerializer 13 · zArchive 10）→ `analysis\pseudo\zoro\zserial.decomp.txt`。
2. ✅ 结构结论：**双基接口** —— `zStream`（前端，vtbl+8=WriteRaw/+0xC=ReadRaw，+4=mode）vs `zBaseBuffer`（后端，vtbl+4=GetBufferSize/+8=GetPosition/+0xC=Seek/+0x10=Read/+0x14=Write）；zArchive=前端+任意后端适配、zFileSerializer=前端+内嵌 zFile+写缓冲、zMemory/zFile=后端实现；zMemory 12B 起（+4 step/+8 data/+0xC size/+0x10 cap/+0x14 pos/+0x18 refs）；zFile +4=HANDLE(+8 脏标志)。
3. ✅ **S4 格式**：zStream 字符串变长长度编码（1B / FF+16 / FF FF FF+32 / FFFFFFFF 哨兵；宽前缀 FF FE FF）读写一致；`zMemory::Serialize`=[len16] 或 [FFFF+len32]+原始 blob；EndLine=CRLF/L"\r\n"；WriteText 宽=字节×2。
4. ✅ 6 处怪癖入册（Q1 Write 恒返 0 / Q2 handle 判据 0 vs -1 / Q3 GetBuffer 置 size / Q4 seek-end 减法 / Q5 zArchive::Close 仅解绑 / Q6 Insert memmove 伪影待核）+ 第三例分配混用（realloc/zrt_new/free）。
5. ✅ 规格/类型落盘：`analysis\pseudo\zoro\zserial.md`、`analysis\types\zserial.h`；status-overrides 317/317；幂等 skip 复验。

**阶段 2 第四批（2026-10-17，eslib 绘图基座 esSeg 族 · 用户指示转 eslib 优先）✅**：
1. ✅ 反编译 147/147（esSeg 77 · esSegList 37 · esSegBase 14 · esSegGemotry 8 · esSegObj 5 · esSegItem(s) 6）→ `analysis\pseudo\eslib\esSeg-base.decomp.txt`。
2. ✅ 结构结论：谱系 esGraphObject→esSegBase→esSeg→具体段类；持有链 amulet `esSeg ↳ esSegList(0x2030) ↳ esShapePath(0x330f) ↳ esCanvas(0x2020)`；esSeg +0x58 控制点/+0x5C 数/+0x60 逐点标志(0断1线3贝)/+0x64 别名；esSegList head/tail 侵入链（0x44）。
3. ✅ **S1 工厂表**：`esSeg::Create` 76 项「类型字→类/尺寸」；未知类型抛异常（非返回空）；`GetPtsObj` 4 类尺寸标注特判待后续批。
4. ✅ 序列化 §7：esSeg=[类型字16][矩阵(可选)][点数16][原始字节点]；esSegList=[计数32][段流]（旧档 roleSheet 门 <0x1070612）。undo 码 0x524（首段切换）/0xf2dc（控制点差分）。
5. ✅ 10 处怪癖 Q1–Q10 入册（含 Q7：0x8123 毒化哨兵新旁证 GetJiaoCount）+ ILT/COMDAT 折叠表 10 地址（防误读导入面）。
6. ✅ 规格/类型落盘：`analysis\pseudo\eslib\esSeg-base.md`、`analysis\types\esSeg-base.h`；status-overrides 464/464；幂等 skip 复验。
   未命名候选：0x6002（尺寸 0x74）/0x4285（0x7c）两个工厂类。

**阶段 2 第五批（2026-10-17，eslib 样式中枢 esStyleSheet/esPenInfo/esBrushInfo）✅**：
1. ✅ 反编译 149/149（esStyleSheet 103 · esBrushInfo 34 · esPenInfo 12）→ `analysis\pseudo\eslib\esStyleSheet.decomp.txt`。
2. ✅ 结构结论：esStyleSheet = **组合对象**（+0x000 esFontSheet 起 19 个内嵌子表 → +0x840 esStrRes → +0x850 版本 0x2000837 → +0x858 考试样式 → +0x874/878 +0x994 隐藏系统 → +0x908/0x940/0x958 列表 → +0x9B8 enmSMode → +0x9BC SFlags → +0x9C0 共享 scratch 模型）；ee-draw `caretContext().fontSheet == styleSheet` 同体得证（字体表即 +0x000）。
3. ✅ **SFlags 位→子表全表** + 序列化管线：双写校验（读侧不等即清 + 抛 Q8）、imageSheet 双版本门（Q9）、SetLoadingSFlags 版本门控掩码、`"EduerParaSyles"` 文件头（原文拼写）、esBrushInfo 版本 ≥0x81 + 内嵌图。
4. ✅ esPenInfo 单位 **1/400mm**（默认宽 0x50=80=0.2mm ↔ ee-draw `pen_mm 0.25`→100 的由来）；CreatePen 文本框分支调试绿 0xff007f00（Q11）。esBrushInfo 类型码（0/1/2/0x13/0x14/0x15/0x16）+ 三掩码 bit24 哨兵（Q7）+ α 编码 `|0xff00`（Q6）+ FillRectEx 栈上整建 esStyleSheet（Q10）。
5. ✅ 怪癖 Q1–Q12 入册（含 Q1 共享 scratch +0x9C0 覆盖语义、Q12 ToModel 忽略 compos）+ 折叠表（0x18c0 penInfo ctor≡op=≡imageModifiers move=；子表赋值全走 esBlockSheet::operator=）。
6. ✅ 规格/类型落盘：`analysis\pseudo\eslib\esStyleSheet.md`、`analysis\types\esStyleSheet.h`；status-overrides 613/613；幂等 skip 复验。

**阶段 2 第六批（2026-10-17，eslib 绘图叶段族 1/2 · seg 基本形）✅**：
1. ✅ 反编译 174/174（esSegGon 38 · esSegRect 35 · esSegCircel 31 · esSegRoundRect 24 · esSegLine 23 · esSegPoint 13 · esSegRectEx 10）→ `analysis\pseudo\eslib\esSeg-leaf.decomp.txt`。
2. ✅ 结构结论：谱系 `esSegLines→esSegGon→esSegLine`（Gon 是 Line 父类）/ `esSegNative→esSegPoint` / `esSegGemotry→esSegRect→esSegRectEx`、RoundRect、Circel；**类型字任意化**——esSegLine 0xe100..0xe10b、esSegCircel 0xe280..0xe289 两族交互吸附模式（SetPointPos 按 type 分派，落定后复位）；Rect/RoundRect 锁定比（+0x6c s；四半径=min(|W|,|H|)/4）；RoundRect 12 顶点环（侧中点 0..3 + 角弧点 4..11，直段每段一个 esSegGon、角弧 esSegArc）；Circel 布局（+0x68 r / +0x6c 角 / +0x70 心 / +0x78 closed + 两端点）；esSegPoint 点尺寸=宿主 esShapeLine 笔宽（min 50 单位）——与 ee-draw dots 通道吻合。
3. ✅ 撤销码入册：0xf2e8/0xf2ee/0xf2ef/0xf2ff（Gon 点增删/旋转）、0xf2dc（MovePointTo）、0xf2d0/0xf2d3/0xf2d6（Circel 角/r/心）、0xf2f8（RoundRect 半径块）、0x2201/0x2202（Rect 样式/比）、0x5fe（RectEx 尺寸交换）。
4. ✅ 12 处怪癖 Q-gon-1..3 / Q-rect-1..2 / Q-RoundRect-1..2 / Q-circel-1..2 / Q-point-1..3 入册（0x8123 毒哨兵、SetRound 越界读 0x14/0x18、DoSnap pts[−1]、IsEqual 与对方 r 比较、圆破弧强制 0x4307 等，均待 L4 差分）。
5. ✅ 规格/类型落盘：`analysis\pseudo\eslib\esSeg-leaf.md`、`analysis\types\esSeg-leaf.h`；status-overrides **787/787**；幂等 skip 复验。

**阶段 2 第七批（2026-10-17，eslib 绘图弧族 · seg 叶族 2/2）✅**：
1. ✅ 反编译 142/142（esSegArcBase 34 · esSegArcFace 23 · esSegArc 18 · esSegLines 15 · esSegCircels 15 · esSegGonFace 15 · esSegArc90 13 · esSegEllipseEx 9）→ `analysis\pseudo\eslib\esSeg-arc.decomp.txt`。
2. ✅ 结构结论：谱系 `esSegLines→esSegArcBase→{esSegArc, esSegArc90}`、`ArcBase→esSegGlow→esSegCircels`、`esSegGon→esSegGonFace`、`esSegArcFace` 直派 esSeg（与 esSegArcRuler 同址折叠）、`esSegEllipseEx : esSegEllipse`；弧族双表示（3 控制点 + r/dir/a0/a1/center/mid；退化 |r|<1e−5 时角度字段存坐标）；类型字 0x42c1/0x4306（双角）/0x4307（单角，整圆语义）三位一体；三点定圆 GetCircleOrg（静态）；断口拆链 esSegLines::BreakLine；弧面环带（幅宽 500=1.25mm + 翻向）与圆环组（环距默认 0x4b0=3mm，属性流 >>2）。
3. ✅ 撤销码入册：0xf2d1/0xf2d2/0xf2d3/0xf2d5/0xf2d6（a0/a1/r/dir/center）、0xf2d4（Circels 内半径）、0xf2e8（Lines type）、0xf2ff（ArcFace 循环首点）、0x1a01/0x1a02（幅宽/翻向）。
4. ✅ 14 处怪癖入册：Q-lines-1 · Q-arcbase-1..4 · Q-arc-1..2 · Q-arc90-1 · Q-circels-1 · Q-arcface-1..2 · Q-gonface-1..2 · Q-ellipseex-1（含 GetMidAngle 就地取正副作用、MovePoint_3Points 直写坐标、DoSnap 双 SnapObj、ctor float 参数序推断等，均待 L4 差分）。
5. ✅ 规格/类型落盘：`analysis\pseudo\eslib\esSeg-arc.md`、`analysis\types\esSeg-arc.h`（142 个 RVA 全注释）；status-overrides **929/929**；幂等 skip 复验。

**阶段 2 第八批（2026-10-17，eslib 标注族 · S5 起步）✅**：
1. ✅ 反编译 72/72（esSegLable 28 · esLableBox 34 · esLableBoxEx 10）→ `analysis\pseudo\eslib\esSeg-lable.decomp.txt`。
2. ✅ 结构结论：标签三段文本模型（Part1/2/3 + 段长字节 0x70..0x72；分数式双盒 0x160000c2/0x16000041/0x16000081）；内嵌 EQLine@+0x80；属性组 0xa00（a01..a0e）；位置码（+0x73 低半字节九宫格 + +0x74 高半字节自定义六向 + floats）；特性字（GetLableFreature 槽<<16|位域|MathCharType 累加位；OnMessage 0x113）；标注框 8 槽点协议（0–4 盒、>5 引线）+ 布置族（CCD/CCD_TB/Any/BJ/GongCa/YX/ZJ/Paren + Ex 的 CVL/CHL）；标注样式面 esDS_Txt（+0x10&0x1000 边框 / +0x14 填充）。
3. ✅ 撤销码入册：0xa01（槽/色/字体）· 0xa0a/0xa0b/0xa0f（+0x74/0x6C/0x73）· 0xa10（文本数据）· 0xa11/0xa12（+0x78/0x7C floats）。
4. ✅ 21 处怪癖入册：Q-lable-1..10（IsEqual 0x7C↔param+0x78 笔误、圆点半径 Load 5/2 vs Draw 2 笔宽、0x8123 死存再现、operator= 浅拷文本指针、GetTextData 消费性、Build pt[5] 相位 等）· Q-lablebox-1..6（Build 不写 pts[5]、Qiujiao 返回全宽、+0x4C Matrix/CComBSTR 双解、GongCa 51 阈值 等）· Q-lableboxex-1..2（IsEqual 副作用写 +0x5C、CVL/CHL 地址夹层），均待 L4 差分。
5. ✅ 规格/类型落盘：`analysis\pseudo\eslib\esSeg-lable.md`、`analysis\types\esSeg-lable.h`（72 个 RVA 全注释，机检 72/72 对齐 inventory）；status-overrides **1001/1001**；幂等 skip 复验。

**阶段 2 第九批（2026-10-17，eslib 轴/曲线族 · S6 起步）✅**：
1. ✅ 反编译 112/112（esSegAxis 36 · esSegBezier 28 · esSegSimpleAxis 17 · esSegSimpleSingleAxis 13 · esSegCurve 9 · esSegFreeBezier 9）→ `analysis\pseudo\eslib\esSeg-axis.decomp.txt`。
2. ✅ 结构结论：坐标轴=两臂基点模型（ctrl pts[0] 基点 / pts[1]/pts[2] 两臂端；RevX/RevY 置换取端；三角波刻度每齿 250·净推进 500）；esAxisObj 0xDC 内嵌 @+0x6c + 3 标签盒（+0x148/14c/150）+ 偏移三对（+0x154）+ 退化位 0x46；贝塞尔 3n+1（锚+双柄三连组；InsertPoint1 重叠 2 点扩段 / InsertPoint2 纯 3 点块 / GetCtlPts 三模式 0x98630000/0xa8640000 柄掩码）；平滑曲线 Catmull-Rom 式 get_curve（d2/d3 重心参数化）；随手画 FreeBezier（mode1 采样追加 ≤3 点/步、mode2 FitToBezierA 抽稀）；单线/十字刻度尺（GetBiaociPts 三级刻度长 400/300/200、中刻度位 step==10?5:1、刻度位 0x70 默认单线=1/十字=0）。
3. ✅ 撤销码入册：0xb11（标签拖拽）· 0xc21..0xc3a / 0xc53（轴属性流）· 0xc48/0xc49（标签盒增删）· 0xc51/0xc52/0xc54（轴对象字节交换/存盘差分）· 0xf2dc / 0xf2ea↔0xf2eb / 0xf2ec↔0xf2ed / 0xf2ef（贝塞尔/曲线点增删）。
4. ✅ 怪癖入册：Q-axis-1..9（className 错名×2 · op= 盒浅拷贝 · 三角波重叠 · GetTBOrg 置换取端 · GerDrawFlags 双语义 · +0x46 四位一体 · MoveAcmePoints DWFont · GetLbcLines +0x6a · Undo 默认 CaretMove）· Q-bez-1..9（count−=4 笔误 · 柄拖邻锚 2×delta · 3k+1 修补 · 0x8123 死存 · 吸附反直觉 · 柄折回锚 · 张力常量 · 插点 undo 异源 · 四常量采样）· Q-sax-1..8（pts[1]=(x,x) · 刻度位默认 · 三级刻度长 · 2000 边距 · 逗号 max · 保序夹紧 · 柄逆序 · cross 比较），均待 L4 差分。
5. ✅ 规格/类型落盘：`analysis\pseudo\eslib\esSeg-axis.md`、`analysis\types\esSeg-axis.h`（112 个 RVA 全注释，机检 112/112 对齐 inventory）；status-overrides **1113/1113**；幂等 skip 复验。

**阶段 2 第十批（2026-10-17，eslib 形状核族 · S1 完整化）✅**：
1. ✅ 反编译 253/253（esShapePath 74 · esShapeGroup 79 · esShapeBase 58 · esShapeLine 24 · esShapeCap 18）→ `analysis\pseudo\eslib\esShape.decomp.txt`（机检 253/253 对齐 inventory），规格 `analysis\pseudo\eslib\esShape.md`、类型头 `analysis\types\esShape.h`（253 个 RVA 全注释）。
2. ✅ 结构结论：谱系 esShapeBase→{esShapeLine 0x3109 / esShapeCap 0x320b→{esShapePath 0x330f / esShapeGroup 0x3008}}；Path 段表链（esSegList 0x44；组 +0x60/+0x64 首尾；段链 next@+0x3c）+ 三件套 brush@+0x68 / liquid@+0x6c / bright@+0x70；重段型工厂 19e200（25+ 段型 §4.1 表）+ 点串构造 19f470（type 字节 &3 + 末位 &0x80 闭合）；GrapConvert→esLineList 折线化（弧线拟合）；Group 子链 +0x5c/+0x60 + 链接点链（节点 0xC）+ 矩阵层 esMatrixObj@+0x74（flag 位 27）；组工厂 CreateObject 尺寸表（0x3908 0x68/0x320b 0x60/0x3008 0x84/0x3109 0x5c/0x330f 0x74/0x3700 0x88/0x3e00 0x50/0x3a03 0x60/0x3a08 0x50/0xb001 0x78）。
3. ✅ 填充 API 正路实证：SetSolidBrush 仅空槽创建（Q-shape-16）、UpdateBrush/SetBrushObj 重建协议（undo 0x520/0x521/0x522 三选一）、SetBrush 允许 NULL；与既有 ee-draw 填充验证法（`esShapePath::GetBrush` 非空）吻合。
4. ✅ 撤销码入册：0x502（亮位）· 0x50d（flags 统一）· 0x520..0x523（刷）· 0x601/0x602（液体成对）· 0x804 · 0xf006 · 0xf0b/0xf0c/0xf11/0xf12 · 0xf0d/0xf0e/0xf0f · 0xf10/0xf2f1。
5. ✅ 怪癖入册：Q-shape-15..23（CheckValid 会 free 空表 · SetSolidBrush 仅空槽 · 刷/液体成对 undo 码 · 渲染模式位首段 &0x800 · 命中选码 7/8/0xb/0x12 · 路径 RecalcLayout 不外扩 400 · 链接点 +0x64 双语义 · 矩阵层子跳过渲染 · 组工厂尺寸表权威），均待 L4 差分。
6. ✅ status-overrides **1366/1366**；幂等 skip 复验；5 项 checks 全 PASS。

**阶段 2 第十一批（2026-10-17，eslib 画布核族 · S3 起步）✅**：
1. ✅ 反编译 269/269（esCanvas 245 · esEmbedder 24）→ `analysis\pseudo\eslib\esCanvas.decomp.txt`；规格 `analysis\pseudo\eslib\esCanvas.md`、类型头 `analysis\types\esCanvas.h`（269 个 RVA 全注释，机检 OK 269/269 对齐 inventory）。
2. ✅ 结构结论：esEmbedder→esCanvas 谱系 + 宿主双向链（宿主 +0x40 vs +0x81 映射）；**撤销分发 Undo/Undata 码表-码翻转对**（页边距 0x204..0x207 · 页码 0x208 · flags 0x20e · 选择态点 0x210 · 背景色 0x212 · 矩阵 0x216 · 轮廓 0x209 · 边框点 0x20a↔0x20b · 锚点 0x214↔0x215 · 角色 0x523 · 组 0xf005↔0xf006 · 控制点 0xf2f1）；**变换三通道**（Graphics 平移+矩阵合并 / egGraphics TranslateTransform+Multiply / GDC 克隆+epModifyDeviceTransfrom；ToExternal 内→外应用矩阵 / ToInternal 可逆判定+求逆回内）；**导出族**（DrawToMetafile skip 0x7000 · GetOutputRect min-101 · CreateDotmap=esShapeLine(pt,0x6001) · 无 alpha 褪白）；**自毁协议**（EraseSelectedItems/GraphicOperation ▸ 0xf2f1）。
3. ✅ 边框点协议：AddBorderPoint（0x20a）· InsertBorderPoint · RemoveBorderPoint · AddNewPoint · DelBorderPoint（0x20b）；GetOutlinePoints 相对内容中心 · SetOutlineInfo 空表恢复默认边距 800/400。
4. ✅ 怪癖入册：Q-canvas-1..30（isfloatbox/isfixed 链位置 · AddItem 头插 vs Insert 反向 · GetNextBox 回绕 · 文件级编辑快照 · GetOwnCanvas host tag · 对称边距居中 · 导出阈值 · 自毁协议 等），均待 L4 差分。
5. ✅ status-overrides **1635/1635**；幂等 skip 复验；5 项 checks 全 PASS。

**下一步**：第十二批 **文本排版（3.7，S2）**：`esTextUI`/`esPara`/`esTextLine`/`esEQLine`/`esFormulaBox`…；画布列表层（3.6b：esPageList/esCanvasList/esCanvasState 152 个）可随后。收尾项：未命名回写候选（FUN_10028e01/1000a130/1001c230 + 0x6002/0x4285 工厂类）、各批 Q 怪癖的 L4 差分、esFont 字段裁决（Q-lable-4）、Tier 0 余项（0.7 容器族等）后置。幂等复跑：`python tools\re_ledger.py`（无变更时 skip；`--force` 重建）。

## 5. 纪律提醒（每轮开工必读，细则见任务书 + AGENTS.md）

- 只写 `D:\EE Reverse` 内；一结论一证据（含地址/字段偏移/hash/现场截图）；批量前先小样本。
- 动态操作禁区：不手工拼装对象挂画布；插画布只走 `insertCanvasNative`（两参 `InsertCanvas(ui,canvas,-1)` @0x48c980 + 引擎自建 esCanvas，2026-10 已验证；**无参重载 @0x48c6e0 禁用**）；fontSheet 只在 caretContext().fontSheet；不删已有对象；动前 Ctrl+S；崩溃查 `Backup\bk55_*.tmp`。
- 字段全对 ≠ 可用；检查通过 ≠ 能用；栅格像素 ≠ 几何真相。
