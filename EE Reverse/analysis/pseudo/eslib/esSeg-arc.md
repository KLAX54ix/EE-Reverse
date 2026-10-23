# eslib 绘图弧族 — 反编译规格（阶段 2 · 第七批 · 绘图核心 3/6）

- 模块：eslib.dll；函数：**142 个**（esSegArcBase 34 · esSegArcFace 23 · esSegArc 18 · esSegLines 15 · esSegCircels 15 · esSegGonFace 15 · esSegArc90 13 · esSegEllipseEx 9）
- 伪代码（原样）：`analysis/pseudo/eslib/esSeg-arc.decomp.txt`（matched=142 dumped=142）
- 类型头：`analysis/types/esSeg-arc.h`
- 台账：142/142 → `decompiled`（status-overrides）
- 角色：第四批 `esSeg` 基座的**弧族叶段实现**（弧/圆环组/弧面/多边形面/椭圆延伸），外加全族公共点链工具 `esSegLines`。本批定下弧族字段布局（半径/方向/起终角/圆心/中角）、三点定圆、弧拆分（GetBreakLines）、弧面环带与撤销码。

## 0. 谱系与公共结构（本批结构性结论）

| 结论 | 证据 |
|---|---|
| `esSegLines → esSegArcBase → {esSegArc, esSegArc90}`；`esSegArcBase → esSegGlow → esSegCircels`；`esSegGon → esSegGonFace`；`esSegEllipseEx : esSegEllipse`；**`esSegArcFace : esSeg` 直派（不经 ArcBase）** | ctor 链：ArcBase 三 ctor（`124330/124350/1243d0`）调 esSegLines；Arc `1280d0/128110` 调 ArcBase；Circels `1af70/1afb0` 调 esSegGlow；GonFace `3f26d0/3f2710` 调 esSegGon；ArcFace `1e010/1e060` 直调 `esSeg::esSeg`；EllipseEx 调 `esSegEllipse` ctor。dtor：ArcFace `1e1a0` 直调 `esSeg::~esSeg` |
| `esSegLines` 是**全族公共点链工具**：显示点缓存（`+0x34/+0x38`）、前后链（`+0x3C/+0x40`）、控制点数组（`+0x58/+0x5C`）、拆链（BreakLine）、链点移动（MoveLinkPoint） | Arc 族直接复用：esSegArc::MovePoint `129f30` → `esSegLines::MoveLinkPoint`；GonFace dtor → esSegLines；ArcFace::Undo 末尾落 `esFormulaBox::CaretMove`（esSeg 直派则不同） |
| 弧族**双表示**：控制点 3 个（P0=起点、P1=中点(+8)、P2=末点(+0x10)）＋角度字段。`+0x68` float r · `+0x6C` int dir（1=顺时针？0=反） · `+0x70` float a0 · `+0x74` float a1 · `+0x78/+0x7C` center · `+0x80` float mid（缓存） | 全族读写一致；退化（r<1e−5）时角度字段**直接存坐标 int→float**（InitPoints `124fa0`、CheckCenterPoint `126100`、MovePoint_3Points `12a820`），互为冗余 |
| 类型字三位一体：**0x4307**=单角弧（a0==a1，整圆语义）· **0x4306**=双角弧（a0≠a1，带 dir） · **0x42c1**=基线弧（近 0x4306 但 GetBreakLines 不拆） | `128150` 写 0x4307、`128290` 写 0x4306；GetBreakLines `124510` 按类型分派；CheckIntoRing `111810` 把 0x4307 升 0x4306 |
| dtor 三链折叠：`~ArcBase`(f3b0, 5 符号)→`~esSegCircel`；`~Arc90`(f700, 12 符号)→`~ArcBase`；`~Circels`(f790, 5 符号)→`~Arc90` | ILT 折叠表（§2–§5 各表） |
| `operator=` 梯：`Lines⇒esSegGemotry`(f6c0)；`ArcBase⇒Lines+7 dword`(f8a0)；`Arc⇒ArcBase+5 dword`(f910)；`Arc90⇒ArcBase`(f980)；`Circels⇒esSegGlow::operator=`(10bc0)；`GonFace⇒esSegGon+4 字段`(10d70)；`EllipseEx⇒esSegEllipse::operator=`(10dc0)；`ArcFace⇒esSeg::operator=`(10ee0) | 各 op= 函数体 |
| `className()` 不报自身名（折叠回父 ID）：ArcBase/Gon→`esSegLines::ID()`（10e230）；Arc90/Arc/Glow→`esSegArcBase::ID()`（1c080）；Circels→`esSegGlow::ID()`（1aed0）；EllipseEx→父 `esSegEllipse::ID`（1d910） | 各 className 函数体 |
| **esSegArcRuler↔esSegArcFace 折叠**：BreakLine `18c00`、Undata `18cd0`、MovePoint `19a40`、CheckCenterPoint `19b00` 同址共用（直尺圆弧面同族实现） | ILT 折叠（2 符号组） |
| 弧族自带**三点定圆**静态工具 `GetCircleOrg`（124b90）：弦中垂线/斜率解圆心，zFtoL 取整写出；另有 `GetCircleOrg_For3P`（esGraph，BuildEx 用） | GetCircleOrg / BuildEx `126ad0` |

**类型字/尺寸**（工厂表见第四批 spec §2.1）：0x42c1 esSegArc(0x98) · 0x4282 esSegArc90(0x84) · 0x4306/0x4307 esSegArc 变体(0x98) · 0x480f esSegArcFace(0x84) · 0x4a8a esSegEllipseEx(0x7c) · 0x4c0e esSegGonFace(0x74) · 0x6003 esSegCircels(0x8c) · 0x4285 esSegEllipse 父(0x7c)。编辑态：Arc 由 SetPointPos `1283d0` 使用 **0xe401/0xe402**（Snap 预置态）。

## 1. esSegLines（15 个）（谱系公共父类，无自身构造类型字）

布局：`+0x34/+0x38` 显示点缓存（ptr/count）· `+0x3C`/`+0x40` 前/后链对象（next/back）· `+0x58` 控制点数组 · `+0x5C` 计数（ushort）。

