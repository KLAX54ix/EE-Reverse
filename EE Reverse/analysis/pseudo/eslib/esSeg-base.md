# eslib 绘图对象模型基座 — 反编译规格（阶段 2 · 第四批 · 绘图核心 1/6）

- 模块：eslib.dll；函数：**147 个**（esSeg 77 · esSegList 37 · esSegBase 14 · esSegGemotry 8 · esSegObj 5 · esSegItem+esSegItems 6）
- 伪代码（原样）：`analysis/pseudo/eslib/esSeg-base.decomp.txt`（matched=147 dumped=147）
- 类型头：`analysis/types/esSeg-base.h`
- 台账：147/147 → `decompiled`（status-overrides）
- 角色：**S1 绘图对象模型的基座**。画布上的"线段级"对象（直线/多边形/贝塞尔/圆/弧/矩形/尺寸标注/坐标轴/图片框…）
  全部继承 `esSeg`；`esSeg::Create(类型字)` 是引擎全局的「类型字 → 具体类」工厂（76 项对照表，见 §2）；
  `esSegList` 是"多段折线组"容器。本批把三者布局/调用链/序列化格式一次定死。

## 0. 谱系与持有链（本批结构性结论）

| 结论 | 证据 |
|---|---|
| `esGraphObject → esSegBase → esSeg → <全部具体段类>` | ctor/dtor 链：`esSegBase 3e42b0` / `esSeg 1043b0` / `esSeg dtor 104460` |
| `esSegList : esGraphObject`，类型字 **0x2030**，持 `esSeg` 侵入式双向链（head/tail） | ctor `1b00d0`；AddSegObject `1b0330` |
| 持有链（amulet 上溯）：`esSeg ↳ esSegList(0x2030) ↳ esShapePath(0x330f) ↳ esCanvas(0x2020)` | Relist `1b08b0`（逐级 amulet 类型检查）；OnBreakLine `104d90`；GetOwner `104fd0` |
| `esSegGemotry : esSegNative 系`（中间父类符号被折叠，待后续核）；行为上当 esSeg 用 | BreakLine `10110f40` 直接 `esSeg::OnBreakLine((esSeg*)this,1)`；className `110e80` 返回 `esSegNative::ID` |
| `esSegObj`/`esSegItem(s)`＝无 vptr 的纯数据助手（"点数组 + 分段标志"所有权容器） | ctor `3e3760` / `12150` |
| 链节点约定：段在 esSegList 内 `+0x3C=next`、`+0x40=prev`；列表在自身兄弟链里同构 | AddSegObject `1b0330`；esSegList::Detach `1a6860` |

类型字速查（本批观测）：`0x2030`=esSegList · `0x330f`=esShapePath · `0x2020`=esCanvas。
`esScopedAmulet::operator_class_esAmulet_(x)` = 取 x 的"上一级所有者"（循环上溯）。

## 1. esSegBase（14 个）

**布局**（esGraphObject 基类占 +0x00..+0x33）：

| 偏移 | 类型 | 含义 | 证据 |
|---|---|---|---|
| +0x04 | ushort | **类型字**（具体类一个值；工厂 Create 最后统一写入） | Create `3e1070` 末尾 |
| +0x34 | tagPOINT* | "安全点"缓存（懒构建，`Build` 填；dtor free） | get_safe_points `e680`；dtor `3e42f0` |
| +0x38 | int | 点数（与 +0x34 配对） | 全族 |

| 函数 | 入口 | 规格 |
|---|---|---|
| `Build(int)` | `5a90` | **ILT 折叠 stub**（38 个符号同址：Cancel/CollectStyles/DirectlyShow/ExecuteCommand(esObject)/OnDraw/OnCreate(esSeg)… 函数体=ret） |
| `get_safe_points(Matrix*)` | `e680` | +0x34==0 → 虚调 `vtbl+0x7C Build(0)`；矩阵非空且 `FUN_10027a90()==0` → `FUN_1040e590` 返回变换副本；否则返回原始 +0x34 |
| `GetPtsObj()` | `e6e0` | 类型 0x1000/0x1002 → `GetAboveObject(0x8001)`（HDim）；0x2001/0x1003 → `(0x8002)`（VDim）；否则自身 |
| `OnMovePoint(zPoint,…)` | `e750` | 转 `vtbl+0x74` 后 `vtbl+0x44(0)`（标改动） |
| `SetPointPos(…)` | `e790` | 恒 `return 2`；**与 esSegLable::SetPointPos 折叠同址** |
| `esSegBase(esSegBase const&)` | `e7b0` | 浅拷贝 +0x34/+0x38 |
| `ctor / dtor` | `3e42b0 / 3e42f0` | ctor 清 +0x34/+0x38；dtor `free(+0x34)` |
| `ID / isKindOf / isOf` | `3e4170 / 3e4180 / 3e4220` | `"esSegBase"`；isKindOf 逐级上溯（模板样板，后文各类不再重复） |
| `GetTotalMatrixEx(Matrix*)` | `3e4330` | 沿 amulet 上溯：遇 **esCanvas → 直接返回**；遇 esShapeGroup：this 为其直接子(组+0x40==this)且组+0x34 有 0x8000000 → 取 GetMatrix；否则 GetMatrixEx 复合；到顶返回 0 |
| `GetTotalMatrix(Matrix*,int,int)` | `3e4490` | 先跳过类型字<0x4000 的容器层；自身为 esSeg 且 param_2≠0 时取 `esParaLine::GetCompos()+4`；再经 `esShapeBase::GetTotalMatrix` |
| `get_line_by_ratio(p1,p2,t)` | `3e4610` | t<1.0（常量 PTR_1057ef28）→ `p1 = p2 + t·(p2−p1)`；否则 `p2 = p1 + t·(p2−p1)` |

