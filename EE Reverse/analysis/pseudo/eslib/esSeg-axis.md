# eslib 轴族与曲线族 — 反编译规格（阶段 2 · 第九批 · 绘图核心 5/6）

- 模块：eslib.dll；函数：**112 个**（esSegAxis 36 · esSegBezier 28 · esSegSimpleAxis 17 · esSegSimpleSingleAxis 13 · esSegCurve 9 · esSegFreeBezier 9）
- 伪代码（原样）：`analysis/pseudo/eslib/esSeg-axis.decomp.txt`（matched=112 dumped=112）
- 类型头：`analysis/types/esSeg-axis.h`
- 台账：112/112 → `decompiled`（status-overrides）
- 角色：S6 轴/曲线族 —— 坐标轴段 `esSegAxis`（**成员类型字 0x5006**，esSeg 直派，内嵌 `esAxisObj` @+0x6c 承担坐标几何，另挂 **3 个 `esFormulaBox` 标签盒**：0=原点标、1=横轴标、2=纵轴标）＋ 贝塞尔/折线段 `esSegBezier`（类型字 **0x4703**，控制点 3n+1 模型）与其两个派生 `esSegCurve`（**0x4708**，Catmull-Rom 式平滑插值）与 `esSegFreeBezier`（随手画自由曲线，`esBezier3::FitToBezierA` 抽稀）＋ 简易轴 `esSegSimpleSingleAxis`（**0x5002**，: esSegRuler，单线刻度尺）与 `esSegSimpleAxis`（**0x5001**，: esSegSimpleSingleAxis，十字轴 + 可选四向刻度）。本批定下：轴的**两臂基点模型**（pts[1]/pts[2] 各兼一端，RevX/RevY 置换取用基点——见 §0）、三角波刻度折线（每刻度净推进 500、齿 ±250/±125）、3 标签盒布置（GetTBOrg/SetTextBoxPostion）、曲线族**控制点三连组**（锚+双柄）编辑协议（GetCtlPts/DeletePoint/InsertPoint1/2）与撤销码 0xb11/0xc48/0xc49/0xc51/0xc52/0xc54/0xf2dc/0xf2ea/0xf2ec/0xf2ef。

## 0. 谱系与公共结构（本批结构性结论）

| 结论 | 证据 |
|---|---|
| `esSegAxis : esSeg` 直派：**esAxisObj 内嵌 @+0x6c**（0xDC 字节）；3 个盒指针 @+0x148/0x14c/0x150；3 对 float 标签微调 @+0x154..+0x168；总尺寸 0x16c | ctor `3fd350` / `Initialize` / `Serialize` |
| `esSegBezier : esSegGon`；`esSegCurve : esSegGon`；`esSegFreeBezier : esSegBezier`（控制点模型全套继承） | ID/isKindOf 链 |
| `esSegRuler → esSegSimpleSingleAxis → esSegSimpleAxis` 两段派生；后两个 `operator=`（`10730` / `10820`）均为 thunk（→`esSegRuler::op=` / →单轴 `op=`） | 两 op= 块头 |
| `operator=` ILT 折叠簇 **@`f720`（8 符号）**：`esSegBezier / esSegCurve / esSegHVLine / esSegLine` 的 operator=（含 && 与 const& 变体）全部 → `esSegGon::operator=` | `f720` 块头 ILT 注释 |
| `esSegFreeBezier::operator=`（`fac0`，64B 实函数）= 折叠簇 + `+0x68`（容量）/`+0x6c`（容差）/`+0x70`（闭合）三字段 | 块体 |
| `esSegAxis::operator=`（`108f0`，206B 实函数）：`+0x68`(ushort) + `+0x6a/+0x6b`(字节) + `esAxisObj::operator=` + **3 盒指针浅拷贝** + 6 float【Q-axis-2】 | 块体 |
| `esSegBezier::MoveAcmePoints` ILT 折叠 4 符号 @`1145e0`（esSegBezier/esSegGon/esSegLable/esSegPoint 同体）；`esSegSimpleSingleAxis::GetLbcLines` 与 `esSegSurface::GetLbcLines` 折叠 @`175a0` | 块头 |
| className 错名折叠：`esSegSimpleAxis::className`（`147d0`）→ `esSegSimpleSingleAxis::ID`；`esSegFreeBezier::className`（`11cd20`）→ `esSegBezier::ID`【Q-axis-1】 | 函数体 |
| **轴几何模型**：ctrl pts[0]=基点（Initialize 写 (0,0)），pts[1]/pts[2]=两臂端点（相对基点存储，各兼一端）；`Build` 折线 = 纵段 `[0..+0x6a)` + 横段 `[+0x6a..count)`，每段 = 起点→三角波刻度串→端点；RevX/RevY 位**置换两端点的取用基点**（不是坐标翻转）；esAxisObj::Build 另画轴杆/箭头/刻度盘。刻度数 len<0xfb?0:min((len−0xfa)/500,2)（条件式原样见 §1 Build） | `Build 3fd8a0` |
| **曲线族模型**：ctrl pts（+0x58/+0x5c）**3n+1 点**（锚+双柄三连组）；显示点（+0x34/+0x38）由 BuildLines/Build 重建；段数=(count−1)/3；顶点编辑 = 锚（idx%3==0）+ 双柄；`esSegCurve` 用 get_curve 把取样点升为平滑 3 连组后再走 BuildLines | `GetCtlPts / BuildLines / InsertPoint1` |
| **简易轴模型**：`: esSegRuler`（追加刻度原语）；显示点 `+0x34`：SingleAxis=[0..1]轴线+[2..]刻度对；SimpleAxis=[0..3]两轴四端+[4..]刻度对；`+0x58/+0x5c` 控制点（Single=2 点 / Simple=3 点）；`+0x6c/+0x6e`(ushort)=400 基准；`+0x68` float 角度缓存；`+0x70` byte 刻度位（Single ctor=1 / Simple ctor=0；bit0=负向、bit1=正向，&0xc 参与中档长度判定） | ctor / Load / Draw / DoSnap / GetBiaociPts |
| **撤销码（本批）**：0xb11（轴标签 3 偏移之一，9B）· 0xc48/0xc49（标签盒 建/删 blob，zMemory 0x100/0x1000）· 0xc51/0xc52（轴对象两快照 memcmp，12B 字节交换）· 0xc54（+0x94/+0x98 尺寸组，8B）· 0xf2dc（顶点点移，0x10B/0x20B）· 0xf2ea↔0xf2eb（1 型插点，alloc 0x2c/0x14）· 0xf2ec↔0xf2ed（2 型插/删点，alloc 0x1c/4）· 0xf2ef（曲线插点，4B） | 各 Undo/Undata 块 |

