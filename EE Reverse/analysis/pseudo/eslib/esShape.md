# eslib 形状对象族 — 反编译规格（阶段 2 · 第十批 · 绘图核心 6/6）

- 模块：eslib.dll；函数：**253 个**（esShapeBase 58 · esShapePath 74 · esShapeGroup 79 · esShapeLine 24 · esShapeCap 18）
- 伪代码（原样）：`analysis/pseudo/eslib/esShape.decomp.txt`（matched=253 dumped=253）
- 类型头：`analysis/types/esShape.h`
- 台账：253/253 → `decompiled`（status-overrides）
- 角色：S1 形状对象基族 —— 全部可绘制图形对象的共同祖先链 `esGraphObject → esShapeBase → esShapeLine → { esShapeCap · esShapePath · esShapeGroup }`。esShapeBase 持有"段包装指针 `+0x40` + 角色 `+0x4c` + 32 位标志 `+0x34`"；esShapeLine 追加内嵌 `esPenInfo@+0x50`；esShapeCap 追加双端饰字 `+0x5c/+0x5e`；esShapePath 追加段表链（`esSegList`）+ 笔刷 + 液体填充 + 亮位；esShapeGroup 追加子对象双链 + 控制点链 + 联动线链 + 重复器 + 独立矩阵层。本批定下：**段工厂 `OnStructure`**（`1a0ad0`，17 种"轻段型"→esSeg 包装；路径侧大 ctor `19e200` 另有一张"重段型"表）、**路径渲染的双通道**（`DrawGraphics`：首段类型字 `&0x800` → 段自绘 `vtbl+0xb0`；否则 `DrawForNormal` 走 esMoldPath）、**组的 offset-100 控制点协议**（`+0x64` 数组 / `+0x6a` 计数 / `CreateUserLinkPoints` 打包 / `GetLinkPts` 展开）、**组矩阵层**（`flags & 0x8000000` → `esMatrixObj(+0x74)` 独立管理变换，否则用段 `+0x40` 的 esParaLine::GetCompos 矩阵）、**三套序列化**（base/line/path/group 各自的字段流）与全批撤销码（§6）。

## 0. 谱系与公共结构（本批结构性结论）

| 结论 | 证据 |
|---|---|
| `esShapeBase : esGraphObject`，**尺寸 0x50**：`+4` 类型字 · `+8` esAmulet*（父链，经 esScopedAmulet） · `+0x34` dword 标志 · `+0x38` ushort · `+0x3c` word · `+0x40` esSeg*（段包装） · `+0x44` next / `+0x48` prev（父子链） · `+0x4c` esRole* | ctor `19b470` / dtor `19b540` / `Detach 19c490` / `DeleteSlef 19c5a0` |
| `esShapeLine : esShapeBase`，**尺寸 0x5c**：内嵌 `esPenInfo @+0x50`（`+0x50` 色 dword / `+0x54` 样式 / `+0x58` 线宽；默认 0xff01 / 0 / 0x50） | 默认 ctor `1a0870`、`GetPenInfo 11a20`（return this+0x50）、拷贝 ctor `11a60`（base 拷贝 + peninfo 拷贝） |
| `esShapeCap : esShapeLine`，**尺寸 0x60**：`+0x5c`、`+0x5e` 两个 ushort（默认 0x400/0x400）；拷贝/赋值**只多拷这两字** | 拷贝 `11d40` / `op= 11d90` / 大 ctor `1a2500`（默认 flags=0x4070037、pen 0xff01） |
| `esShapePath : esShapeCap`，**尺寸 0x74**：段表首 `+0x60` / 尾 `+0x64`（esSegList 链） · 笔刷 `+0x68` · 液体 `+0x6c` · 亮位 byte `+0x70`（默认 100） | 拷贝 `11fd0`（只多拷 +0x60/+0x64/+0x68/+0x6c/+0x70） / `SetBright 11fb0` / `IsEmpty 11f80`（`+0x60==0`） |
| `esShapeGroup : esShapeLine`，**尺寸 0x84**：子链首 `+0x5c` / 尾 `+0x60`（子 next `+0x44` / prev `+0x48`） · ctrl 链 `+0x64` + 计数 word `+0x6a` · 特性 ushort `+0x68` · 联动线链 `+0x6c`（节点 {esSegLinkLine*, ushort idx, next}=0xC） · `esShapeRepeater* +0x70` · `esMatrixObj +0x74`（Gdiplus 矩阵 @+0x78） | ctor `3c5a60` / `op= 12870` / `CreateObject 3c6be0` |
| 对象类型字（`+4`）：Line 0x3109 · Cap 0x320b · Group 0x3008 · Path 0x330f · Holder 0x3908 · Control 0x3a08 · OleCanvas 0x3700 · Dime 0x3e00 · Link 0x3a03 · 组矩形段 0xb001；**"无段"对象 GetShapeType 返回 0xffff** | 各 ctor / `CreateObject 3c6be0` / `GetShapeType 116a0` |
| Base 级操作全部**转发段虚表**：CollectStyles→`+0x10` · OnCreate→`+0xa0` · SnapPoint→`+0xd0` · HitTestAcme→`+0xc0` · MatrixProc→`+0x84` · AppendMatrix→`+0x80` · LoadEdge→`+0xac` · GetOrg→`+0xcc` · AddPoint→`+0xd8/+0x88` · LoadLbcLines→`+0xb4` · Serialize 段→`+0x40` · CopyFrom 段→`+0x24` · Load 段→`+0xe0` | 各转发函数体 |
| 标志 `+0x34` 已知位：`0x1000` closed（闭合） · `0x8000` cyclic（成环） · `0x100` package（组封装） · `0x30` 闭合过渡（CheckEndDrawing 清） · `0x80` 可吸附（SnapPointProc） · `0x400` ctrl 特殊 · `0x800` ctrl 起点标志 · `0x4000` 填充模式（DrawForNormal 的 FillMode；=1 → SetFillMode(alt)） · `0x400000` 液体存在 · `0x800000` 可填充子标记（GetFillBorders） · `0x1000000` 隐藏/跳过（组渲染工具态） · `0x2000000` · `0x4000000` 叠加区 · `0x8000000` 组矩阵层 · 位 16..23（`0xff0000`）= 8 个布尔特性（道具 0xf01..0xf08） | LoadProp/SaveProp `1a7cf0`/`1a7f20`、CheckEndDrawing、各函数 |
| 道具组 **0xf00**（通用布尔特性）：`0xf01..0xf08` ↔ `flags` 位 16..23（逐个 AddItem，仅当 `param_2 & 0xff0000 & flags`）——**须 `param_2 & 0x1000000`** 且对象非 0x330f → 段 `vtbl+0x18`（加载）/`+0x1c`（保存）级联；`0xf0b↔0x4000000`、`0xf0c↔0x2000000`、`0xf11↔0x1000000`（非 0x3a08 才给）；`0xf12↔0x8000000` **仅 0x3008（组）**，且其变更时调 `esShapeGroup::ReleaseMatrixLayer(this, m_pUndo)` | `LoadProp 7587` / `SaveProp 7650` 原文 |
| 标志变更统一记 **undo 0x50d**（`FUN_10026360(this, 0x50d, this+0x34)` 存旧值）；0x50d 撤销时若 `0x9000` 位有变化 → 段 `vtbl+0x44(0)`（重排） | `SaveProp 7756` / `Undo 8286` |
| 矩阵协议：`esMatrixObj`（组 `+0x74`）——`flags & 0x8000000` 时组 `GetMatrixEx/AppendMatrix/MatrixProc/Render/OnMovePoint` 走**自矩阵层**，否则走段 `+0x40` 的矩阵（`esParaLine::GetCompos`）；`epCloneMatrix`/`FUN_10027140` 为矩阵拷贝/串联辅助 | `GetMatrixEx 3c68c0` / `AppendMatrix 3c6a30` / `Render 3c8fd0` / `OnMovePoint 3c6b30` |
| 组"第三方控件协议"：对象带 ctrl（0x3a08 子）时 `+0x6a`=ctrl 计数、`+0x64`=ctrl 指针数组（首指针 = 链接点包装）；`CreateUserLinkPoints 3cb070` 打包、`GetLinkPts 3c7060` 展开（无 ctrl 时按组矩形 4 边 16 等分点展开） | 两函数原文 |

**布局总表**

- esShapeBase（0x50）：`+4` type · `+8` amulet · `+0x34` flags · `+0x38` ushort（MarkProperty） · `+0x3c` word · `+0x40` esSeg* · `+0x44` next · `+0x48` prev · `+0x4c` esRole*
- esShapeLine（0x5c）：`+0x50` esPenInfo{色 dword/样式/宽} · `+0x54` 样式 word（&0xf00/&0xf000 两位段） · `+0x58` 线宽
- esShapeCap（0x60）：`+0x5c`/`+0x5e` ushort（形状端饰；大 ctor 按段型写 0x400/0x404/0x402）
- esShapePath（0x74）：`+0x60` esSegList* 首 · `+0x64` 尾 · `+0x68` esBrush* · `+0x6c` esLiquid* · `+0x70` byte bright
- esShapeGroup（0x84）：`+0x5c`/`+0x60` 子链首尾 · `+0x64` ctrl 数组 / `+0x6a` 计数 · `+0x68` ushort 特性（道具 0x801..0x809） · `+0x6c` link 链 · `+0x70` repeater · `+0x74` esMatrixObj（矩阵 @+0x78）

