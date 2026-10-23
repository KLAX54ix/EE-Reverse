# 镇海区九年级期末数学试卷 —— 插图重画进度

源文件：`D:\EE Reverse\2025-2026学年浙江省宁波市镇海区九年级（上）期末数学试卷.wsd`
（EE 里已打开；文本与 30 张内嵌 PNG 均已抽出，见 `analysis/paper-align.txt`、`captures/paper-figs/`）

> 本文件最初是**镇海卷**的配方日志；2026-10-19 的慈溪坐标轴/原生轴成果已回填 §6。
> 慈溪各题的案例与句柄见 `analysis/cases/index.md`，不要拿本文件的状态表当慈溪进度。

## ★ 2025-12 关键结论（会话可能被压缩，先看这里）

### 1. 标注（字母）—— EE 自己的权威配方（来自 Editer.exe `FUN_00426480`）
```c
shape = operator_new(0x5C);  esShapeLine::esShapeLine(shape);   // esShapeLine = 0x5C
shape->style |= 0x04001007;
seg   = operator_new(0xD8);  esSegLable::esSegLable(seg);       // esSegLable = 0xD8
esSegLable::Initialize(seg, fontSheet);                          // ★ 必须有，否则文字为空
*(void**)(shape + 0x40) = seg;
esObject::SetParent(seg, shape);
```

### ★ 1.5 拖动乱码 —— 已定位并修复（本轮 2025-12）
**根因不是"派生类"，是缺了一步 `HandMoveText` settle。** 反编译 `FUN_00426480`（建标注）+
`FUN_00426900`（插标注+进入拖动）确证：

- Editer.exe 里 0x28B8BC / 0x28B9AC 那套 vtable 是**静态链接副本**（槽位全是 `jmp [IAT]` 桩，
  逐槽跳到 eslib 同一批函数：`+0x64 RecalcLayout`→`0x72df91e0`、`+0x7c Build`→`0x72dfbd80`、
  `+0xb0 Draw`→`0x72dfad30`）。**不是派生类，对象仍是 0xD8**，vtable 差异纯属外观。
- EE 用**默认构造** `esSegLable()`（不是 6 参值构造），随后 `Initialize(fontSheet)`。
- **关键遗漏**：建完 + `AddItem` 后，EE 调 `esSegLable::HandMoveText(seg, POINT, 0)`（flag=0）
  来 settle，把 `+0x74`（文字对齐）和 `+0x78`/`+0x7c`（文字偏移 float）写成引擎自己的值，
  然后再 `Build(1)` 让 `+0x73` 低半字节对齐。不调它，这几个字段停在 ctor 默认值，
  **一拖动就用"引擎从不产生的状态"重排 → 字母偏 + 吐乱码**。
- settle 用 `(0,0)` 点即"居中"：`+0x74 = 0x54`、`+0x78 = +0x7c = 0.5`。`+0x73 = 0x84` 是
  "未拖动"的正确值（原生标注 `+0x73=0x82` 是它被拖动过、`+0x74=0xb4` 的结果，不是 bug）。
- 顺带修了 **fontSheet 解析 bug**：`esPageList::GetStyleSheet()` 这名字是误导——它返回的其实是
  **文档的 esFontSheet**（`+0xd4` 该指的对象）。旧的"heap 扫描取第一个有 styleSheet 的字体表"
  会落到**模板字体表**上 → 字体/度量全错。现在直接拿页表的 GetStyleSheet 结果；光标画布（
  `GetActiveCanvas` 枚举不到）改用 `caretContext()`（`esTextUI::GetOwner` → 页表 → 字体表）。

**改动**：`ee_bridge.js::makeLabelShape` 新增 settle 步骤（默认开，`opts.settle:false` 关），
`AddItem` 后 `HandMoveText(seg, 0,0, 0)` + `Build(1)`；`ee_mcp_server.py::label_context`
改用页表字体表。**待用户拖动一个新建字母目视确认。**


### 2. 标注特性字（ctor 的 K）—— ★ 2026-10 修正：旧结论"高 16 位 = 字体槽"已推翻
```
k = 0x80000000 | byte0=主文本字符数 | byte1<<8=标注点字符数 | byte2<<16=边框字符数 | byte3<<24=flags
```
- ctor 的 ulong **不是原子 feature word**，而是**逐段字符数 + flag 字节**（反编译 esSegLable ctor）：
  byte0→`+0x70`、byte1→`+0x71`、byte2→`+0x72`、byte3→`+0x73`（flags，`0x80` = 数学化）。
- `RecalcLayoutLable` 只按 `+0x70` 个字符 append → **byte0 写 1 = "ABC" 只渲染 "A"**：多字符截断的根因。
- **字体槽只放 `+0x6e`，绝不能塞进 k**：旧写法 `(槽<<16)|1` 把槽写进 byte2（边框后缀字符数），
  单字符时凑巧看着对，多字符全截断；`+0x72` 非 0 还会让引擎 append 垃圾后缀。