**布局总表**

- esSegAxis（0x16c）：`+0x34/+0x38` 显示点/count（两轴折线含刻度）· `+0x46` ushort **退化位**（bit0=pts[1].x==pts[2].x 横段退化、bit1=pts[1].y==pts[2].y 纵段退化）· `+0x58/+0x5c` 控制点（3 点，alloc 24B；[0]=(0,0)、[1]=端点1−基点、[2]=端点2−基点）· `+0x60` flags · `+0x68` ushort 标签字体槽 · `+0x6a` byte 纵段点数（X 段起点 index）· `+0x6b` byte 活动标签 idx（≥3=无）· `+0x6c..+0x147` esAxisObj · `+0x148/0x14c/0x150` 盒指针 · `+0x154+i*8` 3 对 float 标签偏移
- esSegBezier（esSegGon 派）：`+0x3c/+0x40` 前/后链接对象指针（首末顶点删除许可、0x700000 链接标记）· `+0x58/+0x5c` 控制点（3n+1）· 其余 esSegGon
- esSegFreeBezier：`+0x68` int 容量（初 100）· `+0x6c` int 容差（param&0xfff）· `+0x70` bool 闭合（param&0x8000）
- esSegSimpleSingleAxis：`+0x34/+0x38` 显示点/count · `+0x58` 控制点（2 点）· `+0x68` float 角度 · `+0x6c/+0x6e` ushort 400 · `+0x70` byte=1
- esSegSimpleAxis：同上级 + `+0x5c=3`（3 控制点）、`+0x70` byte=0

## 1. esSegAxis（36 个）（esSeg 直派 + esAxisObj）

布局见 §0。轴几何（杆/箭头/刻度/标签定位）全走内嵌 `esAxisObj`（+0x6c）；本类 `+0x34` 显示点 = 两轴折线（含三角波刻度），`+0x6a` 为纵段点数。标签由 3 个 `esFormulaBox` 承担（0=原点、1=横轴、2=纵轴，默认文案表 `DAT_1069dd58+idx*2`）。

