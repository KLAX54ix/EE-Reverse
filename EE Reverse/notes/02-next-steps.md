# EE 逆向 — 交接文档（新会话从这里开始）

> 新开会话后，只需说：**「读 `D:\EE Reverse\notes\02-next-steps.md`，然后继续」**

---

## 0. 一句话现状

**字母标注（含与用户手插字母一致的斜体样式）与角度标记（直角符号 / 等角弧 / 双弧）都已打通并截图目视确认**；
画布选择已确定化。`ee_draw_label`、`ee_draw_arc`、`ee_draw_angle_mark`、`ee_canvases`、`ee_diag`
均已作为 MCP 工具上线。
★ 2026-10：**多字符标签截断 bug 已修**（ctor 的 k 字实为逐段字符数，字体槽只进 `+0x6e`；
详见 `analysis/figures-progress.md` §2）；**字体槽自动解析上线**（`ee_fonts`），新文档不再需要人工点对话框。

⚠️ **中途 EduEditer 崩过一次**（手工造 `esCanvas` + `esDocument::InsertNewCanvas` 看似成功，
却让编辑器在下一次重绘时退出）。磁盘上的 `.wsd` 是安全的——所有绘制都只在内存里。
那条死路已在 §2.1 和 §4 第 16 条标死，**别重走**。

✅ **`ee_new_canvas` 随后打通了**：真正的卡点是"活的 `esTextUI` 只能从页表拿"
（堆扫描找不到它）+"光标必须在正文里"（`IsValid()` == `esTextUI+0xdc != 0`）。
现在它调用引擎自己的 `esTextUI::InsertCanvas()`，不手工造对象，编辑器不再崩。
已知边界见 §2.1 末尾（返回值不等于实际画布、不要连调）。

---

## 1. 环境与工具（都在，可直接用）

| 项 | 路径 / 说明 |
|---|---|
| EE 主程序 | `D:\educationeditor\EduEditer\Editer.exe`（x86 MFC，运行时基址 0x660000） |
| 绘图引擎 | `eslib.dll`（16,123 导出，运行时基址 0x6d210000 随启动变） |
| Frida 桥 | `D:\EE Reverse\bridge\ee_bridge.js`（**每次 attach 重新读取**） |
| 直连控制器 | `D:\EE Reverse\bridge\ee_client.py`（`EE` 类 + `VT` 类名表） |
| **MCP 服务器** | `D:\EE Reverse\mcp-server\ee_mcp_server.py`，已在 `C:\Users\84184\.dsh\cordis.patch.yml` 注册为 `ee-draw` |
| Ghidra 12.1.4 | `D:\EE Reverse\tools\ghidra_12.1.4_PUBLIC`（`JAVA_HOME=D:\java`） |
| Ghidra 项目 | `D:\EE Reverse\analysis\ghidra-proj`，内含 **`EEeslib/eslib.dll`** 与 **`EEediter/Editer.exe`** |
| 反编译脚本 | `tools\ghidra-scripts\DumpDecomp.java`（按名字模糊匹配，**匹配的是 Ghidra 里的 demangle 名，如 `esShapeBase::Draw`，不是 mangle 名**） |
| **vtable 离线解析** | `tools\vtinfo.py`（`vt` / `slot` / `rva` / `find`，不需要目标在跑） |
| **窗口截图** | `tools\capture_window.ps1` + `tools\crop.py` → 可直接目视验证渲染结果 |
| 已 dump 的反编译 | `analysis\decomp-shape.txt`、`decomp-draw.txt`（形状/段/标签绘制链）、`decomp-arc.txt`（esSegArc） |
| 已知模型文档 | `notes\01-drawing-model.md`（**必读**，§7.7–§7.9 是标签与圆弧配方） |

**改完 `ee_bridge.js` 或 `ee_mcp_server.py` 必须重启 MCP 服务器进程才会生效**：

```powershell
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
  Where-Object { $_.CommandLine -like '*ee_mcp_server*' } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
# 下次调用 MCP 工具时 DSH 会自动重新拉起
```