- 桥已按文本长度自动算 byte0（`opts.k` 只当 flags 模板）：实测 A=741 / AB=1482 / ABC=2223（宽度 ≈×N）、
  EQLine `+0x30` item 数 1/2/3；`Build`/`RecalcLayout` 反复调用**幂等**（`ClearAllContent` 先清后填）。
- **bit31 保留**（byte3 = `0x80` 数学化）；旧说法"低位必须 `0x0001`"其实是 byte0 = 1 个字符的巧合。

### 3. 内嵌文本行 esEQLine（`seg+0x80`）
- `+0x30` = 项数 = **字符数**（桥按文本长度自动写 byte0 后，引擎填充即正确）。
  ~~建成后强制 = 1~~ —— **不要强制**：那是旧 k 编码（槽进了 byte2）时代对垃圾后缀的补丁，
  会把多字符标签截成首字形。现在引擎填几个字符就是几个 item。
- **`+0x04` 高 16 位必须是 `0xFFFF`**（引擎自己造的是 `0xFFFF0003`，我的是 `0x00000003`）。
  高 16 = 0 被当成"格式索引 0"，**首次绘制能过，一重排就按错误格式解析** → 乱码 + 位置错。
  （桥已自动写：`opts.formatWord`；MCP 侧同值兜底、幂等。）
- **回读不要触发重建**：`setLableStyle` 的 `rebuild` 必须显式 `true` 才做（以前 `!== false`，
  每次"只读检查"都在给所有标注追加一项 → 自己喂乱码）

### 4. 加粗点（用户快捷键 `` ` ``，0.4mm）
```
esShapeLine + 320×320 短段 + 笔宽 160（160/400 = 0.40mm）+ 样式字 0x04000005
```
不是圆点。已做成 `ee_draw_figure` 的 `dots:[[x,y],...]`（在统一线宽**之后**创建，否则被 0.25mm 覆盖）。

### 5. 虚线
```
esPenInfo + 0x04 :  0 = 实线   3 = 虚线
```
服务端直接把 `shape+0x54` 写成 3（真正的虚线，不是切段）。

### 6. 坐标轴（工具栏原生）—— ✅ 2026-10-19 已完全打通（旧“渲染不出来”结论作废）

> 本节 2025-12 的旧状态“对象能构造但渲染不出来”已经过时。2026-10-19 补齐了
> **绝对定位矩阵**、**G 标志（esFormulaBox 标签）**、**用户最终轴样式** 三件事，已在慈溪 Q5
> 实画并通过 audit。详细字段与最新配方以 `AGENTS.md`「2026-10-19 坐标轴逆向」和
> skill `ee-draw` 为准；下面保留结构说明，并修正旧配方。

```c
// 1) 配置对象 esAxisObj（普通类、无 vtable）
obj = operator_new(0x400); ??0esAxisObj@@QAE@XZ(obj);
//    默认：+0x4=10、+0x8=10000（x 刻度参数）；+0xc=256、+0x10=10、+0x14=10000（y）
//    +0x68..+0x7c = 内容矩形/原点，默认 0
esAxisObj::InitSize(obj, &rect, origin, 1);   // mode=1：rect/origin 直接是页面单位
// 2) 轴段 esSegAxis（0x16C，typeId 0x5006）
seg = operator_new(0x16C); ??0esSegAxis@@QAE@XZ(seg);
seg->vtable = Editer.base + 0x2921D4;          // Editer 里的静态副本
// 3) 外层 esShapeCap（0x60，typeId 0x320B）—— 不是 esShapePath！
shape = operator_new(0x60); ??0esShapeCap@@QAE@XZ(shape);
shape->vtable = Editer.base + 0x29210C;
shape+0x40 = seg; esObject::SetParent(seg, shape);
// 4) ★ 绝对定位：段 +0x4c 的 Gdiplus 矩阵平移到页面原点
GdipSetMatrixElements(seg+0x4c, 1,0,0,1, origin.x, origin.y);
//    不做这步 → 轴画在画布 (0,0)，图形在 2 万单位外，就是“图形不在坐标轴里”
// 5) Initialize(seg, styleSheet, axisObj, G1, G2)
//    ★ G1=G2=1；0/0 时不建 esFormulaBox，只剩光秃刻度短线（“一堆短线”）
esSegAxis::Initialize(seg, styleSheet, obj, 1, 1);
// 6) 挂画布 + 首次 Recalc → 范围/bbox/轴点数组全部转成页面绝对坐标
esCanvas::AddItem(canvas, shape, 1);  Recalc(shape);
// 7) 用户最终轴样式（styleAxisShape）：
//    AddOrRemoveTextBox(seg, ss, 1, 1, NULL) → x 标签框 +0x14c
//    AddOrRemoveTextBox(seg, ss, 2, 1, NULL) → y 标签框 +0x150
//    +0x148 是 G=1,1 自带的原点 O 标签框
//    关刻度：seg+0x6c/0x78/0x104/0x110/0x12c/0x130 = 0；+0xec/+0xf8 = 0
//    箭头样式 4/较细：seg+0x10=0x10, +0x44=0x10000, +0x13c=8
//                      shape+0x10=15, shape+0x5c=0x03040400, shape+0x58=100
//    再 SetTextBoxPostion(seg, 0/1/2) + Recalc
```