| 函数 | 入口 | 规格 |
|---|---|---|
| `operator=` | `108f0` | `esSeg::operator=` + `+0x68`、`+0x6a/+0x6b` + `esAxisObj::operator=` + **3 盒指针浅拷贝** + 6 float【Q-axis-2】 |
| `ID / isKindOf / isOf` | `3fd210 / 3fd220 / 3fd2c0` | `"esSegAxis"`；isKindOf：this==0→0、名不中→`esSeg::isKindOf`；isOf 仅自比 |
| `ctor()` | `3fd350` | `esSeg` + vftable + esAxisObj@+0x6c + `FUN_10027a00(+0x154, 8, 3, FUN_10027af0)`（3 对 float 槽初始化器）；**type=0x5006**；清零 +0x46、+0x68、+0x6a/+0x6b、+0x148..+0x168 |
| `~esSegAxis()` | `3fd430` | 3 盒 `vtbl[0](1)` 释放 + `~esAxisObj` + `~esSeg` |
| `Initialize(...)` | `3fd4c0` | 字体槽参数→`+0x68`；默认笔 `GetPenInfo`（类型 0xff01、宽 0x50）；分配 3 控制点：`[0]=(0,0)`、`[1]=端点1−基点`、`[2]=端点2−基点`（取 esAxisObj 基点域 +0x70/74 与 +0x78/7c）；`+0x5c=3`；3 对标签偏移初值（f680,f544）/（0,f518）/（f680,0）；3× `AddOrRemoveTextBox(i, 建立位)`；`vtbl+0xa0(字体表)` |
| `RecalcLayout()` | `3fd6e0` | `esAxisObj::GetContentRect` ∪ 3 盒 `GetBounds` → `epTransfromRect(+0x4c)` → ∪ 显示折线点(+0x34) → `SetSolidRect/SetBoundingRect` |
| `Build(n)` | `3fd8a0` | ①`InitSize(端点1−基点, 端点2−基点)`；②刻度数：纵 `len=pts[0].y<pts[1].y ? pts[1].y−pts[0].y : (pts[2].y<pts[0].y ? pts[0].y−pts[2].y : 0)`，`len<0xfb→0` 否则 `min((len−0xfa)/500, 2)`；横同构（pts[1].x / pts[2].x）；③纵段（判别 `IsRevY`）：起点 `(!RevY) (o.x, max(o.y, pts[2].y)) / (RevY) (o.x, min(o.y, pts[1].y))`，终点 `(!RevY) (o.x, pts[1].y) / (RevY) (o.x, pts[2].y)`；刻度（n>0）：方向 `s=(pts[2].y<pts[0].y?−250:+250)`，首点 `起点+s`，每刻度 `y+=s/2`→点`(o.x−250,y)`、`y+=s`→`(o.x+250,y)`、`y+=s/2`→`(o.x,y)`（**每刻度净 500、点序推进重叠 1 点**【Q-axis-3】）；段末端点 flag=1，`+0x6a=纵段点数`；④横段：起点 flag=0 `(!RevX)(min(o.x,pts[1].x), o.y) / (RevX)(max(o.x,pts[2].x), o.y)`，终点 `(!RevX)(pts[2].x,o.y)/(RevX)(pts[1].x,o.y)`，刻度同构（±250 竖直齿）；⑤`SetPtInfo(pts,flags,count,0,1)`；⑥`esAxisObj::Build(矩阵(+0x4c), GerDrawFlags())`；⑦3× `SetTextBoxPostion(i)` |
| `Load(page,subj,dp)` | `3fe2e0` | 门 +0x34（空→Build）；`GetFont(page+0x38, +0x68)`；`esAxisObj::Load`；`GerDrawFlags()&7` 逐位 → 对应盒 `esFormulaBox::OnLoad`；段==2 → `esScriber::LoadLine(pts,pts+1)` 否则 flags 变体 |
| `Draw(render,dp,matrix)` | `3fe850` | 主分支：`dp+0x18&0x10000000`（非编辑）→ 清活动盒位；编辑态 `6b<3` → 屏蔽该盒，否则 `GetLabel(6b)` 取 label 字节；`esAxisObj::Draw(axObj, render, +0x68, matrix, mask, labelbyte)`；折线段：纵 `[0..+0x6a)`、横 `[+0x6a..]`（`DrawLine`/`DrawTypedLines`）；箭头 `dp+0xe & IsVisibleArrowY/X`；`(mask&7)` → 图元 Save→MultiplyTransform→3 盒 `OnDraw`→Restore；其二分支（`dp+0x18&0x20000000`）：`+0x44=1`、只画选中盒/`esAxisObj::DrawLab` |
| `GerDrawFlags()` | `3fed40` | bit0=+0x148 存在；bit1=+0x14c 存在**或** safe[2].x≠safe[3].x；bit2=+0x150 存在**或** safe[1].y≠safe[0].y；对置位盒先做 `RecalcLayout`；末：`pts[1].x==pts[2].x→清 bit1`、`pts[1].y==pts[2].y→清 bit2`【Q-axis-5】 |
| `GetTBOrg(idx,pt)` | `3feee0` | idx0→基点；idx1（横轴标）`x=(!RevX)?pts[2].x−800:pts[1].x+800`、`y=pts[0].y`；idx2（纵轴标）`x=pts[0].x`、`y=(!RevY)?pts[1].y+800:pts[2].y−800`（800=2mm）【Q-axis-4】 |
| `HandMoveText(&pt,mode)` | `3ff000` | idx<3：mode0 拖拽→undo **0xb11**（9B：idx 字节+新偏移两 float）→写 `+0x154+idx*8`；mode≠0 返回当前；idx≥3→`esAxisObj::GetLabel/SetLabOffset` |
| `SetTextBoxPostion(idx)` | `3ff560` | 盒=`[+0x148+idx*4]`；org=`GetTBOrg`；偏移=`+0x154+idx*8`；eps=`DAT_1057f070`：`|d|≥eps` 且 `1.0≤d`→`org+d`；`|d|≥eps` 其余→`org−尺寸+d`；`|d|<eps`→居中 `org−尺寸/2+尺寸*d` |
| `CollectStyles(sheet)` | `3ff700` | `esUseInfo::CollectStyles(sheet,+0x68,1)`；3 盒 `vtbl+0x68` |
| `IsEqual(obj,sheet)` | `3ff780` | `esSeg::IsEqual` + 盒/字体槽比较 |
| `Serialize(arch,sheet,ver)` | `3ff890` | `esSeg::Serialize` + esAxisObj + `+0x68` + `0x18B` 字节 [+0x154..) + 3 盒；版本门（sheet+0x850 > 0x1060307 时追加 1 字节 7） |
| `CopyFrom(obj,exch)` | `3ffc50` | ID 判型；`esAxisObj::CopyFrom`；字体槽经 `esStyleExchanger::GetFontIdx` 重映射；3 盒 `vtbl+0x24` 克隆 + `vtbl+0x74` 绑 sheet |
| `GetLbcLines(list,matrix,n)` | `3ffe30` | 按 `+0x6a` 把显示折线拆两段 → `FUN_1037fc10`【Q-axis-8】 |
| `MoveAcmePoints(group,pts,n)` | `3fffd0` | 点==NULL→组尺寸写 `+0x94/+0x98`；否则逐 acme（类型=`(acme+4)>>2`；对象类别由 DWFont 虚表低 16 位 `0x45d/0x45e/0x45f` 判【Q-axis-7】）：case0 `pts[0]=(x,y)`、1 `pts[2].x=x & pts[0].y=y`、2 `pts[1].x=x & pts[0].y=y`、3 `pts[1].y=y & pts[0].x=x`、4 `pts[2].y=y & pts[0].x=x`；`CheckPointsPositon`；0x45e+位图 → `+0x94/98=组尺寸×scale{FUN_10052d70}` |
| `GetAxisTransfrom(pt)` | `4002c0` | 克隆矩阵(+0x4c) → `FUN_10052bd0(dx,dy,1)` 平移（目标≠基点时）+ `FUN_1005dea0(+0x94,+0x98,0)` 缩放 |
| `MovePoint(pt,i,flags,check)` | `400390` | `+0x46` 退化位且 `!(flags&8)`：柄 1/2（x 退化）/3/4（y 退化）归一为整体移动；整体（i==0）：delta=新点−基点，间距≥100 → 两端平移否则各自夹紧；柄 i∈1..4：`1→pts[2].x`、`2→pts[1].x`、`3→pts[1].y`、`4→pts[2].y` |
| `CheckPointsPositon()` | `400860` | 两端夹紧（原样）：一端不得越过基点 0x190(400)，另一侧按 0x5dc(1500)/0x7d0(2000)/0xfa0(4000) 极限收位；x/y 对称两组 |
| `unMPSave(mode)` | `400cd0` | 读：`+0x94/+0x98` 变化→undo **0xc54**(8B)；存：`+0x46 = (pts[1].x==pts[2].x) | ((pts[1].y==pts[2].y)<<1)`；写 `+0x94/+0x98`【Q-axis-6】 |
| `LoadProp(mgr,ver)` | `400e60` | 组 **0xc00**：`font=GetFont(sheet,+0x68,DAT_1057f0b4)`；c28=font+6、c29=font[0]、c2a=font+0x28&3、c2b=font+0x14；c45/c46/c47=盒存在位；`esAxisObj::LoadProp` |
| `SaveProp(mgr,ver)` | `400fd0` | 静态快照 `DAT_106cda38`（0xDC，惰性 init：esAxisObj::CopyFrom+基类 SaveProp）：`memcmp(snap,+0x6c,0xc)→0xc51`；`memcmp(+0x78,0xc)→0xc52`；逐字段↔0xc21..0xc3a/0xc53（ushort/dword/byte 三种交换记录器 FUN_10052810/10026360/10025f60）；字体组（c28/c29/c2a/c2b）克隆+变更→0xc28 记录+换槽；c45/46/47→`AddOrRemoveTextBox`；有变→`vtbl+0x44(0)` |
| `AddOrRemoveTextBox(sheet,i,add)` | `4016d0` | 增：undo **0xc48**(1B) → `esFormulaBox(0x4c)` → `ResetLineWidth(this)` → `AddLines(box,0,1)` → `SetText(box+0x14, DAT_1069dd58+i*2, 1, sheet, 0xffff)` → `StylizeFonts(FUN_1007c430(sheet,0x40000,0))` → `SetStyleSheet vtbl+0x74`；删：undo **0xc49**（序列化盒）→ 释放盒 |
| `Undata(&code,data,&sz)` | `401a30` | **0xc51**@+0x6c / **0xc52**@+0x78 字节交换；**0xc54** 8B 交换 `+0x94/98`；**0xb11** idx<3 float 对交换+`SetTextBoxPostion`；**0xc49**→zMemory 读 idx(+字体 ushort)→重建盒（`vtbl+0x40` 反序列化 + `SetStyleSheet`）→输出码 0xc48；**0xc48**→序列化/删除→输出码 0xc49；否则 `esAxisObj::OnUndata`→`esSeg::Undata` |
| `OnMessage(msg,ulong)` | `402060` | 3 盒 `vtbl+0x48`：任一处理→`vtbl+0x44(0)`；`esSeg::OnMessage` |
| `HitTest(ht,mode)` | `4020f0` | `+0x44≠0→0`；`+0xc==0→清 0x6b`；`esSeg::HitTest`；盒 i∈{1,2}：i==1 需 `pts[1].x≠pts[2].x`、i==2 需 `pts[1].y≠pts[2].y`；命中→`SetSelInfo(0x17/0x18)`+`6b=i`；标签→0x1a+6b；本体→sel 7 |
| `GetActiveTBox()` | `402350` | `6b<3 → 盒[6b]` 否则 0 |
| `GetActiveBoxRect(i,rect)` | `402380` | 盒 `GetBounds`（标签走 `esAxisObj::GetBounds`）；4 角 `FUN_10027a30` 变换 → `GetRectByPoints` → 外扩 200 |
| `Undo(code,*p)` | `402580` | **0xc21↔+0x84**、0xc22↔+0x86、0xc23↔+0x8c、0xc24↔+0x88、0xc25↔+0x90、0xc28↔+0x68、0xc31↔+0xa0、0xc32↔+0x9d、0xc33↔+0xa8、0xc34↔+0xa2、0xc35↔+0x9e、0xc36↔+0xac、0xc37↔+0xa4、0xc38↔+0x9f、0xc39↔+0xb0、0xc3a↔+0xb4、0xc53↔+0x9c（ushort/dword/byte 对应）；default→`esFormulaBox::CaretMove`【Q-axis-9】 |
| `GetCtlPts(list,n)` | `402a00` | 5 柄：`[0]=基点`、`[1]=(pts[2].x, o.y)`、`[2]=(pts[1].x, o.y)`、`[3]=(o.x, pts[1].y)`、`[4]=(o.x, pts[2].y)`；`FUN_10027a30(pts,5)` 变换→`esVertexInfo(this)` |
| `DoSnap(mgr)` | `402c10` | `SnapPoint(基点, 2)`；可吸附→矩阵变换：`SnapPoint(esAxisObj::GetSnapPointBy 结果, 0x200 / 结果为基点时 0x20)`；`SnapLines`：纵段 `[6a−2]`×2（6a>1 时）、横段 `[count−2]`×2（count−6a>1 时），flag 0x1000 |

