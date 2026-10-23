# eslib 画布对象族 — 反编译规格（阶段 2 · 第十一批 · 嵌入画布 3.6a）

- 模块：eslib.dll；函数：**269 个**（esCanvas 245 · esEmbedder 24）
- 伪代码（原样）：`analysis/pseudo/eslib/esCanvas.decomp.txt`（matched=269 dumped=269 · 18,179 行）
- 类型头：`analysis/types/esCanvas.h`
- 台账：269/269 → `decompiled`（status-overrides）
- 角色：文档"插图画布"的**双对象对** —— `esEmbedder`（类型字 0x40 的**内嵌字符对象**，以字符身份进文本行：字体槽 `+0x1a`、上下留白 `+0x1c/+0x20`、总宽 `+0x30`、被绑画布 `+0x38`、垂直对齐模式 `+0x3c`、内边距 `+0x40`）持有 `esCanvas`（类型字 0x2010，尺寸 0xe0，`esContainer` 派生）：图形双链（`+0x34` 首 / `+0x38` 尾，节点 `+0x44` next / `+0x48` prev）· 宿主回引 `+0x40` · 角色 `+0x48` · 32 位标志 `+0x4c` · 画布链 `+0x50/+0x54` · 原点平移 `+0x58/+0x5c` + 内嵌矩阵 `+0x64` · 边距 LTRB `+0xb8..+0xc4` · 外框 `+0xc8` · 内容实心 `+0xa8` · 状态字 `+0xd8` · 自定义边框点 `+0xda/+0xdc`。本批定下：**布局三态（内嵌/环绕/浮动）与边框两型（矩形/自定义点）**、**ReсalcLayout 的外框—内容—边距算法**、**全批撤销码（§8）**、**嵌入宿主对齐模式（§1）**、**框选/角色/选择状态** 及坐标变换协议。绘制/快照/导出（§7.2）与变换/排列/剪贴板（§7.3）两区段本轮补读（**269/269 全读**）。

## 0. 谱系与公共结构（本批结构性结论）

| 结论 | 证据 |
|---|---|
| `esCanvas : esContainer`（op= 直调 `esContainer::operator=`）—— esContainer 供出 `+4` 类型字（本类 = **0x2010**）· `+0xc` 修改标志 · `+0x34/+0x38` 图形链首尾；esCanvas 自有字段 `+0x3c` 起至 `0xe0` | `operator= 13870` / `IsEmpty 4550` / ctor `1c37b0` |
| `esEmbedder : esCharEx`（拷贝 ctor/op=/Undo 均链 esCharEx 基实现）；类型字 `+4=0x40`；尺寸 ≥0x44（拷贝 ctor 只多拷 `+0x38/+0x3c/+0x40`） | 拷贝 ctor `8390` / op= `83e0` / ctor `a7860` / Undo `a8060` |
| 宿主绑定协议：`esCanvas+0x40` ↔ `esEmbedder+0x38`（或 `esCvsAnchor`）双向；**内嵌态宿主 = esEmbedder（0x44）、环绕态宿主 = esCvsAnchor（0x2c），切换即 OnQuickLayout 重建**；embedder 析构清 `canvas+0x40=0` 后调 `canvas vtbl+0x5c(0,0)`；反向 `RemoveEnvoy` 用 `esChrObj::RemoveSelf(+0x40)` | dtor `a7910` / RemoveEnvoy `1cede0` / OnQuickLayout `1ccac0` / GetAnchor `13500` |
| 画布由 **esCanvasList**（类型 0x2011）持有链：列表 `+0x38` 首 / `+0x3c` 尾；节点 `+0x50` next / `+0x54` prev；`IsFixed`=`+8!=0 && +0x54==0`；`IsFloatBox`=`+0x54!=0 && +0x40==0 && +8` 为 0x2011 | `Detach 1d5760` / `IsFixed 13740` / `IsFloatBox 13690` |
| 布局三态（flags&7）：**内嵌 inline（0）** / 环绕 wrapped（1..3）＋ followed 位 3；宿主迁移协议 `esMainTable::SetAsEmbeddFiture`（变内嵌）/ `esTopTable::SetAsAnchorFiture`（变浮动）由 CheckLayoutChange 触发 | `IsInline 135d0` / `IsWrapped 13600` / `CheckLayoutChange 1cc2a0` |
| 边框两型（flags 位 12..13 = 0x3000）：0x1000 矩形 / 0x2000 自定义点（点数组 `+0xdc`、点数 `+0xda`）；外框统一在 `+0xc8`（zRect），边距 `+0xb8/+0xbc/+0xc0/+0xc4` | `GetFrameType 13700` / `SetOutlineInfo 1c4c30` / `GetOutlineInfo 1c4850` |
| 默认边距：`SetOutlineInfo(NULL)` → L=R=**800**、T=B=**400**；`SetAsDefaultEmbeddedStyle` 全部 **400**；构造三参版 `(w,h)` = 默认构造 + `SetAsBorderRect(0,0,w,h)`（→ 0x1000） | 三函数原文 |
| 锚点对象 **esCvsAnchor**（独立类型，GetAnchor 经 vtbl+8 判型）：`+0x14` short 索引（撤销 0x523 同款）、`+0x24` canvas 反引；撤销码 0x214（摘）/0x215（建） | `Undo 1d0050` / `Undata 1d02e0` |
| 全局静态：`GetShapeList()` 返回文件级 `m_shape_list`（`esShapeList::Reset(list,this)` 后使用）——**多画布共享实例，非并发安全** | `13850` |
| OnEdit 快照用**文件级静态** DAT_106cd038（旧 flags）/DAT_106cd248（旧外壳矩形）；退出对比 `&0x30f` + 矩形 → 按宿主类型（esEmbedder 0x40 / esCvsAnchor 0x81）记撤销记录 | `OnEdit 1c3f70` |

**布局总表**

- esContainer 供出：`+4` 类型字（0x2010）· `+8` 所有者（画布时 = esCanvasList*，类型 0x2011）· `+0xc` 修改标志（置 1 即"已改"）· `+0x34/+0x38` 图形链首/尾
- esCanvas（0xe0）：
  - `+0x3c` ushort **页码**（`page()` 直读；撤销码 0x208）· `+0x3e` ushort（随 op= 拷贝；用途待核）
  - `+0x40` host（esEmbedder/esCvsAnchor/…，双向）· `+0x44` dword **背景色**（COLORREF；FillBackround 填充内容区 / Load 输出整幅背景矩形 / CreateBitmap 清屏色 / 属性 0x212）· `+0x48` esRole*
  - `+0x4c` dword 标志 · `+0x50/+0x54` 画布链 next/prev
  - `+0x58/+0x5c` 原点 x/y（矩阵平移量）· `+0x60` esMatrixObj（**Matrix @+0x64**）· `+0x70` esRefLine
  - `+0xa0` es3DSpace* · `+0xa4` 活动图形（GetActive）· `+0xa8` 内容实心矩形（内部坐标，4 个 int）· `+0xac..+0xb4` 续（并集缓存）
  - `+0xb8/+0xbc/+0xc0/+0xc4` 边距 L/T/R/B · `+0xc8` 外框矩形（外部坐标；GetWidth/Height 源）
  - `+0xd8` ushort 状态（bit0 锁定；bit2=4 TextUI dirty；bit3=8 宿主待通知；其余交互态）· `+0xda` ushort 自定义边框点数 · `+0xdc` tagPOINT* 边框点数组
- esEmbedder（**尺寸 0x44**，OnQuickLayout 内 `operator_new(0x44)`；esCharEx 基类部分不展开）：
  - `+0x14` ushort（SerializeForRevive 双写）· `+0x1a` 字体槽索引（CreateItem 烘入）· `+0x1c/+0x20` 上/下留白（ResetObjSize 按对齐模式算）· `+0x30` 总宽
  - `+0x38` esCanvas*（被绑画布）· `+0x3c` int 垂直对齐模式（0 默认 / 负=显式下基 -(v+1) / 1 上基 / 2 居中 / 3 顶 / 4 底；属性 0x202，撤销 0x202）· `+0x40` int 内边距量（字高×DAT_1057ef78）

**标志 `+0x4c` 位表**

| 位（掩码） | 含义 | 证据 |
|---|---|---|
| 0..2 (`7`) | 布局模式：0=内嵌；1..3=环绕（子类型） | `GetWrapMode 13720` / `IsInline 135d0` |
| 3 (`8`) | followed（紧随） | `IsFollowed 13630` / LoadProp 0x102 |
| 7 (`0x80`) | 属性 0x104（语义待核） | `LoadProp b1d0` |
| 8..9 (`0x300`) | 水平对齐（存值 = 枚举<<8） | `GetAlign 137d0` / LoadProp 0x103 |
| 11 (`0x800`) | 属性 0x105（语义待核） | `LoadProp b1d0` |
| 12..13 (`0x3000`) | 边框类型：0x1000 矩形 / 0x2000 自定义点 | `GetFrameType 13700` |
| 14 (`0x4000`) | 动态模式（IsDynamicMode） | `IsDynamicMode 133c0` |
| 15 (`0x8000`) | 仅旧版序列化：标记"流中含 +0x44"；读后掩 `0x73ff` | `Serialize d4ee0` |
| 16..17 (`0x30000`) | 考试标记 exam mark（值 = 结果>>16） | `GetExamMark 136e0` |
| 20 (`0x100000`) | 允许默认动画 | `IsAllowDefAnimat 135a0` / OnAllowDefAnimat 撤销 0x20e |

**序列化版本常量**（Serialize `d4ee0`）：`0x107000c` · `0x107000d` · `0x1090629` · `0x2000432` —— 版本分叉：<0x107000d 老格式（页码 ushort `+0x3c` + tagPOINT + lamp 参数直接写；flags 只读 ushort，`&0x8000` 位决定是否读 `+0x44`，再掩 `0x73ff`）；≥0x107000d 写 esRefLine（`vtbl+0x40`）；边框三态（矩形 LTRB<<2 / 点数+raw / tagRECT raw）；数量 + 图形逐只（各 `vtbl+0x40`）+ esMatrixObj + 尾部基类流。

**画布 vtbl 已确认槽**：`+0x10` CollectStyles · `+0x18` LoadProp · `+0x1c` SaveProp · `+0x24` CopyFrom · `+0x34` GetID · `+0x38` 自毁 · `+0x3c` Insert · `+0x40` Serialize · `+0x44` 重排通知 · `+0x48` OnMessage · `+0x4c` IsEqual · `+0x58` CreateObjByType · `+0x5c` 宿主解绑回调(0,0)。

## 1. esEmbedder（24 个）（内嵌字符对象 = 画布的文本行身份）

