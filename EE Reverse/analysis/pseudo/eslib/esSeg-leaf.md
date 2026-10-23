# eslib 绘图叶段族 — 反编译规格（阶段 2 · 第六批 · 绘图核心 2/6）

- 模块：eslib.dll；函数：**174 个**（esSegGon 38 · esSegRect 35 · esSegCircel 31 · esSegRoundRect 24 · esSegLine 23 · esSegPoint 13 · esSegRectEx 10）
- 伪代码（原样）：`analysis/pseudo/eslib/esSeg-leaf.decomp.txt`（matched=174 dumped=174）
- 类型头：`analysis/types/esSeg-leaf.h`
- 台账：174/174 → `decompiled`（status-overrides）
- 角色：第四批 `esSeg` 基座的**具体叶段实现**（直线/折线/矩形/圆角矩/圆/点/扩展矩形）。本批同时定下各族的编辑器内字段布局、点操作、吸附约束族（esSnapManager 交互）、撤销码。

## 0. 谱系与公共结构（本批结构性结论）

| 结论 | 证据 |
|---|---|
| `esSegLines → esSegGon → esSegLine`（**Gon 是 Line 的父类**；三者共用 +0x58 点数组 / +0x5C 计数） | ctor 链：esSegGon `e2d0` 调 esSegLines；esSegLine `eb80` 调 esSegGon |
| `~esSegCircel`(f050) 与 `~esSegLines`/`~esSegPolygon`/`~esSegRect` **折叠同址** → 四类统一走 `esSegGemotry::~esSegGemotry` | 0xf050 ILT 4 符号 |
| `operator=` 梯：RectEx→Rect→esSegGemotry；RoundRect→esSegGemotry（+1 dword）；Gon→esSegLines；Circel→esSegGemotry（+9 dword） | f3d0/f070/f5f0/f6e0/f810 |
| `esSegLine` 对象可承载**任意类型字**（ctor `ebb0` 直写 param_4）；引擎用临时类型字 **0xe100..0xe10b 进入交互吸附模式**，由 `esSegLine::SetPointPos` 按 type−0xe100 分派（圆族同理 **0xe280..0xe289**，见 §5） | SetPointPos `eec0`；Circel SetPointPos `123070` |
| "Set\*Line"族返回码语义（推定，全族一致）：**1**=仅更新自由点 **2**=吸附命中（AnyMove + type 复位 0x4701） **4**=吸附类型已锁定 | 全族一致 |

**类型字/尺寸**（工厂表见第四批 spec §2.1）：0x4701 esSegLine(0x68) · 0x4702 esSegGon(0x68) · 0x4281 esSegRect(0x70) · 0x4283 esSegRoundRect(0x6c) · 0x4284 esSegCircel(0x8c) · 0x6001 esSegPoint(0x68) · 0xd083 esSegRectEx(0x70)。

## 1. esSegLine（23 个）（0x4701；谱系叶）

布局：`+0x58` 点数组（2 点，TagPOINT×2）· `+0x5C` 计数 · `+0x4C` 矩阵（Gdiplus::Matrix，基座布局）。