## 2. esSeg（77 个）

**布局**（在 esSegBase 之上；对象尺寸 0x68 起，见工厂表）：

| 偏移 | 类型 | 含义 | 证据 |
|---|---|---|---|
| +0x3C | esSeg* | 链 next（在 esSegList 内） | AddSegObject `1b0330`；RecalcLayout `1b0a50` 遍历 |
| +0x40 | esSeg* | 链 prev | 同上 |
| +0x44 | uchar | 标志（ctor 置 0） | ctor `1043b0` |
| +0x46 | ushort | （ctor 置 0） | 同上 |
| +0x48 | esMatrixObj(0x10B) | 内嵌变换矩阵（+0x4C 为 Gdiplus::Matrix 数据） | dtor `104460`；Invert `ea00` |
| +0x58 | tagPOINT* | **控制点数组**（编辑手柄；可编辑对象才有；dtor free） | GetVertex `eb30` |
| +0x5C | ushort | 控制点数 | 同上 |
| +0x60 | uchar* | **逐点分段标志：0=断开 1=直线 3=贝塞尔**（dtor free） | AddPts `1b0590`；GetSegLines `3e3990` |
| +0x64 | esSeg* | 双向别名（组对象 ⇄ 代表对象） | SetAlias `105010` |

### 2.1 工厂表 `esSeg::Create(ushort type)`（`3e1070`）★ 本批最有价值

`operator_new(size)` + 具体类 ctor，最后 `*(ushort*)(obj+4)=type`；**未知类型 → `zApiThrowMemoryException()`（抛异常，非返回空）**。

| 类型字 | 类 | 尺寸 | | 类型字 | 类 | 尺寸 |
|---|---|---|---|---|---|---|
| 0x4087 | esSegStar | 0x84 | | 0x6001 | esSegPoint | 0x68 |
| 0x410b/0x410c | esSegSpring | 0x74 | | 0x6002 | `FUN_10013dd0`（待命名） | 0x74 |
| 0x410d | esSegCoil | 0x70 | | 0x6003 | esSegCircels | 0x8c |
| 0x4281 | esSegRect | 0x70 | | 0x6004 | esSegSectionLine | 0x6c |
| 0x4282 | esSegArc90 | 0x84 | | 0x6005 | esSegSurface | 0x6c |
| 0x4283 | esSegRoundRect | 0x6c | | 0x6006 | esSegText | 0x84 |
| 0x4284 | esSegCircel | 0x8c | | 0x6007 | esSegRuler | 0x74 |
| 0x4285 | `FUN_1011dfc0`（待命名） | 0x7c | | 0x6009 | esSegArcRuler | 0x78 |
| 0x4286 | esSegPolygon | 0x7c | | 0x600a | esSegRulerTextA | 0x7c |
| 0x42c1 | esSegArc(param) | 0x98 | | 0x600b | esSegRulerTextB | 0x7c |
| 0x4306/0x4307 | esSegArc(param) | 0x98 | | 0x600d | esSegLable | 0xd8 |
| 0x4488 | esSegWall | 0x6c | | 0x600e | esSegMatchMan | 0x130 |
| 0x4489 | esSegPipe | 0x70 | | 0x6010 | esSegBond | 0x70 |
| 0x4701 | esSegLine | 0x68 | | 0x7001 | esSegLinkPoint | 0x8c |
| 0x4702 | esSegGon | 0x68 | | 0x7002 | esCtrlGroupMove | 0x8c |
| 0x4703 | esSegBezier | 0x68 | | 0x7101 | esCtrlPoint | 0x8c |
| 0x4704 | esSegHVLine | 0x68 | | 0x7102-04 | esCtrlLineMove | 0x8c |
| 0x4705 | esSegRoundLine | 0x6c | | 0x7105 | esCtrlXYAny | 0x8c |
| 0x4708 | esSegCurve | 0x68 | | 0x7106 | esCtrlXYMove | 0x9c |
| 0x480f | esSegArcFace | 0x84 | | 0x7107 | esCtrlScale | 0x8c |
| 0x4a8a | esSegEllipseEx | 0x7c | | 0x7108 | esCtrlRotate | 0xa4 |
| 0x4c0e | esSegGonFace | 0x74 | | 0x7109 | esCtrlScRot | 0x98 |
| 0x5001 | esSegSimpleAxis | 0x74 | | 0x710a | esCtrlDot | 0x90 |
| 0x5002/0x5003 | esSegSimpleSingleAxis | 0x74 | | 0x710b | esCtrlGon | 0x90 |
| 0x5004 | esSegArrowLines | 0x6c | | 0x710c | esCtrlBezier | 0x90 |
| 0x5005 | esSegGlow | 0x8c | | 0x710d | esCtrlAnyRot | 0x94 |
| **0x5006** | **esSegAxis** | **0x16c** | | 0x8001 | esHDim | 0x84 |
| 0x8002 | esVDim | 0x8c | | 0x8003 | esSegAnyBZ | 0x84 |
| 0x8004 | esSegNumberBZ | 0x88 | | 0x8006 | esSegDiameter | 0x98 |
| 0x8007 | esSegRadius | 0x98 | | 0x8008 | esSegDjbz | 0x84 |
| 0x8009 | esSegYxbz | 0x80 | | 0x800a | esSegOI | 0x8c |
| 0x800b | esSegParen | 0x88 | | 0x800c | esSegRough | 0x8c |
| 0x800d | esSegOT | 0x8c | | 0x800e | esSegCuttingLine | 0x90 |
| 0x800f | esSegTolerance | 0x9c | | 0x8103 | esSegHVBZ | 0x84 |
| 0x9001 | esSegLinkLine | 0x78 | | 0x9002 | esSegElbowLinkiLine | 0x80 |
| 0x9003 | esSegBezierLink | 0x80 | | 0x9404 | esSegLinkHVLine | 0x78 |
| 0xa001 | esSegTable | 0x7c | | 0xa002 | esSegFormulaBox | 0x7c |
| 0xa004 | esSegTextBox | 0x78 | | 0xa008/0xafff | esSegPlaceHolder | 0x7c |
| 0xa010 | esSegImage | 0x98 | | 0xa030 | esSegVideo | 0xa8 |
| 0xa040 | esSegAudio | 0x9c | | 0xa100 | esSegPhoto | 0x98 |
| 0xb001 | esSegGroupRect | 0x78 | | 0xc081 | esSegFrame | 0x68 |
| 0xd083 | esSegRectEx | 0x70 | | | | |