| 函数 | 入口 | 规格 |
|---|---|---|
| `ID / isKindOf / isOf` | `111210 / 111220 / 1112c0` | `"esSegLines"`；isKindOf 先判 **this==NULL→0**，比名不中→`esSegGemotry::isKindOf`；isOf 仅自比 |
| `operator=` | `f6c0` | 2 符号折叠（含移动赋值形态）→ 转 `esSegGemotry::operator=` |
| `ctor()` | `111350` | `esSegGemotry` + vftable；`+0x5C=0`、`+0x58=0`（空点链） |
| `GetStartPoint()` | `111390` | 显示点 `+0x34==0`→`vtbl+0x7C()` Build；**type==0x4307 或 cnt<2**→显示点[0]；否则 ctrl[0]→`pttoptf`→`FUN_100279d0`（世界变换）→`ptftopt` |
| `GetEndPoint()` | `111480` | 同前哨；退化→`IsClosed(1) ? 显示[0] : 显示[(+0x38)−1]`；否则 ctrl[cnt−1]→`FUN_10027a30(&pt,1)` |
| `GetEndPointIndex()` | `111570` | `return (+0x5C)−1`（直读控制点计数） |
| `GetBackObj()` | `111590` | 自邻指判定：**类型字 & 0x100**（点对象）→NULL；`+0x40!=0`→返回 `+0x40`（链对象）；否则 `IsClosed(0)==0`（断开）且 amulet=`0x2030` 链表对象→返回**链表尾**（list+0x38） |
| `GetNextObj()` | `111600` | 对称：`+0x3C!=0`→返回之；否则断开且挂链→链表头（list+0x34） |
| `Undo(id,data,sz)` | `111670` | **0xf2e8**：`type` 旧值↔`data[0]` 往返；其它→`esFormulaBox::CaretMove`（基座） |
| `OnMovePoint(pt,idx,flags,chk)` | `1116e0` | 守卫：**仅链上**（`+0x3C!=+0x40`）且 `type!=0x4307`；idx==0→`GetBackObj`（若 back 为 0x4307→其 `vtbl+0x74(GetEndPointIndex(back))`+`vtbl+0x44(0)`）；idx==末位→`GetNextObj` 对称；否则自身 `vtbl+0x74(pt,idx,flags,chk)`+`vtbl+0x44(0)` |
| `CheckIntoRing(undo)` | `111810` | `0x4701`(Line)→`0x4702`(Gon) 恒；**0x4307→0x4306 仅链上**（否则 0）；变更→`vtbl+0x44(0)`+undo `FUN_10052810(this,0xf2e8,&old)`；返回 1/0 |
| `MoveLinkPoint(mask,chk)` | `1118c0` | `mask!=0 && flags&0x300`：**&0x100**→`FUN_103e36b0(1,this,0)`+`GetNextObj`+`FUN_103e36b0(1,next,1)` 资格判定→端点不同则 `next.vtbl+0x74(endPt,0,0x100,chk)`+`0x44(0)`；**&0x200**→对称走 back（idx=`GetEndPointIndex(back)`） |
| `BreakLine(pts,n)` | `111a80` | 见下**注**（断口拆链）；事件数>0 时走 List/Path/Canvas 三级 amulet 链 |

**注（BreakLine 断口机制）**：守卫 `!IsClosed(0) || 链上`→转 `esSegGemotry::BreakLine`（不拆）。断口位掩码：**bit1=idx0、bit2=末位**（GetBreakLines 用 0/1/2 三槽映射回 idx0/idx1/idx2）；`local_50`=内部断口数（`0<idx<count−1`）。有动作时先 `esCanvas::RemoveControlAndLinkPoints`。毗邻链情形：`esUnMove(0x18)`（原始数据登记）+ 新建 `esShapePath(0x74)` + `AddSegList` + `CopyPropFrom` + `canvas.vtbl+0x3c(新,旧,1)` + `[新+0x3c]=1` + `SetUnAddInfo` + `Rec_Add`。`local_50==0`（仅端点断口）→`OpenCanvas`（若 closed）+ `SetFirstItem`/`Relist` 组合：closed 且 mask≠3 时 mask==1→`SetFirstItem(this)`；`+0x3C==0`→返，否则 `SetFirstItem(+0x3C)`；mask==3 且双邻→`SetFirstItem(this)`；随后 `+0x40&&mask&1`→`Relist(头,this,0)`、`+0x3C&&mask&2`→`Relist(+0x3C,0,1)`。有内部断口→新建 `esSegList(0x44)`+其 `vtbl+0xEC GetBreakLines` 拆段→左右先 `Relist`（+0x3C 起始）→每段独立 `esShapePath`（`AddSegObject`）挂链→**销毁旧 shape**。

**怪癖**：
- **Q-lines-1** `CheckIntoRing` 的 0x4307→0x4306 升级**仅在有链邻居时发生**（直接排除 0x42c1/0x4701 等其它类型），交互建模的"套环即双角弧"语义，待动态验证。

## 2. esSegArcBase（34 个）（无自身类型字；esSegArc/esSegArc90 的父类）

布局：`+0x68` float **r** · `+0x6C` int **dir**（1/0） · `+0x70` float **a0** · `+0x74` float **a1** · `+0x78/+0x7C` **center**（tagPOINT） · `+0x80` float **mid**（缓存，`GetMidAngle`）。退化约定：`|r|<1e−5` 时角度字段存**坐标 float**（int x/y 直转），见 InitPoints/CheckCenterPoint。