**怪癖**：
- **Q-axis-1** className 错名折叠两处：`esSegSimpleAxis::className` 返回的是 **`esSegSimpleSingleAxis::ID`**；`esSegFreeBezier::className` 返回 **`esSegBezier::ID`**——按 className 判型的工具都会认成父/兄弟类。
- **Q-axis-2** `operator=` 对 3 个标签盒做**指针浅拷贝**（不克隆盒对象）——拷贝后两轴共用同一盒实例，仅"源即将移交"语义下可用。
- **Q-axis-3** `Build` 刻度三角波：每刻度 3 点（`o.x−250` / `o.x+250` / 回轴）但点序指针只推进 2 → **相邻刻度共用"回轴点"槽位**（连续 Z 折线形态）；常量 250/125/500/0xfb 全为硬编码。
- **Q-axis-4** `GetTBOrg` 标签位置硬编码 800（=2mm）偏移；idx1/idx2 的取端逻辑：`!RevX` 横轴标贴在 pts[2].x 端、`RevX` 贴 pts[1].x 端（纵轴标同理反之）——**RevX/RevY 的实质是"两端点谁承当该轴端点"的置换**，不是坐标轴方向的镜像。
- **Q-axis-5** `GerDrawFlags` 返回值双语义：位 0..2 既当"三盒是否要重排"（存在性/几何差∪），又当"横/纵轴可见"（末尾按退化位清除）；调用方 Build 把它整个喂给 `esAxisObj::Build`。
- **Q-axis-6** `unMPSave` 存路径把退化位写进 `+0x46`（`pts[1].x==pts[2].x→bit0`、`pts[1].y==pts[2].y→bit1`）——该位同时被 `GerDrawFlags`（清显示位）、`HitTest`（屏蔽对应标签盒）、`MovePoint`（柄归一为整体）三处消费。
- **Q-axis-7** `MoveAcmePoints` 以 **DWFont 虚表低 16 位当类 ID**（`0x45d/0x45e/0x45f`）识别自绘笔对象；`0x45e` 且有位图时把 `+0x94/+0x98` 写成"组尺寸×缩放"（与普通拖动路径共用同一函数）。
- **Q-axis-8** `GetLbcLines` 用 `+0x6a` 把同一条显示折线拆成两段提交；`+0x6a` 由 Build 写入——Build 未跑（或写入异常）时轴在投影/打印侧会整体退化为单段。
- **Q-axis-9** `Undo` 兜底 `default→esFormulaBox::CaretMove`（该函数属标注框族，与轴无关）——疑似原版复用 switch 兜底。

## 2. esSegBezier（28 个）（: esSegGon；成员类型字 0x4703）

布局见 §0。控制点 **3n+1**（锚+双柄三连组，首末各 1 锚）；`count-1` 必须是 3 的倍数；显示点由 `BuildLines` 重建。段操作三型：`InsertPoint1/DelPoint1`（重叠 2 点扩段）、`InsertPoint2/DelPoint2`（纯 3 点块插删）。