## 1. esShapeBase（58 个）（全部图形对象的基类）

| 函数 | 入口 | 规格 |
|---|---|---|
| `GetShapeType()` | `116a0` | 类型字==0x3008→0；`+0x40==0`→**0xffff**；否则 `esLineHead::GetFontIndex(seg)`【Q-shape-1】 |
| `DrawForInternal(...)` | `116f0` | 基类空实现（21B，仅解构 std::function 参数） |
| `IsClosed / IsCyclic / IsClosedEx` | `11710 / 11740 / 11770` | `flags&0x1000` / `flags&0x8000` / `IsClosed() \| (IsCyclic()<<1)` |
| `IsPlaceHolder()` | `117c0` | `+0x40 && type==0x3908 && 段型==0xafff`（无内容 Canvas 占位） |
| `IsPtInPt(pt, ±range)` | `11810` | solid rect 外扩 `range` 后 PtInRect |
| `ctor(拷贝/移动) / operator=` | `11870 / 118f0` | esGraphObject 拷贝 + **`+0x34..+0x4c` 全拷**（含段指针/链指针浅拷） |
| `ID / isKindOf / isOf` | `19b330 / 19b340 / 19b3e0` | `"esShapeBase"`；isKindOf：this==0→0、名中→1、否则 `esGraphObject::isKindOf` |
| `ctor()` | `19b470` | 清零 `+0x34..+0x4c`（100B） |
| `CollectStyles(sheet)` | `19b4e0` | 非 0x330f 且段存在 → 段 `vtbl+0x10`；role → `vtbl+0x10` |
| `~esShapeBase()` | `19b540` | `esRole::Release(+0x4c)` + 段自毁 `vtbl(1)` + `~esGraphObject` |
| `CheckEndDrawing(cnt, checkonly)` | `19b5e0` | 占位/无段→0。分支 A（段型字 `&0x1c0 != 0x100`，成环判定）：0x4488≥4 / 0x4489·0x480f·0x6009（须 checkonly==0）/ 0x5004≥3 / 0x4c0e≥3…… 取首末点，重合→置 `0x8000` + 段 `vtbl+0x44(0)` 并 return 1；分支 B（闭合判定，须 type==0x330f、段为 esSegLines）：0x4306/0x4307 须 checkonly==0、0x4702≥3、0x4703≥2、0x4704≥4、0x4705/0x4708≥3 → 首末点重合→置 `0x1000`、清 `0x30` |
| `LoadLbcLines(list,matrix)` | `19b940` | `IsContainLBCLines` 门 → `FUN_10380b20` + 段 `vtbl+0xb4(list, matrix, 0)` + `FUN_10380b40` |
| `IsEqual(obj,sheet)` | `19b9a0` | `esGraphObject::IsEqual` + `+0x34` 等 + role 等 + （330f 特判→1；否则段 `vtbl+0x4c`） |
| `GetTotalMatrix(dst, skipself)` | `19ba70` | 沿 amulet 父链：自 this 起凡 esShapeGroup 且（skipself 或非首级）→ `GetMatrixEx` 右乘；遇 esCanvas → 无第三参则返回 0，否则 canvas 矩阵；返回经过的组数 |
| `IsContainLBCLines()` | `19bc00` | 330f→1；段型∈{0x4c0e, 0x480f, 0x4a8a} 或 0x6001<型<0x6006 或 0x5001<型<0x5007 → 1 |
| `Serialize(arc,sheet,ver)` | `19bc90` | 写 `[type][+0x34][role]`；**非 0x330f** → 段：`ReadWord 型`+工厂 `(this+0x58)(型)`+`ResetLineWidth`+段 `vtbl+0x40(arc,sheet,param_3)`；末 `esObject::Serialize` |
| `CopyFrom(src,exchanger)` | `19bdc0` | `esSeg::BreakLine`；ID 判型：拷 `+0x34`；非 330f 且 src 有段 → 工厂建段 + `ResetLineWidth` + 段 `vtbl+0x24(src段, exchanger)`；role → `esStyleExchanger::CopyRole` |
| `SearchUp(level)` | `19c160` | `level!=0xc` → `esObject::SearchUp`；否则返回自身 |
| `AddPoint(...)` | `19c190` | 330f → `EnumSegments`+组 lambda；否则段 `vtbl+0xd8`（可加点判定）+ `vtbl+0x88`（加点） |
| `OnMessage(msg,ulong)` | `19c2f0` | 段 `vtbl+0x48` + role `vtbl+0x48`，任一处理→`vtbl+0x44(0)`；末 `esObject::OnMessage` |
| `GetNextObjID()` | `19c460` | `+0x44==0`→0；否则 `esObject::GetID(+0x44, 0)`（下一个对象的导出 ID） |
| `Detach()` | `19c490` | 从父（`+8` amulet）摘链：无父→`vtbl+0x44(0)`；父为组(0x3008)→修补组 `+0x5c/+0x60` 与自身 `+0x44/+0x48` 双向链；非组→修补 `+0x34/+0x38`；`ResetLineWidth(this,0)` |
| `DeleteSlef(p1,p2)` | `19c5a0` | `p1==0` 或 `prev==next`：`p2==0` → `vtbl+0x38`（自毁）+ `delete(this,1)`；否则 amulet `vtbl+0x5c(1,p2)`（交父级删除协议） |
| `OnItemModified()` | `19c630` | 330f → `EnumSegments` 逐段通知；否则段 `vtbl+0x44(0)` |
| `RecalcLayout()` | `19c720` | 段 solid/bounding → `SetSolidRect` / `SetBoundingRect`（**外扩 400**） |
| `HitTest(ht,mode)` | `19c7c0` | `+0xc==0` 门；330f → `EnumSegments` 收集命中；否则 `CheckRectL` + 段 `vtbl+0xc4(ht)` → 返回段 |
| `GetOrg(...)` | `19c970` | 330f：遍历段表（首尾段判定）求各段 org（段 `vtbl+0xcc`），多样→0，一致→1；否则段 `vtbl+0xcc` |
| `GetCtrInfo(list,mask,...)` | `19ca80` | 段 `vtbl+0xd4(l, param_4)`；段对象为字体项（vtbl ID 位 &0x10）→ 追加 `esVertexInfo(段 vtbl+0x68(0,-1) 点, flag 0x25410000)` |
| `BreakCyclic()` | `19db50` | `flags&0x8000` → undo **0x50d** + 清位 |
| `IsLoadable()` | `19dba0` | 0x3a08→0；0x3908→ `+0x40==0` 或段型 0xafff（占位）→0；其余 1 |
| `Load(page,subj)` | `19dc10` | 空实现（16B，直通返回）——实际装载在各子类 |
| `Draw(render)` | `19dc20` | solid rect `esRender::IsVisible` → `vtbl+0xbc(render)` |
| `GetLineList(list,mode)` | `19dc60` | 段 `vtbl+0x8c(list, 0)` + `esLineList::EndOnePts(list, 0)` |
| `GetCommonSidePoints(dst,rect)` | `19dca0` | 由 solid rect 生成 5 点：`[0]=(midX,top) [1]=(left,midY) [2]=(midX,bottom) [3]=(right,midY) [4]=(midX,midY)` |
| `LoadLines(worker,mode)` | `19ddc0` | `mode==0`：父为组→父 `vtbl+0x6c(worker,0)`；否则 `esGraphWorker::Add(this,1,1)` |
| `AppendMatrix(m,u)` | `19de20` | 段 `vtbl+0x80(m,u)`；role 为画刷扩展→`esBrushEx::AppendMatrix` |
| `MatrixProc(mode)` | `19de70` | 段 `vtbl+0x84(param)`；role→`esBrushEx::MatrixProc` |
| `SnapPoint(mgr,mode)` | `1a5d10` | bounding `esSnapManager::CheckRect` → 段 `vtbl+0xd0(mgr)` |
| `HitTestAcme(ht,mode)` | `1a5d90` | 段 bounding `CheckRectP` → 段 `vtbl+0xc0(ht)` |
| `IsPtInMaxBox(pt,range)` | `1a5e20` | bounding 外扩 `range` 后 PtInRect |
| `LoadEdge(group,matrix)` | `1a5e90` | `vtbl+0xac` 取单段（Path 会新建）→ 若为 esShapePath → 段 `vtbl+0xb8(group,matrix)`；默认返回 2；临时段自毁 |
| `Insert(obj,obj,mode)` | `1a60a0` | `+0x40 = param` + `ResetLineWidth` |
| `OnCreate(sheet)` | `1a60d0` | 段 `vtbl+0xa0(sheet)` + `vtbl+0x44(0)` |
| `HitTestForRole(ht)` | `1a6cb0` | 段型 0x3a08→0；role（esRoleList）`+0x38` `vtbl+0x8c` |
| `HitTestObjClick(ht,pt)` | `1a6cf0` | model box（esTextBox::GetModelBox）==7 → `+0x44=this`（本体命中）；否则 0 |
| `IsRgnClicked(pt,...)` | `1a6e50` | 射线隔数（段 `esSeg::GetJiaoCount` 奇偶）→ 点是否落在填充区 |
| `LoadProp(mgr,param)` | `1a7cf0` | ①`param&0x1000000` 且非 330f → 段 `vtbl+0x18(mgr,0)`；②组 0xf00：`0xf01..0xf08` ↔ `flags` 位 16..23（逐位 AddItem）；③`param&0x4000000` 且非 0x3a08：`0xf0b/0xf0c/0xf11` ↔ `0x4000000/0x2000000/0x1000000`；**0x3008 加 `0xf12` ↔ `0x8000000`** |
| `SaveProp(mgr,param)` | `1a7f20` | 同 LoadProp 镜像：①段 `vtbl+0x1c`；②各位段 IsModified → 改 `local_c` 副本；③`0xf12` 变更且 0x3008 → `ReleaseMatrixLayer(this, m_pUndo)`；末 `flags!=local_c` → `FUN_10026360(this, 0x50d, this+0x34)` 记旧值 + 写回 |
| `DeleteRole()` | `1a8ca0` | undo **0x523**（role 下标 word，role+0x14）→ `esRole::Release` + `+0x4c=0` |
| `OnActive(closing)` | `1a8d20` | `param==0` 且型 0x3700（OLE 画布）→ `GetFixedCanvas` → `esOleObject::IsOpen/Close` |
| `Undo(code,...)` | `1a8d70` | **0x50d**：`flags` 经 zStream `<<旧 >>新` 交换；`0x9000` 位变化且段存在→段 `vtbl+0x44(0)`；default → `esFormulaBox::CaretMove`（文本框撤销兜底） |
| `SetRole(sheet,name)` | `1a8e10` | `+0x4c==0` 且 name==0：型 0x3908 →（`vtbl+0xa8` 子 role）若得→返回其型字；型 0x3008 → 0x3008；否则 0x330f。name 给出 → `esRole::CreateRole(this,sheet,1)` + `SetName`，返回自身型字 |
| `Undata(&code,data,&sz)` | `1a8ec0` | **0x523**：换出当前 role 下标（`role+0x14`；无 role→0xffff），新值 0xffff → `+0x4c=0`；否则从 `m_pUndo+8 ↓ +0x794` esStyleList 取 role + `ResetLineWidth`；else `esObject::Undata` |