| 函数 | 入口 | 规格 |
|---|---|---|
| `GetSearchChar(c)` | `8370` | 恒返回 `L'\x0e'`（14）——"查找/替换"把整块画布当单一字符 |
| `ctor(拷贝)` | `8390` | esCharEx 拷贝 + `+0x38`(canvas) / `+0x3c` / `+0x40` 三字段 |
| `operator=` | `83e0` | 同上（esCharEx::operator= + 三字段） |
| `ID()` | `a7710` | `L"esEmbedder"` |
| `isKindOf(name)` | `a7720` | 名匹配→1，否则 esCharEx::isKindOf |
| `isOf(name)` | `a77d0` | 同上（isOf 语义） |
| `ctor()` | `a7860` | esCharEx() + `+4=0x40` + `+0x38/+0x3c/+0x40=0` |
| `ctor(canvas*)` | `a78b0` | 同上 + `+0x38=c`；**`c+0x40=this`**（绑定回写） |
| `~esEmbedder()` | `a7910` | 解绑：若有 canvas → `c+0x40=0`、`c vtbl+0x5c(0,0)`；~esCharEx |
| `GetMd5ForExam(md5s)` | `a7990` | canvas 存在 → 内容/名字串交 esSelector 形成选择串 → `FUN_1007c110` 记 MD5（考题比对） |
| `CreateItem(id, fontSheet)` | `a7a20` | 重绑 `c+0x40=this`；`+0x1a = esFontSheet::GetCurFontIndex(fontSheet,0)`（字体槽烘入，见 AGENTS 字体槽陷阱） |
| `CollectStyles(sheet, mask)` | `a7cc0` | esCharEx::CollectStyles + canvas `vtbl+0x10(sheet)` |
| `CheckCanvasPosition(&x,&y)` | `a7d00` | 取本条字符内坐标（`vtbl+0xc4`）→ 与外框 `+0xc8` 原点求差 → 非零则 `esCanvas::Offset` 对齐；返回 canvas |
| `Load(line,...)` | `a7db0` | CheckCanvasPosition + canvas `Load(page, subj)` |
| `Draw(render,...)` | `a7df0` | CheckCanvasPosition；`esRender::IsShow(render, 0x80000000)` → canvas `Draw(render, show)` |
| `ResetObjSize(...)` | `a7e40` | 尺寸核心：`+0x40 = 字高 × DAT_1057ef78`；`+0x30 = 宽 + 2×+0x40`；按 `+0x3c` 模式（0 默认 / <0 显式下基 / 1 上基 / 2 居中 / 3 顶 / 4 底）用画布轮廓高分配 `+0x1c`(顶)/`+0x20`(底) 留白；inline 与非 inline 分支 |
| `Undo(0x202,A,B)` | `a8060` | 码 **0x202** ↔ `+0x3c` 经 zArchive 对换；else esCharEx::Undo |
| `IsClickable(sheet)` | `a80d0` | amulet `esSnapObj::Is(4)` → 1（画布可点判定） |
| `OnMessage(msg,flag)` | `a8120` | canvas `vtbl+0x48`；处理过 → 自身 `vtbl+0x44(0)`；末 esObject::OnMessage |
| `Undata(...)` | `a8180` | 直通 esObject::Undata |
| `IsEqual(obj,sheet)` | `a81b0` | esCharEx::IsEqual + canvas（`+0x38` 同 / 都空 / `vtbl+0x4c`） |
| `SerializeForRevive(arc)` | `a8240` | 存"跨档复活"引用：canvas 对象 id（或 0）+ 解引用；读回按 id 从 esStyleList（`m_pUndo+8 ↓ +0x794`）取回重绑；另存/读 `+0x3c`、`+0x14` |
| `Serialize(arc,sheet,ver)` | `a8330` | 主档：canvas 有无以标记字识别（读回 `operator_new(0xe0)` 建画布再反序列化绑定）；主表存在时 `AddCanvas` + 新画布按相对对象序入链；`+0x3c`、`+0x14` 双写 |
| `CopyFrom(obj,exchanger)` | `a8640` | `+0x3c` 对齐；新建 canvas（0xe0）→ AddCanvas → canvas `vtbl+0x24(srcCanvas, exchanger)`（内容克隆） |

## 2. esCanvas 状态/查询（L5–704 精读区）

| 函数 | 入口 | 规格 |
|---|---|---|
| `IsEmpty()` | `4550` | `+0x34==0`（无图形） |
| `page()` | `13370` | `+0x3c` ushort（**页码**，撤销码 0x208 同字段） |
| `matrix()` | `13390` | 返回 `(Matrix*)(this+0x64)`（esMatrixObj 内嵌矩阵） |
| `IsDynamicMode()` | `133c0` | flags & `0x4000` |
| `IsLocked()` | `133f0` | `+0xd8 & 1` |
| `Lock()` | `13420` | `+0xd8 \|= 1`（加锁） |
| `Unlock()` | `13450` | `+0xd8 &= ~1`（解锁） |
| `SetState(m)` | `13480` | `+0xd8 \|= m` |
| `RemoveState(m)` | `134b0` | `+0xd8 &= ~m` |
| `CheckState(m)` | `134e0` | 返回 `+0xd8 & m`（非零即含 m 段） |
| `GetAnchor()` | `13500` | `+0x40` 且 `vtbl+8(ID)` 判为 esCvsAnchor → 返回，否则 0 |
| `GetEmbedder()` | `13550` | 同上判 esEmbedder |
| `IsAllowDefAnimat()` | `135a0` | flags & `0x100000` |
| `IsInline()` | `135d0` | flags & 7 == 0 |
| `IsWrapped()` | `13600` | flags & 7 != 0 |
| `IsFollowed()` | `13630` | flags & `8` |
| `IsHostedBox()` | `13660` | `+0x40 != 0` |
| `IsFloatBox()` | `13690` | `+0x54!=0 && +0x40==0 && +8!=0 && (+8)`为类型 0x2011 |
| `GetExamMark()` | `136e0` | flags & `0x30000` |
| `GetFrameType()` | `13700` | flags & `0x3000` |
| `GetWrapMode()` | `13720` | flags & 7 |
| `IsFixed()` | `13740` | `+8!=0 && +0x54==0` |
| `IsFixed(type)` | `13780` | `+0x54==0 && +8!=0 && (+8)`为指定类型 |
| `GetAlign()` | `137d0` | flags & `0x300` |
| `GetWidth() / GetHeight()` | `137f0 / 13810` | 外框 `+0xc8` 矩形宽 / 高 |
| `Get3DSpace()` | `13830` | `+0xa0` |
| `GetShapeList()` | `13850` | 全局 `m_shape_list` 重置后返回（esShapeList::Reset(list,this)） |
| `operator=` | `13870` | esContainer::operator= + `+0x3c..+0xdc` 全段拷贝（含 esMatrixObj/esRefLine 子对象赋值） |
| `className()` | `1b2a60` | 直返 `esContainer::ID()`（= `L"esContainer"`）——画布对外类名走容器基名 |
| `ID()` | `1c3670` | `L"esCanvas"`（静态） |
| `isKindOf(name)` | `1c3680` | 名 == ID() → 1；否则转 `esContainer::isKindOf` |
| `isOf(name)` | `1c3720` | 仅与 ID() 比较（不上溯父类） |

## 3. 生命周期 / 图形链 / 宿主（L1706–2606 精读区）

| 函数 | 入口 | 规格 |
|---|---|---|
| `esCanvas()` | `1c37b0` | 默认构造：esContainer + 子对象 esMatrixObj(@+0x60) / esRefLine(@+0x70)；类型字 0x2010 |
| `esCanvas(copy)` | `1c3890` | 拷贝构造（524B）：基类拷贝 + 全字段 + 子对象拷贝 |
| `esCanvas(w,h)` | `1c3aa0` | 默认构造 + `SetAsBorderRect(0,0,w,h)`（→ 边框 0x1000） |
| `~esCanvas()` | `1c3bb0` | 析构（285B）：反绑宿主 → 子对象/边框点回收（细节复核后补） |
| `TransferFrom(group)` | `1c3cd0` | 整段搬迁：组 `+0x5c` 首/`+0x60` 尾链 → 本画布链尾；节点 `+0x44` 为链 next |
| `SetAsBorderRect(l,t,r,b)` | `1c3d60` | 写外框 `+0xc8`；边框类型置 `0x1000` |
| `Initialize()` | `1c3dc0` | 字段初始化（边距/状态/链清空；细节复核后补） |
| `OnAllowDefAnimat()` | `1c3eb0` | 切换 flags `0x100000` + 撤销码 0x20e |
| `SetAsDefaultEmbeddedStyle()` | `1c3f20` | 内嵌默认样式：四边距全 400 |
| `OnEdit(p1,p2)` | `1c3f70` | 编辑期快照：静态 DAT_106cd038(flags)/DAT_106cd248(矩形)；退出对比 `&0x30f`+矩形 → 按宿主类型记 Rec_Data（未改动不记） |
| `Delete3DSpace()` | `1c41f0` | 释放 `+0xa0`（es3DSpace）置 0 |
| `Create3DSpace()` | `1c4260` | 懒建 es3DSpace（`operator_new(2000)`）→ `+0xa0` |
| `CreateChildLable(pt,id,mode)` | `1c4320` | 在 pt 建子标签图形挂链尾 |
| `OnActive_(closing)` | `1c43a0` | 激活态切换（高亮/控制点注册） |
| `OnSetTextUI(obj)` | `1c4430` | TextUI 变更 → `+0xd8 \|= 4`（TextUI dirty） |
| `SetModifiesForHost()` | `1c44b0` | 通知宿主已修改：清 `+0xd8` 宿主待通知位（bit3=8） |
| `SetModifiedFlags(m)` | `1c4540` | `+0xc=1`；按 m 置 `+0xd8` 交互/通知位 |
| `UpdateAnchorPostion(sheet)` | `1c4590` | 同步锚点（esCvsAnchor）位置 |
| `AddItem(shape, mode)` | `1c45d0` | **mode==0 头插 / !=0 尾插**；`ResetLineWidth(item,this)`；item 已选中（item+0x3c）→ SetSelObj，且无活动图形时 SetActive |
| `Insert(obj, ref, mode)` | `1c46a0` | **mode==0**：无 ref 尾插、有 ref 插到 ref 前；**!=0**：无 ref 头插、有 ref 插到 ref 后（与 AddItem 次序相反，见 Q-canvas-4） |

## 4. 边框 / 轮廓（L2590–3427 精读区 + 边框点簇 `1d8b10`–`1d9090`）

| 函数 | 入口 | 规格 |
|---|---|---|
| `GetCustomBorderPtCount()` | `1c4820` | `+0xda` ushort |
| `GetOutlineInfo(areaBoder)` | `1c4850` | 导出轮廓到 esAreaBoder：有点 → 点集路径；无点 → 边距/外框路径 |
| `IsImageFigure()` | `1c48b0` | 遍历图形链找图像段（esSegImage）并返回（图像直通判定） |
| `GetNextBox(dir)` | `1c49a0` | 画布链漫游：dir==0 用 `+0x50`(next)（尾节点回环取列表首的 next，语义照实见 Q-canvas-3）；dir!=0 用 `+0x54`(prev)，prev==列表首时回环取 `+0x3c`(尾)；结果==自身 → 0 |
| `ShrinkageMargin(mode)` | `1c4a70` | 按内容包围与外壳计算可收缩边距量 |
| `SetOutlineInfo(areaBoder)` | `1c4c30` | 逆操作（1761B）：**边框类型由点模式决定** —— 模式 0x2000 → 自定义点（记点数、分配 `+0xdc` 数组）；否则按边距写入（**存储 = 引擎值/4**，含 <400 时的默认/清零特判）；`local_c` 模式值 `<<12` 写入 flags；末 SetModifiedFlags + InvalidateState |
| `SetMargin(l,t,r,b)` | `1c5320` | 直写 `+0xb8/+0xbc/+0xc0/+0xc4` |
| `SetMargin(zRect)` | `1c5350` | 从矩形（L/T/R/B 序）写四边距 |
| `ResetCanvasBoder()` | `1c5390` | 边距归零 + 边框类型清除 |
| `AdjustEdeg(cm, pt)` | `1c54a0` | 矩形边框（须 0x1000）边距调节：**cm<0 = 提交** —— 当前边距与静态快照 DAT_106cd028.. 比对，差异边记撤销（0x204 L / 0x205 T / 0x206 R / 0x207 B，旧值）；`m_pUndo==0` 时只存快照返回 1。**cm>=0 = 拖动** —— 取 GetFrameRect 按 cm 改一边为 pt（x：0/2/4 左边、1/3/6 右边；y：0/1/5 上、2/3/7 下），重算边距（含"快照 L&R 均为 0 → 双侧同动"特判）→ `vtbl+0x44(0)` 重排 |
| `SetBorder(pt, cm)` | `1c57c0` | **仅 frame==0（无边框）时**生效：以内容盒（solid 外扩 400、去原点平移）为基准按 cm 求该边距（左 0/2/4、右 1/3/6、上 0/1/5、下 2/3/7；clamp ≥0），变更边记撤销；末尾 eaAct 活动态变化 → `vtbl+0x44(0)` |
| `GetOutlinePoints(&n, dx, dy)` | `1c5a10` | 输出**绝对**轮廓点（调用方 free）：非自定义 → GetOutlineRect 平移 (dx,dy) 输出 4 角（分配 5 点，末点闭合）；自定义 → `+0xda` 点数，每点 = `+0xdc[i]` **+ 内容实心中心** + (dx,dy)，末点闭合 |
| `AddBorderPoint(pt, mode, dist)` | `1d8b10` | 自定义边框加点：先查距现有点 ≤dist → 0；再逐边求点到线距 ≤dist → `mode==0` 记撤销 **0x20a**（int 索引＝插入位序）→ `InsertBorderPoint(i+1, pt−中心)` → 1 |
| `InsertBorderPoint(idx, relPt)` | `1d8e00` | 数组扩容插入：count+1、新分配、memcpy 前后段、写 `+0xdc[idx]`（**相对中心坐标**）、释放旧数组 |
| `RemoveBorderPoint(idx)` | `1d8f00` | 收缩删除：**count≥4 才允许**；count−1、memmove；数组不缩容；返回 1 |
| `AddNewPoint(pt, p3, p4, flag)` | `1d8f90` | 统一加点入口：flag==0 → ToInternal 后对**选中图形**（实心外扩 p6 内 PtInRect）调 `esShapeBase::AddPoint`，返回 1 即中止；flag!=0 → `AddBorderPoint` |
| `DelBorderPoint(pt, mode, dist)` | `1d9090` | 自定义边框删点：count≥4 且有点；GetOutlinePoints 逐点距 ≤dist → `mode==0`：`OnEdit(1,1)` + 记撤销 **0x20b**（12 字节：索引+坐标）→ RemoveBorderPoint → `vtbl+0x44()` → `OnEdit(0,1)`；返回 1 |