| 函数 | 入口 | 规格 |
|---|---|---|
| `ID / isKindOf / isOf` | `ea40 / ea50 / eaf0` | `"esSegLine"`；isKindOf 先比自身名，不中→`esSegGon::isKindOf`（谱系回退 Line→Gon→Lines） |
| `ctor()` | `eb80` | `esSegGon::esSegGon` + vftable + **type=0x4701** |
| `ctor(zPoint,ushort type)` | `ebb0` | `esSegGon(z,z)`（两点同） + vftable + **type=param_4**——通用"指定类型字"构造，引擎借此把同一对象切成 0xe1xx 交互模式 |
| `ctor(zPoint a,zPoint b,Matrix*)` | `ebf0` | `esSegGon(a,b)` + type=0x4701；矩阵空→`AnyMove(this, b, 1, 0)`（把第 1 点拖到 b＝两点直线），否则 `FUN_10027140(matrix,0)` 挂矩阵 |
| `GetClipLine(t1,t2)` | `eca0` | t1==t2→NULL；取 `P(t)=p0+(p1−p0)·t`（zFtoL 取整）两点 → `FUN_1012be30(第二点)`==0 时**新建 esSegLine(P1,P2,this+0x4C)**（共享矩阵）；命中→NULL |
| `SetPointPos(mgr,mode,flags,mtx)` | `eec0` | **按 m_type−0xe100 分派**：0→SetAngleLine·1→SetVertical·2→SetCVertical·3→SetMeanLine·4→SetTangent·5→SetPingLine1·6→SetPingLine2·7→SetVLine·8→SetHTangent·9→SetVTangent·0xa→SetGongTangent·0xb→SetCurveTangent。default（自由拖动）：退化线先存原位到静态 `DAT_106cd210`（TLS 懒初始化）；mode==1→`point[1]=Invert(snap)`，flags&8→`point[0]=2·原位−point[1]`（镜像）否则 `point[0]=原位`；mode≠1→`AnyMove(snap)`+type=0x4701+return 2 |
| `SetAngleLine` | `f2c0` | 定角：mode1→point[1]=Inv+point[0]=point[1]；`SetSnapType(1,1)`→4。mode2→point[1]=Inv；`SetSnapType(1,1)`→point[0]=Inv+4。else `GetAnglePoint`→AnyMove+0x4701+2；否则 point[1]=Inv。返回 1 |
| `SetGongTangent` | `f4c0` | 公切：mode1→折叠（point[0]=point[1]）+`IsSnapped(0x20)`+`SetSnapType(1,1)`+`SetSnapType(0x20,1)` 全中→4。else `GetGongQieLine`；==0→point[1]=Inv+point[0]=point[1]；≠0且 flags&0x10→AnyMove+0x4701+2；否则 point[0]=Inv(切线点)、point[1]=Inv(snap) |
| `SetVertical` | `f6d0` | 竖直：mode1→`SetSnapType(0x10,0)`→4（无折叠）；否则以 point[0] 为基准 `GetVerticalPoint`→命中且&0x10→AnyMove+0x4701+2；尾 point[1]=Inv。返回 1 |
| `SetTangent` | `f800` | 切线：mode1→`SetSnapType(0x20,0)`→4 时**先把 point[0] 存 DAT_106cd218/21c**；未锁定→point[1]=Inv。else **先恢复 point[0]=静态值**；`GetTangentPoint`→命中且&0x10→AnyMove；**ret==−1 时 point[0] 关于 point[1] 镜像**（2p0−p1）+type=0x4701+2；尾同镜像逻辑+point[1]=Inv |
| `SetCurveTangent` | `fad0` | 曲线切线：mode1→`SetSnapType(0x40,0)`→4；否则以 point[0] 为基准 `GetCurveTangentPoint`→命中且&0x10→AnyMove+0x4701+2；尾 point[1]=Inv。返回 1 |
| `SetCVertical` | `fbf0` | 连心竖直：mode1→折叠+`SetSnapType(1,1)`→4。mode2→point[1]=Inv；`SetSnapType(1,1)`→**两点都设为平均点**（(x0+x1)/2,(y0+y1)/2，÷DAT_1057f298）→4。else `GetCVertPoint`→命中且&0x10→AnyMove+0x4701+2；否则 point[1]=Inv |
| `SetMeanLine` | `fea0` | 中线：mode1→折叠+`IsSnapped(0x10)`且`SetSnapType(0x10,1)`→4。mode2→折叠+`IsLineInersction`且`SetSnapType(0,1)`→4。else `GetMeanLine`→point[0]=Inv(A)、point[1]=Inv(B)；&0x10→AnyMove+0x4701+2 |
| `SetVLine` | `110110` | 垂线：mode1→折叠+`SetSnapType(1,1)`→4。mode2→point[1]=Inv；`SetSnapType(1,1)`→point[0]=point[1]+4。else `GetVLinePoint`→命中且&0x10→AnyMove+0x4701+2；否则 point[1]=Inv |
| `SetPingLine1` | `110300` | 平行线1：mode1→折叠+`IsSnapped(0x10)`且`SetSnapType(1,1)`→4。mode2→折叠+`SetSnapType(1,0)`→4。else 以 point[0] 为基准 `GetPingPoint`→命中且&0x10→AnyMove+0x4701+2；否则 point[1]=Inv |
| `SetPingLine2` | `110530` | 平行线2：mode1→折叠+`IsSnapped(0x10)`且`SetSnapType(0,1)`→4。else `GetPingLine(point[0],snap)`→命中且&0x10→AnyMove+0x4701+2；否则 point[0]=Inv(第一交点)、point[1]=Inv(snap) |
| `SetHTangent` | `1106e0` | 水平切：mode1→折叠+`IsSnapped(0x10)`且`SetSnapType(0x20,1)`→4。else `GetHTangent`→point[0]=Inv；命中且&0x10 时：mode==3→AnyMove+0x4701+2；mode==2 且`SetSnapType(1,2)`→point[1]=Inv+4。尾 point[1]=Inv |
| `SetVTangent` | `110900` | 竖直切：mode1→折叠+`IsSnapped(0x10)`且`SetSnapType(0x20,1)`→4。mode2→`GetVTangent`→命中且&0x10→`SetSnapType(1,2)`+AnyMove+**4**；否则 point[0]=Inv(A)+point[1]=Inv(B)。else（含 mode3）→`point[1].x=Invert(snap).x`（只写 x）；&0x10→0x4701+2 |
| `MoveAcmePoints(vg,pt,flag)` | `110b10` | type==0x4702→`esSegBezier::MoveAcmePoints`；否则 flag==1 且 pt 非空→`esVertexGroup::GetAcmeList`+AnyMove；返回 1 |
| `MovePoint(zPoint,idx,flags,chk)` | `110ba0` | type==0x4702→`esSegGon::MovePoint`；else **链单点**（+0x3C==+0x40）且 flags&8→`esSegGon::ExtendingLine`；else `AnyMove(this,pt,idx,0)`；尾 `esSegLines::MoveLinkPoint(this, idx==0?flags&0x200:flags&0x100, chk)` |
| `BuildEx(esSeg*,t)` | `110c50` | type==0x4702→`esSegGon::BuildEx`；src==NULL 或 t≥DAT_1057f0b4→`vtbl+0x7C()`（普通 Build）；点数相等→分配临时数组、逐点 `esSeg::step`（本点→对点插值）→`SetPtInfo(tmp,NULL,n,1,0)`；否则 vtbl+0x7C |

注：`SetTangent` 用的 `FUN_10027af0` 是 PointF 构造辅助；`GetMeanLine` 前置两个 `FUN_10027af0()` 为同族调用（反编译丢参）。

## 2. esSegGon（38 个）（0x4702；esSegLine 的父类）

布局：`+0x58` 控制点数组（ushort 计数 +0x5C）· `+0x34/+0x38` 安全点缓存（基座）。**点含义**：0x4702 为多边形控制点；0x4701 两控制点同 lerp 源。