**怪癖**：
- **Q-shape-1** `GetShapeType` 对"无段对象"返回 **0xffff**（不是 0）——0 专指组；用返回值做表下标的代码须先滤 0xffff。
- **Q-shape-2** `LoadProp/SaveProp` 的位 16..23 特性**仅当调用方 mask 覆盖**（`param_2 & 0xff0000`）才枚举；编辑器分批 read property 时会看到部分位缺失，属预期。
- **Q-shape-3** `+0x34` 的 0x8000000（组矩阵层）**不在通用位段**里：LoadProp 只对 0x3008 给 `0xf12` 道具；SaveProp 里它的变更伴随着 `ReleaseMatrixLayer` 这一副作用（先释放再改位）。
- **Q-shape-4** `Undo 0x50d` 的副作用：`0x9000`（cyclic|closed）任一变化都会强制段 `vtbl+0x44(0)` 重排——所以"改闭合属性=重建段"。
- **Q-shape-5** `DeleteSlef` 的链尾特判 `prev==next`：链上只剩自己时走组交接（`vtbl+0x5c(1,...)`），否则直接自毁。
- **Q-shape-6** `HitTestObjClick`（base）只认 model box 7（本体）；路径/组各自覆写（§4/§5）。

## 2. esShapeLine（24 个）

| 函数 | 入口 | 规格 |
|---|---|---|
| `GetPenInfo()` | `11a20` | return (esPenInfo*)(this+0x50)（内嵌，不分配） |
| `~esShapeLine()` | `11a40` | `TLaterParam::~(+0x50)` + `~esShapeBase`（peninfo 无堆资源） |
| `ctor(&& / const&)` | `11a60` | ILT 折叠（move+copy 两符号同一实现）：base 拷贝 ctor + vftable + `esPenInfo::esPenInfo(this+0x50, src+0x50)` |
| `operator=(&& / const&)` | `11ad0` | ILT 折叠：`esShapeBase::operator=` + `esPenInfo::operator=` |
| `ID()` | `1a0720` | `L"esShapeLine"` |
| `isKindOf(name)` | `1a0730` | ==ID → 1；否则 `esShapeBase::isKindOf` |
| `isOf(name)` | `1a07e0` | 逐字比 ID |
| `ctor()` | `1a0870` | type 0x3109；pen 0xff01 / 0 / 50 |
| `ctor(esShapeLine* src)` | `1a0900` | "克隆样式"构造：默认 base + 拷 `+0x50/+0x54/+0x58` + `+0x34`（不动段/链/role） |
| `ctor(tagPOINT&, type, flags)` | `1a09a0` | base 默认 + `OnStructure(pt, type, flags)` |
| `ctor(esSnapManager*, type, flags)` | `1a0a20` | `esSnapManager::GetSnapPoint` → `OnStructure`（画图工具"落点即建"通道） |
| `OnStructure(pt, type, flags)` | `1a0ad0` | 1773B——**段工厂主表（§2.1）**：默认 type=0x3109、pen 若 0→0xff01、`flags=0x4000005`；末尾 `+0x40=段` + `esCalligraph::ResetLineWidth` |
| `Load(page, subj)` | `1a1270` | `GetSolidRect(1)` → `elfPage::NewSubj(this, subj, rect, 1, role)` → 段 `vtbl+0xe0(page, subj, 上下文{pen=this+0x50, 0, flags})`——段自己把内容装进 subj |
| `Render(render)` | `1a1320` | `painter->GetGraphics(0)` → `Save` → `GobackToDrawPoint` → 段 `vtbl+0xb0(render, 同上下文, matrix)` → `Restore` |
| `GrapConvert()` | `1a1400` | 型须 0x3109/0x320b；段型 0x6001/0x600a/0x600b → 0；否则 new esShapePath(0x74) + `InitPropertys(this, 1)` + `flags=0x40700ff`；`esLineList` ← 段 `vtbl+0x8c(list, IsCyclic)` → `GetShape`；路径无段→销毁返回 0；段是 esSegImage → `MackPicBrush` → `SetBrush`【Q-shape-9】 |
| `IsEqual(obj, sheet)` | `1a1610` | base + `memcmp(pen@+0x50, 12 字节)`（色/样式/宽全等） |
| `ToFixColor(scheme)` | `1a1680` | 色非 0 且无 alpha 区（`&0xff000000==0`）→ `esColorScheme::GetColor`；变化→undo **0x503**（记录旧色） |
| `Serialize(arc, sheet, ver)` | `1a1700` | base + `esPenInfo::Serialize`；**加载时** styleSheet 版本 `< 0x1000203`（旧档）→ `flags \|= 0x4000000` 且色 `ToEpColor(色, 0x11)` |
| `CopyFrom(src, exchanger)` | `1a1780` | base + 源同型 → **源 pen 拷入自身 pen**（`esPenInfo::CopyTo(源, 自身)`，约定：首参=源） |
| `GetSnapPoints(pts, rect)` | `1a17f0` | 段分派：esSegGon→自身实现；0x6001→1 点；0x6010→两端点 2；0x6002→`GetCommonSidePoints` 5 点；0x6003→esSegCircels 中心（须在 solid rect 内）；0x5005→esSegGlow 中心；其余 0 |
| `GetColors(arr, mask)` | `1a1b50` | `mask&1` 且 pen 色非 0 → 去重后把 `+0x50` 追加进数组（返回 1） |
| `LoadProp(mgr, param)` | `1a1bb0` | `uVar1 = param & flags`；`uVar1&7` → 组 0x500：`&1`→**色** 0x503（无 alpha：色原值+0x504=alpha 字节；**有 alpha：0x503=色\|0xff000000、0x504=色>>24**）；`&4`→**宽** 0x506 `+0x58`；`&2`→**样式** 0x507 低 8 位、0x511 `(&0xf00)>>8`、0x512 `(&0xf000)>>0xc`（+0x54）；末尾 base【Q-shape-10】 |
| `SaveProp(mgr, param)` | `1a1d00` | 镜像回写：**宽** 0x506 `CheckWrite`，变且非 330f 且有段→段 `vtbl+0x44(0)` 重算；**色**：段型 0xa002/0x600d（公式框/标签）走 `SetTextColor` 特殊通道，否则 `Find(0x505)` 有则 `CheckWrite(0x505)` 无则 `CheckWriteColor(0x503/0x504)`；色非 0 且宽 0 → 记 0x506 + 宽置 0x28；**样式**：0x507/0x511/0x512 拼回 `+0x54`（未闭合才有 0x511/0x512），变化→`FUN_100260d0(this, 0x507, &old)`；末尾 base |
| `Undo(code, ...)` | `1a20a0` | **0x503/0x505**→色 `+0x50` 交换；**0x506**→宽 `+0x58`；**0x507**→样式 `+0x54`；default→base |