| 函数 | 入口 | 规格 |
|---|---|---|
| `className()` | `10e230` | 2 符号折叠（ArcBase+esSegGon）→ 返回 `esSegLines::ID()` |
| `operator=` | `f8a0` | 拷 7 字段：`+0x68,+0x6C,+0x70,+0x74,+0x78,+0x7C,+0x80`（含换序防混叠） |
| `~esSegArcBase()` | `f3b0` | 5 符号折叠（ArcBase/EllipseEx/Gon/RectEx/Star）→ 体为单调用 `esSegCircel::~esSegCircel`（ILT 折叠命名） |
| `ID / isKindOf / isOf` | `1241f0 / 124200 / 1242a0` | `"esSegArcBase"`；isKindOf 不中→`esSegLines::isKindOf`；isOf 仅自比 |
| `ctor()` | `124330` | `esSegLines` + vftable（其余字段 0） |
| `ctor(ushort type)` | `124350` | `+4`=type；**`+0x68=0`、`+0x6C=1`（dir 默认 1）**、`+0x70/74/78/7C/80=0` |
| `ctor(zPoint,ushort)` | `1243d0` | alloc 0x18 三控制点**全=pt**；`+0x5C=3`；center=pt；`+0x6C=1`；余 0 |
| `GetBreakLines(list,flag,brks,n)` | `124510` | 断口槽映射：0→bit1、1→bit2、2→bit1；**0x4307 与 0x4306 都取 `mask&2`**（其它类型取全 mask）。`uVar2!=0` 且（`type!=0x4306` 或角跨≥1e−5）→弧路线：`mid=GetMidAngle`；`param_2!=0` 且未链时：mask==2→单个 `esSegArc(mid,r)`；mask==1→单个 `esSegArc(a0,+0x70,r)`；mask==3→两个弧（a0 与 mid）；拆出段写类型码 0x4307/0x4306；均 `AddSegObject`。gon 路线：G1=`[(int)a0,(int)a1], center`、G2=`center, 2·center−ctrl[0]` 两条 esSegGon——见 **Q-arcbase-1** |
| `GetCircleOrg(pts,&org,&dir)`(static) | `124b90` | P0==P2→(P0==P1? org=P0, 返 0 : org=mid(P0,P1), 返 1)；否则弦旋转对齐试探：`|Δy'|≥10.0`→斜率 `−(Δx/Δy)` 解圆心（zFtoL 取整写出）+方向位 `dir=(P1.y≤P0.y)`，返 1；`|Δy'|<10`→返 0（近共线退化） |
| `UnitOtherMaxRect(rect)` | `124f00` | 世界变换 center（`+0x78`）后扩 zRect |
| `InitPoints()` | `124fa0` | **0x4306 且 |r|<1e−5**→P0=`((int)a0,(int)a1)`、P1=center、P2=2·center−P0（坐标↔角度字段约定）；否则 P0/P1/P2=`GetPointFromAngle(a0/mid/a1)` |
| `MovePoint_4Points(pt,idx,flags,chk)` | `125140` | idx0/2：`Invert`；`!(flags&8)` 且 r>0→`esEntersect(0x18)`+`GetNearestPoint` 约束到圆；`flags&8`→r=dist(pt,center) 夹≥10（f4cc）；idx0→a0=GetAngle_y(center→pt)+`epNormalAngle360P`+`CheckArcDirection(0,0)`+重算 P0（r 变则重算 P2）；idx2 对称；再 P1=mid；idx1（中角）：r=dist 夹≥10 或按 `Δ=(angle−+0x80)` 平移双角+epNormal——见 **Q-arcbase-2**；`InitPoints`；`+0x80=angle`；idx3：整体平移 3 控制点+center |
| `MirrPts()` | `125780` | `dir=(dir==0)?1:0`；交换 `+0x70/+0x74`（a0↔a1）；交换 pts[0]/pts[2]；`vtbl+0x44(0)` |
| `unMPSave(arch)` | `125860` | 基类 + 存撤销码：a0→**0xf2d1**、a1→**0xf2d2**、r→**0xf2d3**、center→**0xf2d6**（`FUN_10052940`）、dir→**0xf2d5**（`FUN_100260d0`）；尾 `+0x80=GetMidAngle` |
| `Undo(id,data,sz)` | `125a30` | 0xf2d1↔`+0x70`、0xf2d2↔`+0x74`、0xf2d3↔`+0x68`、0xf2d5↔`+0x6C`(int)、0xf2d6↔`+0x78`(pt)；default→`esSegLines::Undo` |
| `SetPointPos(mgr,idx,flags,mtx)` | `125ba0` | `mode==1`→angle=`GetAngle_y(center→pt)`；`+0x80=+0x74=+0x70=angle`；r=dist；ret 1。`mode==2`→`+0x74=angle`、`CheckArcDirection(1,1)`、ret 1。default ret 2。尾 `P=GetPointFromAngle(+0x74)`→`FUN_10027a30(&P)`→`ResetSnapPointPos(P)` |
| `CheckArcDirection(mode,which)` | `125d60` | a0≠a1→mid 与对径（mid±π）择近（环绕比较）；`v1<v2`→mid 返；否则 `param_1!=0`→翻 `+0x6C`、cached=对径、返；`param_1==0` 且 param_2==0→a0=a1、否则 a1=a0（折叠）。随后 `param_1==0`：r=`fabs(r)`；**`|cached−角|≥π/2`→cached=角±π；否则→`r=−r`（xor 0x80000000）+cached=角**；`param_1!=0`→cached=角 |
| `Get3Points(&p0,&p1,&p2)` | `125ff0` | 拷 ctrl 0/1/2 原样 |
| `GetCenterPoint()` | `126080` | 返回 center（`+0x78`）经 `FUN_10027a30(&pt,1)` 变换 |
| `OnCreate(styleSheet)` | `1260e0` | `InitPoints` |
| `CheckCenterPoint(idx)` | `126100` | `param_1!=1` 时三分支：**A) P0==P2**→center=P0、按旧偏移主轴向 ±r（zFtoL）移动、angle=GetAngle_y(P0→center)、a0=a1=angle、ctrl[1]=mid 点，返；**B) 10<r≤50000**：`epNormalArcAngles` 算扫掠>3π/2→弦系 center=P0+(半弦,±高)（高=√(r²−half²)）、dir=(center.y−P0.y<0)?1:0、回旋、重算 a0/a1、ctrl[1]=mid，返；**C) P0≠P2**（含 param_1==1）→ctrl[1] 拉回弦垂直平分线（水平弦→x=avg、竖弦→y=avg、一般→弦系 x=半弦保留 y 回旋）。最后 `GetCircleOrg(ctrl,&center,&dir)`：返 0→r=0、center=ctrl[1]、a0=(float)P0.x、a1=(float)P0.y（存坐标）；否则 r=dist(P0,center)、a0/a1=GetAngle_y(P0/P2→center) |
| `BuildEx(src,t)` | `126ad0` | 守卫（src null/类型不符/`t≥1.0`）→`vtbl+0x7C` Build；0x4307/0x4282→dir 异则换角序、`step()` 插值 center/r/a0/a1→`BuildArc`；否则三点 `step()`→`GetCircleOrg_For3P`：返 0→0x4306 两点 `SetPtInfo(2,1,1)`／否则一点中点 `SetPtInfo(1,1,1)`；≠0→r=dist、三点三角、方向位=角序单调性→`BuildArc(center,r,aFirst,aLast,dir)` |
| `BuildArc(center,r,a0,a1,dir)` | `1270f0` | `esBezierArc(center,a0,a1,dir)` 采样、`n=GetPtCount`；0x4282→`count=n+2`；`n<1`→2 点=(cx,cy−r) 绕 center 按 a0/a1 旋转、`SetPtInfo(2,1,1)`；否则 `GetPts(n,r,r)`、末点=首点（n<Count）、`Count−n>1`→倒数第 2=center；flags [0]=0、1..n−1=3、n..=1；`SetPtInfo(Count,0,1)` |
| `Build(n)` | `127360` | `r≤0.0f`：0x4306→2 点（ctrl[0]、ctrl[末]）`SetPtInfo(2,1,1)`；否则 1 点 `GetPointFromAngle(a0)` `SetPtInfo(1,1,1)`。`r>0`：`esBezierArc` 采样（0x4282 扩 2 点；`n<1`→同上 2 点退化）→`GetPts`+flags [0]=0/1..=3/尾=1→`SetPtInfo` |
| `GetDefaultPtOrg(out)` | `127710` | 世界变换 center；返回 1 |
| `GetLbcLines(mgr,mtx)` | `127750` | `r≤0` 且 0x4306 且 ctrl[0]≠ctrl[1]→组合矩阵后以 [ctrl[0], ctrl[末]] 登记直线（`FUN_1037fc10`）；否则 `pttoptf(center)`+`FUN_1037fec0`（圆登记） |
| `GetPointFromAngle(angle)` | `127960` | `|r|≥1e−5`→`x=cx+r·sin(a)`、`y=cy−r·cos(a)`（a=0 → 上，屏幕顺时针）；否则 center |
| `IsEqual(obj,sheet)` | `127a90` | `esObject::IsEqual`+矩阵比较（`FUN_1005e200`）+比 dir/r/a0/a1/center |
| `Serialize(arch,sheet,ver)` | `127b70` | 存序：dir、r、a0、a1、center。读档版本门：`>0x107010d` 旧路（+归一 a0/a1+GetMidAngle→`+0x80`）；否则新版：`!(param_3&1)`→矩阵反序列化（`+0x48`）、读五字段归一、`ctrl` 空→alloc 0x18 三件、`+0x80=GetMidAngle`、`InitPoints`、`esObject::Serialize` |
| `CopyFrom(obj,exch)` | `127de0` | `esSeg::CopyFrom`；同 ID→拷 dir/r/a0/a1/center |
| `GetMidAngle()` | `127e80` | `a0==a1` 且 `r≤0`→返 a0；`a0≠a1` 且 r<0→**就地 `r=fabs(r)`（改 `+0x68`）**；mid=`epNormal((a0+a1)/2)`；`(dir!=0 && a1≤a0) || (dir==0 && a0≤a1)`→mid±π。见 **Q-arcbase-3** |
| `SnapFarPoints(mgr,pt,thr,skip)` | `12bb10` | `+0x34==0` 退；分派：0x42c1→`param_4==2` 退、<0→1、`pt=ctl[param_4==0]`；0x4306→`param_4==1` 退、idx=`(param_4==0)?2:0`；0x4282/0x4307/0x5005/0x6003→`param_4==3` 退→`GetCenterPoint`；`FUN_10027a30(&pt,1)`；末 `|Δx|≤thr`→`AddSideLine`（垂直线）、`|Δy|<thr`→`AddSideLine`（水平线） |