| 函数 | 入口 | 规格 |
|---|---|---|
| `operator=` | `f720` | ILT 折叠簇（8 符号：本类+esSegCurve+esSegHVLine+esSegLine × &&/const&）→ `esSegGon::operator=` |
| `MoveAcmePoints(group,pts,n)` | `1145e0` | ILT 折叠 4 符号；逐 acme：`idx=(acme+4)>>2`、`pts[idx]=新点`；return 1 |
| `ID / isKindOf / isOf` | `1149c0 / 1149d0 / 114a70` | `"esSegBezier"`；isKindOf：this==0→0、不中→`esSegGon::isKindOf`；isOf 仅自比 |
| `ctor()` | `114b00` | `esSegGon` + vftable + **type=0x4703** |
| `ctor(zPoint)` | `114b30` | esSegGon(x,y,x,y)？——控制点 2 个同点、`+0x5c=2` |
| `ctor(PointF*,n)` | `114c20` | 点转换后写入；`+0x5c=(n/3)*3+1`（钳成 3k+1）；`ptftopt` 坐标取整 |
| `ctor(tagPOINT*,n)` | `114d30` | 直接 `memcpy` n 点 |
| `CheckFirstLastLink()` | `114e00` | `count>6` 且 `esBezier3::LinkBezier(&pts,count)`（首末相接判定）→ 尾 3 点搬到 pts[0..2]、`count−=3`、`Build`（把末段并到首段） |
| `MovePointTo(idx,pt,flags)` | `114f00` | undo **0xf2dc**(0x20B)：[idx0][idx+2][3 点]；拖段端=整段（3 点组）平移；段数<3 → no-op |
| `SetPointPos(i,pt,flags)` | `1150f0` | **i==0（删除后重建）：`count −= 4`**【Q-bez-1】、`count<4→2` 否则 Build→3；i>0：`knots=count/3+1 < i` → 追加 3 个末点副本；`count<5` → 5 点 `[P,P,Q,Q,Q]`；镜像 `pts[count−3]=2*pts[count−2]−pts[count−1]`（flags&8 除外）；flags&0x10 → 末点=新点；Build；return 1 |
| `MovePoint(i,pt,flags,check)` | `115580` | 锚（i%3==0）：两邻柄同 delta（flags&8 除外）；柄（flags&8）：邻锚==旧柄位 → 邻锚平移 **2×delta**【Q-bez-2】，否则柄绕锚旋转回原角度；i==0 → `esSegLines::MoveLinkPoint(flags&0x200)`；i==last → 追加 flags&0x100 路径 |
| `UnitOtherMaxRect(rect,pt)` | `115940` | 用**控制点**（+0x58）而非显示点；与 `esSegRoundLine::UnitOtherMaxRect` 折叠 |
| `BuildLines(n)` | `115a40` | `n≤3` → `SetPtInfo`（fill=1，作折线）；否则 `(n/3)*3+1` 点、fill=3（多边形语义） |
| `AddPoint(pt,tol,mode)` | `115aa0` | 距任一锚 ≤tol → 2；逐 3 点段 `esGraph::IsPtOnBezier(…,&t,…)`，`t∈(DAT_1057f0b8, DAT_1057f1e8)` → `InsertPoint1(idx+1, 分割点)` + undo **0xf2ea**(0x14B) + `vtbl+0x44(0)`；return 1；落空 0 |
| `Undata(&code,data,&sz)` | `115d80` | **0xf2ea↔0xf2eb**（alloc 0x2c / 0x14）；**0xf2ec↔0xf2ed**（alloc 0x1c / 4）；否则 `esSegGon::Undata` |
| `InsertPoint1(i,pts)` | `116040` | 在 ctrl i 处插 3 点，新段与邻段**重叠 2 个控制点**（借用邻居的）→ `count+=3`；释放旧显示点（0x8123）【Q-bez-4】 |
| `DelPoint1(i)` | `116150` | InsertPoint1 逆操作：`count−=3`（重叠 2 点还原） |
| `InsertPoint2(i,pts)` | `116290` | 纯 3 点块插入 ctrl i（`count+=3`，无重叠） |
| `DelPoint2(i)` | `1163c0` | 纯 3 点块删除（`count−=3`） |
| `GetControlLine(i,&pts)` | `1164c0` | 取**显示点** (k−1,k,k+1) 三点（闭合段首末回绕）——UI 控制柄连线 |
| `SnapPointWhenCreate()` | `1165f0` | `n=(count/3−1)*3+1`；`count<0x65` → 每 3rd 锚作吸附候选，否则仅首点【Q-bez-5】 |
| `DoSnap(mgr)` | `1166b0` | `count<0x97` → 每 3rd 显示锚 `SnapPoint`，否则仅首末；`SnapObj(…,0x2000)`【Q-bez-5】 |
| `HitTestAcme(ht,mode)` | `116790` | `CheckMode(0x10)` 门；锚（每 3rd）→ sel **0x10**+idx；柄（%3≠0）→ sel **6**+idx；象限由 `GetPtForBezier` 判 |
| `GetAcmePoint(i,*pt)` | `116e60` | i 越界 → solid-rect 中心；否则显示点 pts[i] |
| `GetCtlPts(list,n)` | `116f20` | 见下（2854B，三种显示模式） |
| `DeletePoint(i,mode)` | `117a60` | 锚删除：首/末锚先经 `+0x40/+0x3c` 链路对象 `vtbl+0xbc` 许可；`count<7` → 清空路径（`vtbl+0x14`+`+0x5c(0,0)`）；否则 undo **0xf2ed**(0x1cB：[local_28][3 点]) + `DelPoint2(local_28)`；`local_28` = 首段 i / 尾段 i−2 / 中段 i−1。柄删除：柄≠锚位 → undo **0xf2dc**(0x10B：[k][k][x][y]) + **柄折回锚点** + `vtbl+0x44(0)`；柄已在锚位 → 0【Q-bez-6】 |