| 函数 | 入口 | 规格 |
|---|---|---|
| `GetPointCount()` | `eb10` | `return (ushort)(this+0x5C)`；**ILT ≡ esSeg::GetVertexCount** |
| `operator=` | `f6e0` | 转 `esSegLines::operator=` |
| `ID/isKindOf/isOf` | `e180/e190/e240` | `"esSegGon"`；isKindOf 不中→`esSegLines::isKindOf` |
| `ctor()` | `e2d0` | esSegLines + vftable + **type=0x4702** |
| `ctor(tagPOINT*,int,Matrix*)` | `e300` | 计数→+0x5C；`operator new(count*8)` 拷贝点；矩阵非空→`epCloneMatrix(this+0x4C, m)` |
| `ctor(zPoint,zPoint)` | `e5f0` | 2 点版（count=2，写两点） |
| `BreakLine(int*,int)` | `e3f0` | 非闭合→`esSegLines::BreakLine` 原样。闭合（IsCyclical）：`esSeg::OnBreakLine(this,0)` 摘出得 owner；断口 idx=*param_1；若 `0<idx<count−1`：**点数组旋转**——idx 起的 (count−1−idx) 点前移、原前 idx 点接后、末补首点（闭合）；undo `Rec_Data(0xf2ff,4B=前移段长)`；vtbl+0x44(0) |
| `FromBezer(PointF*,n)`(static) | `e6d0` | **每 3 点取一**建折线：count=n/3+1；逐点 D2DPointF→ptftopt 存回 |
| `CheckFirstLastLink(double)` | `e800` | count>3 且末点到直线 p0→p1 距离<DAT_1057f1f8 → `p0=末点`、`count−−`（去首尾重复）、标改、return 1 |
| `ResetMatrix()` | `e8e0` | type==0x4701→置 0x4702；`TransformPoints(pts,n)`+FUN_100272d0（矩阵复位） |
| `Normatllize()` | `e930` | type 0x4702/0x4703→原地变换+复位，返回 NULL；type 0x4701/0x4704→**新建 esSegGon 拷贝点**并变换，返回新对象（Gon 化） |
| `SnapFarPoints(mgr,pt,thr,skip)` | `112140` | +0x34 安全点存在时：逐点（跳过 \|skip\|）世界坐标化；`\|dx\|<=thr`→`AddSideLine(点,dx,pt,0)`、`\|dy\|<thr`→`AddSideLine(点,dy,pt,1)`（为吸附登记垂直/水平辅助线） |
| `LinkTo(other)` | `112240` | 同类型才联：`GetCompos(other)` 无变换 → 0x4704 拒绝，否则两方 `ResetMatrix` 后 `AddLines(other, this->pts, count−1)`；有变换 → 拷贝本点、逆变换、0x4704 要求逐边水平/垂直（两轴差>1 即拒绝）、`AddLines(other, tmp+1, count−1)`；成功后 `other->vtbl+0x44(0)`、返回 1 |
| `SnapPointWhenCreate(mgr)` | `1124b0` | `+0x38` 显示点存在：`IsSnapable(2)`→`SnapPoints(ptrs, display−3, 2)`；type==0x4702 且 ctrlCount<0x14 且 `IsSnapable(8)`→逐段**中点**`SnapPoint(mid,8)` |
| `DoSnap(mgr)` | `1125d0` | 无安全点先 Build；type∈{0x4701,0x4702,0x5004,0x4704,0x4c0e}：`SnapObj(safe,flags,display,0x1000)`+`SnapPoints(all,2)`+中点吸附(<0x14 点)；其它类型只对**首末点**`SnapPoint(...,2)`。恒 return 0 |
| `Undata(id,data,&sz)` | `1127a0` | **0xf2ef**（撤销"删点"的逆）：取 {index}，构造 12B{index,x,y} 自当前点、`DelPoint(index)`、返 0xC、id→0xf2ee；**0xf2ee**：取 {index,x,y}`InsertPoint`、返 4、id→0xf2ef；**0xf2ff**：按存值旋转点数组（同 BreakLine 公式）、原地、id 不变；其它→`esSeg::Undata` |
| `AppendPoint(zPoint)` | `112a80` | 若新点与末边**共线**（(p0−q)×(p1−q)==0）→直接**替换末点**；否则 `AddLines(1)` 追加 |
| `GetSnapPoints(out,zRect&,lenient)` | `112b20` | ctrlCount<2 或 >100→0。**集 A** {0x4702,0x5004,0x4c0e,0x4704,0x4488,0x4705,0x4489}：取显示点（==ctrlCount 用 +0x34 否则 +0x58 并变换）→**剔除同 x/同 y 延续的共线中间点**成简化轮廓；`简化数*4<ctrlCount`→0；lenient：去首尾重复；首=x/首=y 与首末相同→再退 1 点；`==4 且 ctrlCount==5`→out[3]=zRect::CenterPoint；最后 `zRectTempl::ResetFrom(out,n)`。**集 B** {0x4701,0x6005,0x410d}：首点/末点 2 点→SetRect+NormalizeRect，返回 2。否则 0 |
| `FitLines(a,b)` | `112fc0` | count>3：`esBezier3::FitToBezierA(&pts,n,a,b)` 新计数→+0x5C；Build(0) |
| `AddPoint(zPoint,flag,d)` | `113020` | 拷贝点集变换后：与**任一点**距离≤d→return 2；扫描每线段 `GetPtToLineDistance`≤d 命中→flag==0 时取垂足 Invert 回局部（0x4704/0x4488 保持轴向坐标）→`InsertPoint(i+1,pt)`→标改→undo `0xf2ef`(索引)；**type==0x4701 时 undo `0xf2e8` 并升 type 0x4702**；返回 1（未命中→0） |
| `InsertPoint(idx,pt)` | `1133d0` | count++ 新分配、前后段拷贝、写点、free 旧指针（**free 后写 0x8123 毒哨兵，见 Q-gon-1**）；标改。**ILT ≡ esSegLinkHVLine::InsertPoint** |
| `DelPoint(idx)` | `1134e0` | 同上删除版；**ILT ≡ esSegLinkHVLine::DelPoint** |
| `DeletePoint(idx,probe)` | `1135e0` | 边界检查；**闭合且 count≤4 拒绝**。0 点：无 prev 时非闭合→允许=count>2，闭合且挂 esSegList(0x2030)→问链表 amulet 对象 `vtbl+0xBC` 裁定；末点同型（用 +0x3C）。0x4704/0x4488 中间点：邻居 x 或 y 相等才可删。probe≠0→只 return 1；否则 `RemoveControlLink`+标改；count<3→**自毁**（vtbl+0x14 + vtbl+0x5C(0,0)），否则 undo `0xf2ee`(12B{idx,x,y})+DelPoint |
| `GetNextPoint(idx,out)` | `1139d0` | idx<count−1→pts[idx+1] 变换；末点：有 next 且 next.type==0x4702→**next 的 pts[1]**；无 next 且闭合挂链→list 头(+0x34) 若 0x4702→其 **pts[1]**；否则 0 |
| `GetBreakLines(list,flag,brks,n)` | `113b40` | 若有合法断口（0<idx<count−1）：逐段 `esSeg::Create(this.type)`+`AddLines(pts+start,(end−start)+1)`+矩阵克隆（`esParaLine::GetCompos(obj)+4 ← this+0x4C`）→尾插 list；再对**环绕段** `AddLines(list->tail, this->pts+1, brks[0])` 补闭合 |
| `GetBackPoint(idx,out)` | `113d40` | idx≥1→pts[idx−1] 变换；首点：有 prev 且 0x4702→**prev 的 pts[count−2]**；无 prev 闭合挂链→list 尾(+0x38) 若 0x4702→其 **pts[count−2]**；否则 0 |
| `GetNearPt(&pt,idx,flag)` | `113ea0` | flag==0：用 GetBack/GetNextPoint 取邻居，x 取 \|dx\| 更近者、若 <**0x259(601)**→吸附 pt.x；y 同。flag≠0：取 idx=count−2（idx==−3 时 count−1，clamp≥0）单点，\|dx\|、\|dy\|<601 吸附 |
| `BuildEx(src,t)` | `114090` | src==NULL 或 t≥DAT_1057f0b4→Build(0)；计数相等→逐点 `esSeg::step` 插值到临时数组→`vtbl+0xF0`(BuildLines(tmp,n))；否则 Build(0) |
| `BuildLines(pts,n)` | `1141b0` | `SetPtInfo(this,pts,NULL,n,1,1)`；`pts!=+0x58` 时 `FUN_10528fdd(pts,8)`（**operator delete[]**，接管所有权） |
| `Build(int)` | `114210` | `vtbl+0xF0(+0x58, +0x5C)`（用控制点重建显示点） |
| `MovePointTo(other,pt,which,noundo)` | `114240` | other==this 且 count<3→0；noundo==0：目标 idx=（which==0?count−1:0），undo `0xf2dc`(16B{idx,idx,x,y})，Invert(pt)→写 pts[idx]、标改；返回 1 |
| `SetPointPos(mgr,idx,flags,mtx)` | `114360` | GetSnapPoint→Invert→浮点对；flags&8→`GetNearPt(…, idx, 1)`；**idx==0**→count−−、`count<2?2:3`；**idx==count**→count++ 重分配后追加；写 pts[idx]=pt、逆变换、`ResetSnapPointPos`；返回 1。**ILT ≡ esSegPipe::SetPointPos** |
| `GetAcmePoint(idx)` | `114500` | idx<0→0；pts[idx] 世界化输出 |
| `SetAcmePoint(idx,pt)` | `114570` | idx<count；idx<0→count−1；Invert 写 pts[idx]；返回 1 |
| `ExtendingLine(zPoint,which)` | `114660` | 仅 which∈{0,1}；段非水平（两端 y 不等）时：测段长/角度（pttoptf→GetAngle_x→FUN_10027170 轴向吸附），**先把 pts[which].y=pts[1−which].y**；再写 `pts[which].x=Invert(zPoint).x`（水平延长） |
| `MovePoint(zPoint,idx,flags,chk)` | `114830` | flags&8：**孤点两段线**（count==2 且无前后邻）→`ExtendingLine`；否则 `GetNearPt(&pt,idx,0)`。Invert(pt) 变了才写；分流：`(type&0x1C0)==0x100`→idx0/末点各 `MoveLinkPoint(flags&0x200/0x100)`；否则闭合（IsCyclical）时 idx0↔末点**同步复制**保持闭合 |