## 5. 属性 / 布局切换 / 持久化（L6586–7345 与 L12964–13484 精读区）

| 函数 | 入口 | 规格 |
|---|---|---|
| `EnumSelectedItem(fn)` | `1cb0f0` | 遍历图形链，对选中图形（`+0x3c!=0`）调回调；回调返回 0 中止 |
| `ToFixColor(scheme)` | `1cb180` | 颜色固化（导出/打印以外的颜色方案转换；简） |
| `LoadProp(mgr,mask)` | `1cb1d0` | 组 `0x10000000` → `0x100` 段：0x101 wrap / 0x102 followed / 0x103 align / 0x104→bit0x80 / 0x105→bit0x800 / 0x106 布局模式；组 `0x20000000` → `0x200` 段：0x201 边框类型 / 0x202 宿主 `+0x3c` / 0x204..0x207 边距（值/4）/ 0x212 `+0x44` |
| `GetOutlineUndoInfo(&sz)` | `1cb550` | 打包轮廓撤销 blob：点数+点集+外框矩形+边距矩形 |
| `SetOutlineUndoInfo(blob,&sz)` | `1cb670` | 解包应用（撤销恢复） |
| `ChangeFitureLayout(oldFlags, mode)` | `1cb810` | mode0→(wrap3,align1)；mode1→(wrap2,align3)；mode2/3→(wrap0,align0)+followed=1；mode4→边框类型 0x1000/0；按新旧 flags 决定撤销记录；prop 0x106 写回 mode |
| `SaveProp(mgr,mask)` | `1cbaf0` | 镜像 LoadProp：逐字段比较变更 → AddItem 记录 + 相应撤销码（0x204..0x207 边距回写 ×4 等） |
| `CheckLayoutChange(oldFlags, mode)` | `1cc2a0` | `(oldFlags&0xf)==(new&0xf)` 且 wrap==0 且 mode∈{2,3} → `MoveEmbeddedCanvas`（插入点重定位）；wrap 内嵌↔环绕跨界 → `OnQuickLayout` / `SetAsEmbeddFiture` / `SetAsAnchorFiture` 宿主迁移 |
| `MoveEmbeddedCanvas(sheet,mode)` | `1cc470` | 重嵌宿主：沿 `+0x40` 宿主链找 esPara；`GetActiveShow<2`（段级）→ **跨段搬迁**：esPara::GetNextVisible/GetPrevVisible 找目标 → Rec_Data **0x511f**（3×ID：父/属性对象/段）→ detach + insert → 样式居中化（HorzAlign=2）+ nature 继承（邻段 nature∈[8,12] 沿用否则 0）→ ResetParaSIdx；否则（单元格内）→ 新建空段（esPara 0x80）挂 paraBox → ResetCompos → 新 esEmbedder(0x44) → CreateItem(0x40,sheet) → esText::AddChrObj → `vtbl+0x44(0)` |
| `OnQuickLayout(sheet,mode)` | `1ccac0` | 宿主重建总入口：无宿主→返回；沿链找段；RemoveEnvoy 拔旧宿主。**环绕态（flags&7!=0）**：必要时拆分/换段后建 **esCvsAnchor(0x2c)** → AddChrObj → anchor `vtbl+0x44(1)`；**内嵌态**：确保段样式居中（不居中则 ResetParaSIdx）或新建居中段（param_2==2 前插、否则后插），再建 esEmbedder(0x44) → CreateItem(0x40,sheet) → AddChrObj → `vtbl+0x44(0)` |
| `IsExtArea()` | `1cd0b0` | 无宿主（`+0x40==0`）时：父不是 esCanvasList（0x2011）→ 1；四边距全 0 → 1；否则 0。有宿主 → 0 |
| `Serialize(arc,sheet,ver)` | `1d4ee0` | 见 §0 序列化说明（版本分叉 + 边框三态 + 子对象流） |
| `CopyFrom(src,exch)` | `1d5530` | 逐字段拷贝 + 图形链重建（各 obj `vtbl+0x24`）+ refLine/matrix + 边框点数组深拷 |
| `GetNextObjID()` | `1d5720` | `+0x50==0` → 0；否则 `esObject::GetID(+0x50,0)`（**下一画布**的导出 ID） |
| `Detach()` | `1d5760` | 从画布链摘除（列表 `+0x38/+0x3c` 首尾修补、邻节点 `+0x50/+0x54` 改指）+ `esCanvasState::OnRemove` |
| `IsDeletable()` | `1d5850` | 托管且有边框（L/R/B/T 差 > 2000 = 5mm）且**正在编辑激活** → 不可删；否则可删 |
| `DeleteSlef(p1,p2)` | `1d5910` | 链尾特判 + `vtbl+0x38` 自毁 / 交容器删除协议 |
| `SetUnDelInfo()` | `1d59a0` | 清"不可删"标记 |
| `DeleteSel()` | `1d59c0` | 删除选中集：若"无活动 或 全部已选"且 `IsDeletable` → 画布自毁协议返回 2；否则（不可整体删）→ `SetSelObj(0, mode0)` 把**全部图形**标选（= 退化为清空内容）。然后 SetActive(0)、CheckRemoveControlAndLinkInfo(1)、逐选中图形：有 undo → 图形 `vtbl+0x14`（删除记录）→ `vtbl+0x38` 自毁 → `vtbl(1)`；末画布 `vtbl+0x44(0)`；返回 1 |

## 6. 选择 / 角色 / 焦点（L8778–9200 与 L11088–11299 精读区）

| 函数 | 入口 | 规格 |
|---|---|---|
| `SelectFromRect(rect, flags, mode)` | `1ce520` | 框选：**mode==0** 增量加入（AcmeList 交互态：候选 = `sel==期望值 \|\| sel!=0`；命中判定 0x330f 走 EnumSegments 段级、有段走 `FUN_101aed00`；命中 → `shape+0x3c=1`；末尾 OnEndAdd/UpdateState）；**mode!=0** 全量重算：`flags&4` 置位 = 仅处理**原未选**，否则全部；`flags&8` → 外扩 1 相交即选，否则全含（IsContain）；末尾 SetActive(首个选中) + InvalidateState |
| `IsEqualRoleName(name)` | `1cea00` | `+0x48` role 名比较 |
| `SetRole(sheet,name)` | `1cea30` | 无活动图形：无 role 且名非空 → `esRole::CreateRole(this,sheet,1)` + SetName + `ResetLineWidth(role,this)`；返回码：已有 role→**0x2020**；新建且 `IsFixed`→**0xffff**、非固定→**类型字 0x2010**。有活动图形：第一遍对选中（`+0x3c!=0 && +0x4c==0 && 型!=0x3a08`）探测 esShapeBase::SetRole 类型字（不一致→0xfffe、无→0）；第二遍赋名（单只＝原名，多只＝`L"%s%d"` 从 1 递增）；**role+0x14 = role 索引**（撤销 0x523 载体） |
| `DeleteRole()` | `1cec90` | 撤销码 **0x523**（2 字节 role 索引 word；无 role=0xffff）→ esRole::Release + `+0x48=0` |
| `SetActive(shape)` | `1ced10` | 换活动：旧 OnActive(0) / 新 OnActive(1) → `+0xa4=shape` |
| `CancelAllSelect()` | `1ced70` | 全图形 `+0x3c=0`；有活动 → OnActive(0)；`+0xa4=0`；InvalidateState |
| `RemoveEnvoy()` | `1cede0` | `esChrObj::RemoveSelf(+0x40)`（宿主字符自文本摘除）+ `+0x40=0` |
| `GetActive()` | `158e60` | 返回 `+0xa4` |
| `IsFocused()` | `1d2070` | 焦点判定（esSelState） |
| `SetActive()` | `1d20b0` | 置活动（选择态） |
| `SetFocus()` | `1d20e0` | 置焦点 |
| `InvalidateState()` | `1d2140` | 选择状态失效 |
| `State()` | `1d2180` | 返回 esSelState*（画布级选择管理器） |
| `GetAcmeList()` | `1d21c0` | 返回 AcmeList（顶点选择链） |
| `IsSelectedAllItems()` | `1d2200` | 全选判定 |
| `SetSelObj(shape, mode)` | `1d5b00` | 选择集操作：**0**=全选（并激活，含 param 或首只）· **1**=取消选 param_1 · **2**=选中并激活 · **3（或 param==0）**=清空全选（可保留 param_1 选中并激活）· **4**=切换；尾部：活动对象空/未选 → 从链尾（`+0x38` 经 `+0x48`）回扫首个选中设为活动；SetFocus + InvalidateState + AcmeList::Clear；返回新活动 |
| `MakeEdgeStyle(sheet,dst)` | `1d2240` | 由连接线生成边样式 |
| `DrawSelState(render, mode)` | `1c5bc0` | mode==0：边框 0x2000 且有点 → GetOutlinePoints 构 egPath → `esRender::FillSelPath`；否则 `FillSelRect(GetOutlineRect)`。mode!=0 → `FillSelRect(实心矩形)` |

## 7. 坐标 / 布局计算 / 命中（L7781–8778 + L13815–15647 精读区）