**GetCtlPts 细则**（`116f20`）：门 +0x34；若 `+0x5c%3≠1` → **复制末点补到 3k+1**、释放旧数组（0x8123）、`vtbl+0x7c` 重建【Q-bez-3】；随后三种模式（`FUN_1000e650` 两次判别）：
1. **编辑主模式**：逐 3rd 锚（flag=idx），`param≥0` 时追加控制柄（前柄掩码 `0x98630000`、后柄 `0xa8640000`；与锚重合的退化柄省略）；显示 flags&0x100 且未闭合且 `+0x40==0 || +0x3c==0` → 首/末顶点 flag|=**0x700000**（链接标记）；
2. **显示点表模式**：直接列显示点（idx%3==0 → flag=idx；==1 → 0x98630000；==2 → 0xa8640000）+ 每段 `D2DPointF` 连接线；
3. **纯拷贝模式**：显示点原样拷贝（flags=NULL）。
最后 `esVertexInfo(this)` 入列表；return 1（空返 0）。

**怪癖**：
- **Q-bez-1** `SetPointPos(i==0)` 删除后重建时 `count -= 4`（3 点一段却减 4）——疑原版笔误（正常流程靠 Undata 恢复，见 esSegGon 批次）。
- **Q-bez-2** `MovePoint` 柄拖动：当"邻锚恰好位于旧柄位"时，邻锚整体平移 **2×delta**（double-delta）——连续拖动的加速度怪癖。
- **Q-bez-3** `GetCtlPts` 的 **3k+1 修补**：控制点数不是 3k+1 时复制末点补齐并释放旧数组后重建——顶点编辑 UI 的防熔断。
- **Q-bez-4** **0x8123 死存储模式**再现：`InsertPoint1`（L2815）、`DelPoint1`（L2860）、`GetCtlPts`（L3501）等释放路径（全套枚举见台账注）。
- **Q-bez-5** 吸附点密度**反直觉**：`SnapPointWhenCreate` 点数 ≥0x65 时吸附候选只剩首点；`DoSnap` ≥0x97 时只剩首末——点越多吸得越稀。
- **Q-bez-6** `DeletePoint`：**柄删除=柄折回锚点**（对象减顶点靠删锚）；锚删除=删整段（`DelPoint2` + undo 0xf2ed）；首末锚删除需链接对象（`esSegBezierLink`）许可。

## 3. esSegCurve（9 个）（: esSegGon；成员类型字 0x4708）

平滑插值曲线：外部喂采样点，`BuildLines` 把它升成 Catmull-Rom 式三次贝塞尔（控制点三连组）后按 esSegBezier 布局显示。`operator=` 折叠于 `f720`（见 §0）。

| 函数 | 入口 | 规格 |
|---|---|---|
| `ID / isKindOf / isOf` | `117ed0 / 117ee0 / 117f80` | `"esSegCurve"`；isKindOf：this==0→0、不中→`esSegGon::isKindOf`；isOf 仅自比 |
| `ctor()` | `118010` | `esSegGon` + vftable + **type=0x4708** |
| `ctor(zPoint)` | `118040` | `esSegGon(x,y,x,y)`（两点重合）+ 0x4708 |
| `BuildLines(n)` | `118080` | `n==2` → `esSegGon::BuildLines`（直接线段）；`n>2`：分配 3n+1；`pt[0]=pt[1]=param[0]`；内点循环 `get_curve` 输出 [c1,P2,c2] 写入；开口 → 末点重复（`count=local_24+2`）；闭合 → `get_curve(2nd-last, first, second)` 写回首段与尾；`SetPtInfo(pts,NULL,count,fill=3,transform=1)`；释放入参（≠+0x58） |
| `get_curve(P1,P2,P3,out)` | `1183a0` | `d2=|P1−P2|²`、`d3=|P2−P3|²+d2`；`|d3|≥DAT_1057f020` → `mid=P1+(P3−P1)*d2/d3`、`out=[P2+(P1−mid)*k, P2, P2+(P3−mid)*k]`（k=`DAT_1057f170` 张力系数，值待定【Q-bez-7】）；退化 → `3×P2` |
| `DoSnap(mgr)` | `118640` | 闭合 → 仅 `SnapObj(全显示点,0x2000)`；开口 → 另 `SnapPoint(首,2)`、`SnapPoint(末,2)`；return 0 |
| `AddPoint(pt,tol,mode)` | `1186e0` | 距任一控制点 ≤tol → 2；逐段 `esGraph::IsPtOnBezier`（开区间 `DAT_1057f0b8 < t < DAT_1057f1e8`）；命中且 mode==0 → `Invert` + `esSegGon::InsertPoint(knot+1, 投影点)` + undo **0xf2ef**（4B = knot+1）→ `vtbl+0x44(0)`；return 1；否则 0【Q-bez-8】 |

**怪癖**：
- **Q-bez-7** `get_curve` 张力系数 `DAT_1057f170` 与退化阈值 `DAT_1057f020` 数值未提取（值待定）——影响曲线"鼓度"；升级控制点用 `d2/d3` 重心参数化。
- **Q-bez-8** `esSegCurve::AddPoint` 走 **`esSegGon::InsertPoint`**+undo **0xf2ef**，而 `esSegBezier::AddPoint` 走 `InsertPoint1`+**0xf2ea**——曲线与折线的"插点"撤销码不同源（Undata 分支也独立）。

## 4. esSegFreeBezier（9 个）（: esSegBezier；随手画自由曲线）

随手画工具后端：进度中由 `SetPointPos(mode1)` 追加采样并即时抽稀，完成后 `SetPointPos(mode2)` 走 `FitToBezierA` 拟合成贝塞尔。type 仍为父类 **0x4703**。

| 函数 | 入口 | 规格 |
|---|---|---|
| `operator=` | `fac0` | 64B 实函数：折叠簇（esSegGon::op=）+ `+0x68`（容量）/`+0x6c`（容差）/`+0x70`（闭合） |
| `ID / isKindOf / className / isOf` | `11cc70 / 11cc80 / 11cd20 / 11cd30` | `"esSegFreeBezier"`；className→`esSegBezier::ID`【Q-axis-1】；isKindOf：不中→`esSegBezier::isKindOf` |
| `ctor(zPoint,ulong)` | `11cdc0` | `+0x70=(param&0x8000)!=0`（闭合）· `+0x6c=param&0xfff`（容差）· `+0x68=100`（容量）；`malloc(100*8)`；**pts[0]=pts[1]=param**、`+0x5c=2`；`Build(0)` |
| `DelSamePoints()` | `11cee0` | `count>2` → `count=esBezier3::FitToBezierA(&pts, count, +0x6c, 1)`（抽稀）；`+4=0x4703` |
| `Build(n)` | `11cf30` | `param==0` → `esSegGon::Build(0)`；否则 `SetPtInfo(pts,NULL,count,fill=1,…)`（开放折线） |
| `SetPointPos(pt,tol,mode)` | `11cf70` | mode==0 → 2；**mode==1（随手画追加）**：距末点 ≤`DAT_1057f308` → 0（忽略）；否则末段长 ≥ `|+0x6c|/2` → 追加 `n=min(dist/(2|tol|)+1, 3)` 个插值点（容量不足 **+100** 重分配，0x8123；上限 `count+n<0x7fff`）；末段短 → **覆写末点**；return 1；**mode==2（收笔）**：`DelSamePoints` + `vtbl+0x7c`（Build）→ 2【Q-bez-9】 |