**怪癖**：
- **Q-arcbase-1** `GetBreakLines` 的 gon 路线两条 `esSegGon` 构造在反编译里**丢参**（仅见 `[((int)a0,(int)a1), center]` 与 `[center, 2·center−ctrl[0]]` 两组点；点数/矩阵参数不可见）——按 2 点 esSegGon 重构造，待差分复核。
- **Q-arcbase-2** `MovePoint_4Points` 中角分支对 **`+0x70` 重复调 `epNormalAngle360P`**（疑漏 `+0x74`），行 ~3930；动态表现=拖中角时 a1 不归一，待验证。
- **Q-arcbase-3** `GetMidAngle` 对 `r<0` 有**就地取正副作用**（写回 `+0x68`）——名字像查询，实际会改状态。
- **Q-arcbase-4** 弧族 ctor 的 float 参数序（r 与角）按**函数体字段写入**判定：f1→`+0x68`(r)、f2→`+0x70`(a0)、f3→`+0x74`(a1)；反编译调用点隐藏参数不可见，栈槽分析无法独立复核。

## 3. esSegArc（18 个）（0x42c1 / 0x4306 / 0x4307 多用；esSegArcBase 子类）

布局：`+0x84` int **环缓存在场标记**（Build 时闭弧吸附命中→1）· `+0x88/+0x8C`、`+0x90/+0x94` 两等待吸附点（仅 `+0x84!=0` 有效）；其余同 ArcBase。