### 2.1 OnStructure 段工厂表（"轻段型"→esSeg 包装）

| 段型字 | 段对象（new 尺寸） | 附加设置 |
|---|---|---|
| 0xe0xx（`& 0xf000 == 0xe000`） | `esSegPoint`(0x68) | 线宽 `+0x58=200` |
| 0xafff | `esSegPlaceHolder`(0x7c) | `flags \|= 0x20002`；pen=0 |
| 0x6001 | `esSegPoint`(0x68) | `+0x58=200` |
| 0x6002 | `FUN_10013d50()`(0x74)（线型段工厂函数） | `flags \|= 0x20002` |
| 0x6003 | `esSegCircels`(0x8c) | `flags \|= 0x20002` |
| 0x6004 | `esSegSectionLine`(0x6c) | `flags \|= 0x20002` |
| 0x6005 | `esSegSurface`(0x6c) | `flags \|= 0x20002` |
| 0x6006 | `esSegText`(0x84) | pen=0；`flags \|= 0x20002` |
| 0x6007 / 0x6008 | `esSegRuler`(0x74) | — |
| 0x6009 | `esSegArcRuler`(0x78) | — |
| 0x600a | `esSegRulerTextA`(0x7c) | **`flags=1`（整体覆盖默认）** |
| 0x600b | `esSegRulerTextB`(0x7c) | **`flags=1`** |
| 0x600e | `esSegMatchMan`(0x130) | **`flags=7`**；`+0x58=100` |
| 0x6010 | `esSegBond`(0x70) | `flags \|= 2` |
| 其它 | （无段，`+0x40=0`） | 保持默认 type=0x3109 / pen=0xff01 / flags=0x4000005 |

末尾统一：`+0x40 = 新段` + `esCalligraph::ResetLineWidth(段, this)`。

**怪癖**：
- **Q-shape-7** 0x600a/0x600b/0x600e 的 `flags` 是**直接赋值**（1/1/7），会冲掉默认的 0x4000005——这三型（文本尺 A/B、匹配人）没有通用标志位，`CheckEndDrawing` 等大分支对它们另有特判。
- **Q-shape-8** 0x6002 的段工厂是 `FUN_10013d50`（未命名，疑 esSegLine 的受限构造通道）；引用时按 RVA 记录。
- **Q-shape-9** `GrapConvert` 只认 0x3109/0x320b 两种对象类型，且把 0x6001（点）/0x600a/0x600b（文本尺）直接拒回 0——"转换为图形对象"只针对图形菜单对象。
- **Q-shape-10** 属性侧的位段网关 `uVar1 = param_2 & flags`：属主工具只会为**对象当前 flags 里置位的组**枚举道具（颜色/样式/宽三组位 0..2）；0x6002 的吸附点用法与 0x6003 相同（5 点/中心）。

## 3. esShapeCap（18 个）（尺寸标注/轴类形状）

| 函数 | 入口 | 规格 |
|---|---|---|
| `~esShapeCap()` | `11d20` | 仅 `~esShapeLine`（+0x5c/+0x5e 是 POD，无资源） |
| `ctor(&& / const&)` | `11d40` | ILT 折叠：line 拷贝 + vftable + 拷 `+0x5c/+0x5e` |
| `operator=(&& / const&)` | `11d90` | ILT 折叠：line op= + 拷 `+0x5c/+0x5e` |
| `ID()` | `1a2190` | `L"esShapeCap"` |
| `isKindOf(name)` | `1a21a0` | ==ID → 1；否则 `esShapeLine::isKindOf` |
| `className()` | `1a2240` | **`return esShapeLine::ID()`**（ILT 4 类折叠：Cap/Group/Holder/Ole 同址）【Q-shape-14】 |
| `isOf(name)` | `1a2250` | 逐字比 ID |
| `ctor()` | `1a22e0` | type 0x320b；`+0x5c=+0x5e=0x400`；`flags \|= 0x4000030` |
| `Load(page, subj)` | `1a2340` | 同 Line::Load，上下文多带 `+0x5c/+0x5e` |
| `Render(render)` | `1a2400` | 同 Line::Render，上下文多带 `+0x5c/+0x5e` |
| `ctor(esSnapManager*, type, flags)` | `1a2500` | 默认 `flags=0x4070037`；`+0x5c=+0x5e=0x400`；pen 若 0→0xff01；**switch(type)**：0x5001→`esSegSimpleAxis(0x74)`+`flags\|=0x80`+`+0x5e=0x404`；0x5002/0x5003→`esSegSimpleSingleAxis(0x74)`+`flags\|=0x80`+`+0x5e=0x404`；0x5005→`esSegGlow(0x8c)`；0x500d→`esSegArrowLines(0x6c, arg=1)`+`+0x5e=0x402`；**0x5006（坐标轴）无 case**【Q-shape-11】；末尾 `+0x40=段` + ResetLineWidth |
| `IsEqual(obj, sheet)` | `1a27b0` | line + `+0x5c/+0x5e` 相等 |
| `Serialize(arc, sheet, ver)` | `1a2820` | line + **`flags & 0x30` 才**读写 `+0x5c/+0x5e` 两 ushort（闭合图形不存端饰） |
| `CopyFrom(src, exchanger)` | `1a28a0` | line + 源同型 → 拷 `+0x5c/+0x5e` |
| `LoadProp(mgr, param)` | `1a2920` | line + **未闭合**且 `uVar1&0x30`：`&0x10`→0x508(`+0x5c` 低 8 位)/0x50a(高 8 位)；`&0x20`→0x509(`+0x5e` 低)/0x50b(高) |
| `SaveProp(mgr, param)` | `1a2a00` | 镜像回写（`IsModified` 才拼字）；`+0x5c`/`+0x5e` 变化 → `FUN_10052810(this, 0x508/0x509, &old)` |
| `Undo(code, ...)` | `1a2c20` | **0x508**→`+0x5c` 交换；**0x509**→`+0x5e` 交换；其余 base |
| `GetTextObj()` | `1a2cc0` | 段型 0x5006 → `esSegAxis::GetActiveTBox`（轴的文本盒）；否则 0 |

**怪癖**：
- **Q-shape-11** `esShapeCap(snapMgr, 0x5006, flags)` **没有分支**：轴对象不能经 Cap 工厂通道构造（与 AGENTS.md 逆向结论一致，程序侧仍走"直线+字母"替代）。
- **Q-shape-12** 端饰属性（0x508/0x509 ↔ `+0x5c/+0x5e`）在 LoadProp/SaveProp/Serialize 三处**统一受 `flags&0x30` 与"非闭合"双重门控**——闭合图形无端饰语义。
- **Q-shape-13** `FUN_10052810(this, 0x508/0x509, &old)` 是 ushort 级 undo 记录器（对称 base 的 `FUN_10026360` dword 版）。
- **Q-shape-14** `className` 的 ILT 折叠意味着**运行时无法用虚函数区分 Cap/Group/Holder/Ole 的类名**——判类型必须用 `+4` 类型字（0x320b/0x3008/0x3908/0x3700）。

## 4. esShapePath（74 个）（自由路径 / 填充图形）