（两处 `FUN_*` 待命名 → RE-UNKNOWNS 候选：0x6002 尺寸 0x74、0x4285 尺寸 0x7c。）

### 2.2 方法表

**构建 / 样板：**

| 函数 | 入口 | 规格 |
|---|---|---|
| `Create(ushort)` | `3e1070` | 见 §2.1 |
| `ctor / dtor` | `1043b0 / 104460` | ctor：+0x46=0、矩阵 ctor、+0x58/0x5C/0x60/0x64/0x40/0x3C=0；dtor：`if(+0x34==+0x58) +0x34=0`、free+0x58、free+0x60、SetAlias(0)、矩阵 dtor |
| `ID/isKindOf/isOf` | `104270/104280/104320` | `"esSeg"` |
| `operator=` | `ec40` | 基类 + +0x3C/+0x40/+0x44/+0x46/矩阵/ +0x58/+0x5C/+0x60/+0x64 |
| `AddPoint(zPoint,int,int)` | `12460` | 恒 `return 0`（与 esOleImple 折叠；具体类各自 override） |
| `BreakLine(int*,int)` | `6690` | **ILT 折叠 stub**（31 符号同址：CollectStyles/CopyFrom(esObject)/LoadProp/SaveProp/Serialize(elfPage)… 函数体=ret） |

**点集 / 几何：**