| 函数 | 入口 | 规格 |
|---|---|---|
| `GetBoundsForUpdate(mask)` | `1cd140` | 焦点 → GetBounding，否则 GetSolidRect；并入活动图形 6 点（`+0x10..+0x34`，经 esDrawingModifier::GetActiveShape） |
| `GetSelBounds(mode)` | `1cd390` | 组活动（0x3a08）或 mode → 包围矩形；否则选中实心并集 |
| `CheckOperationFeasible(op)` | `1cd4e0` | 选中 0x330f → EnumSegments 逐段检查；否则段 `vtbl+0xd8` |
| `ModifyTransfrom ×3` | `1cd5f0 / 1cd670 / 1cd6f0` | 把画布变换应用到 Gdiplus Graphics / egGraphics / GDC 三种目标 |
| `ToExternal ×3` | `1cd800 / 1cd890 / 1cdbc0` | 内部 → 外部坐标（Point / PointF / tagRECT） |
| `ToInternal ×3` | `1cd920 / 1cd9f0 / 1cdb50` | 外部 → 内部坐标（Point / tagRECT / PointF） |
| `GetMatrix(dst)` | `1cdc20` | 拷贝 `+0x64` 矩阵后 append Translate(`+0x58`,`+0x5c`) |
| `ConvertAsInternal(shape)` | `1cdca0` | shape `vtbl+0x70(`画布矩阵`, 0)`（图形坐标 → 画布内部） |
| `RecalcLayout()` | `1cdd50` | **本批核心算法**（1993B）：① 遍历图形链，seg 类型 0x6010 先调 seg `vtbl+0x44(0)`（图像重排）；② 内容包围并集（活动图形 6 点并入）+ 矩阵变换；③ 外框 `+0xc8`：0x1000 时内扩 400 + 边距夹持，且 **L==R → 设为"水平居中"、T==B → "垂直居中"**；④ 内容实心 `+0xa8`；SetSolidRect/SetBoundingRect（外扩 100）；⑤ InvalidateState；宿主变化 → SetModifiesForHost 或置 `+0xd8` bit3 延迟 |
| `LoadSnapLines(mgr, rect, p3, p4)` | `1d5ce0` | 装填吸附侧线：候选 X = 选区左右边 + 中心（`|宽|>阈值` 才加中心）；候选 Y 同理；逐图形（param_7 过滤：0 全部 / 1 跳过活动 / 2 跳过已选）对准距 ≤ 阈值者取 `vtbl+0x68` 对齐点集，逐点与候选 X（`AddSideLine` 0）/ Y（`AddSideLine` 1）差 ≤ 阈值 → 加线 |
| `SnapSnapPoint(cmd, mgr)` | `1d6050` | 吸附点管线：`IsSnapable(0x10000000)` 时先对组（0x3008，最大盒 +400）做**连接点吸附**（GetLinkPts → SnapLinkPoints）；再按 cmd 过滤图形（0x465 只喂首个接受者；0x1f42/0x1f43 跳过活动；0x452..455/0x45c..45f 或 snapType&0x71 跳过已选；其余全遍历）→ 逐只 shape `vtbl+0x90(mgr,1)` |
| `HitTestGraphics(ht)` | `1d6280` | 先 HitTestNormal 命中 → 1；否则同列表活动画布（esCanvasList::GetActive）→ HitTestCanvasFrame 命中 → 1；锁定 → 0；固定 → -1；否则设矩阵（GetMatrix + FUN_101df370）后：内容空且宿主 tag 检查 0x81 通过且点在外框内 → `SetSelInfo(0x1d)` → 1；默认 -1（tag 语义见 Q-canvas-22） |
| `HitTestNormal(ht)` | `1d6440` | 点 → 内部坐标；外框按半径（ht+0x24 ×3 或 ×4 分支）膨胀 PtInRect；命中 → `CheckMode(0x10)` 转 HitTestCtrlPoint；`CheckMode(5)` → 非动态 HitTestAcme / 动态 HitTestVertex；再测内区矩形 → HitTestObjClick |
| `Offset(dx,dy)` | `1d1030` | 非固定画布整体平移：若有图形+锚点+followed → dx/dy **取整到 400（1mm）网格**；`+0x58/+0x5c += d` + OffsetObjRect + 外框偏移 |
| `SetOffset(x,y)` | `1d1130` | 绝对设置（差量应用同 Offset）；非固定；有变更返回 1 |
| `Translate(dx,dy,order)` | `1d11c0` | 矩阵平移：有 undo 时先存 **0x216**（0x18=6×float 矩阵）；按 MatrixOrder 应用；`vtbl+0x44(0)`；AcmeList::UpdatePoints |
| `IsPtInFrameRect(pt)` | `1d1290` | ToInternal 后 PtInRect(GetFrameRect) |
| `GetFrameRect()` | `1d12c0` | 若 `eaProject::GetActiveFrame(this)!=0` → 调 `vtbl+0x64` 刷新；返回 **`+0xc8` 矩形**（权威外框） |
| `GetAngle()` | `1d12f0` | `epCalcAngle(矩阵@+0x64)` |
| `Rotate(mode, ang, flags)` | `1d1330` | 非固定：**0 开始**（快照矩阵→静态 DAT_106cd010..、记基角 DAT_106cd00c/008）；**1 拖动**（角=基角+ang；非 flags&4 时按步长 DAT_1057f450（flags&8→DAT_1057f0b4）取整；绕外框中心旋转）；**2 提交**（矩阵与快照异 → 记 **0x216** 旧矩阵）——用第三组文件级静态（见 §8 注） |
| `CreateGroupObj(flags,p2,p3,p4)` | `1d1650` | 成组：统计选中（排除 0x3a08；另计"有 role 联动项"）；弹窗校验（无选中/单选/条件不符）；`CheckRemoveControlAndLinkInfo(2)` + OnEdit(1,0) → 新 esShapeGroup(0x84)+SetRectObject → 逐只 detach + Append（首只先 Insert），控制项先通知其 `+0x40` 对象 → InitGroupInfo + CreateUserLinkPoints + Regroup → `vtbl+0x44(0)` + 记 **0xf005**（ID 数组）→ OnEdit(0,0) |
| `ReGroup(flags)` | `1d1940` | 对选中组（0x3008）逐个 `esShapeGroup::Regroup(g,1,flags)` |
| `TransferTo(dst,dx,dy)` | `1d1990` | 整画布内容搬迁：建平移矩阵 → 逐图形 detach → `vtbl+0x70(矩阵,0)`（过到目标坐标系）→ 追加进目标画布（`AddItem(dst,shape,1)`） |
| `UnGroupObj()` | `1d1a90` | 解组：需活动图形；OnEdit(1,0) + `CheckRemoveControlAndLinkInfo(3)` + 清活动 → 逐选中组 `esShapeGroup::UnGroup(g,this)` + 删组对象 → OnEdit(0,0) + `vtbl+0x44(0)` |
| `MoveToTop(mode)` | `1d1b70` | 层序提升：头→尾遍历记 local_18＝最近选中；遇未选且已有锚 → `esUnMove(0x18)` + `esUndo::Rec_Add` + detach + `Insert(shape, local_18, 0)`（插到锚**前**）；mode0（相交检查）/mode1 移动后清锚；返回是否动过 |
| `MoveToUnder(mode)` | `1d1d00` | 层序下压：尾→头遍历记 local_3c＝最近选中；遇未选 → esUnMove + detach + `Insert(shape, local_3c, 1)`（插到锚**后**） |
| `GetOwnCanvas()` | `1d1ec0` | 从宿主沿 amulet 向上找"所属画布"：tag 0x40 + ID esCvsAnchor → `+0x24`；tag 0x81 + ID esEmbedder → `+0x38`；否则 0（**tag 与 ctor 写入值 0x40 的矛盾见 Q-canvas-22**） |
| `HitTestScaleBox(ht)` | `1d65e0` | 空闲态缩放手柄：仅 无活动图形 + frame==0 + 有宿主；实心外扩半径处 8 柄（**0 TL·1 TR·2 BR·3 BL·4 L中·5 T中·6 R中·7 B中**）→ `SetSelInfo(0x33, this, i)` → 1 |
| `ScaleFrame(rect, mode)` | `1d6780` | 外框拖缩：实心去原点求宽高（低于静态下限放弃）；mode<4 用**对角比**等比、≥4 用宽/高比（各 clamp ≥ 静态下限）；锚点=对角手柄（同 0..7 编号）；矩阵=平移到锚→缩放→平移回；退化（行列式 0）时 OnEdit(1,0) → 快照静态 → 非 1×1 记 **0x216** → `vtbl+0x44(0)`；正常时矩阵 to_inside 写 `+0x64` → 逐图形 `vtbl+0x70(矩阵, m_pUndo)` → `TransfromOrgine` |
| `HitTestEdgeFrame(ht)` | `1d6cd0` | 编辑框边/角：非固定 + frame 0x1000；最近边取 0 左/1 右/2 上/3 下（阈值 ht+0x28）；角柄=左缘(0,2)/右缘(1,3)/上缘(0,1)/下缘(2,3)（**TL,TR,BL,BR** 编号），边中点=4 L/5 T/6 R/7 B；中点柄仅"父非 esCanvasList 或未聚焦"可用；有宿主 → 码 0x1f（否则 0x20）；CornerSize = CalceCornerSize/2（有宿主）；无宿主未命中柄 → `SetSelInfo(0x1d)` 整框；有宿主 → 0（交 HitTestGraphics/ObjClick 兜底） |
| `IsPointInsideOutlines(pt)` | `1d7220` | 内含判定：无宿主 → 外框**内缩 400** PtInRect；有宿主 → GetOutlineRect（frame==0 时再按边距内缩）；自定义点 → 粗判后 `esGraph::IsPtInGon(点集+闭合)` |
| `HitTestOutlines(ht)` | `1d73b0` | 轮廓命中：无宿主 → 0；点集补闭合点；逐**顶点** HitTestPoint → `SetSelInfo(0x31 自定义 / 0x32 矩形, idx)` + set_return_point；无自定义时再测**边中点**（idx+4，码 0x32）；自定义时 `HitTestLines` 命中轮廓线 → `0x21`；最后 IsPtInGon → `8`（内部区域） |
| `HitTestExPoints(ht)` | `1d76f0` | 扩展选择点：State 空→0；先测选择态点 `state+0x1c` → `0x1c`；SetExSelBound 重建后取活动图形：8 顶点分奇偶两遍 HitTestPoint → `0xe`；活动 9 点多边形（shape+0x40）IsPtInGon → `0xc`；再 8 点 HitTestPointEx → `0xd` |
| `HitTestCtrlPoint(ht)` | `1d7a80` | 控制点：State 空→0；半径 = ht+0x24 的 3 倍；遍历图形（`vtbl+0xb0` 有控制点且非活动）：包围命中且 `vtbl+0x98(ht,1)` → 记录拖拽原点（state+0x18/+0x14）返回 1；否则外扩（右/下 3r）再判：锚点 = `vtbl+0x68` 对齐点 → `SetSelInfo(0x13, shape)` + 原点记录 |
| `BreakLines()` | `1d7d40` | 直通 AcmeList::BreakLines |
| `TestConnect(j1,j2,mode)` | `1d7d70` | AcmeList::TestLink(j1,j2)；返回"列表存在" |
| `ConnectLines(junctor)` | `1d7db0` | junctor 位判定（vtbl(0)&1）→ junctor `vtbl+8(undo)` 执行连接 → AcmeList::Clear → 1 |
| `IsWrittingCanvas()` | `1d7e20` | 无宿主 + 父为 esCanvasList + 父 `+0x38`==this + 父类判型通过 → 1（"正在书写的画布"） |
| `RemoveAcmeByPoint(pt)` | `1d7ea0` | AcmeList::RemoveAcme(x,y,10) → UpdateState → 1 |
| `SelectAcmeByPoint(pt, clear, all)` | `1d7ef0` | AcmeList 按点选：clear → 清；遍历（已选或 all 才测，包围外扩 25）：0x330f → EnumSegments 逐段、有段 → 段级命中 → `shape+0x3c=1`；末 OnEndAdd+UpdateState；返回状态或画布脏位 |
| `HitTestVertex(ht)` | `1d8170` | 顶点模式（动态）：还原 ht 上下文（state `+0x18/+0x14/+8`）；逐已选图形 `vtbl+0x98(ht, 0x400000)` → 顶点子判定（101d82e0） |
| `HitTestAcme(ht)` | `1d8380` | AcmeList::HitTest 优先；否则还原上下文；`CheckMode(4)==0` → 逐已选 `vtbl+0x98(ht,0x400000)`；否则仅活动图形（其 seg 为 esSegImage 时 `vtbl+0x98(ht,0)`）；IsClicked：起点变化 → ht+0x48=1 + 更新 state 原点；**SetActive(candidate)** |
| `HitTestFirstObjClick(ht)` | `1d8650` | 首击穿透：外框 CheckRectL → selinfo(0)；逐已选图形实心 CheckRectL + `vtbl+0x8c` → 返回 `esTextBox::GetModelBox(ht)` |
| `HitTestObjClick(ht)` | `1d8740` | 对象点击：不可见→0；实心 CheckRectL；**空画布**：非固定且聚焦→0，否则 `SetSelInfo(1,this)`→1；有图形：按"无活动→先未选 / 有活动→先已选"两遍：占位段（IsPlaceHolder && HitTestHolders）命中直接 1；`vtbl+0x8c` 命中：未选 → `SetSelInfo(1,shape)`+ht+0x44=shape；已选且 `ht+0x40&8` 置位 → `SetSelInfo(3,shape)`+ht+0x44；已选且未置位 → 仅在特定编辑上下文（宿主 tag0x40、非 0x1000 框、state 活动、GetEditState==0x452、模型盒不在 0x14..0x1b）仍 `1`；IsClicked → 清 state 原点 |