| 函数 | 入口 | 规格 |
|---|---|---|
| `IsEmpty()` | `11f80` | `+0x60==0`（无段表即空） |
| `SetBright(b)` | `11fb0` | `this[0x70]=b`（亮位字节，渲染时传给笔刷） |
| `ctor(const&)` | `11fd0` | Cap 拷贝基座 + 浅拷 `+0x60/+0x64/+0x68/+0x6c/+0x70`（不深拷贝段表/笔刷） |
| `operator=(&&/const&)` | `12040` | ILT 折叠：同上（Cap op= + 5 字段浅拷） |
| `AddSegObject(seg,mode)` | `19beb0` | `+0x60==0` → `new esSegList(0x44)` 挂 `+0x60/+0x64`+`ResetLineWidth`；`esSegList::AddSegObject(+0x60, seg, mode)`；`+0x40=seg` |
| `NormalRing(undo)` | `19bf70` | 段链归一化：esBulletsManager 临时上下文 + lambda 回调后 `EnumSegments()`（内部收尾/重排） |
| `SnapPoint(mgr,mode)` | `19bff0` | bounding `CheckRect` → 逐表 `esSegList::SnapPoint`，任一成功→1 |
| `SnapFarPoints(mgr,pt,range,mode)` | `19c090` | 点在 solid 外扩 `range` 内（任轴）→ 逐表逐段 `seg vtbl+0x70(mgr,x,y,range,mode)` |
| `AddSegList(list)` | `19c380` | 表入尾链：`ResetLineWidth(list,this)`；`list+0x3c=旧尾`→旧尾 `+0x40=list`（或 `+0x60=首表`）；`+0x64=新尾`；`+0x40=首表首段` |
| `AddSegListEx(list)` | `19c3f0` | 空表（`+0x34==0`）→ free 表返回 0；否则 `+0x40=0` + `AddSegList` → 1 |
| `RemoveAllPts()` | `19c6b0` | 清全部段表：`+0x40=0`；逐表 free（`vtbl(1)`）；`+0x60/+0x64` 归零 |
| `LoadProp(mgr,param)` | `19cbf0` | ①`param&0x1000000` 且**单表单段** → 段 `vtbl+0x18(mgr,0)`（文本/轴等专属道具级联）；②Cap 链；③`&8` → 组 0x500：0x501=`esPropBrushItem(刷)`（既有则 `vtbl+0x38` 刷新）；`&0x2000000` → 0x502=亮位；`&8==0 && &0x40` → 组 0x600：0x611=液体高度（无液体→记 0，否则 `esLiquid::LoadProp`） |
| `SaveProp(mgr,param)` | `19cdb0` | 镜像：单表单段 → 段 `vtbl+0x1c`；0x611 变更：值 0 → **undo 0x602**+free 液体；非 0 → **undo 0x601**+`new esLiquid(0x2c,组)`+若 `flags&0x400000==0` 则 undo 0x50d+置位（`0x400000`=液体存在）；未变更 → 液体自身 `SaveProp`；0x501 变更 → `UpdateBrush(this, styleSheet, brushInfo)`；0x502 变更 → **undo 0x502**（记旧 1 字节）后写亮位 |
| `Undata(&code,data,&sz)` | `19d100` | 0x502 亮位交换；**0x521→0x520**（换出刷数据、free 刷、`+0x68=0`）；**0x520→0x521**（`CreateBrush` 装入）；0x522 刷数据交换；**0x601↔0x602**（液体取/装）；`0x541..0x57f` → `刷 vtbl+0x2c`（笔刷子撤销通道）；否则 base |
| `GetCtrInfo(list,mask,...)` | `19d410` | 条件分支 → `GetLiquidCtlPointInfo`；lambda + `EnumSegments`（逐段收集控制点）；特定条件下再补 `esVertexInfo(首段起点, 0x25410000)` |
| `HitTestLiquidAcme(ht)` | `19d5f0` | bounding 命中且 `!(mode&0x10)` 且有液体 → 液体 batchinfo 点 `HitTestPoint` → `SetSelInfo(0x12)` |
| `HitTestAcme(ht,mode)` | `19d6c0` | 液体点命中（0x12）优先；否则 lambda+`EnumSegments`；命中且 model box∈{0x10,0x6} 时按**相邻段类型 0x4703（贝塞尔）**把 `ht+0x44/+0x38` 重定向到段端点 |
| `GetLiquidCtlPointInfo(list)` | `19d9e0` | 有液体 → 液体 batchinfo 点 → `esVertexInfo(pt, 0x50610000, 1, this)` 加入列表 |
| `CreateObject(type)` | `19dee0` | `type==0x2030` → `new esSegList(0x44)`；否则 `esSeg::Create(type)` |
| `ID / isKindOf / isOf` | `19df80 / 19df90 / 19e040` | `"esShapePath"`；isKindOf 失败回落 `esShapeCap::isKindOf` |
| `ctor()` | `19e0d0` | Cap 默认 + type 0x330f + `flags=0x40700ff` + `+0x70=100`；`+0x60/+0x64/+0x68/+0x6c=0` |
| `ctor(src,deep)` | `19e140` | 同上默认；`src==0` → 仅默认；否则 `InitPropertys(this, src, deep)` |
| `ctor(snapMgr,type,flags)` | `19e200` | 4075B——**"重段型"工厂（§4.1）**；末尾 `AddSegObject(this, seg, 1)`；0x4c0e/0x480f → 经 `esTextMaker::GetActiveLine` 取默认刷 `SetBrushObj`；`param&0x80` → `flags\|=0x1000 &=~0x30`（成环） |
| `ctor(pts,types,count)` | `19f470` | 静态点串构造：type 字节 `&3`：3=贝塞尔段（跳 2）、1=直线段、0=断开；`FUN_1019f690(起,止,类)` 逐段建段；末字节 `&0x80` → `CloseFigure` |
| `~esShapePath()` | `19f830` | `RemoveAllPts` + free 笔刷 `+0x68`（`vtbl(1)`）+ free 液体 `+0x6c`（`vtbl(1)`）+ `~esShapeCap` |
| `ToFixColor(scheme)` | `19f8f0` | Line 版 + 笔刷 `vtbl+0x68(scheme, undo)`（笔刷随配色方案换色） |
| `EnumSegments()` | `19f930` | 逐表逐段（`list+0x34` 起 `seg+0x3c` 链）调用 `FUN_1013f6c0(seg, &cnt)`（std::function 逐段访客）；任一段返回非 0 → 1；走完 → 0 |
| `CreateFromPathData(pts,types,count,?)` | `19fa10` | static：由点数组+类型字节数组**重建** esShapePath（局部 esSegGon/esSegBezier；自由笔迹/粘贴路径通道） |
| `RecalcLayout()` | `1a0150` | `+0x40=首表首段`；边界=**各表 solid/bounding 逐表 Union**（路径版不外扩 400）→ `SetSolidRect/SetBoundingRect`；末 `UpdateFillBounds` |
| `UpdateFillBounds()` | `1a0280` | 有笔刷且刷带变换（`+0x15&0x10`）→ 组 `esLineList`（`vtbl+0x7c`）→ 刷矩阵 `GetRect` → `esBrushEx::SetDestRect(刷, rect)`（填充目标框随几何更新） |
| `InitPropertys(src,deep)` | `1a0350` | `+0x70=100`；src 为 0x330f → 拷 `flags`/pen/`+0x5c/+0x5e`；`deep && +0x68==0`：src 有刷 → `esBrush::Create(刷型)` + 刷 `vtbl+0x70` 拷数据；src 有液体 → `esLiquid::Clone`；src 为 {0x3109,0x320b,0x3a03,0x3908} → 取 `esShapeLine::GetPenInfo` 拷贝 |
| `CopyPropFrom(sheet,src,?)` | `1a04f0` | free 自身刷/释放 role；拷 `+0x70/+0x34`/pen/`+0x5c/+0x5e`；src 有刷 → `Create`+刷 `vtbl+0x70` 拷；**刷型 `+0x15==0x16`（图片刷）→ `UpdateFillBounds` + `esPicBrush::ResetImageSize(刷, sheet, rect)`**；液体 Clone；`src+0x4c` role → `esRole::Clone` + sheet role 表注册 → `+0x4c` + `ResetLineWidth` |
| `ConnectClose()` | `1a5bf0` | `flags=(flags&~0x30)\|0x1000`；逐表 `esSegList::ConnectClose`；失败的表 → `vtbl+0x38` + free（引擎自己摘除连不上的表） |
| `LoadPtsList(dst)` | `1a5c80` | 把自身全部表**迁给 dst**（逐表 `AddSegList(dst, list)`）；自身 `+0x40/+0x60/+0x64` 清零；两端各触发刷新虚调用（`+0x44(0)`、`+0x5c(0,0)`） |
| `Insert(list,pos,mode)` | `1a5f50` | 表插入链：`mode==0` 插到 `pos` 前（pos==0 追尾）；否则插到 `pos` 后（pos==0 插头）；末 `+0x40=首表首段` |
| `CheckValid()` | `1a6120` | 逐表：**空表（`+0x34==0`）→ free 表的清理**；否则计数；`+0x40` 重指首表首段；返回"有非空表" |
| `IsReallyClosed(tol)` | `1a61f0` | 逐表：首末段都须 `esSeg::IsPPline`；首段起点 vs 末段终点 dx/dy 均 ≤ `tol`（`FUN_10027ae0` 绝对值）；任何超差 → 0；全过 → 1 |
| `GetLineList(list,mode)` | `1a62d0` | `IsClosed()` 门；单段表 → `seg vtbl+0x8c(list, closed)`；多段表 → 两趟 `esSeg::GetPath`（先计数后填充）→ `esSegObj(0x14)` → `esLineList::Add` + `EndOnePts(closed)` |
| `GrapConvert()` | `1a64c0` | `EnumSegments`（==0 → 0）；`vtbl+0x7c` 填 `esLineList` → `new esShapePath` + `InitPropertys(this, 1)` + `esLineList::GetShape`（弧线拟合）；新路径无段 → 销毁→0 |
| `OpenCanvas(undo)` | `1a6680` | `flags&0x1000` → undo **0x50d** + 清 0x1000 + 置 `0x30`（闭合→开放，进入"画图过渡"态） |
| `CloseFigure(update)` | `1a66e0` | `param!=0` 且首段 `型字&0x100`（可连）→ 逐表首末点不同则 `末段 vtbl+0x74(末点,...)` 补一段连线；末 `flags\|=0x1000`、清 `0x30` |
| `HitTestObjClick(ht,mode)` | `1a6d30` | pt=ht 点；`bVar=有刷`；有液体且批点行匹配 → `bVar\|=2`；**无刷无液**或未命中区域 → base HitTest（命中→选码 **7**）；否则选码 **8**（仅填充）/ **0xb**（填充+液体）【Q-shape-19】 |
| `SetSolidBrush(color)` | `1a6f20` | `+0x68==0` 才建：`new esSolidBrush(0x1c, color)` → `+0x68`（**已有刷则静默忽略**——换填充须走 UpdateBrush/SetBrushObj）【Q-shape-16】 |
| `AppendMatrix(m,undo)` | `1a6fb0` | lambda + `EnumSegments`（逐段 `vtbl+0x80`）；`+0x68` 为 esBrushEx → `AppendMatrix`；`+0x4c` role → `AppendMatrix` |
| `MatrixProc(mode)` | `1a70a0` | lambda + `EnumSegments`；刷带变换 → `esBrushEx::MatrixProc`；role → `MatrixProc` |
| `LoadMoldPath(moldPath,fill)` | `1a7150` | `IsClosed` 门；逐表 `esSegList::LoadPath(list,moldPath,常矩阵,NULL)` + `esMoldPath::EndGeometry(closed)`；闭合 → `CloseAllFigures`；末写填充模式 `param_2` |
| `LoadEdge(group,matrix)` | `1a71d0` | `new etShape(0x24)` → `etGroup::Append`；逐表逐段 `esSeg::LoadShape`；闭合表 → `etShape::EndGeometry`；`etShape::SetAttribut(pen@0x50, brush@0x68, bright)`；矩阵参数 → `vtbl+0x20`；固定返回 0 |
| `SetModifiedFlags(n)` | `1a7300` | 直通 `esObject::SetModifiedFlags`（ILT 与 esTopTable 折叠同址） |
| `GetSnapPoints(pts,rect)` | `1a7320` | 单表单段且段为 esSegGon → `esSegGon::GetSnapPoints(...,closed)`；闭合 → `GetCommonSidePoints`；非单表单段 → 0；单段普通：`[0]=首点 [1]=末点`+rect=两端框；段型 0x4306 且为 esSegArc 圆心在框内 → `[2]=圆心` 返回 3，否则 2 |
| `Render(render)` | `1a7530` | `GetGraphics(0)` → `Save` → `GobackToDrawPoint(局部矩阵)` → `DrawGraphics(this,render,矩阵)` → `Restore`（局部 esStyleList(8)+CComBSTR RAII） |
| `DrawGraphics(render,matrix)` | `1a75f0` | **首段类型字 `&0x800` → 段自绘 `vtbl+0xb0(样式盒, matrix)`**；否则 `DrawForNormal`【Q-shape-18】 |
| `DrawForInternal(render,matrix)` | `1a76b0` | esMoldPath 变体：`LoadMoldPath(fillmode=flags&0x4000)` → `esMoldPath::Transform(matrix)` → `FUN_101ba3c0(pen@0x50, brush@0x68)` |
| `Load(page,subj)` | `1a77b0` | `elfPage::NewSubj(this, subj, solidRect, 1, role)`；首段 `&0x800` → 段 `vtbl+0xe0(样式盒)`；否则 `LoadForNormal` |
| `LoadForNormal(page,subj)` | `1a78b0` | `AddPen` → 液体 `Load` → 刷 `vtbl+0x90` → `LoadMoldPath` + `esMoldPath::Load`（路径装入页对象） |
| `DrawForNormal(render,matrix)` | `1a7a30` | esMoldPath（fillmode=`flags&0x4000`，=1 → SetFillMode(alt)）；有刷 → 刷 `vtbl+0x78(render, matrix, moldPath, bright)`（**填充绘制**）；液体 `OnDraw`；pen：**非闭合** → `CreatePen`+`Draw` 画线；**闭合** → `DrawPath` 描边 |
| `LoadLbcLines(undo?)` | `1a7c70` | `IsClosed` → `FUN_10380b20/40` 包裹；逐表逐段 `seg vtbl+0xb4`（LBC 线装载） |
| `IsEqual(obj,sheet)` | `1a8220` | Cap 版 + `+0x70` 亮位等 + `+0x68` 刷互拍（其一有→不等）+ `+0x6c` 液体 `IsEqual` + **逐表 `vtbl+0x4c`**（表数一致且逐表相等） |
| `Serialize(arc,sheet,ver)` | `1a8370` | 旗标字节：bit2=单表单段 / bit1=单表多段 / bit8=CompMatrix / bit0x10=刷 / bit0x20=液体；**加载反序：先 `RemoveAllPts`**；刷经 `LoadBrush`、液体 `new+SetObjData`、矩阵由 `CompMatrix` 恢复 |
| `CopyFrom(src,exchanger)` | `1a8ab0` | Cap `CopyFrom` → src 同型（ID 判）→ 逐表 `new esSegList` + `AddSegList` + 表 `vtbl+0x24(src表, exchanger)`；刷 `Create(型)` + 刷 `vtbl+0x24`；液体 Clone；亮位拷贝 |
| `LoadBrush(arc,sheet)` | `1a8c40` | `ReadByte 刷型` → `esBrush::Create(型)`（失败抛内存异常）→ 刷 `vtbl+0x40(arc, sheet, 0, this)` |
| `CompMatrix(out?,m?)` | `1a8fa0` | 无表/无首段 → 0；尾表 next==0 且首段 prev==0（全链单段）→ 0；否则克隆矩阵×2 + `esParaLine::GetCompos(首段)` + `FUN_10052d70/10052f50` 串接 → `EnumSegments` 应用；`EnumSegments==0`（全拒）→ 释放克隆返回 1，否则 0 |
| `SetBrush(brush)` | `1a91f0` | free 旧刷（非空）→ `+0x68=brush`（**允许 NULL**=清填充）【Q-shape-16】 |
| `GetColors(arr,mask)` | `1a9240` | `mask&8==0` → Line 版（pen 色）；`mask&8` → 有刷且刷型 `&0x10`（实心类）→ `esSolidBrush::GetColor` 去重入数组 |
| `ResetPicSize()` | `1a92e0` | solid rect 有效且刷为图片刷(0x16) 且可逆矩阵 → 依中心/尺寸重设图片刷目标（配合 `esPicBrush::GetInvertMatrix`） |
| `IsEqualBrush(info)` | `1a94d0` | `esBrush::IsEqual(+0x68, info)` |
| `UpdateBrush(sheet,info)` | `1a94f0` | 位掩码 `info+0x148`：`&1` 且（无刷或刷型变）→ 重建路径：图片刷先按 `esLineList::GetRect` 写 `info+0x18` 尺寸 → `SetBrushObj` → **undo 0x520（新无刷）/0x521（原无刷）/0x522（数据不同）**；`&1` 且刷型同 → 刷 `vtbl+0x80` 直接更新；`&1==0` 且 `&0x1000000` 且 trs 变 → 刷 `vtbl+0x80`；渐变类(0x13) → `SetPathRect(solid)` |
| `SetBrushObj(info,sheet,matrix)` | `1a9820` | 缓存旧矩阵（brushEx）→ free 旧刷 → `esBrush::CreateFromBrushInfo(info, sheet)` → 新刷带矩阵时 `AppendMatrix`（参数矩阵或旧矩阵）；渐变 → `SetPathRect(solid)`；末 `UpdateFillBounds` |
| `Undo(code,...)` | `1a99f0` | `+0x6c` 液体先 `esLiquid::Undo`（返 0 不认才回落）→ `esShapeCap::Undo` |
| `CollectStyles(sheet)` | `1a9a40` | base + 刷 `vtbl+0x10` + 逐表 `vtbl+0x10` |
| `OnMessage(msg,mode)` | `1a9ab0` | 逐表 `vtbl+0x48`，任一处理 → `vtbl+0x44(0)`；末 `esObject::OnMessage` |
| `SetLiquidHight(h,snapMgr)` | `1a9b20` | 无液体 → 0；`h==1` → `esLiquid::SetLiquidHight(1, NULL, NULL, snapMgr)` → 1；否则带 undo+m_pUndo(this) 调液体 |
| `GetBrushInfo(info)` | `1a9b80` | 无刷 → 0；`info==0` → 刷在"pen 无色且非闭合"时 0 否则 1；有 info → 刷 `vtbl+0x74(info)` → 1 |