**只允许一个 Frida 客户端**：跑 `bridge\*.py` 脚本前先杀掉 MCP 服务器进程。
沙箱可能禁止本会话枚举进程（`Get-Process`/`tasklist` 静默返回空），
此时上面的 WMI 命令会报「拒绝访问」——需要放宽权限才能执行；
`frida.enumerate_processes()` 也会漏掉 Editer.exe，**不要用它判断 EE 是否在跑**，直接调 `ee_status`。

---

## 2. 待办（按优先级）

### 2.1 【最高】`ee_new_canvas` —— 已定位到真正的卡点，但**有一条会崩编辑器的死路，别走**

**先纠正两条旧结论：**

- ❌ 旧文档说"`esCanvas` 构造函数没有导出" —— **错的**。`??0esCanvas@@QAE@XZ`（RVA `0x1c37b0`）、
  `??0esCanvas@@QAE@HH@Z`（`0x1c3aa0`）、`?Initialize@esCanvas@@QAEXXZ`（`0x1c3dc0`）**全都导出了**。
- ✅ 对象大小 **0xe0**（`esCanvasList::CreateObject`，RVA `0x1c22b0`：
  `operator_new(0xe0)` + `__autoclassinit2(c,0xe0)` + `esCanvas::esCanvas(c)` + `*(u16*)(c+4)=typeId`）。
  普通画布的类型字是 **0x2020**（从活画布上读出来的）。

#### ⛔ 死路：手工建 `esCanvas` + `esDocument::InsertNewCanvas`

看起来完美：`doc+0xcfc` 确实是 `esPageList*`，`InsertNewCanvas` **返回 1**，
`ee_canvases` 也把新画布列为活动画布……

**然后 Editer.exe 就死了**（`script has been destroyed`，进程消失，未保存内容全丢）。

原因：这样插进去的画布**没有嵌入文本流**。真正的嵌入动作
（`operator_new(0x44)` + `esEmbedder` + `esText::AddChrObj` + `esMainTable::AddCanvas`）
在 `esTextUI::InsertCanvas(esCanvas*, int)` 里；少了它，画布是 0×0 的悬空对象，
下一次排版/重绘就把它解引用掉。

> `ee_bridge.js` 的 `createCanvas` 现在**默认拒绝**插入（要显式传 `confirmDangerous` 才做）。
> **不要**为了"先拿到一个画布"而重新打开这条路。

#### 🔑 真正的卡点：`esTextUI::IsValid()` 就是 `*(int*)(this + 0xdc) != 0`

`esTextUI::InsertCanvas()`（RVA `0x48c6e0`）的前置链：

```
IsAbleToInput(this,1) → GetMainTable(this,-1,NULL) → GetSelState(this)
→ sgMedia::GetLamp(this+0x14) → <lamp 转 ID2D1Geometry*> → *(short*)(geom+4) == 4
```

实测（`ee_diag insertprobe`，传 `pageList` = 活动页表）：5 个 `esTextUI` 实例
**vtable 都对，但 `IsValid()` 全为 0**、`IsAbleToInput(1)` 全为 0、`GetMainTable` 全为 NULL。
其中 `0xae92f90` 的 styleSheet 正是本文档的 `0xae925c8`，所以它才是"活的那个"。

**根因**：`IsValid()` 与 `IsAbleToInput()` 都先看 `+0xdc`，而 `+0xdc` 由
`SetUIOwner`（在 `esTextUI::SetTextUI(esObject*)` 里被调用）写入 ——
**只要 EduEditer 没拿着文本光标（比如焦点在浏览器上），它就被清成 0**，插入路径整条失效。

#### ✅ 已打通：`ee_new_canvas` 现在调用引擎自己的插入

**根因就一条**：活的 `esTextUI` **不在堆扫描结果里**——它挂在页表上，
只能通过 `?GetUI@esPageList@@QBEPAVesTextUI@@XZ`（RVA `0x726e0`）拿到。
原来的 `newCanvas()` 只遍历堆扫描到的 5 个实例（全是模板/工具栏的 UI），所以永远返回 NULL。

第二个条件也确认了：`IsValid()` 就是 `*(int*)(this + 0xdc) != 0`，
**只有光标落在正文里才为真**。实测（同一进程，只差一次鼠标点击）：

| 时机 | `GetUI` 返回 | `IsValid` | `IsAbleToInput(1)` | `GetMainTable` |
|---|---|---|---|---|
| 刚打开文档、未点正文 | 拿不到 | 0 | 0 | 0x0 |
| **点进正文之后** | `0x7c88850` | **1** | **1** | `0x7c8cd04` |