| 函数 | 入口 | 规格 |
|---|---|---|
| `ID / isKindOf / isOf` | `127f90 / 127fa0 / 128040` | `"esSegArc"`；isKindOf 先判 this==NULL→0，不中→`esSegArcBase::isKindOf`；isOf 仅自比 |
| `operator=` | `f910` | ArcBase + 拷 `+0x84,+0x88,+0x8C,+0x90,+0x94`（含换序防混叠） |
| `ctor()` / `ctor(zPoint,ushort)` | `1280d0 / 128110` | 基类 + vftable + `+0x84=0` |
| `ctor(PointF,f1,f2,Matrix*)` | `128150` | 基类默认 + **type=0x4307** + 3 控制点 + center=ptftopt + `+0x68=f1(r)` + `+0x70=+0x74=NORM(f2 角)` + `+0x6C=1` + `+0x80=GetMidAngle` + 矩阵→`FUN_10027140` + `InitPoints`（参数序见 Q-arcbase-4） |
| `ctor(PointF,f1,f2,f3,Matrix*,dir)` | `128290` | 基类默认 + **type=0x4306** + 3 控制点 + center + `+0x68=f1(r)` + `+0x70=NORM(f2 a0)` + `+0x74=NORM(f3 a1)` + `+0x6C=dir` + `+0x80=GetMidAngle` + 矩阵 + `InitPoints` |
| `SetPointPos(mgr,mode,flags,mtx)` | `1283d0` | **0xe401**（=−0x1bff）：mode==1→`IsSnapped(0x10)&&flags&0x10&&SetSnapType(0x10,1)`→4；否则 `GetSnapPointF`→`GetArcRound`：==0→`r=0`；否则 center=ptftopt、`r=Getparam()`；`flags&0x10`→**type=0x4307** 返 2；ret 1。**0xe402**：同型（`GetArcAngle`；mode1 需 `SetSnapType(1,1)&&SetSnapType(0x10,1)`→4）。**0x4306**：`GetSnapPoint`→`Invert`；mode1：P2 未变→0，否则 `P2=pt`+`CheckCenterPoint(2)`→1；else 2。**0x42c1**：`GetSnapPoint`→`Invert`；mode1：`P1=pt`、center=mid(P0,pt)、r=dist、a0=a1=`GetAngle_y`→1；else 2。default→`esSegArcBase::SetPointPos` |
| `Connect(other)` | `128880` | 圆心一致（`FUN_1012bd80`）+ other 无变换（`GetCompos`+矩阵比较）+ **链邻互指校验**（this+0x40/other+0x3c、this+0x3c/other+0x40）+角度配对（dir 同→用 other a0/a1 原序、异→交换），容差 1e−5；命中→写 `a0` 或 `a1`=对端角并**塌缩**（\|a1−a0\|≈0 或 ≈2π→a1=a0）；不中→return 0；成功 `vtbl+0x44(0)`+`InitPoints`→1 |
| `GetCtlPts(list,flag)` | `128b90` | `+0x84!=0`→先挂 2 点（`+0x88`、`+0x90`）flags `0xe4880000`×2 owner NULL。开放：0x4306→3 点 [P0,P1,P2] owner=this（开放且 `+0x40==0`→`SetFlags(1)`；`+0x3C==0`→`SetFlags(2)`）；其它→4 点 **[P0,P2,P1,center]** flags [0,2,1,3]（0x4307→flags[3]\|=0xeb660000；开放且 `+0x40==0`→flags[0]\|=0x700000、`+0x3C==0`→flags[1]\|=0x700000）。闭合：0x4306/0x42c1→3 点 [P0,P1,center] flags [0,1,0xeb660002]；其它→[P0,center,P0] flags [0,0xeb660001,2]；恒返回 1 |
| `Build(n)` | `129300` | `esSegArcBase::Build` + `+0x84=0`；`n==0` 且 `IsClosed(1)`→`pttoptf(center)`→`FUN_10133830`→`FUN_10135530()` 非 0→`+0x84=1`、`+0x88/+0x8C`=Invert(点1)、`+0x90/+0x94`=Invert(点2) |
| `DoSnap(mgr)` | `1294d0` | `+0x34==0`→Build。**r≤10**→矩阵+`IsSnapable(0x40)`→`SnapPoint(center)`→Restore→返 0。r>10：`SnapObj(显示点,0x4000)`→bVar2；矩阵+`IsSnapable(0x40)`→`SnapPoint(center)`（`+0x84!=0` 再 SnapPoint ×2）；`IsSnapable(2)`→`SnapPoint(ctl[0])`+（开放→ctl[+0x10]、闭合→ctl[+8]）；`IsSnapable(0x10)` 且开放→`SnapPoint(ctl[+8])`；bVar2→`FUN_10133990(center,r)`→`AddObjectLine`；Restore；`IsClosed(1)&&IsSnapable(0x100)`→`pttoptf`+`FUN_10133830`+`FUN_10135350`→命中循环 4 点 `SnapPoint`。恒 return 0 |
| `MoveAcmePoints(vg,pt,flag)` | `129b10` | 仅 flag==1。开放：0x4306→idx==1 返 0、否则 `ctl[idx]=pt`+`CheckCenterPoint(idx)`→1；0x4307→idx∈{0,2}：r=dist 夹≥10、idx0→`a0=GetAngle_y`+NORM+`CheckArcDirection(0,0)`+`P0=GetPointFromAngle(a0)`（r 变则重算 P2），idx2 对称；再 `P1=GetPointFromAngle(GetMidAngle)`→1。闭合：0x4306/0x42c1→`MovePoint_Ring`→1；0x4307→`MovePoint_Cricel`→**0** |
| `MovePoint(zPoint,idx,flags,chk)` | `129f30` | 开放：0x4306→`MovePoint_3Points` 后 idx==0→`MoveLinkPoint(flags&0x200)`、idx==2→`(flags&0x100)`；其它→`MovePoint_4Points`，链上且 flags&0x300→`MoveLinkPoint(flags&0x300)`。闭合：0x4306/0x42c1→`Invert`+`MovePoint_Ring`；其它→`Invert`+`MovePoint_Cricel` |
| `MovePoint_Ring(pt,idx,flags,chk)` | `12a0d0` | 入口 `dir=1`。idx==2→**整体平移**（3 控制点+center）。非 flags&8：idx0→`P2=pt; P0=P2`、**center=mid(P1,pt)**、a0=a1=`GetAngle_y(center→pt)`、`+0x80`=∓π；idx1→`P1=pt`、**center=mid(P0,pt)**、`+0x80=GetAngle_y`、a0=a1=`+0x80`±π。flags&8：angle=GetAngle_y（idx1 时 +\π）→NORM→a0=a1=angle、`+0x80`=angle±π、`P2=GetPointFromAngle(a0)`、`P0=P2`、`P1=GetPointFromAngle(+0x80)`。尾：r=dist(center→pt) |
| `MovePoint_Cricel(pt,idx,flags,chk)` | `12a5c0` | 入口 `dir=1`。idx==1→整体平移。否则 `P2=pt; P0=P2`、r=dist、a0=(r>0? `GetAngle_y(center→pt)` : 0)+NORM、a1=a0、`+0x80=a0`±π、**`P1=2·center−P0`**（对径点） |
| `MovePoint_3Points(zPoint,idx,flags,chk)` | `12a820` | 直写模式判定：flags&8 且（idx0→`+0x40==0`、idx2→`+0x3C==0`、idx1→无链）→**local_10=0**（直写）。直写（r==0）：idx0→`P0=pt`、a0=(float)pt.x、a1=(float)pt.y（NORM 各一）+center=(P0+P2)/2、P1=center；idx1→整体平移到 `P1=pt`、a0=(float)P0.x、a1=(float)P0.y；idx2→`P2=pt`+center=(P0+P2)/2、P1=center。直写（r>0）：idx0→a0=GetAngle_y+NORM+`CheckArcDirection(0,0)`+P0=GetPointFromAngle(a0)+P1=GetPointFromAngle(GetMidAngle)；idx2 对称（a1）；idx1→r=dist+InitPoints。常规（local_10=1）→`ctl[idx]=pt`+`CheckCenterPoint(idx)` |