**怪癖**：
- **Q-gon-1** `InsertPoint`/`DelPoint`/`SetPointPos` 释放旧数组后**先在 +0x58 写 0x8123 再覆盖**（与第四批 Q7 同型"毒哨兵"惯例）——待差分复核。
- **Q-gon-2** `GetSnapPoints` 的"简化轮廓"算法对自交/重复点依赖 `local_14` 状态机（-1/-2 哨兵），非数学稳健共线剔除。
- **Q-gon-3** `esSegGon::SetPointPos` 的 `idx==0 → count−−` 分支无内存重分配（只改计数），**疑似交互建模的"撤销新建点"语义**，待动态验证。

## 3. esSegRect（35 个）（0x4281；esSegRectEx 的父类）

布局：`+0x58` 两点 **[0]=(L,T)、[1]=(R,B)**（tagPOINT×2）· `+0x5C`=2 · `+0x68` byte 样式（低 3 位=**Acme 样式**；bit4 `0x10` 与样式 1 联动，见 SaveProp）· `+0x6c` float **s=锁定比 W/H**（`ResetLockedScale`）· `+0x34/+0x38` 显示点（Build 后 5 点 **TL,TR,BR,BL,TL**）· `+0x4C` 矩阵。
**Acme 点序**（GetCurAcmePoints / GetPointAt 一致）：0=TL 1=BR 2=TR 3=BL 4=L-mid 5=R-mid 6=T-mid 7=B-mid。