### 4.1 大 ctor `19e200` 的"重段型"表（段型→段类）

| 段型字 | 段类 | 备注 |
|---|---|---|
| `0xe3xx / 0xe1xx / 0xe2xx / 0xe4xx / 0xe5xx`（`&0xf000==0xe000`） | esSegGon / esSegLine / esSegCircel / esSegArc / esSegHVLine | "点对+尺寸"快速段分支 |
| 0x4488 / 0x4489 | esSegWall / esSegPipe | |
| 0x4087 | esSegStar | |
| 0x410b / 0x410c / 0x410d | esSegSpring（两 case 同体） / esSegCoil | |
| 0x4281 | esSegRect | |
| 0x4282 | esSegArc90 | |
| 0x4283 | esSegRoundRect | |
| 0x4284 | esSegCircel | |
| 0x4285 | （见 dump，无独立构造探针） | |
| 0x4286 | esSegPolygon | |
| 0x42c1 / 0x4306 / 0x4307 | esSegArc | 三 case 同体 |
| 0x4701 | esSegLine | |
| 0x4702 | esSegGon | |
| 0x4703 | esSegBezier | |
| 0x4704 | esSegHVLine | |
| 0x4705 | esSegRoundLine | |
| 0x4708 | esSegCurve | |
| 0x4712 | esSegFreeBezier | |
| 0x4713 | esSegFreePoly | |
| 0x4714 | （见 dump，经 FUN 转发） | |
| 0x480f | esSegArcFace | 构造后 `SetBrushObj` 默认刷（`esBrushInfo(0x158)`、0xff01/0x14、经 `esTextMaker::GetActiveLine` 取样式表） |
| 0x4a8a | esSegEllipseEx | |
| 0x4c0e | esSegGonFace | 同默认刷 |