| 函数 | 入口 | 规格 |
|---|---|---|
| `GetVertex(ushort,tagPOINT&)` | `eb30` | +0x58 控制点[idx]；空或越界→0 |
| `step(int,int,float)` / `step(float…)` / `step(zPoint,zPoint,float)` | `eb80/eba0/ebd0` | 线性插值 `(b−a)·t+a` |
| `GetPoints(int&)` | `107af0` | 返回 {+0x34, count}（不拷贝；必要时先 Build） |
| `GetPts(tagPOINT*&,uchar*&)` | `106200` | **分配拷贝** pts(×8)+flags，返回 count（调用方 free） |
| `get_path(tag_EPPATH*,Matrix*)` | `e8e0` | 打包输出 `{pts(+0),flags(+4),count(+8),owned(+0xC)}`：无安全点先 Build；矩阵有效且 `FUN_10027a90()==0` → 变换副本且 owned=0，否则原始 +0x34 且 owned=1 |
| `GetPath(pts,flags,start)` | `1057b0` | 从 start 起拷贝到调用者缓冲；返回拷贝个数（负→0） |
| `SetPtInfo(pts,flags,count,fill,doTransform)` | `1065d0` | 设 +0x34/+0x38/+0x60；**pts==+0x58 时先深拷贝**；flags==NULL 时分配并 `[0]=0` 其余=fill；doTransform→FUN_10027a30 |
| `AddLines(pts,n)` | `107ff0` | 追加密控制点到 +0x58（重分配+拷贝+free 旧） |
| `Build(int)` | `107dc0` | `SetPtInfo(+0x58, NULL, ctrlCount, 1, 1)`（控制点摊成显示点）；与 esSegLinkLine 折叠 |
| `BuildEx(esSeg*,float)` | `107ce0` | 与另一同点数 seg 逐点 `step()` 插值（morph 动画） |
| `ResetPointsForCreate()` | `107df0` | `vtbl+0x7C(1)` |
| `MirrPts()` | `107c10` | 控制点数组反序（新分配+free 旧） |
| `MovePoint(zPoint,int,…)` | `1cf80` | `Invert(world)` → 写 +0x58[idx]（与 esSegSurface 折叠） |
| `AnyMove(PointF,PointF)` / `AnyMove(zPoint,int,int)` | `109060/109270` | 拖动第 idx 控制点（保持长度/夹角规则） |
| `GetbendingPoints(3×tagPOINT,…,n)` / `(tagPOINT*,double,int)` | `106980/106e00` | 生成"弯折"控制点序列（折线/弹簧视觉；含旋转回正） |
| `GetCtlPts(esVertexList*,int)` | `106820` | 构造 `esVertexInfo`（拷贝控制点+变换）；`type&0x100` 且非闭合：无 prev→SetFlags(1)、无 next→SetFlags(2)，`FUN_101ae4e0` 入列 |
| `GetArrowPos(int,int,ushort)` | `107b30` | 首/末段两端点 → **全局静态 scratch（DAT_106ccfdc..e8），非线程安全**（Q6） |
| `GetAcmePoint(int)` | `1080c0` | 无手柄→solid 矩形中心；否则 `FUN_101ae7f0` |
| `GetPointInfo(int)` | `1081d0` | 逐类型"可拖点角色"表：**1=中间 3=首 5=尾**；开放形状只放行首尾、闭合放行全部（&1）；特殊：0x5004/0x6009/0x4c0e/0x4488/0x4489/0x480f/0x4306/0x4307/0x4703(每 3 点)/0x4281(<8)/0x4087(<n−1)/0x410b-0d/0x4282,0x4285(<4)/0x4283(<0xc)/0x4284(==0)/0x4286(<n−1)；末尾按链现状降级（&0xfffd 无 prev / &0xfffb 无 next） |

**变换：**

| 函数 | 入口 | 规格 |
|---|---|---|
| `Invert(tagPOINT)/(PointF)`、`InvertF` | `ea00/ea50/eac0` | 用 +0x4C 矩阵逆变换（`this==0xffffffb8` 是反编译伪影=矩阵指针空检查） |
| `TransformPoints(pts,n)` | `e9e0` | `FUN_10027a30(pts,n)`（矩阵经寄存器传，反编译器缺参） |
| `AppendMatrix / SetMatrixElements / MatrixProc` | `108b00/108b40/108bf0` | 转发 `esMatrixObj`；SetMatrix 后 `vtbl+0x44(0)` |

**查询 / 命中：**

| 函数 | 入口 | 规格 |
|---|---|---|
| `IsEqual(obj,sheet)` | `107510` | 基类 + ctrlCount 相等 + 矩阵等价(`FUN_1005e200`) + `memcmp` 控制点 |
| `IsClosed(0/1)` / `IsClosedEx()` / `IsCyclical()` | `108850/108910/1089b0` | 由 owner esShapeBase 判定；`IsClosedEx`=`shape+0x34 & 0x9000`；`IsClosed(1)` 还要求自身无邻居 |
| `IsSelected(render)` | `1087c0` | 编辑模式 + `shape+0x3C != 0` |
| `GetOwner()` | `104fd0` | amulet 上溯：跳过 0x2030 → esShapeBase |
| `SearchUp(id)` | `105050` | `id==0xD` 特例返回自身；否则基类 |
| `IsPPline(ulong*)` | `105080` | `type&0x100` → 返回 owner esSegList（可输出 owner+0x34）；否则空 |
| `IsFeasible(q)` | `104d30` | `q==0x400` → `(type==0x5004) || (type&0x400)`；否则 0 |
| `GetNextObjID()` | `105580` | 返回 +0x3C 对象 ID |
| `HitTest(esHitTest*,int)` / `HitTestAcme` | `1067c0/1066f0` | 点数≠1 时 `esHitTest::HitTest(pts,flags,n)` 必须命中；`SetSelInfo(7,this,0)` |
| `SnapPoint(esSnapManager*)` | `1055b0` | 非变换中 + bounding 命中 → `vtbl+0xD0(param)` |
| `GetJiaoCount(tag_POINTD)` | `107830` | 沿 +0x3C 段链逐段 `vtbl+0x94`(GetPts) 取点+flags：flags==1 → `esGraph::GetLeftJiaoCount_LINE`，否则 `..._BEZIER`（跳 2 点）；跨段补"上段末点→本段首点"连线段；返回左射线交点累计数（点选/圈选奇偶判定）；**free 后毒化写 0x8123（见 Q7）** |