- `esSegAxis` 的标签是 3 个 `esFormulaBox`：`+0x148`=原点 O、`+0x14c`=x、`+0x150`=y。
- 轴位置/尺寸由 `InitSize` 的内容矩形和原点决定；绝对位置由 `seg+0x4c` 矩阵负责，二者缺一不可。
- 桥 RPC：`makeNativeAxisShape(rect, origin, gx, gy, styleSheet)` + `styleAxisShape(shape, styleSheet)`；
  服务端 `ee_draw_axis` 已自动串联，默认就是用户样式（x/y 标注、无刻度数字、保留 O、样式4细箭头）。
- ⚠️ 改服务端后必须重启 MCP；改桥用 `ee_diag poke` 热重载。



### 7. 光标自动定位（✅ 已实现 —— 2025-12 本轮打通）
**目标**：`ee_goto_problem(n)` 输入题号，光标自动落到那题文字处，然后（可选）`InsertCanvas`，
全程不用手动点光标。

**实测成立的 API 链**（全部是 eslib 导出，都在活进程里验证过）：
```cpp
// 1. 找"活的" esTextUI —— 页表 GetUI 只在光标落在正文里时才非空，别用它做主来源。
//    直接扫 ??_7esTextUI@@6B@ 实例，取 IsValid()==1 的那个（IsValid == *(int*)(this+0xdc)）。
esTextUI::IsValid() / GetCaretOwner() -> esPara*   // 导出名写 esTextLine，实际是 esPara
esTextUI::OnKeyDown(uint vk, int flags)            // VK_UP=0x26 / VK_DOWN=0x28 可用
                                                  // VK_HOME / VK_PRIOR 返回 0（未处理）
esTextUI::GetCaretRect(tagRECT*)                   // 光标矩形（同一段里 y 会跨页跳，别当绝对坐标）
esTextUI::SetCaretToSafePosition()                 // 清选区、把光标夹到有效位；不保证回文首

// 2. 读段落文本 / 顺序遍历段落（关键发现）：
esPara::GetContents(zwstr&, int)                   // ★ 段落文本 getter；zwstr 首 dword = wchar_t*
esPara::GetNextVisible() / GetPrevVisible()        // 按文档顺序走段落链表

// 3. 定位段落（不用构造 std::function！）：文首走到目标段的朴素做法
gotoTop()  = 反复 OnKeyDown(VK_UP) 直到光标不动（para+caretRect 连续 3 次相同）
gotoText() = gotoTop() 后反复 OnKeyDown(VK_DOWN)，每步 GetCaretOwner()+GetContents()，
             直到段落文本包含锚点串（如 "位似图形" / "莱洛三角形"）

// 4. 插入画布 + 拿到"该画布"（★ 2026-10 更新：改走原生通道，详见 AGENTS.md「放画布的正确姿势」）：
esCanvas(w,h) 用引擎构造（??0esCanvas@@QAE@HH@Z = 默认构造 + SetAsBorderRect(0,0,w,h)，frameType 0x1000）
esTextUI::InsertCanvas(ui, canvas, -1) -> 1        // 两参重载 @0x48c980 = 编辑器"粘贴画布"通道（已验证）
esTextUI::GetBefEmbeder() -> esEmbedder*           // ★ 光标处嵌入器
esEmbedder + 0x38 -> esCanvas*                     // ★ 光标处画布（页表 GetActiveCanvas 报不到它）
// 注：无参重载 InsertCanvas() @0x48c6e0 已弃用——直调会让 textUI 半坏（OnKeyDown 恒 0）随后进程崩溃
```
**★ 2026-10 持久化实测**：`insertCanvasNative` 连插 3 张画布 + 画图 → Ctrl+S → 关闭文档 →
**重启 Editer 进程** → 重开 It-test.wsd：三张画布全部存活（`frameType==0x1000` 是原生插入画布的特征字、
61340×30670、图形链 1/8/8 与保存前一致、标注包围盒 2741–3482 无乱码）。审计用
`bridge/audit_canvases.py`（进程里有 500+ 个 esCanvas-vtable 幽灵对象，只有 `+0xc8` rect 非零的才是真画布）。
**回归样本已保留：`samples/It-test.wsd`** —— 跑 `python bridge\audit_canvases.py list` 应看到
3 个 `frameType=0x1000` + 61340×30670 的画布、图形链 {8,8,1}；改动 bridge/服务端后先拿它验回归。
**坐标/单位**：`GetUiRect()` ≈ 68003×98793（1/400mm → 170×247mm，A4 含页边距）。
`InsertCanvas` 返回的画布 ≈ 61340×30670，`GetBefEmbeder()+0x38` 指向同一个对象，画线能渲染。