| 函数 | 入口 | 规格 |
|---|---|---|
| `ID / isKindOf / isOf` | `109b00 / 109b10 / 109bc0` | `"esSegRect"`；isKindOf 不中→`esSegGemotry::isKindOf`；isOf 仅比自身 |
| `className()` | `109bb0` | **ILT 5 符号折叠**（esSegCircel/Lines/Polygon/Rect/RoundRect 同址）→ 返回 `esSegGemotry::ID()`（家族不报自身类名） |
| `ctor()` | `109c50` | esSegGemotry + vftable；+0x6c=0；+0x68=0 |
| `ctor(zPoint&,ushort type)` | `109c90` | type=param_4；count=2；**两点同值**（退化矩形、"跟随光标"创建态）；+0x6c/+0x68=0 |
| `ctor(tagRECT*)` | `109d90` | type=0x4281；写四边；`ResetLockedScale`；**+0x68=0x11**（样式 1 + bit4） |
| `ctor(zPoint&,zSize&)` | `109ea0` | type=0x4281；pts[0]=p、pts[1]=p+size；+0x6c/+0x68=0 |
| `GetRectPoints(tagPOINT*)` | `109fb0` | 填 5 点 TL,TR,BR,BL,TL |
| `GetPointAt(idx)` | `10a440` | x：0/3/4→L、1/2/5→R、余→mid；y：0/2/6→T、1/3/7→B、余→mid（即上表 Acme 点序；返回值经隐藏指针） |
| `GetBreakLines(list,flag,brks,n)` | `10a0e0` | 断口重画可见边；见下**注**（param_2 未用） |
| `SetRect(l,t,r,b)` / `SetRect(tagRECT*)` | `10a590 / 10a600` | 写四边 + `ResetLockedScale` |
| `SetPointPos(mgr,mode,flags,mtx)` | `10a680` | 拖 **BR 点**定尺寸：mode≠1（收尾）→ 若 s==哨兵常量（PTR_1057ef28）则 `ResetLockedScale`，return 2；mode==1：`!(flags&8)` 且 **type==0xa010（esSegImage）** 且 s>eps → 锁定比（R=L+s·dx、B=T+dy）；`flags&8` → **正方形**（m=max(\|dx\|,\|dy\|) 各轴 ±m）；否则自由写 (R,B)；尾 `ResetSnapPointPos(R,B)`；返回 1=变化 / 0=无变化 |
| `MoveAcmePoints(vg,pt,flag)` | `10a9a0` | flag==1 且 acme 数<4 → `MovePointForFree(点数组, 拖动点, …)`（反编译丢参）+ `ResetLockedScale`，返回 1；否则 0 |
| `MovePoint(zPoint,idx,flags,chk)` | `10aa40` | Invert→`idx<4 且 s>eps` 时：**(style&7)==1 → 未按 flags&8 时走锁定路径**，其它样式按 flags&8；本地标志==0→`MovePointForFree`+`ResetLockedScale`，否则 `MovePointForLock(…,s)` |
| `MovePointForFree(pts,x,y,idx,flags)` (static) | `10c100` | flags&8=0 直写：0→(L,T) 1→(R,B) 2→(R,T) 3→(L,B) 4→L 5→R 6→T 7→B；flags&8=1：**成对对称扩缩**（0/1、2/3 对角相向；4/5 只动 x 双端；6/7 只动 y 双端） |
| `MovePointForLock(pts,x,y,idx,s)` (static) | `10be20` | `get_scale(s,…)` 等比后按 idx 从对边反推：0→L=R−s·dx,T=B−dy；1→R=L+s·dx,B=T+dy；2→R=L+s·dx,T=B−dy；3→L=R−s·dx,B=T+dy |
| `get_scale(s,dx,dy)` (static) | `10bd10` | \|s\|≥eps 才作用：dx/=s；**m=max(\|dx/s\|,\|dy\|)**；dx、dy 各取 ±m（等比化） |
| `ResetLockedScale()` | `10c430` | s=\|W\|/\|H\|（H==0→0；abs=FUN_10027ae0） |
| `GetCurAcmePoints(&n)` | `10ae50` | (style&7)：**4→NULL（无控点）**；**0→8 点**（全表）；**1→4 点** TL,BR,TR,BL；**2→2 点 L-mid,R-mid**；**其余(3,5,6,7)→2 点 T-mid,B-mid**；+0x34 空先 Build；返回块由调用方 free |
| `SetAcmeStyle(k)` | `10ac30` | style=(style&0xf8)\|k |
| `LoadProp(mgr)` | `10abe0` | 组 **0x2200** 项 **0x2201**=style&7 |
| `SaveProp(mgr)` | `10acd0` | 0x2201 被改时：style=(style&0xf8)\|item；**(item&7)==1→置 bit4**，否则清 bit4；变化则记 0x2201 |
| `Undo(id,…)` | `10ada0` | **0x2201** swap byte；**0x2202** swap float s；其它→基类 ILT（esFormulaBox::CaretMove） |
| `unMPSave(arch)` | `10ab50` | 基类 + float s；读回变化→记 **0x2202** |
| `Serialize(arch,sheet,ver)` | `10b850` | 基类 + byte 样式 + float s；**读档版本门 0x106070a**（sheet 非空且 +0x850 版本 ≤ 门 → 不读 s，`ResetLockedScale` 重算） |
| `CopyFrom(obj,exch)` | `10b8f0` | 基类；obj isOf("esSegRect") → 拷 +0x68 byte、+0x6c float |
| `GetRect()` (const) | `10ac60` | zRect(pts[0],pts[1])+NormalizeRect |
| `DoSnap(mgr)` | `10b3c0` | 无显示点先 Build；`IsSnapable(2)`→acme 点 `SnapPoints(…,2)`；**type==0x4281** 时：`IsSnapable(0x40)`→**中心** `SnapPoint(…,0x40)`；`IsSnapable(8)`→逐**边中点** `SnapPoint(…,8)`；尾 `SnapObj(+0x34,+0x60,+0x38,0x1000)`；恒 return 0 |
| `ClipRect(render)` | `10b5e0` | 显示点→egPath+CloseFigure→`SetClip`；返回 `egGraphics::Save` 令牌 |
| `GetCtlPts(list,flag)` | `10b6b0` | `GetCurAcmePoints`；n==2 时建索引对 **{2·(style&7), +1}**；`esVertexInfo(pts,对,n,this)` 挂链；返回 1/0 |
| `IsEqual(obj,sheet)` | `10b7e0` | 基类 && style && s 全等 |
| `BuildEx(src,t)` | `10b960` | src==NULL/type≠/t≥DAT_1057f0b4→Build；否则 ctrl 两点逐分量 `esSeg::step` 插值→5 点 TL,TR,BR,BL,TL→`SetPtInfo(…,5,1,1)` |
| `Build(n)` (protected) | `10bba0` | 由 ctrl 直接生成 5 点同上→`SetPtInfo(…,5,1,1)` |

**注（GetBreakLines 断口机制）**：断口索引数组（0..7 合法）→bitmask；起点=数组中下标最小的合法断口（逆序扫描覆盖）；沿矩形绕行 **TL(0)→TR(2)→BR(1)→BL(3)→TL**（若下一顶点对应边中点 4=L/5=R/6=T/7=B 也是断口则走中点）：首段 `esSegHVLine(起点, 2, 矩阵=this+0x4C)` + `AddSegObject(list)`，其余 `esSeg::AddLines` 续点；"下一顶点"仍是断口→当前折线收尾、`operator_new(0x44)` + `esSegList` 挂到**旧链 +0x40**开新子链；回到起始断口结束。无合法断口→整体不动作（正常闭合 5 点由 Build 管）。

**怪癖**：
- **Q-rect-1** `SetPointPos` 对 **type==0xa010（esSegImage）** 走锁定比缩放分支——图族与矩形族共享布局/交互代码（写图族规格时注意别重复）。
- **Q-rect-2** `DoSnap` 逐边中点循环 i=0 时读 `pts[−1]`（偏移 `−8+i*8`）——**疑数组前越界读**；与 Q-RoundRect-1 同族，差分/动态复核候选。

### 3.1 esSegRectEx（10 个）（0xd083；esSegRect 子类，未新增字段）

| 函数 | 入口 | 规格 |
|---|---|---|
| `ID / isKindOf / isOf` | `109630 / 109640 / 1096e0` | `"esSegRectEx"`；isKindOf 不中→`esSegRect::isKindOf`；isOf 仅比自身 |
| `ctor()` | `109770` | esSegRect + vftable + **type=0xd083** |
| `ctor(zPoint a,zPoint b)` | `1097a0` | type=0xd083；count=2；写 a,b；+0x68=0 |
| `GetRectSize()` | `109880` | `zSize(\|R−L\|,\|B−T\|)`（abs） |
| `SetRectSize(w,h)` | `109910` | zRect+NormalizeRect→TopLeft 回写 pts[0]；pts[1]=TopLeft+(w,h)；`vtbl+0x44(0)`（标改） |
| `HitTest(ht,sel)` | `1099d0` | `HitTestLines` 命中→`SetSelInfo(7)`（边上）；否则 `IsPtInGon`→`SetSelInfo(8)`（内部）；返回 1/0 |
| `Undata(id,data,&sz)` | `109a50` | **0x5fe**：档中 {w,h}→`SetRectSize`，且把当前尺寸写回档（**交换语义**，undo/redo 双向可走）；其它→`esSeg::Undata` |

## 4. esSegRoundRect（24 个）（0x4283）