**怪癖**：
- **Q-arc-1** `MovePoint_3Points` 的"直写模式"会把 **float 角度字段直接写坐标**（`(float)pt.x`），是退化弧（r==0）坐标↔角度冗余约定的第三处实现（另两处 InitPoints/CheckCenterPoint）。
- **Q-arc-2** `MovePoint_Cricel`/`MovePoint_Ring` 入口**无条件 `dir=1`**——闭合拖拽后方向被重置，无撤销记录。

## 4. esSegArc90（13 个）（0x4282；esSegArcBase 子类）

布局：与 ArcBase 相同（无新字段；`+0x84` 未用）。`GetBreakLines` 收到局部坐标请参考 §2 全局约定（隐藏参数为 PointF 中心 + 矩阵）。

| 函数 | 入口 | 规格 |
|---|---|---|
| `className()` | `1c080` | 3 符号折叠（Arc90/Arc/Glow）→ 返回 `esSegArcBase::ID()` |
| `operator=` | `f980` | 转 `esSegArcBase::operator=` |
| `~esSegArc90()` | `f700` | 12 符号折叠（Arc90/Arc/ArrowLines/Bezier/Coil/Curve/FreePoly/Glow/HVLine/Line/RoundLine/Surface）→ 体为单调用 `esSegArcBase::~esSegArcBase` |
| `ID / isKindOf / isOf` | `12adc0 / 12add0 / 12ae70` | `"esSegArc90"`；isKindOf 不中→`esSegArcBase::isKindOf`；isOf 仅自比 |
| `ctor()` / `ctor(zPoint,ushort)` | `12af00 / 12af30` | 转发基类 ctor（无新字段） |
| `GetBreakLines(list,flag,brks,n)` | `12af60` | 状态机（初始态=断口槽映射）：0→①`!(mask&2)`→弧（a0,r）态=2；否则→弧（a0,r）态=1；各 force **type=0x4307**+`AddSegObject`。1→②弧（mid,r）force 0x4307+`AddSegObject`态=2。2→③`!(mask&8)`→`esSegGon([P2,center,P0],3,矩阵)` 态=0；否则→`esSegGon([center,P0],2,矩阵)` 态=3。3→④`esSegGon([center,P0,P1],2,矩阵)` 态=0。每熊尾若 `mask&(1<<态)`→`+0x40` 挂新 esSegList |
| `GetCtlPts(list,flag)` | `12b5c0` | 4 点 **[P0,P1,P2,center]** flags NULL owner=this → `esVertexInfo`；返回 1 |
| `MovePoint(zPoint,idx,flags,chk)` | `12b710` | 纯转发 `esSegArcBase::MovePoint_4Points`（41 字节） |
| `GetLbcLines(list,mtx,n)` | `12b740` | `+0x34==0`→Build；`esSegArcBase::GetLbcLines`；**type==0x4282 且显示点数>3**：取 safe_points，对**末两显示点**（flags==1）→`FUN_1037fc10(this, safe_pts+idx−1, 0)`（登记开口尾段） |
| `DoSnap(mgr)` | `12b800` | `+0x34==0`→Build；r>0→`SnapObj(显示点,0x4000)`→bVar1；矩阵+`IsSnapable(0x40)`→`SnapPoint(center)`；**r>0 才继续**：`IsSnapable(2)`→`SnapPoints([P0,P2],2,2)`（两点批量）；`IsSnapable(0x10)`→`SnapPoint(ctl[+8])`；bVar1→total 矩阵+`FUN_10133990(center,r,r)`→`AddObjectLine`；Restore；再 `SnapObj(显示点,0x1000)`。恒 return 0 |

**怪癖**：
- **Q-arc90-1** `DoSnap` 里 `SnapObj` 调用两次（前 0x4000、尾 0x1000）且第二节点在 `r>0` 分支内——静态对比 esSegArc::DoSnap 只有一次尾调，差分候选。

## 5. esSegCircels（15 个）（0x6003；esSegGlow 子类，双亲链 ArcBase→Glow→Circels）

布局：`+0x84` float **内半径（起始半径）** · `+0x88` float **环距**（ctor 默认 **0x4b0=1200 单位=3mm**） · `+0x68` r（末半径） · 其余同 ArcBase。

| 函数 | 入口 | 规格 |
|---|---|---|
| `~esSegCircels()` | `f790` | 5 符号折叠（Circels/FreeBezier/Pipe/Spring/Wall）→ 体为单调用 `esSegArc90::~esSegArc90` |
| `operator=` | `10bc0` | 转 `esSegGlow::operator=` |
| `ID / isKindOf / className / isOf` | `1ae20 / 1ae30 / 1aed0 / 1aee0` | `"esSegCircels"`；isKindOf 不中→`esSegGlow::isKindOf`；**className→`esSegGlow::ID()`**；isOf 仅自比 |
| `ctor()` | `1af70` | `esSegGlow` 默认 + vftable + `+0x88=0x4b0` |
| `ctor(zPoint)` | `1afb0` | 同上 + `+0x84=0` |
| `DoSnap(mgr)` | `1b5f0` | `+0x34==0`→Build；`IsSnapable(0x40)`→`SnapPoint(center)`；`f=FUN_1052a840()`；环数=`f/环距+1`（**余数>10 且环距<内径→+2**）；`r_cur=max(r,+0x84)`；逐环：r_cur>0 且 `SnapObj(显示点,flags+0x60,f/环数,0x4000)`≠0→`Multiply`+`esSnapLine(cx,cy,r_cur,r_cur)`+`AddObjectLine`+`Restore`；r_cur−=环距；游标步进 `f/环数`。恒 return 0 |
| `GetLbcLines(list,mtx,n)` | `1b960` | 同环循环：`D2DPointF(center)`+`FUN_1037fec0`/`FUN_10380b40`/`FUN_10380b20`（矩阵先 `FUN_100279d0`）逐环登记回归线 |
| `Load / Draw` | `1bb80 / 1bbb0` | 直通基类 `esSeg::Load` / `esSeg::Draw` |
| `Build(n)` | `1bbe0` | `+0x84`、`+0x68` 均夹≥100（f518）；max/min 归一；`esBezierArc(center,a0,a1,dir)`；`n=GetPtCount`；环数=`(max−min)/环距+1`（+2 规则同上）；`total=n·环数`；逐环 `GetPts(游标,n,r,r)`、r−=环距；flags `i%n==0→0` 否则 3；`SetPtInfo(total,0,1)` |
| `LoadProp(mgr)` | `1be80` | 组 **0x1b00**、item **0x1b01=环距>>2**（z 单位 1/400mm→属性 1/100mm 换算） |
| `SaveProp(mgr)` | `1bed0` | `CheckWrite(+0x88)`；`inner'=r−floor((r−inner)/环距)·环距`；变化→undo `FUN_10026200(this,0xf2d4,&inner)`（内半径撤销码 **0xf2d4**）；`+0x44(0)` |