**SelInfo 码表（命中族汇总；`esHitTest::SetSelInfo(code, obj, value)`）**

| 码 | 含义 | 出处 |
|---|---|---|
| 0 | 清空 / 首击穿透 | HitTestFirstObjClick |
| 1 | 对象点击选中（未选图形 / 空画布自身） | HitTestObjClick |
| 3 | 已选图形点击（拖拽候选） | HitTestObjClick |
| 8 | 轮廓内部区域 | HitTestOutlines |
| 0xc | 扩展选择多边形内 | HitTestExPoints |
| 0xd | 扩展选择顶点（HitTestPointEx） | HitTestExPoints |
| 0xe | 扩展选择顶点（普通命中） | HitTestExPoints |
| 0x13 | 控制点锚点 | HitTestCtrlPoint |
| 0x1c | 选择状态点 state+0x1c | HitTestExPoints |
| 0x1d | 整个画布框（无 mode 路径） | HitTestGraphics / HitTestEdgeFrame（无宿主兜底） / HitTestGlobalBoxFrame 外环 |
| 0x1e | 整个画布框（`CheckMode(0x20)` 路径） | HitTestGlobalBoxFrame 外环 |
| 0x1f / 0x20 | 编辑框角/边手柄（0x1f 有宿主 / 0x20 无宿主） | HitTestEdgeFrame |
| 0x21 | 轮廓线 | HitTestOutlines |
| 0x31 / 0x32 | 轮廓顶点（0x31 自定义 / 0x32 矩形；边中点 = idx+4） | HitTestOutlines |
| 0x33 | 空闲缩放框 8 手柄 | HitTestScaleBox |

### 7.1 图形运算 / 区域切割 / 擦除（L15930–18179 精读区）

| 函数 | 入口 | 规格 |
|---|---|---|
| `Clips(pt, mode, w1, w2, probe)` | `1d9290` | 夹线/剪切（本批最大 2801B）：命中首个**未选** 0x330f 的段 → 宿主图形；`probe==0 && m_pUndo` 时：无命中 → 无活动返回 0、有活动 `SetSelObj(NULL,3)` 清选返回 1；命中 → OnEdit(1,0) → input checker 喂段（无活动=全部段链、有活动=仅命中图形；`seg vtbl+0xb4(cmd,0,isClosed)`）→ 容器拆路（两路 `get_path`，decomp 均显实参 0，疑 0/1 var 复用）→ CheckValid/InitPropertys → 主路：mode==0 或存在第二路/宿主链非空 → `RemoveControlAndLinkPoints(宿主)`，第二路插入+SetUnAddInfo，第一路按 mode 弃或插入+`HoldLine(mode,…)` 夹线；宿主段链仅剩单段（`*(*(宿主+0x60)+0x40)==0`）→ 删整个图形，否则删命中段（amulet）；宿主被掏空且 IsDeletable → **画布自毁**返回 1；否则 `vtbl+0x44(0)`+OnEdit(0,0)。`probe!=0` 或无 undo → 返回"是否命中" |
| `HoldLine(mode, path, undo)` | `1d9d90` | 夹线笔型切换：mode1 ↔ 笔型(kind)!=0 → kind 置 0、宽 +0x14（<0x1e 加否则夹 0x32）；mode2 ↔ kind==0 → 置 3、宽 −0x14（≥0x1f 减否则 10）；变更记 shape 撤销 **0x507 线型 / 0x506 宽度**（esShape.md §6.1）；状态不匹配 → 仅 `SetSelObj(path,3)` |
| `HeBing(mode)` | `1d9ee0` | 合并同态路径：需活动 0x330f + 选中数 ≥2；选中含非 0x330f → 0；按 `IsClosedEx` 4 类计数，**类别数 ≥2 拒合**；mode0：目标=活动 → 逐其余选中 RemoveControlAndLinkPoints → 逐段链（head `+0x60`、next `+0x40`）`esUnMove`+Rec_Add → detach → `AddSegList(目标)` → 源掏空销毁 → `vtbl+0x44(0)`+SetActive(目标) → 1；mode!=0 → 1（探测） |
| `FenJie(mode)` | `1da1d0` | 分解多段路径：选中 0x330f 且段链非空（`+0x60 != +0x64`）；mode0：逐只 → RemoveControlAndLinkPoints → 逐段链（原文从 `[+0x60]+0x40` 起、next `+0x40`）新建 esShapePath 拷贝(0x74)（样式字取原 `+0x34`）→ `Insert(新, 下一节点, 0)`+SetUnAddInfo → `esUnMove`+Rec_Add → detach → `AddSegList(新)` → 新片 `+0x3c=1`（选中）；原图形 `vtbl+0x44(0)`；末画布 `vtbl+0x44(0)`；返回是否分解过 |
| `SearchUp(kind)` | `1da430` | kind==**0xb**（画布类别）→ 返回自身；否则 `esObject::SearchUp` |
| `FindVideoPlaceHolder()` | `1da460` | 找视频占位：esShapeHolder（0x3908）且其段（`+0x40`）类型字 == **-0x5001**（0xafff）且 flags `&0x2000` → 返回该对象 |
| `MakeRgn(dx,dy)` | `1da4c0` | `GetWrapMode()<5` 才产出：GetOutlineRect；followed → (dx,dy) 相对外框原点；自定义边框点 → `GetOutlinePoints`（count）→ esRgn 点集工厂 `100693f0`（临时数组 free）；否则矩形偏移后 `10069390`；wrap≥5 → 0 |
| `GetOutlineRect()` | `1da680` | 有活动帧 → 先 `GetSolidRect(this,1)` 刷新；恒返回 `+0xc8`（与 GetFrameRect 同源） |
| `InitCreateRgn()` | `1da6b0` | 全图形样式字清 **bit31**（填充标记复位） |
| `CreateFillRgn(pt, brush, mode, undo)` | `1da6f0` | 油漆桶：brush 空 / 画布空 / 点在外框外 → 0；ToInternal；按"有无活动"匹配选择态遍历：0x3008 组 → `GetFillBorders` 命中；含 LBC 线图形 → 0x330f+有刷+`IsRgnClicked` 命中 → 同刷同色 → **返回 0**、`undo&&m_pUndo` → `UpdateBrush` 换刷 → 返回旧填充图形。无旧填充 → `FUN_10381ad0(点)` 由轮廓生成新路径 + `SetBrushObj`；mode!=0 找 bit31 同刷邻路 `FUN_10383740(1)` 合并（旧路删）；新路 `+0x34 \|= 0x80000000`；有旧填充图形 → `InitPropertys` 继承；`Insert(新, 命中, 1)`+SetUnAddInfo → 新图形 |
| `LinkClose(mode)` | `1dad30` | 多线连接闭合（活动须 0x330f）：选中含非 0x330f → **-3**；无未闭合选中 → -1；mode0：逐选中段链 `FUN_10386e60(seg, isClosed)` → 收束 `FUN_10386ff0`（失败 **-2**）→ RemoveControlAndLinkPoints 全 → 建 esCalligraph（活动拷贝 0x74）+ResetLineWidth → 逐只删源图形 → `FUN_103872d0` 装配（失败 0）→ CloseFigure + 样式 `\|0xff` + NormalRing → AddItem+SetUnAddInfo+SetSelObj(3)+`vtbl+0x44(0)`；mode!=0 → 0 |
| `OffsetCtrolPoint(a,b,mode)` | `1db0a0` | 每个 0x3a08 控制点对象 → `esCtrlPoint::OffsetCtrolPoint` |
| `DeleteControlPoints()` | `1db100` | 控制点批量删除：先扫链首连续选中段（允许 0x3a08 / 控制专组 0x3008，否则停）；**全链皆控制物件且 IsDeletable → 画布自毁返回 1**；否则 OnEdit(1,0) 逐选中：0x3a08 → `SetLinkUndo(0xf2f1)` 删节点；0x3008 非专组 → `RemoveControls`；专组 → 删节点（含链修复+active 重设）→ `vtbl+0x44(0)`+OnEdit(0,0)；无活动 → SetActive(最后保留者)；返回是否动过 |
| `RemoveControlPoints(seg)` | `1db360` | 全 0x3a08 → `esCtrlPoint::RemoveCtrlPointWith(ctrl, seg)` |
| `RemoveControlAndLinkPoints(shape)` | `1db3b0` | 除 shape 外全 0x3a08 → `RemoveCtrlPointWith(ctrl, shape)`；shape 为 0x3a08 且有 undo → `SetLinkUndo(0xf2f1)`；0x3008 → `RemoveAllLinkPoints`；0x3a03（esSegLinkLine）→ `RemoveLinkInfo(0)/(1)` |
| `RemoveAllControlAndLinkPoints()` | `1db490` | 全 0x3a08 → `esSeg::RemoveControlLink`；0x3008 → `RemoveAllLinkPoints` |
| `CuttingByLBCLine(sheet, pt, flags, w1, w2)` | `1db500` | 用 LBC 线切割：命中首个未选 0x330f（段级含 `vtbl+0x8c`）/含 LBC 线图形；命中**已选**图形 → 0；`flags==-1` 探测 → 1；对每个选中 0x330f `CuttingPath` 成功：`flags&0x40` 删被切图形；有成功且 `flags&0x80` → 删切割线 → `vtbl+0x44(0)` → 1；否则 0 |
| `GraphicOperation(sheet, pt, op, w1, w2)` | `1db880` | 布尔运算：命中未选闭合 0x330f；`op==-1` 探测 → 1；OnEdit(1,0)；`op&0xf`==3 链式逐只 `FUN_101dc300(选中, 累积, op)`（空结果止）；否则逐只与命中图形运算（任一空则整体失败，弹 `0xa1f` → 0）；无结果弹 `0xa20`（非 6 → 0）；`op&0x40 && op&0x80` + 画布无边框(flags&0x1000==0) + 链上无旁图形 → **画布自毁返回 1**；清选 → 每结果 CopyPropFrom+Insert+SetSelObj(2)+SetUnAddInfo → `op&0x40` 删操作数、`op&0x80` 删命中图形 → `vtbl+0x44(0)`+OnEdit(0,0) → 1 |
| `BreakShape(sheet)` | `1dc400` | 断开图形：需活动；对每个选中取 `vtbl+0xac` 的"断开对象"：无内容（`+0x40==0`）→ 直接释放；否则 `Insert(对象, 原, 1)`+SetUnAddInfo+SetSelObj(2)（0x330f 时样式 `\|0xff`）→ RemoveControlAndLinkPoints(原) → 原图形销毁；返回断数 |
| `Cutting(sheet, cutter, mode)` | `1dc550` | cutter 无 LBC 线 → 0；对每个选中图形（`vtbl+8(ID)` 类型自校通过者）`CuttingPath` 成功 → 原图形销毁；任一成功 → 1 |
| `CuttingPath(sheet, target, cutter, mode)` | `1dc640` | 切割引擎：target/cutter 段分别喂 input checker →（mode==0 且 target 闭合 ? `FUN_10383590` : `FUN_103834f0`）→ 逐结果路径：空段释放；非空 CopyPropFrom → target 未闭合或 `!bVar1&&!IsReallyClosed` → `OpenCanvas`，否则 `CloseFigure` → `Insert(结果, target, 0)`+SetUnAddInfo、`+0x3c=1`；active==target → 改指首结果；返回是否产出 |
| `EraseSelectedItems(sheet, eraser)` | `1dc990` | 橡皮主流程：活动须 0x330f；`ConvertAsInternal(活动→eraser)`+CloseFigure+OnEdit(1,0)+清活动；逐选中 0x330f：无刷 → `EraseLines`、有刷 → `EraseRegion`；结果非空 → `+0x3c=1`+设为活动；画布空且 IsDeletable → **自毁**；否则 OnEdit(0,0) |
| `EraseRegion(sheet, shape, eraser)` | `1dcaf0` | 区域擦除：shape/eraser 段喂 checker（`FUN_103813a0` 各一次）→ `FUN_10383740(2)` 产新路径 → 非空 CopyPropFrom(shape) → `OnItemErased(shape, 新)`；引擎失败（空）→ 返回原 shape 不变 |
| `OnItemErased(orig, result)` | `1dcc20` | 擦除收尾：RemoveControlAndLinkPoints(orig)；result 非空 → `Insert(result, orig, 1)`+SetUnAddInfo+`vtbl+0x44(0)`+orig 销毁+SetActive(result) → result；空 → 释放 result+orig 销毁+`vtbl+0x44(0)` → 0 |
| `EraseLines(sheet, shape, eraser)` | `1dcd00` | 线条擦除：shape/eraser 段喂 checker → `FUN_10381470(eraser 命令)` 产新线路径 → CopyPropFrom + 结果样式字清 **bit 0x1000** → `OnItemErased` |