布局：`+0x58` 两点 **(L,T),(R,B)**（16B）· `+0x5C`=2 · `+0x68` **指针 → 4 个 int 圆角半径** [0]=TL [1]=TR [2]=BR [3]=BL（16B，`FUN_105290e5(0x10)` 分配）· `+0x4C` 矩阵 · `+0x34/+0x38` 显示点（12 顶点环）。
**12 点环**（GetVertexPoints；r0..r3=min(半径, 半宽, 半高)）：0=(L,midY) 1=(midX,T) 2=(R,midY) 3=(midX,B)；4=(L,T+r0) 5=(L+r0,T)；6=(R−r1,T) 7=(R,T+r1)；8=(R,B−r2) 9=(R−r2,B)；10=(L+r3,B) 11=(L,B−r3)。绕行序 **0→4→5（TL 弧）→6→7（TR）→8→9（BR）→10→11（BL）→0**；侧中 0..3 在对应边上作断口落点。

| 函数 | 入口 | 规格 |
|---|---|---|
| `operator=` | `f5f0` | 转 `esSegGemotry::operator=` + 拷 +0x68（1 dword 指针） |
| `IsEqual(obj,sheet)` | `119340` | 基类 && `memcmp(+0x68, obj+0x68, 0x10)==0`（半径块） |
| `Serialize(arch,sheet,ver)` | `1193b0` | 基类 + **半径块 16B 原始读写**（stream vtbl+8 存 / +0xc 读） |
| `CopyFrom(obj,exch)` | `119410` | 基类；obj isOf("esSegRoundRect") → 拷 4 个半径 int |
| `ID / isKindOf / isOf` | `11fe00 / 11fe10 / 11feb0` | `"esSegRoundRect"`；isKindOf 不中→`esSegGemotry::isKindOf` |
| `ctor()` | `11ff40` | esSegGemotry + vftable + **type=0x4283** + alloc 半径 0x10B（**未清零**、点数组未建，见 Q-RoundRect-2） |
| `ctor(zPoint&)` | `11ffd0` | type=0x4283；半径清零；count=2；**两点同值**（退化） |
| `ctor(zPoint&,zSize&,int round)` | `1200f0` | type=0x4283；四半径=round；pts[0]=p、pts[1]=p+size |
| `~esSegRoundRect()` | `120230` | `free(+0x68)` + `esSegGemotry::~` |
| `GetBreakLines(list,flag,brks,n)` | `120270` | 断口 0..0xb、起点同 Rect；绕 12 点环；直段=`esSegGon(&局部2点,2,矩阵+0x4C)` 新建 AddSegObject（**每段一个对象**，不续接）；角弧见下**注**；遇断口→旧链 +0x40 挂新 esSegList；尾 free 顶点块 |
| `DoSnap(mgr)` | `120890` | 无显示点先 Build；`IsSnapable(0x40)`→**中心** SnapPoint；`IsSnapable(8)`→**4 侧中点** SnapPoint；`SnapObj(+0x34,+0x60,+0x38,0x1000)`；恒 return 0 |
| `unMPSave(arch)` | `120b40` | 基类 + 半径块 16B；读回 memcmp 不一致→`esUndo::Rec_Data(…,0xf2f8,tmp,0x10)` |
| `Undata(id,data,&sz)` | `120c20` | **0xf2f8**：交换 0x10B 半径块（旧值拷出进档、档值拷回对象）+`vtbl+0x44(0)`；其它→基类 |
| `SetPointPos(mgr,mode,flags,mtx)` | `120cb0` | mode≠1→2；mode1：拖 (R,B)，`flags&8`→正方形（m=max(\|dx\|,\|dy\|)）；变化时写回并**四半径=min(\|W\|,\|H\|)/4**（`(v+(v>>31&3))>>2` 向上取整）；尾 `ResetSnapPointPos(R,B)`；返回 1/0 |
| `MovePoint(zPoint,idx,flags,chk)` | `120f60` | **flags&8 且 idx<4 → 对称拉伸**（0/1/2/3=左/上/右/下边：该边移到拖动值、对边反向同量）；否则直写：0→L 1→T 2→R 3→B；**4/5→SetRound(0 角 TL)**、6/7→1(TR)、8/9→2(BR)、10/11→3(BL)（三点式半径计算） |
| `SetRound(corner,p1,p2,p3,flags)` (protected) | `1213c0` | dx=\|p3.x−p1.x\|、dy=\|p3.y−p1.y\|；上界=min(半宽,半高) 读自 +0x58 的 **0x14/0x18 偏移（4 点布局——越界，Q-RoundRect-1）**；半径=依三点方位选 dx/dy/max（判定式见代码）；`flags&8==0`→四角同值，否则只写 corner |
| `SetPoints(pts,flags,idx,p1,p2,p3)` (static) | `121570` | 直段（p2.y==p3.y 或 p2.x==p3.x）→单点 p1、flag=idx?1:0；弧段→4 点 **[p2, p1+t·(p2−p1), p1+t·(p3−p1), p3]**、flag=[idx?1:0,3,3,3]（**t=_DAT_1057f160=0.5523** 圆弧近似）；返回新 idx |
| `GetCtlPts(list,flag)` | `121720` | 12 顶点环→`FUN_10027a30(pts,0xc)`→`esVertexInfo(pts,NULL,0xc,this)` 挂链；return 1 |
| `GetVertexPoints(pts,radii)` (static) | `1217f0` | 生成 12 点环（分配 0x60）：先布侧中点，再按四半径（min(半径, 半宽, 半高)）+ 内外方向符号布 8 个角端弧点 |
| `BuildEx(src,t)` | `121cd0` | src==NULL/type≠/t≥DAT_1057f0b4→Build；否则 2 ctrl 点与 4 半径逐一 `esSeg::step`→`GetVertexPoints`→`BuildShape`→free |
| `Build(n)` | `121e50` | `GetVertexPoints`→`BuildShape`→free |
| `BuildShape(顶点)` | `121ec0` | 分配点/旗标缓冲；按 **TL,TR,BR,BL** 序调 SetPoints（角点=(L,T)/(R,T)/(R,B)/(L,B)，二控制点=v4..v11）；尾补闭合点（=首点、flag=1）；`SetPtInfo(this,pts,flags,n,**0**,1)` |

**注（GetBreakLines 角弧）**：偶顶点 4/6/8/10 时拼**尖角点**（4→(v5.x,v4.y)、6→(v6.x,v7.y)、8/10 类推）与**带符号半径** v[n].x−v[n+1].x；按角位取方向数据（TL=(DAT_1057f438,NULL)、TR=(NULL,DAT_1057f128)、BR=(DAT_1057f128,DAT_1057f368)、BL=(DAT_1057f368,DAT_1057f438)）→`esSegArc`（0x98，见批次 7）新建 AddSegObject；\|半径\|<eps 时不建（视为直角）。