**链接 / 生命周期：**

| 函数 | 入口 | 规格 |
|---|---|---|
| `SetAlias(seg)` | `105010` | 双向 alias：双方 +0x64 互指（先解旧链） |
| `Append(seg)` | `1050f0` | 同类型且招接连续（`GetCompos`+`FUN_1005e200`）：0x4702/0x4703 合并控制点（**相邻去重 + 共线中间点剔除**）；0x4306/0x4307 → `esSegArc::Connect` |
| `Detach()` | `107e80` | 从 esSegList 摘除（邻居重接/头尾修正）+ 通知上层 amulet + `ResetLineWidth` |
| `DeleteSlef(int,int)` | `107f50` | 头节点且唯一 → 自毁（vtbl 序 + 释放）；否则委托 owner `vtbl+0x5C` |
| `OnPreMovePoint(worker,int)` | `105650` | owner 为 list → 整链 `esGraphWorker::Add(x,2,3)`；否则自身 |
| `RemoveControlLink()` | `108fd0` | 上溯找 canvas → `RemoveControlPoints(this)` |
| `OnMessage` | `109040` | 直通基类 |
| `OnBreakLine(int)` | `104d90` | seg（或所在中段）→ **esShapePath**：RemoveControlAndLinkPoints → getaway 建 path、`CopyPropFrom`、`BreakCyclic/OpenCanvas`、`AddSegList`、canvas `vtbl+0x3C` 插入、undo `esUnMove` |

**绘制 / 加载（S1、动态桥相关）：**

| 函数 | 入口 | 规格 |
|---|---|---|
| `Draw(render,DRAWPARAM*,Matrix*)` | `1063c0` | DRAWPARAM 有笔或刷时：`egPath(安全点,flags,count)`；`IsClosed(0)`→`CloseAllFigures`；刷→`(*(DRAWPARAM+8))vtbl+0x78`；笔→`esPenInfo::CreatePen(DRAWPARAM+4)` + `esGraphics::DrawPath` |
| `Load(elfPage*,elfSubject*,DRAWPARAM*)` | `1062b0` | `elfSubject::AddPen(sheet,+4,1)`；建 `elfPathGeometry(1)` + `AddPathEx(pts,flags,count,0)` → `elfSubject::Add` |
| `LoadPath(esMoldPath*)` | `e970` | `esMoldPath::AddPoints(pts,flags,count, closed=+0x40!=0)` |
| `LoadShape(etShape*)` | `107e10` | `etShape::AddPoints` 同上 |
| `LoadObjPoints(esLineList*,int)` | `105840` | 按 flags==0 切段，每段深拷贝为 `esSegObj` → `esLineList::Add`+`EndOnePts` |
| `GetLineLength()` | `1059e0` | 折线总长（逐段 sqrt，int 截断） |
| `AddPartPath(mold,int len,int dir)` | `105ab0` | 按长度截取部分路径输出（esGeometry/AddBeziers；dir 反向） |
| `GetLbcLines(xzLbcList*,Matrix*,int)` | `1056c0` | 遍历 pts+flags 输出（0=断开 1=线 3=bezier） |
| `GetRgnPts(…)` | `107800` | `vtbl+0x90`（默认同 GetPts） |

**序列化 / 撤销 / 布局：**

| 函数 | 入口 | 规格 |
|---|---|---|
| `Serialize` | `1075d0` | **格式见 §7.1** |
| `CopyFrom(obj,exchanger)` | `107710` | (BreakLine stub) + 矩阵 CopyFrom + ctrl 点深拷贝（`FUN_105290e5`） |
| `unMPSave(zArchive&)` | `108c10` | 逆操作：写模式标 1 写控制点；读模式无 undo 标 4、有 undo 标 6；差分区间 → `esUndo::Rec_Data(0xf2dc)`（Q8） |
| `Undata(id,data,&size)` | `108eb0` | id==2 → 矩阵恢复；否则按 [first,last] 区间与传入数据交换控制点 |
| `RecalcLayout()` | `108a30` | `GetPathBounds` → `vtbl+0xE4`（定制）→ `SetSolidRect`；`vtbl+0xE8` → `InflateRect(400,400)` → `SetBoundingRect` |
| `SetModifiedFlags(int)` | `106520` | 基类 + 释放显示点缓存（+0x34≠+0x58 时 free）与 flags；**含 `+0x34=0x8123` 死写（疑释放后毒化哨兵，见 Q7）** |

**静态工具：**

| 函数 | 入口 | 规格 |
|---|---|---|
| `FromBezer(PointF*,int)` | `104520` | 3 点（或按点数取采样）→ 拟合圆/弧：外接圆心；退化→分解处理；**有角度→esSegArc(0x98)，无角度→esSegCircel(0x8c)，行列式≈0→NULL**；<5 点用内置常数控制点、5–12 取第 3 点、≥13 取 3/6/9 点（次要细节见伪代码） |

## 3. esSegList（37 个）

**布局**：`+0x34` head esSeg* · `+0x38` tail · `+0x3C/+0x40` 兄弟链 next/prev（列表挂进 esShapePath 时用）；尺寸 0x44。