**已新增的 MCP 工具**：`ee_goto_problem`（id→锚点→goto→可选 insert）、`ee_goto_text`（任意锚点）、
`ee_caret_canvas`（读光标处画布）。题号→锚点表见 `ee_mcp_server.py` 的 `PROBLEM_ANCHORS`。

**教训**：
- `GetUI(pageList)` 对"非活动文档"的页表返回 null；`ee_canvases` 排名第一的画布可能属于另一个页表，
  光标反而在别处 → 之前 `caret` 探针报 "no text UI"、`newCanvas` 插错地，都是这个原因。
- `Frida` 17 里 `Module.getExportByName` 没了，要用 `Module.getGlobalExportByName`。
- 沙箱挡住 WMI/进程枚举时，可用 `ee_diag {op:"poke",addr:"0x0"}` 让 `_rpc` 走 reset 路径，
  下次调用自动重读 `ee_bridge.js`（服务端代码改动仍需真重启）。

### 8. 模块基址（每次重启都变，必须现查）
- `ee_status` 给 eslib base；`ee_diag modules filter=Editer` 给 Editer.exe base
- Ghidra 里 Editer.exe 的 imageBase = `0x400000`，所以传给 FindVtableCtor 的 RVA
  = 运行时vtable − **运行时base**（不是 − 0x400000）
- 已用过的 RVA：坐标轴类 `0x29210C`、文字标注类 `0x28B9AC`

### 9. 铁律
1. **只新建、只画**；改只删**本次刚建的对象**。对已有对象 `unlinkShape` 会留悬空指针 → 满屏乱码。
2. **同一个画布不要反复建删标注** —— 会把引擎卡死（已发生一次，Not Responding）。
3. 每次批量前 **Ctrl+S** 存基线。
4. `ee_redraw` 后 **PrintWindow 截图可能是缓存的旧位图**（连续几张哈希相同就是缓存）→ 以用户屏幕为准。

## 工作流（用户选方案 A：每题一个新画布）

> **用户把光标点到题目处 → `ee_new_canvas` → `ee_draw_figure` 一次画完 → 截图 → 下一题**

固定参数：`pen_mm=0.25`、`font_index=23`（✅ 已确认 = AY / Times New Roman 斜体五号，
本文档固定；**槽号是每个文档独立的**，测试文档是 14，不要跨文档套；★ 2026-10 起
`ee_fonts` / `font_face` 自动解析已可用 —— 新文档不再需要人工点对话框拿槽号）、
`padding=400`（1.00mm）、`math=1`。画布单位 1 = 1/400 mm。

## 状态

| # | 出处 | 原图 | 画布 | 状态 |
|---|---|---|---|---|
| 1 | 选择 5 Rt△ABC（∠C=90°，AB=13,BC=12） | fig01 | `0xad94588` | ✅ 已画（重建 5 次，最终干净） |
| 2 | 选择 6 坐标系位似（B(1/2,−1)→E(−1,2)，比例 −2） | fig07 | `0xad97678` | ✅ 已画（10 路径含 6 真虚线 + 9 标注） |
| 3 | 选择 8 莱洛三角形 | fig10 | | ⬜ |
| 4 | 选择 9 Rt△ABC + 中线 AD + 弧 | fig12 | | ⬜ |
| 5 | 选择 10 正八边形+正方形（图1）/ 函数图象（图2） | fig17 | | ⬜ |
| 6 | 填空 5 ⊙O 内接△ABC（AB=AC, BC=16, OE=5） | fig21 | | ⬜ |
| 7 | 填空 6 △ABC（AC=DC=BD, CF⊥AE） | fig22 | | ⬜ |
| 8 | 解答 1 △ABC（D 为 AC 中点，∠ADE=∠B） | fig23 | | ⬜ |
| 9 | 解答 3 正方形网格作图 ×3 | fig24 | | ⬜ |
| 10 | 解答 5 ⊙O + AD 为直径（∠ACB=60°） | fig25 | | ⬜ |
| 11 | 解答 6 光的折射 图1/图2 | fig27 | | ⬜ |
| 12 | 解答 8 圆内接四边形（AC 为直径）+ 图2 | fig30 | | ⬜ |

**已完成**：题 5 → 画布 `0xb4abe80`；题 8（莱洛三角形）→ 画布 `0x17481130`。
**待重画**：题 6 位似（原来那张画布 `0xad97678` 随文档重开丢失）。

## 铁律（踩坑换来的，务必遵守）

1. **只新建、只画**。要改只删**本次自己刚建的那一个对象**。
   对已有对象调 `unlinkShape` 会留悬空指针 → 满屏乱码（已犯过一次，用户不得不删光画布重来）。