末尾统一：`AddSegObject(this, seg, 1)`；`param & 0x80` → 成环（`flags\|=0x1000`、清 `0x30`）。

**怪癖**：
- **Q-shape-15** `CheckValid` 是**会主动 free 空段表**的清理函数（`list+0x34==0`）——引擎自身唯一的"删对象"通道；项目铁律（禁删）针对手工 unlink，不与之冲突。
- **Q-shape-16** `SetSolidBrush` 仅空槽创建（已有刷不会被覆盖）；`SetBrush` 则无条件替换且**允许 NULL**（`+0x68=0`=无填充）。2026-02 的 `SetBrush(NULL)` 事故是**手工拼装对象+链已坏**所致，引擎函数本体语义上是合法清理路径。
- **Q-shape-17** 两组"成对翻转"undo 码：`0x520/0x521`（刷存活对）、`0x601/0x602`（液体存活对）——`Undata` 收到一个就按对换语义处理并改写成对偶码。
- **Q-shape-18** 渲染通道由**首段类型字位 `&0x800`** 决定：特殊段 → 段自绘；否则 MoldPath 通道。混合路径里首段是"渲染模式选择器"。
- **Q-shape-19** 命中选码：**7**=线，**8**=填充（有刷），**0xb**=填充+液体，**0x12**=液体单点（HitTestAcme/HitTestLiquidAcme）。
- **Q-shape-20** 路径版 `RecalcLayout` **不外扩 400**（只有基类外扩）；边界纯为各表 solid/bounding 的 Union，`UpdateFillBounds` 再按需按刷矩阵校正填充框。

## 5. esShapeGroup（79 个）（组合对象 / 包络）

容器模型：子对象双向链首尾在组 `+0x5c/+0x60`（对象链 next/prev 在子对象 `+0x44/+0x48`，与画布链同构）；包络段/链接点独立于子对象。

| 函数 | 入口 | 规格 |
|---|---|---|
| `IsPackage()` | `12840` | 46B 打包判定（类型/flags 查询） |
| `operator=` | `12870` | Line::op= + 生拷 6 字段 + `esMatrixObj::op=`（矩阵对象整体赋值） |
| `ID / isKindOf / isOf` | `3c5920 / 3c5930 / 3c59d0` | `"esShapeGroup"`；isKindOf 失败回落 `esShapeCap::isKindOf` |
| `ctor(snap,type,flags)` | `3c5a60` | type 0x3008；`new esMatrixObj` → `+0x74`；flags 默认（0x40700ff 类） |
| `~esShapeGroup()` | `3c5b20` | 释放子链 + 矩阵对象 + Cap 基座 |
| `ToFixColor(scheme)` | `3c5c70` | 逐子 `vtbl+0xa4(scheme)`（子对象各自随配色方案，嵌套递归） |
| `SetRectObject(seg)` | `3c5cb0` | 建/换包络段 `esSegGroupRect(0x78)`（"组矩形"伪段） |
| `Append(child)` | `3c5d60` | `ResetLineWidth(child,this)`；入尾链；**道具位合并**：`(child+0x34 & 0xcff0000) >> 0x10` |
| `Insert(child,pos)` | `3c5e00` | 子链插入（语义同 Path::Insert） |
| `RecalcGroupRect()` | `3c5f30` | 由全部子对象包围盒重算组矩形（含包络点） |
| `RecalcLayout()` | `3c6270` | 组布局重算：子链 + 包络 rect + 矩阵层 |
| `RemoveAll()` | `3c63f0` | 清空子链（释放；不向上传播） |
| `ReleaseMatrixLayer()` | `3c6460` | **非 1:1 矩阵**时才释放矩阵层 |
| `RelaseAllTransfrom()` | `3c64f0` | 重置全部变换；undo `0xf0d/0xf0e/0xf0f` |
| `GetMatrix / GetMatrixEx / GetTotalMatrixEx` | `3c6890 / 3c68c0 / 3c6940` | 自身矩阵 / 带参 / 连父级链总矩阵（子→文档坐标） |
| `AppendMatrix(m,undo)` | `3c6a30` | 矩阵级联到全部子（沿 `+0x6c` 链递归） |
| `MatrixProc(mode)` | `3c6ac0` | 矩阵计算变体（不落写） |
| `OnMovePoint(...)` | `3c6b30` | 组控制点拖动派发 |
| `CreateObject(type)` | `3c6be0` | **组专属工厂（尺寸表）**：0x3908 Holder 0x68 / 0x320b Cap 0x60 / 0x3008 Group 0x84 / 0x3109 Line 0x5c / 0x330f Path 0x74 / 0x3700 Ole 0x88 / 0x3e00 Dime 0x50 / 0x3a03 Link 0x60 / 0x3a08 Control 0x50 / 0xb001 esSegGroupRect 0x78【Q-shape-23】 |
| `GetRectPoints(pts)` | `3c6fe0` | 包络矩形角点（控制点/命中用） |
| `GetLinkPts(pts)` | `3c7060` | 链接点数组：`+0x6a==0` → 16 点固定阵列；否则 `+0x64` 自定义数组【Q-shape-21】 |
| `GetSnapPoints(pts,rect)` | `3c72c0` | 29B 小转发 → 吸附族 |
| `SnapPoint(mgr,mode)` | `3c72e0` | 吸附点命中（子链递归） |
| `SnapPointProc(...)` | `3c73e0` | 子链逐对象吸附处理 |
| `GetBrushInfo(info)` | `3c7640` | 收集子对象笔刷信息 |
| `GetLiquidObj()` | `3c76d0` | 取液体对象（子链第一个带液体） |
| `RemoveAllLinkPoints()` | `3c7740` | 清链接点链 |
| `RemoveLinkPoints(...)` | `3c77c0` | 移除指定链接点 |
| `RemoveLinkPoint / AddLinkPoint / GetLinkPoint` | `3c79a0 / 3c7a50 / 3c7af0` | 链接点链增删查（链节点 0xC） |
| `CheckRectModify(...)` | `3c7cd0` | 包络矩形修改合法性检查（拖动框校验） |
| `LoadLinkLines(...)` | `3c7da0` | 59B 转发（链接线装载） |
| `LoadLines(...)` | `3c7de0` | 47B 转发（子对象连线装载） |
| `UnionLinks(...)` | `3c7e10` | 链接点并入包围盒 |
| `LoadLbcLines(...)` | `3c7e90` | LBC 线装载（同 Path 版） |
| `GetFillBorders(...)` | `3c7f90` | 取填充边界（子链递归） |
| `GetLineList(list,mode)` | `3c80c0` | 组版线表：逐子 `vtbl+0x7c` 收集进同一 esLineList |
| `GetCtrInfo(...)` | `3c8380` | 组控制点信息（包络 + 子对象） |
| `HitTestAcmeProc(ht)` | `3c8640` | 命中核心递归：模型框 0x7002 → esCtrlPoint 系列（组专属增强） |
| `HitTestAcme(ht,mode)` | `3c8950` | 命中总入口：`HitTestAcmeProc` 优先，子链回退 |
| `CollectStyles(sheet)` | `3c8b00` | base + 子链 `vtbl+0x10` |
| `OnMessage(msg,mode)` | `3c8b50` | 子链 `vtbl+0x48` 派发 |
| `EnumParagraphs(...)` | `3c8bc0` | 子链段落枚举（文本类子对象） |
| `LoadEdge(page,...)` | `3c8cf0` | 页装载：逐子 `vtbl+0x6c` |
| `DrawForInternal(...)` | `3c8e40` | 内部绘制：逐子 `vtbl+0x3c` |
| `Draw(render,matrix,...)` | `3c8f30` | 绘制入口：组矩阵 + 逐子 `vtbl+0x2c` |
| `Render(render)` | `3c8fd0` | Save/变换/逐子渲染；**flags&0x1000000（矩阵层未释放）子对象跳过自身渲染通道**（组统一代理）【Q-shape-22】 |
| `Load(page,subj)` | `3c91b0` | `elfPage::NewSubj` + 逐子 `vtbl+0x90` |
| `GetShapeCount()` | `3c93e0` | 子链计数（含嵌套展开） |
| `IsBatchble()` | `3c9470` | 可合批查询（渲染优化） |
| `HitTestForRole(ht,...)` | `3c94c0` | 角色命中：逐子 `vtbl+0x84`（组层级代理） |
| `HitTestObjClick(ht,mode)` | `3c9610` | `esSegRect::GetRect` 框 + repeater 时 `DeflateRect` 收缩判定 + 子链递归 |
| `LoadProp(mgr,param)` | `3c98e0` | 逐子 `vtbl+0x18` 透传 + **`param&0x800` 组 0x800：0x801..0x809**（组自身道具） |
| `SaveProp(mgr,param)` | `3c9b60` | 镜像：子透传 + 0x801..0x809 变更（undo `0xf0b/0xf0c/0xf11/0xf12`，对应 flags 位 26/25/24/27） |
| `Regroup(...)` | `3c9f80` | 重组（清矩阵层后重算） |
| `GetColors(list,mask)` | `3c9fd0` | 逐子收集颜色 |
| `IsCtrolOnly()` | `3ca020` | 是否仅控制点对象（无可渲染体） |
| `GetGroupHandel(idx)` | `3ca090` | 取组把手（控制点/缩放柄） |
| `GetStartPoint(...)` | `3ca180` | 组起始描点（包络起点） |
| `GetAlignPoint(...)` | `3ca450` | 对齐点集（吸附对齐） |
| `GetCreateCtrlObj(...)` | `3ca670` | 构造控制点对象集 |
| `LoadUserStymbol(...)` | `3ca770` | 用户自定义符号装载（样式表符号定义） |
| `IsEqual(...)` | `3ca9c0` | Cap 版 + 子链逐对比较 |
| `Serialize(arc,sheet,ver)` | `3caac0` | 829B；**版本迁移 `<0x1070511 / <0x1070615`**；子链递归 + 矩阵层 + 链接点 |
| `CopyFrom(...)` | `3cae10` | 深拷贝：逐子 `CreateObject`+`CopyFrom` |
| `InitGroupInfo(...)` | `3cafa0` | 初始化组信息（首次入组） |
| `CreateUserLinkPoints(...)` | `3cb070` | 建用户链接点：`+0x64` 数组 / `+0x6a` 计数 |
| `FindGroupMoveOffset(...)` | `3cb1b0` | 组拖动吸附偏移计算 |
| `FindObj(id)` | `3cb280` | 子链按 ID 查对象 |
| `SetGroupInfo(...)` | `3cb2c0` | 写组信息 |
| `GetUnGroupInfo(...)` | `3cb3b0` | 解组信息（`0x100` 归档格式） |
| `RemoveControls(...)` | `3cb580` | 移除控制点子对象；undo `0xf10`、`0xf2f1` |
| `UnGroup(...)` | `3cb730` | 解组：undo `0xf006`（子对象移交父级） |
| `Undata(&code,...)` | `3cb910` | `0xf0e→0xf0d`（矩阵还原）；`0xf0d→0xf0e`（再应用 + `RecalcGroupRect`）；`0xf0f` repeater `+0x18/0x1a` 交换；`0xf10` 控制点恢复；`0x2` → `esMatrixObj::Restore`；`0x804` → `+0x68` 值交换；否则基类 |