所以 `ee_new_canvas` 现在：取活动页表 → `GetUI` → 对该 UI 调
`esTextUI::InsertCanvas()`（引擎自己的 Space+G 实现，**不手工造任何对象**）。
实测返回 `{ok:true, textUI:0x7c88850, source:"pageList.GetUI", canvas:0xa33fb40}`，
编辑器不崩、原图 7 个图元完好，随后 `ee_canvases` 报出画布已切到光标处的新空画布，
往里画线能正常渲染（已截图确认画布边框 + 画的线）。

#### ⚠️ 两个已知边界

1. **`InsertCanvas()` 的返回值不是你实际在画的那块画布。**
   它返回 `0xa33fb40`，而页表的 `GetActiveCanvas(pl,0)` 报的是 `0x797a718`；
   往返回的那块上画线**不渲染**，往页表报的那块画**正常显示**。
   → 所以 `canvas()` 继续以**页表报的活动画布**为准是对的，别信 `InsertCanvas` 的返回值。
2. **不要连着重调**。第二次调用又造了个 `0xa33fd10`，但它既没出现在画面上也没变成活动画布
   （连调两次的截图与只调一次完全相同）。目前按"每个画布只调一次"使用。

#### 如果以后还要深挖

- `InsertCanvas` 的返回值与页表活动画布为何不一致：从 `esTextUI::InsertCanvas()` 尾部
  （RVA `0x48c6e0` 从 "operator_new(0x44) + esEmbedder + esText::AddChrObj" 往后）
  看它是否在成功后另建/替换了画布。
- 连调为什么产生孤儿画布：同样看 `esText::AddChrObj` 与 `esMainTable::AddCanvas` 的顺序。

相关导出（都可用）：`?IsValid@esTextUI@@QBEHXZ`(0x6db70)、`?IsAbleToInput@esTextUI@@QAEHI@Z`(0x49a0f0)、
`?GetMainTable@esTextUI@@QBEPAVesMainTable@@HPAUtagPOINT@@@Z`(0x480090)、
`?GetSelState@esTextUI@@QBE?AW4eSS@@XZ`(0x6dd20)、`?GetLamp@sgMedia@@QAEPAVelfLamp@@XZ`(0x6d5c0)、
`?GetUI@esPageList@@QBEPAVesTextUI@@XZ`(0x726e0)。
诊断入口：`ee_diag insertprobe {pageList}`（逐候选报 vtable/IsValid/IsAbleToInput/GetMainTable）。

### 2.2 【低】其他

- ~~**标签字体/斜体**~~ —— ✅ **已解决**：斜体由**字体槽 `+0x6e`** 决定（本文档里槽 0 = 正体、
  槽 13 = 斜体），而且**只在 `feature ≠ 0`（引擎自己解析文本填 EQLine）时生效**；
  手动 `AppendString` 那条路不吃 `+0x6e`，所以怎么调都是正体。
  `ee_draw_label` 现在会自动从画布上已有的标签读出槽号与 padding 并套用，
  画出来的字母与用户手插的**字体/字号/斜体完全一致**（见 `01-drawing-model.md` §7.8 第 4 点）。
  还可继续挖：`esEQLine::AppendString` 第 4 个 `ushort` 参数的语义（手动路径的样式），
  以及除斜体外的字符属性（粗体、字号、颜色 `SetTextColor`）。
  ★ 2026-10：无标签可抄时的自动解析也通了（见 §3.9 第 1 条）；多字符标签截断已修
  （k 字 = 逐段字符数，见 `analysis/figures-progress.md` §2）。
- 样式控制：形状 `+0x34` 是样式字（默认 `0x040700FF`，标签 `|= 0x4001007`），位域未解
- 真正的贝塞尔曲线：`CreateFromPathData` 拒绝全 `0x03` 类型数组，布局未解（函数图象要用）
- 撤销集成：直接 `AddItem` 绕过了 `esUndo`，agent 画的东西 Ctrl+Z 撤不掉
- 页面单位 ↔ 毫米换算未确证

---

## 3. 已完成的、不要重做