2. `esCanvas` 实例扫描（`ee_diag allcanvases`）比页面遍历可靠；`bad` 列 = 文本行项数 ≠ 1 的标注数。
3. 画布枚举要扫多槽位：`GetActiveCanvas(pl, n)` 的 n 是槽位不是序号。
4. 每次批量前先 `Ctrl+S` 存基线 —— 文档重开会让内存里画的全丢。



## 已做的工具增强

- `ee_draw_figure`（一次调用画完整张图）：paths（`close` / `fill` / **`dash`**）+ labels
  + 一次全画布线宽 + 一次标注样式。加 `quiet:true` 只回计数，避免刷屏。
- **虚线 = `esPenInfo+0x04 = 3`**（0=实线，3=虚线）。服务端直接把 `shape+0x54` 写成 3，
  是真虚线，不是切段。验证方法：把编辑器自己画的虚线改成 0 → 变实线；改回 3 → 又变虚线。
- **标注特性字（ctor 的 k）**：★ 2026-10 修正为"逐段字符数 + flags"模型（见本文件 §2）。
  桥按文本长度自动写 byte0，caller 只传 flags 模板 `0x80000000`；字体槽只进 `+0x6e`。
  旧结论 ~~`k = (字体槽 << 16) | 0x0001`~~ 已废弃（多字符截断的根因）。
- **字体槽自动解析（★ 2026-10 新增，不再需要人工点对话框）**：
  `esFontSheet::GetFont(sheet, slot, size)` 返回的 esFont 有 `GetFontName()/IsItalic()/IsBold()/
  GetFontSize()`（1/100pt，1050=五号）→ 新工具 **`ee_fonts`** 列出全部槽；
  `ee_draw_label` / `ee_draw_figure` 在"画布上没有标签可抄"时按 `font_face`（默认
  "Times New Roman"）+ `font_italic`（默认 true）自动解析槽号（当前测试文档 = 槽 11）。
  探测要**跳过越界回落到首个字体的重复指针**（桥按指针重复自动截断）。
- 注意 `esSegLable+0x70` 是**字符数**（`for i<(byte)this[0x70]`），
  不是"数学化"勾选框；单字母时凑巧等于 1。多字符已修复（byte0 = 文本长度，item 数 = 字符数）。
- **画布枚举**：`GetActiveCanvas(pageList, n)` 的 n 不是"第 n 个画布"而是槽位；以前只试 n=0，
  已改成扫 0..7。

## 待确认

1. ~~字体槽 23 对不对~~ —— ✅ 已确认：槽 23 = AY（Times New Roman + 斜体 + 五号）。
   **槽号是每个文档固定的**（存在 .wsd 里，重开不变）；不同文档各自独立
   （测试文档 AY = 槽 14）。**不要跨文档套槽号**。
   （★ 2026-10：自动解析已上线 —— `ee_fonts` 列全表；无标签可抄时按 `font_face`
   默认 Times New Roman 斜体自动找槽；当前进程测试文档实测 = 槽 11。人工点对话框步骤可废除。）
2. 截图看不到新画布 —— 视图停在题首，新画布在屏幕外，需要用户滚动才能目视验证。

## 2026-10-18 活体审计（废纸画布）与修复

**方法（不污染试卷）**：`ee_diag {op:"createcanvas", args:{typeId:0x2020}}` 造一张未嵌入的
esCanvas（0x0 尺寸也够用），把句柄传给 `ee_draw_figure` / `ee_draw_circle`，在内存里画并读回；
画完不挂文档、不保存。本轮实测 fill / dash / dots / 多字符 label / 圆 全部可造。

**实测量到的三个 bug（已修）**：
1. **标签 `+0x70` 是主体字符数，不是"数学化"**：旧 `setLableStyle` 把 math 写进 +0x70，
   实测 ABC 3→1、AB 2→1；下一次 `RecalcLayoutLable` 会把多字符截成首字形。
   修复：math 只写 `+0x73` bit7，`+0x70/+0x71/+0x72` 一概不碰；新造 ABC 经 math=1 后
   `+0x70` 仍 3、`+0x73=0x84`（2026-10-18 实测）。
2. **`setPenWidth` 会覆盖加粗点**：实测 dot `before=160 / after=100`。修复：按段类型 `0x6001`
   跳过；复测 dot 保留 160。
3. **单原语默认笔宽 80（0.20mm）**，不是项目固定的 100（0.25mm）。服务端 0.3.0 起
   line/polyline/polygon/rect/circle/arc/angle_mark 都有 `pen_mm`（默认 0.25）。

**其他实测结论**：
- `shape+0x58` = 所有 shape 的笔宽字段（= 内嵌 esPenInfo+0x08）；圆写 `+0x58` 即 100。
- 填充实测 `fill` 返回 `brush=0x8408e70`、`filled=true`；虚线 `+0x54=3`；EQLine format
  `0xffff0003`；圆段类型 `0x4284`。