### 7.2 绘制 / 快照 / 导出 / 装载 / 段落枚举（L3428–6586 精读区）

| 函数 | 入口 | 规格 |
|---|---|---|
| `RestoreSelInfo(blob,len)` | `1c5d30` | 恢复选择态（589B）：清 `+0xa4`；blob 头 ushort=位图**字数**，按图形序号逐位回写 `+0x3c`；其后的 zArchive 流 ReadInt32=活动对象 ID → `esUndo::GetAt(m_pUndo,id)` + `vtbl+8(esShapeBase::ID())` 校验后写 `+0xa4`；有活动 → `InvalidateState`+`State`+`esAcmeList::Serialize` 续读辅助列表；收尾仍无活动 → 全链 `+0x3c=0`+Invalidate |
| `GetSelInfo(&len)` | `1c5f80` | 序列化选择态（711B）：仅 `IsFocused() && +0xa4` 且选中数>0 才产出；位图按**全链序号**置位（字数=ceil(总数/16)）→ zArchive：WriteWord 字数、位图、活动 GetID、acme 列表（空则 WriteWord 0）→ detach 缓冲返回，长度出参 |
| `GetGrapColors(arr,mask)` | `1c6250` | 沿图形链调 `vtbl+0x9c(arr,mask)`，取首个非零即返回 |
| `FillBackround()` | `1c62a0` | 背景填充：`+0x44`(色) 与 `+0x40`(宿主) 皆非空；刷=MakeBrushColor(render,+0x44,0xff)；GetGraphics(render,0) 填 `+0xa8` 内容矩形 |
| `SaveAsMetafile(path,type,hdc,sheet)` | `1c63a0` | 转存图元文件（904B）：GetOutputRect → 无活动且边框 0x1000 再 Deflate 400 / 否则 Inflate 200 → GetDeviceCaps(0x58/0x5a)→epCalcScaleXY(100)→FUN_10052f50(0,0,w,h)；`type<3` → GDI+ Metafile(emfType=5/4/3) → DrawToMetafile；`type>=3` → SaveDC → FUN_10199210(hdc,…) → DrawToMetafile → GetHENHMETAFILE → RestoreDC → EmfToWmf → CopyMetaFileW(path) |
| `CreateEnhMetafile_FormCurSel(...)` | `1c6730` | 用当前选择建增强图元：GetOutputRect；无活动 → 标记 1；有活动 → 外扩 200；转 CreateEnhMetafile |
| `CreateEnhMetafile(rect,sheet,type,flag)` | `1c67e0` | SaveDC → GetDeviceCaps → epCalcScaleXY(100) → FUN_10052f50 → FUN_10199210(hdc,…7,type) → DrawToMetafile → 取 HENHMETAFILE → RestoreDC |
| `DrawToMetafile(img,rect,sheet,sx,sy,flag)` | `1c69a0` | 图元文件上作画（671B）：新 egGraphics(0x3c) 挂 metafile 图像；`flag && +0x44` → 背景色清屏；Save→Translate(−left,−top)→esPageRender→**逐链（`flag‖+0x3c` 且类型 `&0xf000!=0x7000`）`vtbl+0x74`**→Restore |
| `GetOutputRect(&rect)` | `1c6c50` | 输出矩形（376B）：无活动 → 内容 `+0xa8`（**无边框 Inflate 200 / 有边框 Deflate 200**）；有活动 → 选中（跳 0x7000）solid 并集，全空→0；宽或高 < **101** → 0 |
| `CreateDotmap(sheet)` | `1c6dd0` | 点阵化（1486B）：GetOutputRect（需 w,h>799）→ Inflate 800 → /100 → 建位图 → 白底+SetSmoothingMode(1)+esPageRender → 逐**选中**（跳 0x7000）`vtbl+0x74` → 逐像素（步长 4B）：亮度加权 (r×0x1e+g×0x3b+b×0xb)×a/0x639c < 200 → 建**点对象 `esShapeLine(pt,0x6001,0)`**（笔 0xffcccccc、宽 0x96）尾插+SetUnAddInfo、`+0x3c=0` |
| `CreateBitmap(...)` | `1c73c0` | 位图渲染：GetOutputRect → 活动有无定全选标记 → 四边 Inflate(param_3) → epCalcScaleXY(0,0,param_2,param_2,100) → 建位图（format 0x22009/0x26200a）→ 背景：`+0x44` 有 alpha 直清、否则 0xff02（param_4 时先褪白 0xffffff）→ Translate → param_5==0 时 SetInterpolationMode(5) → esPageRender → 逐（全选或选中，跳 0x7000）`vtbl+0x74` |
| `Load(page,subj)` | `1c7810` | 进页面渲染：无图形或 IsInvisiable → 返回；固定画布 → 按 role 键名 NewSubj；非固定 → solid→NewSubj、外框 Deflate 100→SetRectB(rect,矩阵)；role 表演类 → NewPerfrom；宿主+背景色 → AddRectangle；逐图形可装载者 `vtbl+0xa0(page,subj)` |
| `Draw(egGraphics,x,y,w,h,scale…)` | `1c7a50` | 缩放绘制：Save；scale=param_4/param_8；param_6..9∩solid；esPageRender(gfx,sheet,scale,scale)；SetColorScheme；GetGraphics(0)→BeginDraw→Translate(param_2/scale,param_3/scale)→`Draw(render,0)`→EndDraw |
| `Draw(GDC,…)` | `1c7c40` | GDI 绘制（5253B）：SaveDC→SetMapMode(8)→Window/Viewport Ext·Org（param_8/param_4×10、param_2/param_6）→param_6..9∩solid→esPageRender(gdc,sheet)→BeginDraw→`Draw(render,0)`→EndDraw→ReleaseGraphics→RestoreDC |
| `DrawDropOutline()` | `1c7e30` | 拖放轮廓：外框→IsVisible→笔 0xff04 虚线 3；矩形框→DrawRectangle；自定义点→GetOutlinePoints→DrawLines（回闭合点） |
| `DrawEditCtrlStates(...)` | `1c7fd0` | 编辑态：动态模式或（活动+选择态）才画；ModifyTransfrom+GetBoundsForUpdate→LPM(4)（render+0x54&0x10 时 ×10）→Inflate→IsVisible；非 &0x10：动态→esSegBase::Build；+0x54&2→DrawCtrlServer 否则 DrawControlVertex；非动态→esAcmeList::Draw。&0x10：DrawControlVertex；活动 0x3a08→esShapeControl::DrawCtrlState |
| `DrawEditRelevants()` | `1c8180` | 编辑辅助：非固定：`render+0x54&0x100`→DrawDropOutline；`&8`→外框 IsVisible→`DrawOutline(1)`；否则 DrawFrame |
| `DrawCtrlServer(...)` | `1c8230` | 控制服务：State→SetExSelBound(render+0x78)→活动图形；acme 空→0；helper `vtbl+0x34(render,state+0x1c,state+0x20,active,…)` |
| `IsVisibleIllustration()` | `1c8300` | 可见性：无宿主→0；沿 amulet 链：`esSnapObj::Is(4)` 命中→段 ID→IsHidden→0；tag 0x2020 且 ID=esCanvas→递归；全过→1 |
| `IsInvisiable()` | `1c83f0` | 无宿主→0；amulet 空或 `vtbl+0x74(1)!=0`→1；否则 0（Draw 早退判据） |
| `DrawForInternal(render)` | `1c8450` | 内部绘制（197B）：Save→ModifyTransfrom→逐链 `vtbl+0xb4(render,0)`→Restore |
| `InToCanvas(render)` | `1c8520` | Save+ModifyTransfrom，返回还原令牌（与 DrawForInternal 成对） |
| `Draw(esRender,mode)` | `1c8550` | 主绘制（5190B）：IsInvisiable→跳；无图形且无画布链后继且无宿主→跳；活动==this 且状态&2→跳；宿主且 mode→DrawOutline(0)；InToCanvas+SetDynamicMode+PushDrawPoint；`render+0x54&0x70000` 且活动≠this：宿主+无图形+非3D+0x1000边框→DrawAdjustbleBorder；清 `render+0x54` 低段（0xfff8ffff）；AuxColor 存取→DrawGraphics→还原→PopDrawPoint/Restore |
| `DrawOutline(mode)` | `1c86d0` | 轮廓：GetOutlinePoints 闭合；mode0：非 `&8`→笔 0x3fff7f00（LPM）DrawPolygon；mode≠0：笔 0xff04 虚线 3 画多边形→WorldToPage→GDC：点数组空（矩形）→顶点+边中点方块，否则各点方块（尺寸 render+0x10） |
| `DrawGraphics(render)` | `1c8ac0` | 图形链绘制：宿主+背景色→FillBackround；3D 空间非空→（固定：3Dspace.Draw / 非固定：视口 Deflate 再 Draw）；正常→逐 `vtbl+0x74`；`render+0x54&0x100000`（灰化）→共享链：SetGrayMode(0)+整体 Draw+还原；否则逐子 SetGrayMode(选中且非活动画布?0:1) |
| `DrawControlVertex(render)` | `1c8c70` | 控制点（618B）：State；动态→state\|=0x200；FUN_101ae3f0 起；`FUN_1000e650(0x10)` 分支：逐图形 `vtbl+0xb0` 有控制点→包围可见→`vtbl+0x78(...,0x400000,state+0x18,state+0x14)`；否则含图像→DrawClipBox；`+0x3c` 标志→ResetPos(是否活动)→`vtbl+0x78(...)`；FUN_101aebd0 收 |
| `DrawAdjustbleBorder(render)` | `1c8ee0` | 可调边框把手（1181B）：宿主+无图形+非3D+活动≠this→临时改字体（+0x14=0x7f01）画资源串 0xa1c（提示字形）；GetGraphics(1)→WorldToPage→Save→ResetTransform→笔（活动==this：`GetColor(0xff04)&0x2fffffff`+点划；否则 `&0x3fffffff`+SetLineCap(1,1,0)）→四角 L 形把手+四边中点短横 |
| `DrawCanvasFrame(render,sel)` | `1c9650` | 画布框（1320B）：宿主非空才画；原点/矩阵零→helper 直画（FUN_100dedf0 4 路）；尺寸→角标长 CalceCornerSize；**未聚焦**：色 0xaf04/0x7f03；**聚焦**：色 0x7f3f3f3f/0x7fcccccc 画 7 点角标折线×4+边短划；**锁定**：四边中点叉标+白笔 |
| `CalceCornerSize(w,h)` | `1ca6a0` | 角标长 = `min(w/4, h/4)`，再与 `w/10` 取小 |
| `DrawScaleBoxFrame(render)` | `1ca740` | 空闲缩放框（555B）：solid→WorldToPage；right/bottom+1；GDC Attach→SetROP2(6)→DrawRectangle→还原 ROP→Deflate(1,1)→**8 手柄**（margin=render+0x10）：四角+四边中点定位→`BitBlt 0x330008` 打柄 |
| `HitTestCanvasFrame(ht,mode)` | `1ca9a0` | 边框命中（142B）：IsFixed→0；amulet 空或 tag **0x2012**→0；`CheckMode(0x20)`：非 0→HitTestGlobalBoxFrame(1)；0：amulet tag **0x2011**→HitTestEdgeFrame 否则 HitTestGlobalBoxFrame(mode) |
| `HitTestGlobalBoxFrame(ht,mode)` | `1caa30` | 整框命中（452B）：`mode=CheckMode(0x20)`；mode0：框 0x1000→外框矩形，`param_2==0` 且 HitTestEdgeFrame→1；非 0x1000：宿主+无活动+框0→0，否则 solid。mode≠0→外框。**宿主非空且 `esSnapObj::Is(host,0x40)`→直接 0**；Inflate(`DAT_1057f408/ht+0x30`)→内环内→0；再 Inflate→外环内→`SetSelInfo(mode?0x1e:0x1d)`→1 |
| `DrawFrame(render)` | `1cac00` | 框绘制（206B）：非固定+amulet 非 0x2012：`+0x54&0x20`（拖动中）→宿主 0x40 族→不画，否则 DrawGlobalBoxFrame；否则 tag 0x2011→DrawCanvasFrame；再否则 宿主空/有活动/框非0→DrawGlobalBoxFrame，全否→DrawScaleBoxFrame |
| `DrawGlobalBoxFrame(render)` | `1cacd0` | 整框绘制：框 0x1000→DrawAdjustbleBorder+外框，否则 solid 矩形；`+0x54&0x20` 时取 amulet GetActive==this 定状态 2、用外框；色按状态掩码（0→`&0x3fffffff`、1→`&0x7fffffff`、2→原色）取 GetSchemeColor(1)；阴影刷 0x13、笔宽 DAT_1057f4b0/scale、矩形外扩 2×宽→Save→SetRenderingOrigin(0,0)→DrawRectangle→Restore；锁定且有 helper→`vtbl+0x14(render,rect,state)` |
| `EnumParagraphs(sheet,fn)` | `1caf60` | 段落枚举：逐链节点：esShapeHolder→holder EnumParagraphs、esShapeGroup→group EnumParagraphs；回调返回非零即返回 1，链尽→0 |