| 能力 | 实现位置 |
|---|---|
| 直线/折线/多边形/矩形 | `CreateFromPathData`，规则见 `01-drawing-model.md` §2.3 |
| **真圆形** | `esSegCircel`，配方见 `01-drawing-model.md` §7.1（**不要**再用多边形近似） |
| **字母标注** | `ee_draw_label` → `makeLabelShape`，配方见 `01-drawing-model.md` §7.8（含斜体样式匹配） |
| **直角符号** | `ee_draw_angle_mark(kind="right")` —— 三段开口折线，无新原语 |
| **等角弧 / 双弧** | `ee_draw_angle_mark(kind="arc"/"double")` → `ee_draw_arc` → `esSegArc`，配方见 §7.9 |
| 删除图元 | `ee_bridge.js` 的 `unlinkShape`，见 §7.2 |
| 枚举图元 | `ee_list_shapes`（带类校验 + vtable 类名 + 虚拟 `RecalcLayout` 派发） |
| 画布边界 | `ee_canvas_bounds` |
| **画布选择确定化** | `EEGateway.canvas()` —— 按（图元数 ↓，宽度 ↓）排序，见 `ee_canvases` |
| 重绘 | `ee_redraw`（EnumWindows + InvalidateRect/UpdateWindow） |
| **目视验证** | `tools\capture_window.ps1`（PrintWindow）+ `tools\crop.py` |

**已有 MCP 工具**：`ee_status`、`ee_canvases`、`ee_new_canvas`（已打通，边界见 §2.1）、
`ee_draw_line/polyline/polygon/rect/circle/label/figure/arc/angle_mark`、`ee_fonts`、
`ee_canvas_bounds`、`ee_list_shapes`、`ee_delete_shape`、`ee_redraw`、
`ee_goto_problem` / `ee_goto_text` / `ee_caret_canvas`、`ee_diag`

`ee_diag` 的 op（只读，但 `call`/`callvirt` 会真的执行引擎代码）：
`canvases`、`fontsheets`、`hexdump`、`readu32`、`readstr`、`vtname`、`vtslots`、`zwstr`、
`scantext`、`shapecount`、`recalc`、`names`、`expaddr`、`call`、`callvirt`、`trace`、`tracelog`。

> `ee_diag trace <enable>` 会用 Frida Interceptor 挂 `Draw/Render/GetLineList/IsVisible`，
> 配合一次 PrintWindow 就能看清"某个图元到底走到绘制链的哪一步"——**本轮就是靠它定位问题的**。

### 3.9 线宽 / 文字标注 / 填充 —— 已打通，**批量绘图直接用这套**

**画布单位：1 单位 = 1/400 毫米。** 用户刻度尺标定：17000 单位 = 4.25 cm ✓。
换算：`单位 = 毫米 × 400`；`1 大刻度 = 1 厘米 = 4000 单位`。
（笔、边距、填充走的是**同一套单位**，很自洽。）

| 目标 | 位置 | 值 |
|---|---|---|
| **线宽** | `esPenInfo+0x08`；笔**内嵌在** `shape+0x50`（所以 `GetPenInfo` 恒返回 `shape+0x50`） | `0.25mm = 100`；`0.20mm = 80`（默认） |
| **标注字体** | `esSegLable+0x6e`（u16） | **文档级字体槽号**。"Times New Roman + 斜体 + 五号" = 用户的 **"AY" 方案 = 槽 18** |
| **标注边距** | `esSegLable+0x6c`（u16） | `1.00mm = 400` |
| **数学化 / 标注点 / 边框** | `esSegLable+0x70 / +0x71 / +0x72`（各 u8） | 对话框三个勾选框，非 0 = 勾选 |
| **填充** | **`shape+0x38`** | `0` = 不填；**`12` = 填 #A5A5A5**（用户的阴影色） |
| 标注排版文本 | `esSegLable+0x80` | 引擎填的 `esEQLine`，**别手工填** |

`esSegLable::GetLableFreature`（RVA `0x3eac10`）给出了特性字的合成公式：
`feature = (fontSlot<<16) | (+0x73 & 0xF0) | (+0x70?1:0) | (+0x71?2:0) | (+0x72?4:0) | 数学字符位`