- 标签包围盒（padding=400）：A=3134×3480、AB=4217×3480、ABC=5354×3480；>12000 宽是糊字。
- 桥热重载：`ee_diag poke addr=0x0` 故意触发 `writeI32` 访问违例 → 服务端 reset → 下次调用
  重新加载 bridge（实测）；新增 `getBrush` RPC。

**新工具 / 资产**：
- `tools/check_spec.py`：约束残差检查（equal/angle/collinear/on_segment/midpoint/distance/
  parallel/perpendicular/point_eq）；示例 `analysis/specs/self-test-equilateral*.json`。
- `analysis/cases/`：案例库（README 模板 + index + 北仑 q10 种子卡）。
- MCP 服务端 0.3.0：23 tools（+`ee_audit_canvas`、`ee_draw_axis`）、figure schema 补齐
  `dots/dash/curves/arcs`、label `sup/sub`、`fill:"dark"`；单原语 `pen_mm`。
  **需重启 MCP 才生效**。

**待办**：重启 MCP 后对一张真实画布跑 `ee_audit_canvas`；本轮废纸画布 `0x346bda0` 留在内存里
（未挂文档、不会保存，进程重启即消失），不影响当前试卷。

## 2026-10-19 九下期中选择压轴题 6 图批量（另一文档；本机同进程只开一个文档）

**目标文档**：`九下期中选择压轴题.wsd`（不是宁波模拟卷；用户纠正过一次）。
**结果**：6 张画布全部插入 + 落笔 + `ee_audit_canvas` PASS（Q5 因残留测试字符 Z，shapes=21）。
案例卡：`analysis/cases/2026-jiuxia-qzq-batch.md`；spec：`analysis/specs/nb/q01..q06m.canvas.json`。

**本批新增/修正的机械知识**

1. **`nb_build.py` 折线必须显式 `close:false`**：`ee_draw_figure` 对 >2 点 `paths` 默认**闭合**，
   Q2 双曲线因此多出一条弦（已修 `nb_build`：polylines/arcs/curves 全强制 close=False）。
2. **新插入画布上取不到 fontSheet**：画布不在 `canvasCandidates`、光标又在画布内时，
   `ee_draw_axis`/`ee_draw_figure` 的 `label_context` 回落到失败的 `caretContext` → fs=0x0 →
   `makeNativeAxisShape` 访问违例（**调用崩、进程活**）。→ 直接 `ee_diag` 调桥 RPC
   `makeNativeAxisShape/addItem/recalcShape/styleAxisShape` 并**显式传本档 fontSheet**；
   `ee_draw_figure` 给每个 label 传 `font_sheet`/`style_sheet`。
3. **画布级标签样式会互相覆盖**：`draw_figure` 的 lablestyle 是**整张画布**批量写；
   混字体（数学斜体字母 + 宋体①②③④）必须：`draw_figure` 只放一类，另一类用
   **`ee_draw_label` 逐个加**（走 `makeLabelShape`，不做画布级样式，实测不影响其他标签）。
   `ee_draw_label` 的 `math` 用 `style_flags` 控制（默认 `0x80000001` = 数学化；传 `1` = 非数学）。
4. **光标重绑只能靠用户点一次正文/选项行**：确认 eslib 无可用的"退出画布编辑模式"接口
   （`esCanvasState::CanceActiveCanvas` 只改 active canvas，`OnSetCaretByPoint` 在画布模式下恒 0；
   `isValid` 标志 +0xdc 是**不能写**的：写 1 后 `OnKeyDown` 会在引擎内 AV，**本会话崩两次**）。
   沙箱还禁止 `SetCursorPos`/`SendInput`（外部点击注入无效）；桥内 `SendMessage` 点 view 偶尔生效但不稳。
   → 现实节奏：**每题用户点一次选项行**，不要尝试跨已插入画布 `VK_DOWN` 走位（会返回 0 被挡）。
5. **插入位置 = 选项行行首**：光标到选项行 → `VK_LEFT` 到行首（会先跳到上一段则 `VK_RIGHT` 回来）→
   `insertCanvasNative`。渲染上等于"原图之后、选项之前"，等价于要求的槽位。
6. **`esUndo` 没有 `UnBack` 导出**（只有 `CanUnBack/CanUnNext/DoUndoRedo`，需要 recoder），
   所以**多余对象无法程序撤销/删除**：试验字符一定画在废纸画布上，正式画布只放最终内容。
7. 崩溃代价：本会话因 hack 崩两次、均丢失未保存画布（用户两次重开）。**每次落笔前让用户 Ctrl+S** 是唯一保护；
   保存后文件 mtime 会变（本次最后仍未保存：410711 bytes @12:48，需用户再按一次 Ctrl+S）。