### 7.3 变换 / 排列 / 对齐 / 剪贴板 / 选择序列化（L9198–9872 · L11047–12960 精读区）

| 函数 | 入口 | 规格 |
|---|---|---|
| `ChangePerspective(m1,m2)` | `1cee20` | 视角透视切换（393B）：需 `m1!=m2` 且有选择态；以选择矩形中心建矩阵（源/目标 SetViewMode，目标乘 FUN_10027140(1)）；OnEdit 包裹逐选中 `vtbl+0x70(matrix,m_pUndo)` |
| `LoadSelectShapes(mod)` | `1cefb0` | 装载选择到图形工作器：逐选中 `esGraphWorker::Add(mod,shape,1,8)`+`vtbl+0x6c(mod,1)` |
| `MakeArray(mode,dx,dy,nx,ny,sheet)` | `1cf010` | 阵列复制（802B）：需活动+选择态；GetCurrentData 捕获；`ny==0`→`nx` 份沿 (dx,dy) 递推 OnPast；`nx==0`→`ny` 份；否则 nx×ny 网格（跳过原点份）；收尾：旧尾之后的**新副本全选 `+0x3c=1`**、`+0xa4=+0x38`（尾）、InvalidateState、锚点 Rec_Data(1) |
| `RotateSelected(mode,?,θ,中心,n,sheet)` | `1cf450` | 旋转/旋转复制（822B）：需尾非空+θ≥ε+选择态；`param_2==0`→n−1；n<1 → 纯旋转（矩阵θ：有 acme→MutplayEx 否则 MultiplyMatrix(0x455,1)）；否则：`param_2==0`→原选择转 (n+1)θ，`!=0`→清选不转；副本 i=1..n 各 OnPast(iθ)；收尾同 MakeArray（全选新副本+active=尾+锚点 Rec_Data） |
| `CopyMove(matrix,sheet)` | `1cf8b0` | 原位粘贴：GetCurrentData→SetSelObj(0,3)→OnPast(hMem,matrix,sheet)→GlobalFree→锚点 Rec_Data |
| `OnPreOffsetSelected(&dx,&dy)` | `1cf930` | 拖动预校正（366B）：宿主非 0x40 族→0；无活动→0；全选时要求框 0x1000、用外框（Deflate 400）夹住选择矩形修正 dx/dy；返回仍有位移否 |
| `MultiplyMatrix(matrix,kind,links)` | `1cfaa0` | 选中矩阵变换：矩阵恒等则 0；逐选中：0x3a03→`esSegLinkLine::CheckRomoveLink`，`vtbl+0x70(matrix,m_pUndo)`；links→UpdateLinkPotions(0)；有处理→1 |
| `TransfromOrgine(matrix)` | `1cfb40` | 选择原点随矩阵：`state+0x1c/+0x20` 变换后不同→记撤销 **0x210** 写回 |
| `GetBoxDesc(...)` | `1cfbe0` | 行内基线描述（排版）：单节点链按类型取基线——公式框/图像段/固定画布三类来源（GetBaseLine 等）；输出基线点集与底距；无效→-1 |
| `UpdateLinkPotions(all)` | `1cfff0` | 连线点刷新：逐链 0x3a03（未选中或 all）→`esSegLinkLine::CheckLinkPointEx` |
| `GetOwnList(up)` | `1d1fb0` | 归属列表（122B）：`+8==0`→`up` 时经 GetOwnCanvas 递归上找；`+8!=0` 且 `vtbl+8(ID)==esCanvasList::ID()`→返回 `+8`，否则 0 |
| `GetFixedCanvas()` | `1d2030` | 固定画布（57B）：`GetOwnList(1)` 的 `+0x38` 首画布且 IsFixed→返回 |
| `MirrSel(mode,axis)` | `1d2340` | 镜像选中：需选择态；选择中心；按 axis 取 `(1,0,0,−1)` 或 `(−1,0,0,1)` 翻转矩阵（DAT_1057f0b4/5d0），绕中心平移-翻转-回移；mode 时再 SetViewMode 叠加；经 MultiplyMatrix(0x455,1) 施加 |
| `Alignment_ForGrid(dir,pt,grid)` | `1d25d0` | 对齐网格：需活动；选中排除 0x3a03；`dir` 0/1/2/3=左/右/上/下取参考边对 `pt`；残差 = round(v/grid)×grid−v；非零→逐个 `vtbl+0x70`+UpdateLinkPotions+活动帧刷新；grid==0→1 |
| `SetDynamicMode()` | `1d2b00` | 切换动态模式：flags `+0x4c ^= 0x4000` |
| `SelectAllEqualShapeTypes()` | `1d2b40` | 同类型全选：遍历未选中图形，`FUN_101d2c00(+0x40)` 与活动同类→`SetSelObj(shape,2)`；有→1 |
| `SetHorzAlign(align,wrap)` | `1d2d10` | 水平对齐三态：①无活动（有宿主或非固定）：内容矩形按 0x100 左/0x200 中/0x300 右 `Translate(delta,0,1)`；②有活动：选中并集（排 0x3a03）→平移矩阵 `vtbl+0x70`+UpdateLinkPotions（OnEdit 包裹）；③宿主+环绕：改 flags 对齐位（wrap 子模式 2/3/4），变更→撤销 **0x20e**+`vtbl+0x44` |
| `Alignment(mode,matrix,apply)` | `1d3120` | 对齐主函数（4888B，批内最大之一）：需活动；选中排 0x3a03（活动为连线时特判）；mode 0..5=按活动框对齐（左/上/下/右/垂直中/水平中）；6/7=水平/垂直等距分布（≥3 只）；≥8=等宽/等高（位表）；应用期逐只 `vtbl+0x70(matrix)`+UpdateLinkPotions，OnEdit 包裹；返回 1 |
| `CheckRemoveControlAndLinkInfo(mode)` | `1d4460` | 控制/连线清理：逐链：`+0x40` 为 esCtrlPoint→RemoveCtrlPoints(mode)；否则 esShapeGroup→RemoveLinkPoints(mode) |
| `AppendGraphics(hMem,sheet)` | `1d4530` | 共享内存续贴（3885B）：zSharedMemory(0x100) Attach→zArchive：ReadByte==4→ReadDWord 对象 id→`esObject::IsCanRead`→BeginSerilize(2,id)→Serialize sheet(0x10ffff)→读矩形→SetSelObj(0,3)→`OnPast(arc,sheet,NULL,NULL,0)`→EndSerilize |
| `GetCurrentData(sheet)` | `1d4680` | 复制捕获→共享内存：无图形→0；WriteByte(4)+BeginSerilize(1,0x2000837)；`IsFocused&&+0xa4`→只捕选中否则全链；esPtrExchanger 注册+写 sheet+0x850；Serialize(0x10ffff)；矩形=聚焦?选择:内容；写对象数；逐（`+0x3c` 匹配标记）`vtbl+0x40(arc,sheet,2)`；EndSerilize→Close→Detach 返回句柄 |
| `OnPast(hMem,matrix,sheet)` | `1d48e0` | 共享内存粘贴（309B）：Attach→ReadByte(4)→ReadDWord→BeginSerilize(2,id)→Serialize sheet→读矩形→6 参 OnPast 核心→EndSerilize |
| `OnPast(arc,sheet,undo,matrix,flag)` | `1d4a20` | 粘贴核心（602B）：有活动→清选；ReadDWord 对象数→循环：ReadWord 类型→`vtbl+0x58` CreateObjByType→ResetLineWidth→`vtbl+0x40` 反序列化→（`flag!=0` 且 0x3a08→弃）；0x3908 holder 需 NormalObject 成功；`+0x3c=1`→AddItem 尾插+SetUnAddInfo；收尾指针回填→`vtbl+0x44(0)` |
| `CollectStyles(sheet)` | `1d4c80` | 样式收集：esContainer::CollectStyles；role `+0x48` 非空→`vtbl+0x10(sheet)` |
| `OnMessage(msg,flag)` | `1d4cc0` | role `+0x48` `vtbl+0x48(msg,flag)` 处理过→`vtbl+0x44(0)`；再 esContainer::OnMessage |
| `IsEqual(obj,sheet)` | `1d4d20` | 等价判定：esObject::IsEqual；role 同空/同有（有→`vtbl+0x4c`）；refLine `vtbl+0x4c`；边距 `+0xb8` memcmp(0x10)（自定义点→比点数+点集）；图形链逐只 `vtbl+0x4c`；长度相等 |
| `ModifyTransfrom(Graphics*)` | `1cd5f0` | 原点 `+0x58/+0x5c` 非零→平移 (x,y,0)；`FUN_10027a90()==0`（无绑定上下文）→合并矩阵 `+0x64`（GDI+ Graphics 静态默认上下文） |
| `ModifyTransfrom(egGraphics*)` | `1cd670` | 同上显式版：`TranslateTransform(原点)`+`MultiplyTransform(+0x64)` |
| `ModifyTransfrom(GDC*)` | `1cd6f0` | 克隆 `+0x64`；原点非零→`FUN_10052bd0(x,y,1)`；`epModifyDeviceTransfrom(GDC, 矩阵)`（原点与上下文皆无→早退） |
| `ToExternal(Point*,n)` | `1cd800` | GetMatrix→`FUN_10027a30` 应用（内部→外部，点数组 n 个） |
| `ToExternal(PointF*,n)` | `1cd890` | 同上（浮点 `FUN_100279d0`） |
| `ToInternal(Point*,n)` | `1cd920` | GetMatrix→可逆判定 `FUN_10027480()`（==0→不改动返回 0）→求逆 `FUN_10027330`→应用（外部→内部） |
| `ToInternal(tagRECT*)` | `1cd9f0` | 同上→`epTransfromRect`（照实恒返回 1） |
| `ToExternal(tagRECT*)` | `1cdac0` | GetMatrix→`epTransfromRect`（内部矩形→外部） |
| `ToInternal(PointF*,n)` | `1cdb50` | 同 `1cd920`（浮点） |
| `Undo(code,a,b)` | `1d0050` | 分发：`0x204..0x207` 边距 L/T/R/B（int 交换）· `0x208` 页码（直接 return）· `0x20e` flags `+0x4c` · `0x210` 选择态点 `state+0x1c`（State 空→return）· `0x212` 背景色 `+0x44`（直接 return）；有改动（0x204..0x207/0x20e）且宿主非空→`host vtbl+0x44(0)`；default→`esFormulaBox::CaretMove`（ILT 兜底） |
| `Undata(&code,a,&sz)` | `1d02e0` | 按码重建+翻转码：`0x208` 页码回写+宿主通知 · `0x216` 建 0x18 矩阵 blob（6 值） · `0xf005` 解组回散→翻 0xf006 · `0xf006` 建组（esShapeGroup 0x84+esSegGroupRect 0x78）按 ID 表 Append+Insert+SetGroupInfo→翻 0xf005 · `0x209` 宿主通知+SetOutlineUndoInfo · `0x20a` 删点→翻 0x20b · `0x20b` 插回→翻 0x20a · `0x20c` 单点改（存旧 12B） · `0x20d` 全体偏移取反（8B） · `0x21f` 宿主同步 · `0x214` 摘锚→翻 0x215 · `0x215` 建锚（esCvsAnchor 0x2c+AddChrObj）→翻 0x214 · `0x523` role 索引对换；default→`esObject::Undata` |