**怪癖**：
- **Q-bez-9** 随手画采样：距离阈 `DAT_1057f308`（忽略）+ 末段 `|tol|/2`（改判覆写/追加）+ 单步最多 3 点 + 容量粒度 100——采样节奏由这四个常量共同决定；`+0x6c` 在 ctor 处取 `param&0xfff`（低 12 位）。

## 5. esSegSimpleSingleAxis（13 个）（: esSegRuler；成员类型字 0x5002；单线刻度尺）

布局见 §0。显示点：`[0..1]` = 轴线两端，`[2..]` = 刻度对（每刻度 2 点，`AddExLine`/`DrawPath`）。

| 函数 | 入口 | 规格 |
|---|---|---|
| `operator=` | `10730` | thunk → `esSegRuler::operator=` |
| `ID / isKindOf / isOf` | `162f0 / 16300 / 163b0` | `"esSegSimpleSingleAxis"` |
| `ctor()` | `16440` | `esSegRuler` + vftable + **type=0x5002** |
| `ctor(zPoint)` | `16470` | `+0x5c=2`（2 控制点，alloc）；`pts[0]=(x,y)`；**`pts[1]=(x,x)`**（第二端点 y 写成 x）【Q-sax-1】；`+0x6c=+0x6e=400`；**`+0x70=1`** |
| `Load(page,subj,dp)` | `17030` | 门 +0x34（空→Build）；`AddPenEx`；`+0x38>3` → 刻度：`pts[2..]` 每 2 点一对 `AddExLine`；`param+4` 笔非空 → `AddPen`；`esScriber::LoadLine(pts, pts+1)` 主线 |
| `Draw(render,dp,matrix)` | `17240` | `CreatePen(dp+4)`；`+0x38>3` → `egPath(pts+2, flags+2, count−2)` + `DrawPath`（刻度折线）；`esScriber::DrawLine(pts,pts+1)`；删笔 |
| `DoSnap(mgr)` | `17400` | `SnapPoint(基点)`（+0x58 控制点[0]）；`GetChkAndStep` → 步长；`GetLR` → 左右容量/步长=刻度枚举数；方向符 = `pts[1].y(+0xc) < pts[1].x(+8)` 时取负（**同点 cross 比较**）【Q-sax-8】；`for n=−左..右: SnapPoint((n*步 + 基点.x, 基点.y))`；`SnapObj(pts, 2 点, 0x1000)` |
| `GetLbcLines(list,matrix,n)` | `175a0` | `FUN_1037fc10(this, 显示点, 0)`（单段；与 esSegSurface::GetLbcLines 折叠） |
| `GetLR(&l,&r)` | `175e0` | `l=abs(pts[0].x − pts[1].x) − 2000`；`r=abs(pts[1].y − pts[0].x) − 2000`；各 clamp ≥0【Q-sax-8】（**右支用 pts[1].y 减 pts[0].x**，原样） |
| `GetPts(&pts,&flags)` | `176a0` | 门 +0x34（空→`vtbl+0x7c(0)` 再取）；子类判别：类型字 **==0x5001 → 4 点**否则 2 点；memcpy 点+flags 归还（调用方释放） |
| `Build(n)` | `17780` | `GetLR` → **`esSegRuler::GetBiaociPts`**（基类刻度生成）；写 4 个端点（取 pts[1].x / pts[0].y 等分量，原样）；`+0x68≠0` → 逐点 `Rotate(角度)`；`SetPtInfo(…,count,0,1)` |

**怪癖**：
- **Q-sax-1** `ctor(zPoint)` 把 `pts[1]` 写成 `(x, x)`（y 分量=横坐标）——初始控制点即异常；首帧显示点由 `Build` 重建，但未 Build 前的任何读取（如 GetLR）都用错值。
- **Q-sax-8** cross 比较双处：`GetLR` 右支 `|pts[1].y − pts[0].x|`；`DoSnap` 方向符比较 `pts[1].y < pts[1].x`——同一字段混用作 x/y 坐标，疑原版笔误（影响刻度枚举范围与方向）。

## 6. esSegSimpleAxis（17 个）（: esSegSimpleSingleAxis；成员类型字 0x5001；十字轴）

布局见 §0。显示点：`[0..3]` = 两条轴的四端点（`[0..1]`、`[2..3]` 各一段），`[4..]` = 四向刻度对。控制点 3 个：`[0]`=中心（两轴交点）、`[1]`/`[2]` = 两对角臂端。