**怪癖**：
- **Q-circels-1** `LoadProp/SaveProp` 的环距按 **>>2** 存取（1/400mm→1/100mm 属性单位），内半径反而用完整 z 单位——两种单位约定混载，写外部工具时注意。

## 6. esSegArcFace（23 个）（0x480f；**esSeg 直派**，不经 ArcBase）

布局：`+0x68` ushort **幅宽**（ctor 默认 **500 单位=1.25mm**）· `+0x6A` byte **翻向** · `+0x6C` 环带点数组（完整 2n+1 点）· `+0x70` 环带 flags 数组 · `+0x74` 点数（=2n+1）· 控制点 (P0,P1,P2) + 显示点缓存（基座）。

| 函数 | 入口 | 规格 |
|---|---|---|
| `ID / isKindOf / isOf` | `1ded0 / 1dee0 / 1df80` | `"esSegArcFace"`；isKindOf 不中→`esSeg::isKindOf`（直派） |
| `operator=` | `10ee0` | `esSeg::operator=` + 拷 `+0x68(ushort),+0x6A(byte),+0x6C,+0x70,+0x74,+0x78,+0x7C,+0x80` |
| `ctor()` | `1e010` | `esSeg::esSeg` + vftable + **type=0x480f** + `+0x6C/+0x70/+0x74=0` |
| `ctor(zPoint)` | `1e060` | 「同型；`+0x5C=3`、alloc 3 点全=pt、**`+0x68=500`、`+0x6A=0`**、`+0x6C/+0x70/+0x74=0` |
| `~esSegArcFace()` | `1e1a0` | vftable + free `+0x6C` + free `+0x70` + **直调 `esSeg::~esSeg`** |
| `GetRgnPts()` | `1e200` | `+0x34==0`→`vtbl+0x7C`；alloc `+0x74`×8 点、memcpy 源 `+0x6C`；flags 缓冲 alloc `+0x74` 字节、memcpy 源（显示 `+0x6C`，见 **Q-arcface-1**）；返回 `+0x74` |
| `RecalcLayout()` | `1e2b0` | `+0x34==0`→Build；`+0x6C==0`→用显示点（+0x34/+0x60/+0x38）否则用 `+0x6C/+0x70/+0x74`；zRect→`GetPathBounds`→`SetSolidRect`+`SetBoundingRect` |
| `Load(render,flags,pen)` | `1e370` | `+0x34==0`→Build；**填充通道**（`param_3+8`、`vtbl+0x90`）→`elfPathGeometry(2)`+`AddPathEx`（**环带** `+0x6C/+0x70/+0x74`）；liquid→flags\|=8；AddPen→flags\|=1；flags≠0→`elfPathGeometry(flags)`+`AddPathEx`（**显示点**）+Add |
| `Draw(render)` | `1e550` | 填充=egPath(`+0x6C` 环带)→`vtbl+0x78`；描边=egPath(显示点)+`CreatePen`+`DrawPath` |
| `LoadProp / SaveProp` | `1e6e0 / 1e740` | 组 **0x1a00**、item **0x1a01=`+0x68>>2`**（幅宽）、**0x1a02=`+0x6A`**（翻向 byte） |
| `Undo / IsEqual / Serialize / CopyFrom` | `1e7e0 / 1e880 / 1e8f0 / 1e970` | Undo：0x1a01↔`+0x68`、0x1a02↔`+0x6A`、else `esFormulaBox::CaretMove`。IsEqual/Serialize/CopyFrom 均 `esSeg::` 基类 + 比/存/**isOf(ID)→拷** `+0x68/+0x6A` |
| `SetPointPos(mgr,mode,flags,mtx)` | `1e9f0` | `GetSnapPoint`+`Invert`；mode==1：开放→P2 未变→0、否则 `P2=pt`+`CheckCenterPoint(2)`→1；闭合→P1 未变→0、否则 `P1=pt`→1；mode≠1→2 |
| `Build(n)` | `1eb10` | `n==0`→free `+0x6C/+0x70`；幅宽=±500（`+0x6A` 翻向）；`GetCircleOrg(ctrl,&center,+0x80 dir)`：**退化**→5 点带 `[P0,P2,(P0.x+弦长,P0.y+幅宽),(P0.x,P0.y+幅宽)]` 绕 P0 按弦向旋转（pts[4]=pts[0] 闭合），flags [0]=0 余 1；**正常**→`esBezierArc(center,P0,P2,dir)`、`n=GetPtCount`、`+0x74=2n+1`；内弧 `GetPts(r=|P0−center|)`、外弧 `GetPts(r+幅宽)` 反序、pts[2n]=pts[0]；flags [0]=0、1..n−1=3、[n]=1、n+1..2n−1=3、[2n]=1；`memcpy` 半份（n 点）→`SetPtInfo(pts,flags,n,0,1)`（**显示=内弧一半**；`+0x6C/+0x74` 存完整环带）；`n!=0` 路径：`GetCircleOrg` 直写 `+0x78/+0x80`，退化→`SetPtInfo([P0,P2],NULL,2,1,1)` 否则内弧 `SetPtInfo(pts,NULL,n,3,1)` |
| `BreakLine(list,n)` | `18c00` | `IsCyclical && param_2>0 && OnBreakLine!=0`：`*param_1==1` 时 `FUN_10026090(pts,pts+8)` 平移 + `pts[2]=pts[0]`（循环首点回填）；undo **0xf2ff**；`vtbl+0x44(0)` |
| `Undata(id,…)` | `18cd0` | **0xf2ff**→同上旋转；else `esSeg::Undata` |
| `MovePoint(zPoint,idx,flags,chk)` | `19a40` | `Invert`；`pts[idx]=pt`；**cyclical 且 idx0→`pts[2]=pts[0]`；idx2→`pts[0]=pts[2]`**；`CheckCenterPoint(idx)` |
| `CheckCenterPoint(idx)` | `19b00` | `pts[0]!=pts[2]` 时：y 等→`pts[1].x=(x0+x2)/2`；x 等→`pts[1].y=(y0+y2)/2`；否则旋转法中点（f6b0） |

**怪癖**：
- **Q-arcface-1** `GetRgnPts` 的 flags memcpy 源显示 `+0x6C`（疑应为 `+0x70`）——若为真则 flags 全读自点数组，需差分复核。
- **Q-arcface-2** 本类与 esSegArcRuler **同址折叠**（2 符号组：`18c00/18cd0/19a40/19b00`）——直尺的圆弧面共用同一实现。

## 7. esSegGonFace（15 个）（0x4c0e；esSegGon 子类）

布局：`+0x68` ushort **幅宽**（ctor 默认 500）· `+0x6A` byte **翻向** · `+0x6C` **内缩点数组** · `+0x70` 计数 · 控制点在基座 `+0x58/+0x5C`。

| 函数 | 入口 | 规格 |
|---|---|---|
| `ID / isKindOf / isOf` | `3f2590 / 3f25a0 / 3f2640` | `"esSegGonFace"`；isKindOf 不中→`esSegGon::isKindOf`；isOf 仅自比 |
| `operator=` | `10d70` | `esSegGon::operator=` + 拷 `+0x68(ushort),+0x6A(byte),+0x6C,+0x70` |
| `ctor()` | `3f26d0` | type=**0x4c0e**——**不写 `+0x68/+0x6A`**（见 **Q-gonface-1**） |
| `ctor(zPoint)` | `3f2710` | `+0x68=500`、`+0x6A=0`、`+0x6C=0`、`+0x70=0` |
| `~esSegGonFace()` | `3f2780` | free `+0x6C` + 基类（**不折叠**；反编译显示 `esSegArcBase::~esSegArcBase` 系 ILT 折叠命名） |
| `GetRgnPts()` | `3f27c0` | 用 `+0x70` 计数；border flags 全 1 后 `[0]=0` |
| `RecalcLayout()` | `3f2880` | `+0x6C==0`→用显示点否则 `+0x6C/+0x70`；`SetSolidRect`+`SetBoundingRect` |
| `Undo / CopyFrom` | `3f2970 / 3f2a10` | Undo：0x1a01↔`+0x68`、0x1a02↔`+0x6A`、else `esSegLines::Undo`；CopyFrom 拷基座+`+0x68/+0x6A`（esSegGon 谱系） |
| `Build(n)` | `3f2a90` | free `+0x6C`；`+0x70=+0x5C`；alloc+memcpy；**outline 边偏移 ±幅宽**（按 `+0x6A` 翻向）；头点 `GetAngle_x` 旋转；顶点三元组 `GetJiaoDians`；尾接 `esSegGon::Build` |
| `GetJiaoDians(...)` | `3f2dc0` | d=三角度差；`|d|<0.001` 或 ≈2π→0；`d−=π`；miter=±幅宽·tan(d/2)；clamp/±5000 字面量；返回 0/1/2 |
| `Load(render,flags,pen)` | `3f3140` | 双 `elfPathGeometry(0x40)` type2 `AddExLines` + stylebrush/liquid→flag8/AddPen→flag1 |
| `Draw(render)` | `3f3310` | safe pts；liquid→`AddLines`+`esLiquid::OnDraw`；fill→`AddLines(margin)`+rect+`vtbl+0x78`；pen→`DrawLines` |

**怪癖**：
- **Q-gonface-1** 默认 ctor 不写 `+0x68/+0x6A`（仅 zPoint ctor 写 500/0）——默认构造幅宽/翻向为未初始化值？待查。
- **Q-gonface-2** 全族无 `Initialize`（grep 确认）；Build 依赖 `GetJiaoDians` 的 miter 求交，尖角 >90° 时有 clamp 截断。

## 8. esSegEllipseEx（9 个）（0x4a8a；esSegEllipse 子类，父块 0x1011de80–0x1011fdxx）

布局：继承 esSegEllipse 全部字段（父默认 ctor vftable 0x10572f08、type 0x4285）；**显示点=14=两组 7 点贝塞尔**（内/外轮廓各一段 3 次贝塞尔链）。

| 函数 | 入口 | 规格 |
|---|---|---|
| `ID / isKindOf / className / isOf` | `1d860 / 1d870 / 1d910 / 1d920` | `"esSegEllipseEx"`；isKindOf 不中→esSegEllipse 链；**className→父 `esSegEllipse::ID`（`FUN_1011de80`）**；isOf 仅自比 |
| `ctor()` / `ctor(zPoint)` | `1d9b0 / 1d9e0` | 父 ctor（`FUN_1011dfc0` / zPoint 版）+ vftable + **type=0x4a8a** |
| `operator=` | `10dc0` | 转 `esSegEllipse::operator=`（反编译仅见 `FUN_10010e90(param_1)`） |
| `Load(render,flags,pen)` | `1da20` | `+0x34==0`→Build；flags=`param_3+4` esPenInfo；`(flags&0xff)==0`→style 分支（stylesheet→+2、AddPen→+1）`elfPathGeometry`+`AddPathEx`（显示点）；否则→beziers type2+AddPen+`AddExBeziers(+0x34,7)`+`AddPenEx(+0x34 偏移 +0x30=第二组 7 点)`——**两带环轮廓** |
| `Draw(render)` | `1dd60` | safe_points+egPath；stylesheet→fill `vtbl+0x78`；`CreatePen`；`dash==0`→`DrawPath`；否则 `DrawBeziers(pts,7)`+`SetDashStyle(0)`+`DrawBeziers(pts+6,7)` |

**怪癖**：
- **Q-ellipseex-1** `Draw` 的 dash 分支把同一条 7 点链画两遍（`pts` 与 `pts+6`）并中途 `SetDashStyle(0)`——**疑"两段式虚线段"技巧或反编译字节偏移误**，差分复核候选。