**怪癖**：
- **Q-RoundRect-1** `SetRound` 的半径上界读 `+0x58` 数组偏移 **0x14/0x18**（`p[2].y`/`p[3].x` 的 4 点布局），而 RoundRect 数组只分配 2 点（16B）→ **越界读**（取邻堆数据）。渲染端 GetVertexPoints 会用 min(半径, 半宽, 半高) 再夹一次，故通常无可见后果；差分/动态复核候选。
- **Q-RoundRect-2** `ctor()` 与 `ctor(zPoint&)`/`ctor(zSize&,int)` 初始化不对称：默认 ctor **不清零半径、不建点数组**——差分测试注意构造入口。

## 5. esSegCircel（31 个）（0x4284）

布局：`+0x58/+0x5C` 控制点数组/计数（默认 Build 保留原值）· `+0x68` float **r 半径**（0=退化线）· `+0x6c` float **angle 起始角**（GetAngle_x/y 系）· `+0x70/+0x74` float **圆心 cx,cy** · `+0x78` int **closed 标记**（Build(0) 探测闭合后置 1）· `+0x7c..+0x88` 两个端点（closed 时存的 Invert 后坐标，GetCtlPts/DoSnap 用）· `+0x4C` 矩阵。

| 函数 | 入口 | 规格 |
|---|---|---|
| `operator=` | `f810` | 转 `esSegGemotry::operator=` + 拷 9 dword（+0x68..+0x88） |
| `className()` | `109bb0` | 5 符号折叠（Circel/Lines/Polygon/Rect/RoundRect）→ `esSegGemotry::ID()`（见 §3） |
| `ID / isKindOf / isOf` | `122120 / 122130 / 1221d0` | `"esSegCircel"`；isKindOf 不中→`esSegGemotry::isKindOf` |
| `ctor()` | `122260` | 基类+vftable；**type=0x4284**；+0x78=0、+0x6c=0（r/心未清） |
| `ctor(zPoint,ushort type)` | `1222f0` | **type=param_4（任意——0xe28x 交互模式由此进）**；心=pttoptf(pt)；r=0、角=0、+0x78=0 |
| `ctor(PointF c,float r,float angle,Matrix*)` | `1223b0` | type=0x4284；写心/r/角；矩阵非空→挂 |
| `SetCircleFromPt(PointF)` | `122470` | r=距离(心,pt)（恒写）；\|r\|≥eps 才更新角=GetAngle_y(心→pt) |
| `GetLbcLines(list,mtx,flag)` | `1224f0` | 心/r/角+矩阵 → `FUN_1037fec0(this)` 登记 xzLbcList（线标注通道） |
| `GetDefaultPtOrg(pt)` | `122580` | pt=zFtoL(心)+`FUN_10027a30`（逆变换）；return 1 |
| `GetCtlPts(list,flag)` | `1225e0` | ①+0x78≠0→2 顶点(+0x7c/+0x84)、样式字 `0xe4880000`×2、owner=NULL；②恒有：{圆心, 圆上起点(0,−r 旋转 angle)} 2 点、样式字 {0, `0xeb660001`}、owner=this；return 1 |
| `IsEqual(obj,sheet)` | `1228e0` | 基类 && r==r && **angle==对方 r**（应为对方 angle——疑源 bug/反编译，Q-circel-1） && cx== && cy== |
| `GetBreakLines(list,?,brks,n)` | `122980` | 仅当断口数组含**值 0**：新建 `esSegArc`（0x98）后**强制 type=0x4307** + AddSegObject（圆→弧的断口语义）；param_2 未用 |
| `Serialize(arch,sheet,ver)` | `122ac0` | 基类 + float **r, cx, cy, angle**（无版本门） |
| `CopyFrom(obj,exch)` | `122b90` | 基类；isOf("esSegCircel")→拷 心/r/角 |
| `DoSnap(mgr)` | `122c20` | r>0→`SnapObj(…,0x4000)`（命中→后续加对象线）；矩阵乘 `esMatrixStack::Multiply`；显示点>2 时 `IsSnapable(0x40)`→圆心 SnapPoint（closed 再 +0x7c/+0x84 两点）；`IsSnapable(2)`→圆上起点；命中后建 `esSnapLine(0x78)` `AddObjectLine`；`IsSnapable(0x100)` 且点数==0xd→`FUN_10135350` 取 4 点 SnapPoint；恒 return 0 |
| `SetPointPos(mgr,mode,flags,mtx)` | `123070` | **按 type 分派**：0xe280→ForR；{e281,e284,e285,e289}→For3Q；{e282,e283,e288}→For2Q；{e286,e287}→For1Q；其余→Normal |
| `SnapFarPoints(mgr,pt,thr,flag)` | `123150` | +0x34 存在且 flag≠1：圆心世界化；\|dx\|≤thr→`AddSideLine(…,0)`；\|dy\|<thr→`AddSideLine(…,1)` |
| `CreateCircelForR` | `123240` | r=(float)`Getparam()`；角=GetAngle_x(心,捕捉点)；`flags&0x10`==0→return 1；否则 **type=0x4284**+return 2 |
| `CreateCircelFor1Q` | `123380` | `Get1QCircle`→心/点；type==0xe286 时心再取 `center()`；`SetCircleFromPt(点)`；成功且 &0x10：mode1→`GetSnapType==1 && SetSnapType(0x70,2)`→4；否则 `IsSnapped(0x70)`→type=0x4284+2；其余 1 |
| `CreateCircelFor2Q` | `123490` | `Get2QCircle`→心/r；成功且 &0x10 且(`IsSnapped(0x71)` \|\| `GetSnapType==1`)：mode3→0x4284+2；否则 `SetSnapType((mode1 && type≠0xe282)?0x70:1, 2)`→4；其余 1 |
| `CreateCircelFor3Q` | `123590` | `Get3QCircle`→心/r；成功且 &0x10 且 `IsSnapped(0x71)`：mode3→0x4284+2；否则 snapType=0xe281?(1) : (0xe285?(mode1?1:0x70) : 0x70)→`SetSnapType(_,2)`→4；其余 1 |
| `SetPointPos_Normal` | `1236b0` | mode==1→`GetSnapPointF`+矩阵+`SetCircleFromPt`→1；否则 2 |
| `MoveAcmePoints(vg,pt,flag)` | `123780` | flag==1 且 pt≠NULL：第一个 acme 把手，其计数字段==0→`SetCircleFromPt(pt)`，否则**心=pt**；return 1 |
| `MovePoint(zPoint,idx,flags,chk)` | `123840` | Invert 后：`flags&8 且 idx==0`→角=GetAngle_y(心→pt)（**旋转**）；idx==1→**心=pt**；否则→`SetCircleFromPt` |
| `unMPSave(arch)` | `123930` | 基类 + 4 float；读回逐项比对：角变→Rec(系 0xf2d0)、r 变→Rec(系 0xf2d3)、心变→`esUndo::Write(…,0xf2d6)`（**三码独立**） |
| `Undo(id,…)` | `123aa0` | **0xf2d0** swap 角；**0xf2d3** swap r+`vtbl+0x44(0)`；**0xf2d6** swap 心+`vtbl+0x44(0)`；其它→基类 ILT |
| `BuildEx(src,t)` | `123be0` | 类型不符→Build；心 `step` 插值、r 线性插值；r==0→2 点退化 `SetPtInfo(2,1,1)`；否则 `esBezierArc`(心) 取 n；n==0→保留 +0x58 控制点；否则 `GetPts(n,r,r)`→`SetPtInfo(n,**3**,1)` |
| `Build(n)` | `123e60` | +0x78=0；r==0→2 点退化；否则 `esBezierArc`→`GetPts`→`SetPtInfo(n,3,1)`；**n==0 且 IsClosed 且 `FUN_10135530` 成功**→+0x78=1 并记两端点（+0x7c/+0x84，Invert 后） |