| 函数 | 入口 | 规格 |
|---|---|---|
| `ctor()` / `ctor(pts,flags,n,m)` | `1b00d0 / 1b0130` | 空清；带点版：`esBezier3::FitToBezierOrLine` 先规整，再逐点 AddPts（flags==3 每 3 点一贝塞尔） |
| `dtor` | `1b0260` | RemoveAllItems + 基类 |
| `CreateObject(type) const` | `19dec0` | → `esSeg::Create`（与 esShapeBase 折叠） |
| `GetNextObjID()` | `1a6830` | +0x40 对象 ID |
| `AddSegObject(seg,pos)` | `1b0330` | pos=0 头插 / else 尾插；`ResetLineWidth` |
| `Append(seg)` | `1b03d0` | 若 tail 合并成功（esSeg::Append）则不新建；否则尾插。**esSegGon 会先 `Normatllize`**（合并共线点） |
| `AddPts(pts,n)` | `1b0590` | n==2：tail 是 0x4702 → `AppendPoint`，否则新建 `esSegGon`(2 点)；n==4：tail 是 0x4703 → 追加 3 点，否则新建 `esSegBezier`+AddLines(4)。尾调 `vtbl+0x44` |
| `Insert(obj,sibling,mode)` | `1b0b60` | 相对 sibling 头/尾/前后插入（含 list 自身作为 sibling 的两种头部情形） |
| `RemoveAllItems()` | `1b0770` | 逐个自毁（vtbl[0]） |
| `SetFirstItem(seg,undo)` | `1b07e0` | 把 seg 及以后节点循环旋转到最前；undo 记录类型 **0x524** |
| `DropItemsTo(other)` | `1b1630` | 全链 `esObject::Recycle` 后移入 other（尾接） |
| `Replace(seg,pts,n)` | `1b1230` | 新建 esSegBezier(pts,n) 顶替 seg 在链中的位置（旧的重分配前删除） |
| `Relist(segA,segB,flag)` | `1b08b0` | 把本 list（须挂 esShapePath 0x330f，其父 0x2020）**转为新 esShapePath**：CopyPropFrom、canvas vtbl+0x3C 插入、逐段移入（undo esUnMove） |
| `ConnectClose()` | `1b0c90` | 单段：0x4703→`CheckFirstLastLink`；0x4702/0x4704→Gon 版；双段同类型且连续：0x4702/03/04→`esSeg::Append`、0x4306/07→`esSegArc::Connect`，成功后删被并段 |
| `LinkEqualLines(int)` | `1b0e50` | 0x4701→**0x4702** 升级；相邻同类型 0x4702/03/04 → `esSegGon::LinkTo` 合并 |
| `CloseFigure()` | `1b16a0` | 首段 `type&0x100` 时：末段终点≠首段起点 → `AddPts(2)` 补闭合边 |
| `RecalcLayout()` | `1b0a50` | 全链 solid/bounding 矩形并集 → SetSolidRect/SetBoundingRect |
| `IsInvalidate()` | `1b02b0` | 空链 或 solid 宽<10 且高<10 → 1 |
| `SnapPoint(snapMgr)` | `1a69b0` | 链上任一段命中 → 1 |
| `LoadVertext(vlist)` | `1a6a00` | 每段 `vtbl+0xD4`(= GetCtlPts) 全量 |
| `LoadPath(mold,ratio,matrix)` | `1a6a40` | 按总长比例截取（ratio<0 反向）；否则全量 LoadPath；矩形矩阵变换 |
| `MirrPts()` | `1b11c0` | 每段 `vtbl+0xA4`(MirrPts) + 反转 next/prev + 换 head/tail |
| `ExecuteCommand(cmd)` | `1b1120` | cmd==1 → `MirrPts()` |
| `OnMessage(msg,w)` | `1b1150` | 逐段转发 `vtbl+0x48`，命中则 `vtbl+0x44(0)` |
| `Detach()` | `1a6860` | 从 owner（canvas 链）摘除自己、修正 owner 头尾、`ResetLineWidth` |
| `DeleteSlef(int,int)` | `1a6910` | 头节点且唯一 → 自毁；否则委托 owner `vtbl+0x5C` |
| `Undata(id,data,&sz)` | `1a6c20` | id==0x524 → `SetFirstItem(esUndo::GetAt(...),0)` 且更新 undone 数据 |
| `Clone()` | `1b04f0` | 新 0x44 + `CloneObject(this,new,sheet,0x2030)` |
| `IsEqual(obj,sheet)` | `1b1350` | 基类 + 逐段 `vtbl+0x4C` |
| `CopyFrom(obj,exchanger)` | `1b1580` | (esSeg::BreakLine stub) + 逐段 `CreateObject`+AddSegObject+`vtbl+0x24` |
| `Serialize` | `1b13f0` | **格式见 §7.2** |
| `ID/isKindOf/isOf/operator=/copy ctor` | `1aff90/1affa0/1b0040/10510/104b0` | `"esSegList"` |