**这一节踩过的坑（很重要）**：
1. **改 `+0x6e` 不会立刻生效**。可见文字被烤进 `+0x80` 的 `esEQLine`，字体是**烧进去的**：
   只写字段再 `ee_redraw`，**画面一个像素都不变**。必须 `esSegLable::Build(1)` +
   `RecalcLayoutLable`，或者干脆**删掉重建**（创建流程在 Build 之前设字体，最保险）。
2. **填充开关不是 `+0x34` 样式字的 bit31**（我连续踩了两次）。对照实验：EE 里手工填充前后
   比对同一对象 224 字节，**只有 `+0x38` 从 0 变 12**，样式字根本没动。
3. **`#A9A9A9` 是题目扫描图片里的灰，不是 EE 填充工具的灰（#A5A5A5）**。两者差 4 个色阶，
   肉眼几乎一样，害我误判了好几轮"填充已经好了"。
4. 判读截图时**先确认灰是哪一个色号**，别靠肉眼。

**图幅规则（用户定）**：匀称图形 —— **整体约 5 大刻度（≈5cm），最右侧落在刻度 5~6 之间**；
狭长/扁平的图另外调试。示例：正方形边长 **20060 单位**
（选它是因为 `¼×20060=5015`、`20060/17=1180` 都是整数 → 交点零舍入）。
用户原话：最左侧顶不到 0 刻度没关系，就是"从零点几到五点几"。

**`ee_diag` 本轮新增的 op**：
```
penwidth   {canvas, value}                      一张画布所有图元设线宽（1/400mm）
lablestyle {canvas, fontIndex, margin, math, point, border}
                                                空参数 = 只读回读所有标注的当前值（排查很好用）
fontslot   {face, style}                        探字体表（CheckFont / BuildFont / GetFontID）
poke       {addr, value}                        写 32 位。样式字/填充位没有导出 setter，只能这么写
```

**还没打通的（自己用够，给别人用不够）**：
1. ~~**字体名 → 槽号**~~ —— ✅ **已解决（2026-10）**：不用 `CheckFont`/`GetFontID`（那是另一套
   ID 体系，290 不是槽号）；直接遍历 `esFontSheet::GetFont(sheet, slot, size)` 的返回对象调
   `esFont::GetFontName()/IsItalic()/IsBold()/GetFontSize()`（1/100pt，1050 = 五号）。
   已上线：MCP 工具 **`ee_fonts`**；`ee_draw_label`/`ee_draw_figure` 在"画布无标签可抄"时
   按 `font_face`（默认 "Times New Roman"）+ `font_italic`（默认 true）自动解析槽号，
   返回值里的 `fontIndexSource` 会报来源。实测：测试文档页表字体表 TNR 斜体 = 槽 11。
   坑：越界槽会**回落到首个字体对象**（桥按指针重复截断）；槽表挂在 **esFontSheet** 上
   （页表 `GetStyleSheet()` 返回的就是它）。
2. **颜色 → `+0x38` 值的映射**：只知道 `12 = #A5A5A5`，其它颜色未知（疑似调色板索引）。
   要查就反编译 `esShapeBase` 里读 `+0x38` 的那处。

---

## 4. 坑（都踩过，别再踩）

1. **`Memory.alloc` 的指针转成字符串后会被 GC 释放** → 后续写入已释放内存 → `frida-agent.dll 0xc0000005`。
   凡是"分配 + 填充 + 调引擎"必须在**同一个 JS 帧**内完成。
2. **同一进程只能挂一个 Frida 客户端**，REA 的 Frida 会话与本桥并存会互相干扰。
   另外本会话的沙箱**禁止直接 attach**（`ProcessNotFoundError`），必须走 MCP 服务器。
3. **`esPageList::CreateObject` 不是图元工厂**（只是 `CreatePage` 的薄封装），批量调用会创建大量页对象并导致崩溃。
4. **画布链表可能混有 `Editer.exe` 定义的类**，对它们调 `esShapePath` 的方法会破坏状态（`ee_list_shapes` 已防住）。
5. 引擎不保证线程安全，**多个 MCP 调用不要并发**。
6. 用户文档 `D:\Douding\八下四边形分类汇编.wsd` **绝对不能动**；当前打开的是 `测试文档.wsd`（测试用）。
7. `Editer.exe` 运行时基址 0x660000、Ghidra 基址 0x400000，换算 `运行时 = Ghidra - 0x400000 + 0x660000`。
   **eslib 的类优先用 eslib 导出名调用。**