## 2026-10-19 深夜：保存不写盘 / 删除闪退 的根因与安全流程（★ 重要）

**背景**：本批 6 图重画时连续出现「Ctrl+S 没反应」「关闭重开图全丢」「删我刚画的画布必闪退」。

### A. 保存其实没坏 —— 两件事凑在一起造成的假象
1. **每次向用户提问都会把浏览器/DSH 窗口调到前台**，用户按 Ctrl+S 时焦点常常不在 Editer 上，
   键被浏览器吃掉 → 用户以为“保存异常”。
2. 更关键的：**桥插的画布不会把文档标成“已修改”**（实测插入后 `esPageList::IsChanged()==0`；
   而用户手工输入一个字符后立刻变 1）。编辑器据此认为没改动 → Ctrl+S 静默跳过、关闭也不提示保存。
   实测：干净文档 Ctrl+S 能写盘（14:47、19:27 两次时间戳都变了）；桥插画布后同样的 Ctrl+S 不写盘。

**✅ 已验证的保存流程（程序化，不需要用户按 Ctrl+S）**
```
① 标脏：向文档 view（AfxFrameOrView140u 子窗口）PostMessage WM_CHAR(0x0102, ' ', ...)
   —— 走编辑器自己的输入路径，等价于用户敲一个空格；实测 pl.IsChanged 0→1
   （直接调 esTextUI::OnKeyDown(ui, VK_SPACE, 0) 返回 0，不走文本输入，别用）
② 保存：SendMessage(frame, WM_COMMAND, 0xE103, 0)  // 0xE103 = ID_FILE_SAVE
   —— 从 Editer.exe 的 RT_ACCELERATOR 表解析出来：table 1119 里 Ctrl+S → cmd 0xE103 ✓
③ 验证：看 .wsd 文件 Length/LastWriteTime 变化（实测 410792 → 413616，含 36 个图形对象）
```

### B. 删除闪退：只在“尚未保存的新插入画布”上发生
- 实测：用户点选刚由桥插入、**尚未保存**的画布按 Delete → Editer 立刻崩溃（多次复现）。
- 实测：**保存 → 关闭 → 重开**后再选同一张画布 Delete → **正常删除，不崩**。
  （空白测试画布 20:0x 验证；用户也确认“保存退出重启后再删肯定不闪”）
- 说明：闪退不是删除命令本身的问题，而是**桥插入的画布尚未进入编辑器的序列化/撤销/注册体系**，
  删除路径命中了不安全状态；经过一次保存→重载，对象变成“正常对象”就一切正常。
- 因此：
  * **铁律新增：绝不要删“本次刚插入、尚未保存”的画布**；
  * 误插：立即 **Ctrl+Z**（引擎自带撤销；实测一次 Ctrl+Z 能撤销整串输入/插入，安全）；
  * 确实要删：先执行上面 A 的保存流程 → 关闭文档 → 重开 → 再删；
  * 只要不删，画布+图形保存/重载完全正常（36 个对象已验证随文件保存）。

### C. 其它本次确认的坑
- `esTextUI::AppendBlanks(ui,1,0)` **不要调**（本次调用后进程崩溃，原因不明）。
- `esTextUI` 的 IsValid 标志（+0xdc）**绝对不能手写**（写了能骗过 IsValid，但随后 OnKeyDown 引擎内 AV，崩进程）。
- 画布模式下（插完画布、焦点在画布）**不能靠模拟点击/方向键回正文**：
  `esCanvasState::CanceActiveCanvas` 只改 active canvas，`OnSetCaretByPoint` 恒 0，
  SendMessage 模拟鼠标点击也不可靠；**唯一可靠方式 = 用户真实鼠标点一下正文**。
  所以“每题一张画布”的现实节奏就是：每插一张 → 用户点一次正文。
- 坐标轴：新插画布不在 canvasCandidates 且光标在画布内时，`ee_draw_axis`/`ee_draw_figure`
  取 fontSheet 会失败（fs=0x0 → makeNativeAxisShape AV）。做法：直接 `ee_diag` 调桥 RPC
  `makeNativeAxisShape(rect,origin,1,1,fontSheet)` + addItem/recalc/styleAxisShape，显式传本档 fontSheet；
  label 也要逐个传 `font_sheet`/`style_sheet`。
- 一张画布上两种字体标签（数学斜体字母 + 宋体①②③④）：`ee_draw_figure` 的 lablestyle 是整画布批量写，
  后一次会覆盖前一次 → 先 `draw_figure` 画字母（font 11 / math 1），再用 `ee_draw_label`
  逐个加圈号（font 0 / style_flags 1），**`ee_draw_label` 不做画布级样式**（实测不影响已有标签），
  最后 `setPenWidth(cv,100)` 把新标签的 80 归一（否则 audit 报 label pen 80）。

### 2026-10-19 22:11 收尾（重要：本批图未落盘）