## 4. esSegObj（5 个）

**布局**（0x14B，无 vptr；深拷贝语义的点+标志容器）：
`+0x00 int 保留(0)` · `+0x04 tagPOINT* pts（dtor free）` · `+0x08 uchar* flags（dtor free）` · `+0x0C int count` · `+0x10 ushort flags2`。

| 函数 | 入口 | 规格 |
|---|---|---|
| `ctor(pts,flags,n)` | `3e3760` | flags==NULL 且 n>0 → 自造：`[0]=0` 其余=1（=单条折线）；+0x10=0 |
| `dtor` | `3c4a50` | free(+0x04)/free(+0x08)（不置空） |
| `Colon(dx,dy)` | `3e3800` | 深拷贝（pts 平移 dx/dy、flags 拷贝），结果 `flags2 |= 3`；无点/空→NULL |
| `GetSegLines(esShapePath*)` | `3e3990` | 走 flags：**0=收束当前段**（有段则 `shapePath::AddSegList`）**1=AddPts(2) 3=AddPts(4) 跳 3**；段只有 >1 点才成组 |
| `TransformPoints(Matrix*)` | `3e3b70` | `FUN_10027a30(pts,count)`（同上缺参伪影） |

## 5. esSegItem / esSegItems（6 个）

- `esSegItem`（0xCB）：`+0x00 pts（dtor free）` · `+0x04 count` · `+0x08 next`；ctor `12150`、dtor `12180`。
- `esSegItems`（8B）：`+0x00 first` · `+0x04 last`。`AddItem(pts,n)` `4cf4e0`（尾接新节点）；`RemoveAllItems()` `4cf590`（逐个 `FUN_104cf600(1)` 释放）；ctor `121c0` / dtor `121f0`。
- 用途：`esSeg` 的临时点表容器（如 `CloseFigure` 局部、GetCtlPts 等）。

## 6. esSegGemotry（8 个）

| 函数 | 入口 | 规格 |
|---|---|---|
| `BreakLine(int*,int)` | `110f40` | 先 `esSeg::OnBreakLine((esSeg*)this,1)` 摘出；要求得到 esShapePath；新建 esSegList 并把自身点按分段规则移入（`vtbl+0xEC`）；再插回原位、逐过渡 list 转 esShapePath、`SetUnAddInfo` |
| `ctor` | `110f20` | `esSegNative::esSegNative` + vptr |
| `dtor / operator=` | `ed00 / ed20` | `esSegNative::~` / `esSegFrame::operator=`（**符号折叠证据**，见 §9） |
| `ID / isKindOf / isOf / className` | `110dd0/110de0/110e90/110e80` | `"esSegGemotry"`；isKindOf 上溯 esSegNative；className 返回 `esSegNative::ID` |

## 7. 序列化格式（S4）

### 7.1 esSeg::Serialize（`1075d0`）

```
写（storing，param_3 二进制位 0 = 跳过矩阵）:
  [ushort 类型字]
  if (param_3 & 1)==0 : [esMatrixObj::Serialize(+0x48)]
  [ushort 控制点数 +0x5C]
  控制点数!=0 : [控制点原始字节 点数*8]           // 经 zStream vtbl+8 直写
  esObject::Serialize(...)
读（loading）: 同序；读到点数后 free 旧 +0x58 → 分配（FUN_105290e5）→ vtbl+0xC 直读字节
```
注：**只序列化 +0x58 控制点**（+0x34 显示点由 Build 重建）。

### 7.2 esSegList::Serialize（`1b13f0`）

```
写: if (styleSheet==NULL) [ushort 0x2030]        // 无样式表时才写类型字
    [dword 段数] + 每段 seg->Serialize(vtbl+0x40)
    esObject::Serialize(...)
读: RemoveAllItems; [dword 段数]; 每段: [ushort type] → CreateObject → AddSegObject(尾) → seg->Serialize
    styleSheet 版本 < 0x1070612 时追加 esRole::Read(0x106070b)   // 旧档兼容
    完成后 owner amulet +0x40 = 新 head
```

### 7.3 撤销/逆操作（本批见到的注册码）

| 码 | 来源 | 含义 |
|---|---|---|
| `0x524` | esSegList::SetFirstItem `1b07e0` / Undata `1a6c20` | 首段切换（记录段对象 ID） |
| `0xf2dc` | esSeg::unMPSave `108c10` / Undata `108eb0` | 控制点差分区间 [first,last]+数据 |

## 8. 怪癖（Q1–Q10，RE-UNKNOWNS/差分候选）