## 8. 撤销码表（Undo `1d0050` / Undata `1d02e0`）

| 码 | 载荷 | 应用点 / 副作用 |
|---|---|---|
| `0x202` | int | esEmbedder `+0x3c` 垂直对齐模式（esEmbedder::Undo） |
| `0x204/0x205/0x206/0x207` | int | 边距 L `+0xb8` / T `+0xbc` / R `+0xc0` / B `+0xc4` |
| `0x208` | ushort | 页码 `+0x3c` |
| `0x209` | blob（点数+点集+外框矩形+边距矩形） | 轮廓整体（Get/SetOutlineUndoInfo）→ InvalidateState |
| `0x20a` | int 索引 | 边框点**插入**（AddBorderPoint；撤销＝删） |
| `0x20b` | idx+旧坐标（3×int） | 边框点**删除**（DelBorderPoint；撤销＝插回） |
| `0x20c` | pt+idx | 单点修改 |
| `0x20d` | pt | 全部点偏移 |
| `0x20e` | ulong | flags `+0x4c` 对换（OnAllowDefAnimat 等） |
| `0x210` | pt | 选择态 `+0x1c` |
| `0x212` | dword | `+0x44` **背景色**（COLORREF） |
| `0x214 / 0x215` | esCvsAnchor 字段块（`+0x14` short、`+0x18`、`+0x1c`、`+0x24` canvas 反引） | 摘锚 / 建锚 |
| `0x216` | D2DMatrix blob | `+0x64` 矩阵 |
| `0x21f` | host 通知状态 | 宿主同步标记 |
| `0x511f` | 3×int 对象 ID（父/属性对象/段） | 段落搬迁（MoveEmbeddedCanvas 跨段移动） |
| `0x523` | ushort role 索引（0xffff=无） | role 恢复（DeleteRole/SetRole 配套） |
| `0xf005 / 0xf006` | — | 解组 / 成组（esShapeGroup 重建；CreateGroupObj 记 0xf005，另配套得 ID 数组） |

> §8 注：**顺序移动**（MoveToTop/MoveToUnder）记 `esUnMove` 撤销对象（`esUndo::Rec_Add`），不走 Rec_Data；**Rotate** 用第三组文件级静态（DAT_106cd010.. 矩阵 + DAT_106cd00c/008 角度），与 AdjustEdeg（DAT_106cd028..）、OnEdit（DAT_106cd038/248）三组互不干扰——同一时刻只允许一个交互在编辑。另：§7.1 连线族用到的 **0x506 笔宽 / 0x507 线型 / 0xf2f1 连接点移除** 属 shape 族撤销码（esShape.md §6.1），不进本表。

## 9. 怪癖（Q-canvas-*，本批编号）

- **Q-canvas-1** `+0x3c` 是**页码**（`page()`），不可与图形对象的"选中位 shape+0x3c"混淆——两者同名不同层（画布 vs 图形）。
- **Q-canvas-2** `IsFixed` = "画布链中无前驱节点"（`+8!=0 && +0x54==0`）；`IsFloatBox` 条件含 `+0x54!=0` —— 与 Detach 的 "+0x50 next/+0x54 prev" 互为镜像，读 `IsFixed/IsFloatBox` 时注意是**链位置**判定而非独立标志。
- **Q-canvas-3** `GetNextBox` 的尾/首回环取的是"列表首的 next"（非首本身），2 节点环上可能返回 0 —— 照实记录，画布链遍历优先用显式循环。
- **Q-canvas-4** `AddItem` 与 `Insert` 的 mode 语义**方向相反**（AddItem 0=头插；Insert 0=尾插）。
- **Q-canvas-5** `RecalcLayout` 把"左右边距相等"解释为**水平居中**、上下相等为垂直居中（对称特判），不是保持数值——改边距时相等数值会漂。
- **Q-canvas-6** 悬浮盒（host==0 且浮动态）在 RecalcLayout 中自动获得 0x1000 边框 + 边距归零 + 内容外扩 400。
- **Q-canvas-7** 图像段（seg 类型 0x6010）在每次 RecalcLayout 开头被 `vtbl+0x44(0)` 重排（尺寸可能变），故布局计算须在其后。
- **Q-canvas-8** `SetOutlineInfo` 的边框类型由"点数模式"决定：模式 2 → 0x2000 自定义点；否则按边距特判 0x1000/0；**空点集→恢复默认边距 L/R=800、T/B=400**。
- **Q-canvas-9** esEmbedder 的 `GetSearchChar` 恒为 14 —— "查找"把画布视作单一控制字符；文本遍历工具须按此跳过画布内部。
- **Q-canvas-10** OnEdit 快照存**文件级静态**（DAT_106cd038/DAT_106cd248）：多画布**同时**编辑会互相覆盖快照（编辑器单编辑保证）；对比掩码 `&0x30f`（wrap+followed+align）。
- **Q-canvas-11** `GetNextObjID` 返回**下一个画布**（`+0x50`）的 ID —— 不是图形链下一元素（图形链在 `+0x34`）。
- **Q-canvas-12** 画布—宿主成对死亡协议：`~esEmbedder` 清 `canvas+0x40` 后调 `canvas vtbl+0x5c(0,0)`；`RemoveEnvoy` 走 `esChrObj::RemoveSelf`。绕过协议直接砍一端会留悬空 host。
- **Q-canvas-13** 边距属性存储为"引擎值 **/4**"（LoadProp/SaveProp）；`<400` 有默认清零特判 —— 写属性往返有量化（1 单位=1/400mm，/4 即 0.01mm 步进）。
- **Q-canvas-14** `0x20a/0x20b`（删/插边框点）与 `0x20c/0x20d`（改/移点）分开记：批量拖动边框点应是**一串 0x20c/0x20d**，撤销栈可能很长。
- **Q-canvas-15** 边距四字段 `+0xb8(L)/+0xbc(T)/+0xc0(R)/+0xc4(B)` 与 zRect（left/top/right/bottom）**同布局**——AdjustEdeg 直接以 rect 语义做 EqualRect/字段覆盖，读代码时把 `this+0xb8` 当矩形看。
- **Q-canvas-16** AdjustEdeg 的编辑快照用**另一组文件级静态**（DAT_106cd028..，与 OnEdit 的 DAT_106cd038/248 分离）：`m_pUndo==0` 时只存快照不记撤销；提交时按"哪条边变了"分别记 0x204..0x207。
- **Q-canvas-17** AdjustEdeg 拖动时若"快照 L 与 R 均为 0"（或 T&B 均为 0）→ 对应**两侧边距一起写**（无边框初始态双动）；否则只动被拖边。
- **Q-canvas-18** 自定义边框点 `+0xdc` 存的是**相对内容实心中心**的偏移（GetOutlinePoints 输出时加中心）；别把原始数组当绝对坐标用。
- **Q-canvas-19** `SetBorder` 只在 **frame==0**（无边框）时生效——它给"没边框的画布"用拖点方式建立边距；基准是"内容 solid 外扩 400"（与 Q-canvas-6 的悬浮盒外扩同源）。
- **Q-canvas-20** `SetRole` 返回码三态：0x2020 = 已有 role 未动；0xffff = 固定画布新建（无名）；0x2010 = 非固定新建；多选混合 = 0xfffe。
- **Q-canvas-21** 多选 SetRole 赋名走**两遍**：先探测（类型字一致才继续），再赋名——单只原名、多只"名+序号"（`L"%s%d"` 从 1 递增）。
- **Q-canvas-22** 宿主类型字对不上：esEmbedder ctor 明确写 **ushort 0x40**（两版 ctor 同），但 GetOwnCanvas 用 "tag 0x81 + ID=esEmbedder" 找 embedder（返回 `+0x38`）、"tag 0x40 + ID=esCvsAnchor" 找锚点（返回 `+0x24`），HitTestGraphics 又用 tag **0x81** 做宿主判定。推断 0x40/0x81 是 esSnapObj::Is 的**族类映射**而非 +4 直接值（待核：读 esSnapObj::Is 与 esCvsAnchor 定义）。
- **Q-canvas-23** 边框交互三处有 `OnEdit(1,1)/(0,1)` 包裹（DelBorderPoint；OnEdit 第二参区分图形/边框编辑层）——编辑期快照会重入，别在外层再套 OnEdit。
- **Q-canvas-24**（写档纪律）本 md 早期多行 RVA 误抄（丢前导 `1c`/`1d`；`GetOutlineUndoInfo`/`SetOutlineUndoInfo`/`ChangeFitureLayout` 三行曾把 **dump 行号**当 RVA）。已按 `RVA = entry − 0x10000000` 全部修正并交叉核对（`b11_md_rva_check.py`）。**生成 .h / 机检一律从 dump `entry=` 现算，不信任旧笔记。**
- **Q-canvas-25** 图形样式字 **bit31**（`+0x34 \|= 0x80000000`）是**区域填充标记**：CreateFillRgn 置位、InitCreateRgn 全体清位；油漆桶合并（找同刷邻路）与 GraphicOperation 都靠它识别"填充路径"。（`EraseLines` 另清结果样式字 bit 0x1000，用途待核。）
- **Q-canvas-26** **画布自毁协议**（`vtbl+0x14()` + `vtbl+0x5c(0,0)`，即"把自己从文档里删掉"）在图形运算里反复出现：Clips（宿主掏空且 IsDeletable）、DeleteControlPoints（全链皆控制物件）、GraphicOperation（`op&0x40&&op&0x80`+无边框+无旁图形）、EraseSelectedItems（擦完为空）、CuttingByLBCLine 的 Clips 同款。实现桥时要意识到：这些操作可能**连画布对象本体一起销毁**。
- **Q-canvas-27** `+0x44` = **背景色 COLORREF**（属性/撤销码 0x212）：FillBackround 填内容区、Load 时以 `AddRectangle` 输出整幅底色矩形、CreateBitmap 清屏时无 alpha 用 0xff02（白，param_4 时先褪成纯白 0xffffff）；空值 = 无背景。
- **Q-canvas-28** `CreateDotmap` 生成点阵用**引擎自己的点构造**：`esShapeLine(pt, 0x6001, 0)`（笔 0xffcccccc、宽 0x96）——与原生"加粗点"（AGENTS.md `dots` 通道）同款构造，可互相印证。
- **Q-canvas-29** 导出/快照族（DrawToMetafile/CreateBitmap/CreateDotmap/GetOutputRect/OnPast）统一**跳过类型 `&0xf000==0x7000` 的图形**（占位/隐藏类），且 GetOutputRect 宽或高 < **101 单位（0.25mm）** 即判"无输出"——极小画布导出会静默失败。
- **Q-canvas-30** `HitTestGlobalBoxFrame` 两条怪规矩：① 宿主非空且 `esSnapObj::Is(host,0x40)` → **整框命中直接返回 0**（0x40 族宿主不响应，配合 Q-canvas-22 的族映射解读）；② 命中区是**夹层**：先 Inflate 一次判"在内→0"，再 Inflate 一次判"在外环内→0x1d/0x1e"，即只有"内环之外、外环之内"的一圈算命中。