**怪癖**：
- **Q-circel-1** `IsEqual` 第二比较式把 `this.angle` 与 **对方 r**（param+0x68）比较（应为对方 angle）——疑源 bug/反编译失真；差分复核候选。
- **Q-circel-2** `GetBreakLines` 只认断口值 **0**、产物强制改类型字 **0x4307（esSegArc）**——圆对象在断口链里"变成弧"的语义；param_2 未用。

## 6. esSegPoint（13 个）（0x6001）

布局：`+0x58` 控制点数组（1×tagPOINT，ctor `FUN_105290e5(8)` 分配）· `+0x5C` ushort 计数=1 · `+0x34` Build/显示点缓冲（RecalcLayout/Load/Draw 用）· 继承 `esSegNative`。类型字：**0x6001 实点（工厂）**；编辑器临时交互模式 **0xE001 / 0xE002 / 0xE003**（自由点/镜像点/线上点，吸附落定后复位 0x6001；ctor 任意 type 由此进）。加粗点即 0x6001 esSegPoint，宿主是 `esShapeLine`(0x3109)（与 AGENTS.md 的 dots 通道一致）。

> **勘误（2026-10，批次 7 复核）**：早前把交互模式误记为 0x6001/0x6002/0x6003（反编译以带符号短整型显示为 -0x1fff/-0x1ffe/-0x1ffd）。实际为 **0xE001/0xE002/0xE003**；0x6002/0x6003 不存在于本类，0x6003 是 `esSegCircels` 的静态类型字（批次 7），两者无冲突。

| 函数 | 入口 | 规格 |
|---|---|---|
| `ID()` | `e83f0` | `L"esSegPoint"` |
| `isKindOf` | `e8400` | 不中→`esSegNative::isKindOf` |
| `isOf` | `e84a0` | 只比自身 ID |
| `ctor()` | `e8530` | esSegNative 基类；**type=0x6001** |
| `ctor(zPoint,ushort type)` | `e8560` | type=任意；分配 8B 写首点；+0x5c=1 |
| `~esSegPoint` | `e8610` | vftable + esSegNative 析构 |
| `SetPointPos(mgr,mode,flags,mtx)` | `e8630` | **按 type 分派**（详表见下）；恒先 `GetSnapPointF` |
| `DoSnap(mgr)` | `e89c0` | `IsSnapable(2)`→首点（`FUN_10027a30` 变换）`SnapPoint(…,2)`；恒 return 0 |
| `GetCtlPts(list,flag)` | `e8a30` | 转 `esSegArcRuler::GetCtlPts` |
| `Build(n)` | `e8a50` | 转 `esSeg::Build` |
| `RecalcLayout()` | `e8a70` | `+0x34==0`→先调 `vtbl+0x7c(0)`（Build(0) 生成显示点）；宿主 amulet 非 `esShapeLine(0x3109)`→`esSeg::RecalcLayout`；否则 `GetPenInfo` 笔宽（**下限 0x32=50 单位**）→退化点 InflateRect 成 2w 方框→`SetSolidRect`+`SetBoundingRect` |
| `Load(page,subject,dp)` | `e8b90` | 有显示点时：**实心圆**——`elfSolidBrush`(色=dp 笔色) + `elfSimpleGeometry(2)` + `AddEllipse`（半宽=max(dp 线宽,50) 方框），各 `subject::Add(…,1)` |
| `Draw(render,dp,mtx)` | `e8d00` | `get_safe_points`→`GetGraphics(3)`→`MakeSolidColor`→`egSolidBrush`→**`FillEllipse(x−w, y−w, 2w, 2w)`**，w=max(dp 线宽,50) |

**SetPointPos 分派**（返回码：1=普通移动；2=吸附成功且**类型复位 0x6001**；4=被吸附类型锁定）：
- `0xE003` 线上点（临时）：mode==1→写点（`flags&0x10` 且 `SetSnapType(1,1)` 成功→4）；mode≠1→`GetPointOfOnLine` 得吸附点→写点，成功且 `flags&0x10`→**改 0x6001** 返回 2；否则 1。
- `0xE002` 镜像点（临时）：mode==1→写点（`SetSnapType(0x10,1)` 成功→4）；mode≠1→`GetMirrPoint`→写点，成功且 `flags&0x10`→**改 0x6001** 返回 2；否则 1。
- `0xE001` 自由点（临时）：mode∈{1,2}→`flags&0x10` 且 `SetSnapType(1,1)` 时：`Getparam()<3` 且 `GetFDPoint` 成功→写点、改 0x6001 返回 2，否则写点返回 4；无 `flags&0x10`→写点返回 1。mode∉{1,2}→`GetFDPoint`；写点，成功且 `flags&0x10`→改 0x6001 返回 2。
- 其它（0x6001 实点等）：恒返回 2。

**怪癖**：
- **Q-point-1** 点的大小=宿主 esShapeLine 的**笔宽**（下限 50 单位=0.125mm），`FillEllipse` 半径=w（直径 2×pen）——"加粗点"视觉尺寸由线宽决定，非自有样式字段。
- **Q-point-2** `Draw`/`Load` 只用**第一个**控制点（`ptVar1->x/ptVar1->y`）；count 恒 1 故无害。
- **Q-point-3** `SetPointPos` 对 0xE003/0xE002 在吸附落定时**把自身类型字复位为 0x6001**（线上点/镜像点 → 实点）；自由点（0xE001）落定还要求 `Getparam()<3`。临时模式是"创建中"语义，落定即固化。