- **Q1** `esSeg::Create` 未知类型 **抛异常**（`zApiThrowMemoryException`），不是返回 NULL——批量建对象要catch。
- **Q2** `esSegBase::Build`、`esSeg::BreakLine`、`esSeg::AddPoint`、`esSegList::CreateObject` 等其实是 **ILT/COMDAT 折叠 stub**（详表见 §9）；调用它们之前先确认虚表槽（虚调永远打到具体类实现，直接按名调用会进 stub）。
- **Q3** `GetArrowPos` 返回的是 **全局静态缓冲**（DAT_106ccfdc）；两次取值之间不可交叉。
- **Q4** `esSeg::Append` 的"去重+共线剔除"会**就地改控制点数组**（合并方数据被消费）。
- **Q5** `esSeg::FromBezer` 行列式≈0 返回 NULL、角度≈0 落 esSegCircel、否则 esSegArc——**同一输入可能得到两种类**；3 点拟合结果依赖常量表 DAT_1057f140/f170/f1b8。
- **Q6** `esSeg::Serialize` 读侧**不校验点数上限**（ushort），直接分配直读——坏档可构造 0xFFFF 点。
- **Q7** `esSeg::SetModifiedFlags` 含 `+0x34=0x8123` 死写（在 free 之后、清零之前）；**`GetJiaoCount` 的局部指针在 free 后同样被写 0x8123**（两处同型）→ 更可能是源码"释放后毒化哨兵"惯例而非反编译伪影，**待差分复核**。
- **Q8** `unMPSave` 读模式按 `esObject::m_pUndo==0` 分支写标 4/6——**同一文件两种读法**（有/无 undo）。
- **Q9** `esSegBase::GetPtsObj` 对 0x1000/0x1002/0x2001/0x1003 四类做"取上方关联对象"跳转——这 4 个类型字不在 esSeg::Create 表内（应为 eslib 其它族的标注类），待后续批。
- **Q10** `esSeg::GetTotalMatrix*` 系列对"容器/叶"分界的判据是**类型字 < 0x4000**（0x2030 列表、0x2020 画布在阈值下）——类型字编码本身带层级语义。

## 9. ILT / COMDAT 折叠（同址多符号，解导入面时防误读）

| 地址 | 本批符号 | 折叠群（节选） |
|---|---|---|
| `5a90` | esSegBase::Build | Cancel(esCoreBase)、CollectStyles(×5)、DirectlyShow(esStage)、DrawDynamicVertexs、ExecuteCommand(esObject)、GetText(esChrObj)、Initialize(esDocPage)、OnCreate(esSeg)、OnDraw(CoreBase)、OnParaStyleChanged、OnPreTransfrom、ReplaceFontIndex、SavePoint/RestorePoint(elfSubject)、SetObj/SetValue(esPropItem)、Show(esDialog)、SnapPointWhenCreate(esSeg)、ToFixColor(esShapeBase)、TransformOtherPage、UnitOtherMaxRect/UnitOtherObjRect(esSeg)…（38 个） |
| `6690` | esSeg::BreakLine | CollectStyles(esChrObj)、CopyFrom(esObject)、CountCharacters、LoadProp/SaveProp(×3)、OnDrawAppLog、OnDrawBreaks、Serialize(elfPage)、SetColor(esBrush)、ToFixColor(esBrush)…（31 个） |
| `e790` | esSegBase::SetPointPos | esSegLable::SetPointPos（同体 `return 2`） |
| `ec40`… | 各 operator= | esSeg operator= 独立；见 §6 esSegGemotry 行 |
| `12460` | esSeg::AddPoint | esOleImple::CreateFromData（同体 `return 0`） |
| `1cf80` | esSeg::MovePoint | esSegSurface::MovePoint |
| `107dc0` | esSeg::Build | esSegLinkLine::Build |
| `19dec0` | esSegList::CreateObject | esShapeBase::CreateObject |
| `110e80` | esSegGemotry::className | esSegPoint::className |
| `ed20` | esSegGemotry::operator= | esSegPoint::operator=（两者都转 esSegFrame::operator=） |

## 10. 与动态桥（ee-draw）的相关性（S1 对照点）

- 桥里"填充必须 SetSolidBrush / 加粗点走 esShapeLine / 圆用 esSegCircel"等结论对应的正是本批类：
  `esSegCircel 0x4284`、`esSegGon 0x4702`、`esSegBezier 0x4703`、`esSegLine 0x4701`、`esSegAxis 0x5006`。
- **渲染路径**：`esSeg::Draw` = `egPath(安全点, flags)` + `CloseAllFigures` + 笔(`esPenInfo::CreatePen`)/刷(`DRAWPARAM+8` vtbl+0x78) —— "字段全对≠能用"的根因在 `+0x34 安全点由 Build 重建`（只改 +0x58 控制点不重建就不参与绘制）。
- `RecalcLayout` 的 **InflateRect(400,400)** = 包围盒外扩 1mm——与桥里 `padding=400` 的默认值同源。
- 手工拼装对象挂画布会坏的机理旁证：`Serialize`/`CopyFrom`/`Detach` 全依赖 `+0x3C/+0x40` 链与 amulet 上溯；链字段写坏 → `RecalcLayout`/`Detach` 立刻踩坏邻居。

---

**遗留（待后续批/差分）**：0x6002/0x4285 两个未命名类、esSegNative/esSegFrame 中间谱系核实（§6/§9 折叠）、Q1–Q10 差分复核、`GetbendingPoints` 常量表标注。