**怪癖**：
- **Q-shape-21** Group `+0x64` 双语义：有链接点时是 `+0x64` 数组指针，无链接点时邻域被当计数用——访问前必须 `+0x6a` 判存。
- **Q-shape-22** 矩阵层独立 flag 位 27（`0x8000000`）：`LoadProp 0xf12` 仅 0x3008 且变更才 `ReleaseMatrixLayer`；`Render` 时该位下子对象跳过自身渲染通道（组统一代理）。
- **Q-shape-23** `CreateObject` 的尺寸表是本族"按类型字造框"的权威表（见上表行），离线工具造对象前用它核对尺寸。

## 6. 撤销码与序列化汇总（本批）

### 6.1 撤销码（shape 族）

| 码 | 用途 |
|---|---|
| `0x2` | Group：矩阵层还原（`esMatrixObj::Restore`） |
| `0x502` | 亮位（记旧 1 字节） |
| `0x503..0x50b` | Line/Cap 道具（端饰/轴等，见各自 SaveProp） |
| `0x50d` | **flags 统一通道**（`FUN_10026360(this, 0x50d, this+0x34)`） |
| `0x511/0x512` | Cap 道具 |
| `0x520/0x521/0x522/0x523` | 笔刷存活对/数据（Path/Cap 刷通道，见 Q-shape-17） |
| `0x541..0x57f` | 笔刷子撤销（`Path::Undata` 转刷 `vtbl+0x2c`） |
| `0x601/0x602` | 液体存活对（Path） |
| `0x804` | Group：`+0x68` 值交换 |
| `0xf006` | Group：解组 |
| `0xf0b/0xf0c/0xf11/0xf12` | Group 道具（flags 位 26/25/24/27） |
| `0xf0d/0xf0e/0xf0f` | Group 变换分量（矩阵/偏移/旋转） |
| `0xf10/0xf2f1` | Group 控制点移除 |

### 6.2 序列化旗标（Path::Serialize `1a8370`）

bit2=单表单段 / bit1=单表多段 / bit8=CompMatrix / bit0x10=刷 / bit0x20=液体；**加载反序先 `RemoveAllPts`**；刷 `LoadBrush`、液体 `new+SetObjData`、矩阵 `CompMatrix`。

### 6.3 组版本迁移（Group::Serialize `3caac0`）

`ver < 0x1070511`、`ver < 0x1070615` 两处旧档迁移分支（旧存档兼容）。

### 6.4 链纪律（装载/迁移）

组子对象用与画布相同的 `+0x44/+0x48` 双链，首尾挂在组 `+0x5c/+0x60`；`LoadPtsList` 式迁移必须整链搬 + 双端刷新调用，否则链断（与项目"链写坏=画布点不动"教训同源）。

## 7. 残余与待深挖

- Group 表内简记项（规格较薄，如需行级行为回 dump 对应段）：`IsPackage`、`Insert`、`RecalcGroupRect`、`OnMovePoint`、`GetRectPoints`、`GetSnapPoints`(29B)、`SnapPointProc`、`GetBrushInfo`、`GetLiquidObj`、`CheckRectModify`、`LoadLinkLines/LoadLines/UnionLinks`、`GetFillBorders`、`GetLineList`、`GetCtrInfo`、`HitTestAcmeProc`、`CollectStyles`、`OnMessage`、`EnumParagraphs`、`LoadEdge`、`DrawForInternal`、`Draw`、`GetShapeCount`、`IsBatchble`、`HitTestForRole`、`Regroup`、`GetColors`、`IsCtrolOnly`、`GetGroupHandel`、`GetStartPoint`、`GetAlignPoint`、`GetCreateCtrlObj`、`LoadUserStymbol`、`InitGroupInfo`、`FindGroupMoveOffset`、`FindObj`、`SetGroupInfo`、`GetUnGroupInfo`。
- Path 的 `CreateFromPathData`、`NormalRing`、`GetCtrInfo`/`HitTestAcme` 的顶点型/重定向细节已给要点，未逐字节转录。
- 大 ctor 两个未命名段型：`0x4285`、`0x4714`（探针未捕获独立构造）。
- **对画图工具链的启示**：
  1. 填充正路 = `SetSolidBrush(color)`（仅空槽；改填充=新建路径或 `UpdateBrush/SetBrushObj`）+ `recalcShape`；与既知 `GetBrush` 验证法一致。
  2. 曲线：引擎自身也走"折线化"（`GrapConvert`/`GetLineList`→esLineList）；`0x4703` 虽在段工厂表内，但项目挂载纪律（手搓折线）不变。
  3. 轴类对象（0x5006）不在 Path 工厂表内 → 印证 Q-shape-11。