| 函数 | 入口 | 规格 |
|---|---|---|
| `operator=` | `10820` | thunk → `esSegSimpleSingleAxis::operator=` |
| `ID / isKindOf / className / isOf` | `14720 / 14730 / 147d0 / 147e0` | `"esSegSimpleAxis"`；className→**`esSegSimpleSingleAxis::ID`**【Q-axis-1】 |
| `ctor()` | `14870` | `esSegSimpleSingleAxis` + vftable + **type=0x5001** |
| `ctor(zPoint)` | `148a0` | `+0x6e=+0x6c=400`；**`+0x70=0`**；`+0x5c=3`（3 控制点，alloc 24B，全 = param）【Q-sax-2】 |
| `SetPointPos(mgr,mode,flags,matrix)` | `149a0` | mode==1：`GetSnapPoint` → 对基点（pts[0]）分量差 `local_28=|Δy(pts+0xc)|`、`local_24=|Δx(pts+8)|`；`flags&8`（逗号表达式）→ **两差取 max（正方形化）**【Q-sax-5】；象限常量 `DAT_1057f528/534/50c` 选长边分配：`pts[1].y(+0xc)=角y−d28、pts[2].x(+0x10)=角x+d24`（或对调）；中心 `pts[0]`=两角中点；角点 `ResetSnapPointPos` ← 返回 1；否则 2 |
| `MovePoint(pt,i,flags,check)` | `14d70` | `!(flags&8)`（单点直拖）：i=0→`pts[0]=(x,y)`、1→`pts[2].x`、2→`pts[1].x`、3→`pts[1].y`、4→`pts[2].y`；随后 **4 条保序夹紧**（`pts[1].x≤pts[0].x≤pts[2].x`、`pts[1].y≤pts[0].y≤pts[2].y`）【Q-sax-6】；`flags&8`：i=0 → 3 点整体平移；i>0 → 等长缩放（方向常量 ±5000 → 对应边外扩/内收），方向角写 `+0x68`（`GetAngle_x/y`） |
| `DoSnap(mgr)` | `151f0` | 门 +0x34（空→`vtbl+0x7c`）；`SnapPoint(中心)`；**`+0x70&3≠0` 才枚举刻度**：`GetChkAndStep`、`GetLREx`、四向枚举数=距离/步长（带符号取绝对）；x 向符号 `=(pts[2].x<pts[1].x?−1:+1)×步`；y 向同构；逐刻度 `SnapPoint((±n·步+中心.x, …))`；`SnapObj` 两段（`pts[0..1]`、`pts[2..3]`，0x1000）【Q-sax-2】 |
| `GetLbcLines(list,matrix,n)` | `154b0` | 两段 `FUN_1037fc10(显示点)`、`FUN_1037fc10(显示点+2)` |
| `GetLREx(&nx,&px,&ny,&py)` | `15510` | `nx=abs(pts[0].x−pts[1].x)−2000`、`px=abs(pts[2].x−pts[0].x)−2000`、`ny=abs(pts[2].y−pts[0].y)−2000`、`py=abs(pts[1].y−pts[0].y)−2000`；各 clamp ≥0【Q-sax-4】 |
| `Build(n)` | `15670` | `GetLREx` → **`GetBiaociPts`**（本类重写：生成 4 端点+四向刻度串）；写端点；`+0x68≠0` → 逐点 `D2DPointF`+`Rotate`；`SetPtInfo(…,0,1)` |
| `GetBiaociPts(...)` | `15890` | **`+0x70&3==0` → 仅 4 端点（0x20B）**；否则 `GetChkAndStep` 步长：`count=4+2*(nX+nY)`（nX=左/步+1+右/步、nY 同）；刻度长 3 级：正向齿 `±uVar6(+0x6e=400)`、中档 `±(3/4·uVar6)`（`&0xc==4` 时=全长）、短档 `±(uVar6/2)`（步==2 时=中档）；**中刻度位=`步==10?5:1`**；方向位 bit0=负向、bit1=正向【Q-sax-3】；flags 交替 0/1 |
| `Load(page,subj,dp)` | `15d50` | `AddPenEx`；`count>5` → 刻度对 `AddExLine`；`AddPen`；`LoadLine` ×2（`pts[0..1]`、`pts[2..3]`） |
| `Draw(render,dp,matrix)` | `15fa0` | 笔；`count>5` → `DrawPath` 刻度；`DrawLine` ×2（两轴） |
| `GetCtlPts(list,n)` | `16150` | `pt[0]=+0x58[0]`（中心）；`pt[1..4]` ← **显示点逆序** `safe[3],[2],[1],[0]`【Q-sax-7】 |

**怪癖**：
- **Q-sax-2** `+0x70` 刻度位：SingleAxis ctor=1（刻度默认开），SimpleAxis ctor=**0**（默认刻度全关）；`GetBiaociPts`/`DoSnap` 均以此&3为门——本批未见除 ctor 外的写入方（推测由编辑器 UI 直接改），故"十字轴默认无刻度"的观感来自这里。
- **Q-sax-3** 三级刻度长与"中刻度位"：`步==10` 时中档出现在 mod 5，否则 mod 1；长度档 `400/300/200`（`&0xc==4` 特例=全 400）——刻度的长短节奏由步长与 `+0x70` 位共同决定。
- **Q-sax-4** `GetLREx`/`GetLR` 统一安全边距 **2000（=5mm）**，两端各减后再 clamp 0——轴臂短于 5mm 时不再枚举刻度。
- **Q-sax-5** `SetPointPos` 对称模式用逗号表达式把两差"取 max"方形化（`param_3&8`）；象限常量选长边分配（`528/534/50c` 三个角度常量）。
- **Q-sax-6** `MovePoint` 非对称模式改分量后立即**保序夹紧四连**（单点不能穿越中心）；对称缩放用 ±5000 方向常量 + 角度写回 `+0x68`。
- **Q-sax-7** `GetCtlPts` 把显示点**逆序**映射回 5 个控制柄（`safe[3..0]→pt[1..4]`）——柄序号与显示点序号相反。

## 7. 本批残余与待查

- `esAxisObj`（0xDC 内嵌体）为 eslib 内**外类**：本批只覆盖 esSegAxis 对它的调用面（`InitSize/IsRevX/IsRevY/Build/GetContentRect/GetSnapPointBy/GetLabel/SetLabOffset/GetBounds/OnUndata/LoadProp/SaveProp/CopyFrom/Draw/DrawLab/Load`）；其内部字段（+0x84..+0xb4 等，SaveProp 快照面）未逐字段审计，待独立批次。
- 数值常量待提取：`DAT_1057f170`（esSegCurve 张力系数）、`DAT_1057f020`（退化阈值）、`DAT_1057f308`（FreeBezier 采样阈）、`DAT_1057f070`（SetTextBoxPostion eps）、`DAT_1057f5b8`（1.0 判定）。
- 轴的"两臂视觉朝向"（哪侧是正向、Rev 位实际观感）只按条件式原样记录，未做画面对照验证。
- `esSegSimpleAxis +0x70` 刻度位的运行时写入方未找到（除 ctor）。
- `esSegBezierLink / esCtrlBezier / esBezier3（FitToBezierA/LinkBezier）` 未覆盖（属其它批次）。
- 标签盒默认文案表 `DAT_1069dd58`（3 项）内容未提取（预期 O/x/y）。