8. **`geometry()` 必须走 vtable 派发 `RecalcLayout`（+0x64）**：
   `esShapeLine` 的 +0x64 是 `esShapeBase::RecalcLayout`，而导出
   `?RecalcLayout@esShapePath@@MAEXXZ` 是 esShapePath 的实现，对 0x5C 的 esShapeLine 调用会越界读。
   已改为 `ee_bridge.js` 的 `recalcShape`（`callVirt(obj, 0x64)`）。
9. **`esShapeBase::Draw` 只负责可见性判断**，真正画东西的是 vtable **+0xBC** 的 `Render`；
   条件是 `esRender::IsVisible(GetSolidRect(this,1))`。判断"为什么没画出来"时先确认这条链走到了哪一步。
10. **截图验证的两个陷阱**：
    - `InvalidateRect` 不会让被遮挡的窗口重绘，必须用 `PrintWindow`（本仓库脚本用 flag=2）；
    - **窗口最小化时 `PrintWindow` 返回旧位图**（表现为"图片和新截图一模一样"）。
      `capture_window.ps1` 现在会先 `ShowWindow(SW_SHOWNOACTIVATE)` 还原再抓。
11. **判断"MCP 工具是否生效"**：DSH 会在服务器重启后重新拉取 `tools/list`，新工具立即可用。
12. **标签的斜体（字体槽 `+0x6e`）只在"引擎自己解析文本"那条路上生效**：
    `feature = 0` + 手动 `esEQLine::AppendString` 的路径**永远画正体**，
    把 `+0x6e` 改成什么都不会变（`AppendString` 用它自己的第 4 个参数取字体）。
    要匹配文档里手插字母的斜体，必须用 `feature ≠ 0`。
    `ee_draw_label` 默认已是 `0x80000001`，并自动读文档已有标签的槽号与 padding，
    不要为了"保险"改回 `feature = 0`。
13. **不要用"猜 feature"来决定是否 append**：直接读 EQLine 的 `+0x30` 计数
    （`ee_bridge.js` 已实现 auto 模式）——feature=0 时它会自己补 append，
    feature≠0 时它会跳过，两种情况都不会出现空白或双字母。
14. **`esSegArc` 的角度是弧度、0° 朝上、而且朝负方向扫**（三个坑叠在一起，
    见 `01-drawing-model.md` §7.9）。自己写弧相关代码时按那张表换算，
    否则会得到"转了 90° 的长弧"这种看似引擎有 bug 的结果。
    **验证扫描区间不必截图**：弧的 `p1`/`p2` 就是两个端点，直接和期望值比即可。
15. **不要拿 `PrintWindow` 的同一张图当"没变化"的证据**：EE 窗口最小化时它会返回旧位图。
    `capture_window.ps1` 已会先 `ShowWindow(SW_SHOWNOACTIVATE)` 还原；
    若怀疑图是旧的，先比 SHA256 或改用内存读数验证。
16. **⚠️ 画布不能手工"造一个再登记"**：`esDocument::InsertNewCanvas` 会返回 1、
    `ee_canvases` 也会列出新画布，看起来很成功，**但 Editer.exe 会在下一次排版/重绘时崩溃退出**，
    未保存内容全丢（本项目真实踩过）。原因见 §2.1。`createCanvas` 已默认拒绝插入。
17. **整个窗口截图全黑 = EE 已经没了**，不是截图失败。用 `ee_status` 确认
    （会报 `script has been destroyed`）。此时磁盘上的 `.wsd` 是安全的——
    本项目所有绘制都只在内存里，**没按 Ctrl+S 就没写盘**。

---

## 5. 用户的工作方式

- 数学题 + 模糊图片来自教研网下载的 Word，EE 把图转成 `.wsd`
- **画图前用空格+G 建画布**（这也是 `ee_new_canvas` 想做掉的一步）
- 参照文档：`D:\Douding\八下四边形分类汇编.wsd`
- 判定成败的方法：**让用户目视确认**（他没看到就是没成）；本仓库现已能自行截图预检
- 图形只在内存里，**提醒用户 Ctrl+S**