- 最终结论、删除/保存/插入规则已写入 `AGENTS.md` 的同名小节（★必读），此处只记事实：
- `九下期中选择压轴题.wsd` 最终磁盘状态 = 410733 字节 / 21:38:52（接近原卷，**本批 6 图未保存**）。
- 已验证可用的组合：**用户按空格+G 插画布 → ee_draw_figure 画图 → WM_COMMAND 0xE103 保存 → 看时间戳**。
  单张图验证通过（Q4：11 个对象、审计 PASS、原生画布）。
- 已证明不可用/危险：桥 insertCanvasNative 插画布后删除（必崩）、手工补注册（仍崩）、
  bridge drawCanvasSpec（死锁）、连续输入注入（卡死）、poke 热重载（进程异常）。
- 下次开工：先让用户开文档 → 逐题“用户空格+G 插画布 → 我画 → 最后统一保存并重开验收”，**全程不删任何东西**。

### 2026-10-19 23:0x 原生函数/曲线打通（解决“折线手搓”）

- 结论 & 配方见 `AGENTS.md` 新增小节「2026-10-19 深夜：原生函数图象 / 原生曲线打通」。
- 一句话：`esShapePath::CreateFromPathData` 用
  `types=[0,3,...,0x80]` + 末尾重复最后一点 → 得到**原生 esSegBezier**；
  圆弧用 `ee_draw_arc`（上半圆 `0→180`）。EE 自家“函数图象”产物同样是 esSegBezier。
- 已改：桥加 `makeBezierPathShape/drawBezierCurves/setShapePen`；
  服务端加 `ee_draw_function`，`draw_figure` 的 arcs/curves 改原生（MCP 需重启生效）。
- 已在用户文末样本画布试画：轴 + y=1/x 原生曲线 + 原生半圆，审计 PASS。
- 下一步：用新能力重画 Q2（反比例）、Q6（半圆）等；画完必须 save→close→reopen 验收。

### 2026-10-20 00:xx 原生函数曲线面板（续）

- 逆向得到「函数曲线」非模态面板的全部控件 id 与语义（见 AGENTS.md §8）：5690=Y(x) 公式、5000/5001=从/至、
  5046=使用自定义变量域、5832=生成曲线、5047=输出为曲线对象（不勾=原生函数图象）。
- 结论：**生成必须“先点画布（画布编辑态）→ 再开面板 → 手动填公式/定义域 → 生成曲线”**；
  程序只能读控件/点按钮，**填字被 MFC 拒绝**（WM_SETTEXT/WM_CHAR 均无效）。
- 当前状态：Q2 画布 `0xa4c45a0` 里已有原生坐标轴（rect [19427,2067,41913,25567]，origin [20994,24000]）；
  用户的生成尝试未落盘（画布链仍只有 1 个轴对象）。文末样本画布仍是测试垃圾，勿保存。
- 待办：Q2 = 用户生成原生 y=36/x（定义域 3–11）→ 我补正方形 ABCD/DEFG 线段与字母 A–F,G；
  Q6 = 只需原生半圆弧 + 线段/字母（无需函数面板）。画完统一保存并用时间戳验收。

### 2026-10-20 00:05 今晚收工（交接）

- 文档 `九下期中选择压轴题.wsd` 磁盘仍为 **410733 字节 / 2026-10-19 21:38:52**（今晚没有保存过，
  所以磁盘是干净的；内存里的 Q2 轴画布、文末样本画布及其演示曲线**都未落盘**）。
- 收工时建议：**关闭 Editer 时不保存**（选“否”），下次重开即从干净状态开始。
- 下次开工顺序（Q2）：点 Q2 画布进入编辑态 → 打开「函数曲线」面板 → 手动填 `36/x` + 勾使用自定义
  变量域 + 从 3 至 11 → 点「生成曲线」→ 我检查对象并补 ABCD/DEFG 线段与字母 → 保存并重开验收。
- Q6（半圆）：无需函数面板，用 `ee_draw_arc` 原生弧 + 线段/字母即可，我一人可完成（需你先插画布）。
- 已完成能力：原生圆/弧（esSegArc）；原生贝塞尔（引擎工厂 + Schneider 拟合，控制点少而准）；
  函数图象面板控件已全部逆向（见 AGENTS.md §8），只差“生成”必须由人手输入一次。

> 更正（00:05 复查）：`九下期中选择压轴题.wsd` 磁盘已变为 **417263 字节 / 2026-10-20 00:03:10**
> —— 今晚的内容（Q2 只有坐标轴的画布、文末样本画布 + 我的演示曲线）**已经被保存进磁盘**了
> （可能来自某次“确定/Ctrl+S”）。所以收工不是“磁盘干净”状态。
> 处理办法：重开文档后，**重开状态下的删除是安全的**——可把「文末样本画布」和「Q2 那张只有轴的画布」
> 选中删掉，再保存；或者下次让我先确认每张画布归属再决定删哪些。
