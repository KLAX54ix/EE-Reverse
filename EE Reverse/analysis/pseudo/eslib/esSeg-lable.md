# eslib 标注族 — 反编译规格（阶段 2 · 第八批 · 绘图核心 4/6）

- 模块：eslib.dll；函数：**72 个**（esSegLable 28 · esLableBox 34 · esLableBoxEx 10）
- 伪代码（原样）：`analysis/pseudo/eslib/esSeg-lable.decomp.txt`（matched=72 dumped=72）
- 类型头：`analysis/types/esSeg-lable.h`
- 台账：72/72 → `decompiled`（status-overrides）
- 角色：S5 标注族 —— 文字标签段 `esSegLable`（**成员类型字 0x600d**，内嵌 `esEQLine` @+0x80）与标注框 `esLableBox`（: esFormulaBox）及其扩展 `esLableBoxEx`（: esLableBox）。本批定下标签**三段文本模型**（Part1/2/3 + 分数式双盒）、九宫格/自定义文本偏移与位置码、特性字（GetLableFreature→OnMessage 0x113）、标注框布置函数族（CCD/TB/Any/BJ/GongCa/YX/ZJ/Paren/CVL/CHL）与标注样式（esDS_Txt / esDimenStyle）依赖面。

## 0. 谱系与公共结构（本批结构性结论）

| 结论 | 证据 |
|---|---|
| `esSegLable : esSeg` 直派（ctor `3e8f40/3e8ff0` 调 `esSeg::esSeg`；dtor `3e9190` 逆序 `~esEQLine`→`~esSeg`）；类型字恒等值 **0x600d**（写 `+4`） | ctor/dtor 函数体 |
| `esLableBox : esFormulaBox`；`esLableBoxEx : esLableBox`。esLableBox ctor 无类型字写入（esEquBox 家族非 esSeg） | `443920` / `449d90` |
| `className()` 折叠回父 ID：esLableBox→`esFormulaBox::ID`（`443880`）；esLableBoxEx→`esLableBox::ID`（`449cf0`）；isKindOf 链 Ex→LableBox→FormulaBox（this==NULL→0） | 各函数体 |
| `esLableBox::GetMatrix`（`4d70`，17B，`return (Matrix*)(this+0x4c)`）与 `esColumnItem::GetRegion` 同址（ILT 2 符号） | `4d70` 块头 |
| `esSegLable::operator=` 被 ILT 摆到 `ef80`（批内唯一非同区地址） | `1000ef80` 块 |
| **三段文本模型**（esSegLable）：`+0x70` Part1（主行）/ `+0x71` Part2 / `+0x72` Part3（均为 wchar 计数，低 8 位有效）；Part2/3 承载走 **双盒 esTextItem**：非分数式（bit6 清）用 `FUN_10095830`（0x48B 项）+ ini 码 0x16000041(仅P2)/0x16000081(仅P3)/0x160000c2(双段)；分数式（bit6 置）用 `FUN_1007c700`(0x58B 项)+ini 0 | `RecalcLayoutLable 3eb390` |
| esLableBox 文本：`+0x14` esTextLine（行容器）＋初始化时 `SetupFonts(L"0")` 拿空槽写 `line+0x1e`；多段文本经 `FUN_1007c700` 双盒（ini 码 **0x11000024**），P2→First 盒、P3→Last 盒 | `Initialize 443bb0` / `InitText 443a00` |
| owner 获取统一经成员方法 **`vtbl+0x54(0xe)`**（返回 `esDimBase*` 宿主标注对象）；Load/Draw/HitTest/InitPts/全部 SetMePoints_* 使用 | 各函数体前哨 |
| 标注样式字段面（param 侧 `esDS_Txt`/`esDimenStyle`）：`+0x10` 位集（**0x1000**=边框钢笔；低 4 位=文字排向；0xc0 参与 GetTextAngle）、`+0x14` 填充色、`+0xc` ushort 偏移、`+0x18` ushort（划线样式高位）& `+0x2c` byte（划线类型/线型字）、`+0x20`? 未用 | Load/Draw/SetMePoints_* |
| 序列化版本门：`CollectStyles` 把 `sheet+0x850` 升至 **0x1000202**；读侧 <0x1000202 → `+0x74=(+0x73&0xf)` 且不读 floats；<**0x2000735** 且 `(+0x73&0xf)==4` → 清 `0x73` bit4 | `3ea190` / `3ec400` |

**布局总表**

- esSegLable（≥0xD8）：`+0x34/+0x38` 显示点缓存（alloc 0x30=6 点；count=5；**pt[5]=pt[0]+margin 锚点**）· `+0x58/+0x5C` 控制点（1 点 tagPOINT）/计数 · `+0x60` 点 flags（alloc 5B，[0]=0，[1..4]=1）· `+0x68` wchar_t* 文本 · `+0x6C` ushort / `+0x6E` ushort 字体槽 · `+0x70..0x72` 三段长度字节 · `+0x73` 特性字节（bit4 圆点·bit5 边框·bit6 分数式·bit7 数学；低 4 位=Build 位置码）· `+0x74` 对齐字节（低 4 位 0–8 九宫格码；高 4 位 0x10/0x20/0x30/0x40/0x80/0xc0=自定义六向）· `+0x78/+0x7C` float 自定义偏移 · `+0x80` esEQLine · `+0xD4` esFontSheet*
- esLableBox（≥0x5C）：`+0x14` esTextLine* · `+0x1c` ushort（默认 8）· `+0x24/+0x28` int 盒原点（−w/2,−h/2）· `+0x2c` int 宽 · `+0x3c` ushort（字高/8 或 ×DAT_1057f118）· `+0x40` esFontSheet* · `+0x48` ushort（字高/8 缓存）· `+0x4c` Matrix（GetMatrix/OnLoad/Draw/SetTextPos 视角）· `+0x54` tagPOINT* 点数组（alloc 0x40=8 槽）/ `+0x58` count
- esLableBoxEx：`+0x5C/+0x60` tagPOINT（缓存锚偏移；ctor 清零）

## 1. esSegLable（28 个）（成员类型字 0x600d；esSeg 直派）

布局见 §0。文案三段 + 段长字节 + 特性/对齐字节 + 自定义偏移 float + 内嵌 EQLine；显示点 5+1（第 6 点为 margin 锚）。

| 函数 | 入口 | 规格 |
|---|---|---|
| `ID / isKindOf / isOf` | `3e8e00 / 3e8e10 / 3e8eb0` | `"esSegLable"`；isKindOf：this==0→0，名不中→`esSeg::isKindOf`；isOf 仅自比 |
| `operator=` | `ef80` | `esSeg::operator=` + 逐字段（**+0x68 文本指针浅拷贝**【Q-lable-5】、+0x6C/+0x6E、+0x70..0x74、+0x78/0x7C）+ `esEQLine::operator=`(+0x80) + +0xD4 |
| `ctor()` | `3e8f40` | esSeg + vftable + `esEQLine@+0x80` + +0xD4=0 + **type=0x600d** + +0x68=0、+0x6C=0（ushort）、+0x78/0x7C=0、**+0x74=0** |
| `ctor(zPoint,zwstr,ulong,ushort,ushort)` | `3e8ff0` | 同上；ctrl=1 点（alloc 8，写 x,y，+0x5C=1）；文本 `lstrcpyW` 到新分配 +0x68；**ulong 拆 4 字节写 +0x70..+0x73**；`param_4→+0x6E`（槽）、`param_5→+0x6C`；**+0x74=4**（居中） |
| `~esSegLable()` | `3e9190` | 释放 +0x68（`FUN_10528fdd(...,2)`）+ `~esEQLine` + `~esSeg` |
| `RecalcLayout()` | `3e91e0` | 仅转发 `esSeg::RecalcLayout`；**RecalcLayoutLable 只由 Build 调用**【Q-lable-9】 |
| `LoadProp(mgr,ulong)` | `3e9200` | 组 **0xa00**：a01=font+6（槽）、a02=font+0（名）、a04=font+0x14、a0e=font+0x20、a03=font+0x28&3、a0b=(+0x6C)>>2、a09=bit4、a08=bit5、a0c=bit6、a05/06/07=三段文本（zwstr SetString 切段）、a0a=(+0x74 高半字节==0)? 低半字节 : **0xffffffff**、a0d=bit7 |
| `SaveProp(mgr,ulong)` | `3e9660` | 字体组：克隆 font；按修改项更新 a01/+6（同时 +8=+10=+6）、a03/+0x28、a02/+0、a04/+0x14、a0e/+0x20；`font::IsEqual` 变→sheet 注册+undo 0xa01(+0x6E)+换槽；a0a→+0x74（undo 0xa0a）；a08/a09/a0c/a0d 位合成写 +0x73（变化时 undo 0xa0f 旧字节）；a0b→`esUndo::CheckWrite(+0x6C,4)`。`param_2==0x1000000` 文本更新：拼三段（须 Part1 非空或 P2&P3 双非空）→长度+memcmp 相等→释放新缓冲（**0x8123 死存**）；不等→`GetTextData`(消费)+undo **0xa10**+写 +0x68/段长。有任何变化→`vtbl+0x44(0)` |
| `GetTextData(&sz)` | `3e9fd0` | **消费性**：+0x68==0→(sz=0,返 0)；否则 sz=(len+1)*2+3、blob=[len0][len1][len2][text…]、**free +0x68 并清零**【Q-lable-7】 |
| `Undata(&code,data,&sz)` | `3ea0b0` | 0xa10：`GetTextData`（取旧 blob 供新撤销记录）→段长=data[0..2]→新分配 sz−3 + memcpy→失效；否则 `esSeg::Undata` |
| `Undo(code,...)` | `3e9e10` | **0xa01↔+0x6E**(ushort)、**0xa0a↔+0x74**(byte)、**0xa0b↔+0x6C**(ushort)、**0xa0f↔+0x73**(byte)、**0xa11↔+0x78**(float)、**0xa12↔+0x7C**(float)；default→`esFormulaBox::CaretMove` |
| `CollectStyles(sheet)` | `3ea190` | `esUseInfo::CollectStyles(sheet,+0x6E,1)`；`sheet+0x850` < 0x1000202 → 升之 |
| `Initialize(fontSheet)` | `3ea1e0` | +0xD4==0 时写（惰性绑定字体表） |
| `SetTextColor(color,sheet)` | `3e9560` | font+0x14≠color→Clone→写 +0x14→sheet `vtbl+8` 注册→undo 0xa01(+0x6E)→换槽→`vtbl+0x44(0)` |
| `OnMessage(msg,ulong)` | `3e9600` | `msg.type==0x113` 且 `GetLableFreature()==msg+4` → `vtbl+0x1c(msg+8,0)` 返 1；否则 `esObject::OnMessage` |
| `GetLableFreature()` | `3eac10` | +0xD4==0→0；基=**槽<<16 \| (+0x73&0xf0)**；Part1 逐字符 `GetMathCharType(ch,10)`≠6 → 类型钳制（负→ch>0xff?1:0；>7→2）后 **`\|= 0x100<<type`**；段存在位 \|1/\|2/\|4 |
| `HitTest(ht,mode)` | `3ea210` | +0x34 空→Build。bit5→`HitTestLines(pts,5)`→sel **7**；否则 `IsPtInGon(pts,5)`→sel mode==0?**0x15**:**0x16** |
| `HandMoveText(&pt,mode)` | `3ea2f0` | 逆矩阵求盒中心/半宽与拖拽量；mode==0（拖拽）：x 三分支→+0x74 半字节 **0x10**(内插比→+0x78)/**0x30**(右外 Δ)/**0x20**(左外 Δ)，y 同构 **0x40/0xc0/0x80**（undo 0xa11/0xa12/0xa0a）→`vtbl+0x44(0)`；mode≠0：把 pt 夹入（半宽+max(+0x6C,600)）范围→正变换回写 pt |
| `Build(n)` | `3ebd80` | `RecalcLayoutLable`→宽=`EQLine::Width(+0x80)`（ELF 折叠名 `elfPage::GetColorScheme`）、高=`EQLine::Height`；bit5→margin=+0x6C（否则 0）；alloc 6 点；`GetPointsForRect(0,0,w,h)`+平移；pt[4]=pt[0]；九宫格（+0x74 高半字节==0）：x=(码%3)w/2+Δ、y=(码/3)h/2+Δ，码写回 +0x73 低半字节；自定义：按 +0x74&0x30（0/0x10/0x20/0x30）与 &0xc0（0/0x40/0x80/0xc0）两段 switch 用 +0x78/0x7C 定位（**y-case0 用 宽度/2**【Q-lable-3】）并合成位置码；**pt[5]=pt[0]+margin（赋值先于 `FUN_10027a30(pts,5)`，即变换计数 5 不含 pt[5]）**【Q-lable-10】；释放旧 +0x34（0x8123 死存模式）→ +0x34=pts、+0x38=5；+0x60==0→alloc 5B（[0]=0，[1..4]=1） |
| `IsEqual(obj,sheet)` | `3ec2c0` | `esSeg::IsEqual` + 比 +0x6E/+0x6C/+0x70..0x73/+0x74/+0x78==+0x78、**+0x7C==param+0x78**【Q-lable-1】→文本 `memcmp((len0+len1+len2)*2)` |
| `Serialize(arch,sheet,ver)` | `3ec400` | 写：槽、+0x6C、+0x70..0x73、**+0x74、+0x78、+0x7C（无条件）**、文本 Σlen*2。读：同上字段；**ver<0x1000202→+0x74=(0x73&0xf) 且不读 floats**；**ver<0x2000735 且 (0x73&0xf)==4→清 0x73 bit4**；`esUseInfo::Update`；文本重分配；`Initialize(sheet 或 m_pUndo+8)` |
| `CopyFrom(obj,exch)` | `3ec6c0` | `esSeg::CopyFrom`；按 ID（`vtbl+8`）判定源类型；槽经 `esStyleExchanger::GetFontIdx` 重映射；拷 +0x6C..+0x7C；文本深拷贝（Σlen+1）；`Initialize(exchanger 目标 sheet)` |
| `Load(page,subj,dp)` | `3ea790` | 门 +0xD4；+0x34 空→Build。font+0x20 非 0→实心刷+Add（fill=2）；bit5→`AddPen(param+4)`→fill\|=1；有 fill/stroke→`elfPathGeometry(0x40,fill)`+`AddPolygon(pts,5)`+Add；**bit4 且 (0x73&0xf)!=4 且笔色非 0**→实心刷+圆点 **r=max(笔宽·5/2,100)**（笔宽=param+4→+8）、圆心=ctrl(+0x58) 世界化、AddEllipse【Q-lable-2】；子矩形=`NewSubj(GetSolidRect)`+rect(0,0,w,h).**Offset(pts[5])**+`SetRectB(subj,rect,(Matrix*)(this+0x4c))`；`EQLine::Load(+0x80,page,subj,rect,0)`（page+0x34 暂换递归保护） |
| `Draw(render,dp,matrix)` | `3ead30` | 门 +0xD4；+0x34 空→Build。font+0x20 且 `!(dp+0x18&0x20000000)`→`FillPolygon(get_safe_points(this,param_3),+0x38)`；bit5→`CreatePen(dp+4)`→DrawPolygon 同点集→删笔；文本 `!(dp+0x18&0x10000000)`：Save+`MultiplyTransform(esMatrix(+0x4c,param_3))`+aux 色清零+**`EQLine::Draw(...,pts[5].x,pts[5].y,...)`**+还原；**bit4 且 !(dp+0x18&0x20000000)**→FillEllipse 圆点 **r=max(笔宽·2,100)**、色=`**(dp+4)`【Q-lable-2】 |
| `GetEntersectInfo(pA,pB,&tA,&tB)` | `3eb140` | +0x34 空→Build；锚=ctrl 世界化；`dist(锚,pA)<100`→对显示边 i=1..cnt 做 `Jiao_LineLine(pA,pB,边)`，**tA=max**（`<=` 且 `!=` 模式）；否则试 pB 同法写 tB |
| `RecalcLayoutLable()` | `3eb390` | 门 **+0xD4==0 直接返回**；清空 EQLine（`esText::ClearAllContent`）；`GetFont(+0xD4,+0x6E)`；bit7→`FUN_103e0e30(sheet,0x40000,0)`；`SetFontHeight(font+0x14)`（【Q-lable-4】）；`SetActiveFont/SpecifyFont/SetFontMode(0)`；Part1→`AppendString(+0x80)`+游标推进；Part2/3 见 §0 双盒模型（P2→Box0、P3→Box1；仅 P3 分支把槽写 `EQLine+0x1e`）；`esText::StylizeLabelFonts`；`SetFontMode` 还原；`GWindowDC`+`EQLine::RecalcLayout(+0x80,dc,sheet,0,DAT_1057f0b4,0)` |

**怪癖**：
- **Q-lable-1** `IsEqual` 末比较 `this+0x7C == param+0x78`（param+0x78 被用两次）——`+0x7C` 与对方同字段永不参与比较，疑似原版笔误；两对象 +0x7C 不同也可能判等（影响文本去重/撤销合并）。
- **Q-lable-2** 圆点半径 **Load=笔宽·5/2、Draw=笔宽·2**（下限均 100），且条件不同（Load 多查 `(0x73&0xf)!=4` 与笔色非 0；Draw 只查 `dp+0x18&0x20000000`）——同一对象的打印/屏显圆点大小不同。
- **Q-lable-3** `Build` 自定义偏移 y 分支 case 0 用 `y − 宽度/2`（反编译原样；其余 y 分支用高度）——疑原版复制笔误。
- **Q-lable-4** `font+0x14` 双重用途：`SetTextColor` 写颜色，`RecalcLayoutLable` 又把它送 `esFont::SetFontHeight` —— 字段语义待 esFont 批次（3.7）裁决。
- **Q-lable-5** `operator=` 浅拷贝 `+0x68` 文本指针（不复制内容、无引用计数）——仅可用于"源即将移交"语义的拷贝。
- **Q-lable-6** `Serialize` 写侧无条件写 +0x74/+0x78/+0x7C（版本门只存在于读侧），旧格式兼容靠读侧两条降级规则。
- **Q-lable-7** `GetTextData` 消费性（free +0x68 并清零）——只能用于撤销记录路径；其余用途须先自拷贝。
- **Q-lable-8** **0x8123 死存储模式**再现（Build 的 +0x34 释放路径、SaveProp 的文本相等路径；编译器/反编译形态同批 6 所见）。
- **Q-lable-9** `RecalcLayout` 仅转发 `esSeg::RecalcLayout`；`RecalcLayoutLable` 只被 `Build` 调用 → 一切属性修改后的重排都经 Build（+0xD4 未绑定时 Build 内 RecalcLayoutLable 直接返回）。
- **Q-lable-10** `Build`：`pt[5]=pt[0]+margin` 赋值先于 `FUN_10027a30(pts,5)`（变换计数 5，不含 pt[5]）→ pt[5] 与 pts[0..4] 相位不一致；Load 子矩形偏移与 Draw 文本锚点都依赖 pt[5]，**标注错位/旋转标签文字飞掉从这查**。

## 2. esLableBox（34 个）（: esFormulaBox）

布局见 §0。核心协议：**点数组 8 槽、count=5 时 0–4 为盒多边形（闭合）**；count>5 时 **pts[5..] 为引线折线**（pts+0x28 起，count−5 段）。

| 函数 | 入口 | 规格 |
|---|---|---|
| `ID / isKindOf / className / isOf` | `4437d0 / 4437e0 / 443880 / 443890` | `"esLableBox"`；isKindOf：this==0→0、不中→`esFormulaBox::isKindOf`；className→`esFormulaBox::ID`；isOf 仅自比 |
| `ctor()` | `443920` | `esFormulaBox::esFormulaBox` + vftable + `FUN_10027060` + **+0x1c=8** + +0x54=0 + +0x58=0（无类型字） |
| `~esLableBox()` | `4439b0` | 释放 +0x54；**+0x4c 按 `ATL::CComBSTR` 析构**【Q-lablebox-2】；`~esFormulaBox` |
| `GetMatrix()` | `4d70` | `return (Matrix*)(this+0x4c)`（ILT 2 符号：esColumnItem::GetRegion） |
| `Initialize(sheet)` | `443bb0` | +0x14==0→建 esTextLine（`vtbl+0x58(0)`；sheet 非空→`CheckDynamicChange`+`SetFontMode(3)`+`SetupFonts(L"0")`→槽写 `line+0x1e`+还原模式）+`esLineBox::Append`；转 `esFormulaBox::Initialize` |
| `InitText(s1,s2,s3,sheet)` | `443a00` | +0x14==0→建行+Append；s1 非空→`esTextLine::InitText(+0x14,s1)`；s2/s3 任一非空→新 0x58B esTextItem（`FUN_1007c700`）+`vtbl+0xbc(0x11000024,sheet)`；**s2→`esTextItem::First` 盒、s3→`esTextItem::Last` 盒** InitText；`AddChrObj`；失效 |
| `UnionRect(rect)` | `443c70` | +0x54 非空→`UnionPoints(rect,pts,4)` |
| `Build()` | `443ca0` | +0x58=5；font=`GetFont(+0x40,line+0x1e)`；fh=`GetFontHeight`；活动帧→`esFormulaBox::RecalcLayout`；**+0x24=−w/2、+0x28=−h/2**（w=+0x2c、h=EquBox::Height/2）；分配 0x40 点数组：pts[0..4]=TL/BL/BR/TR/TL、**pts[6/7]=(±(w/2+fh/2),0)**、**pts[5] 不写**【Q-lablebox-1】；返回 w=pts[3].x−pts[0].x |
| `HitTest(ht,mode)` | `4448c0` | count>4→`IsPtInGon(pts,5)`→`SetSelInfo(mode==0?0x1b:0x18, owner=`vtbl+0x54(0xe,0)`, 0xe)`；count>5→`HitTestLines(pts+0x28,count−5)`→sel **7**（同 owner 形态） |
| `GetPts(&n,pts,flags)` | `444990` | +0x54 非空：memcpy `count*8` 至 pts+n；flags：idx **0/5→0** 否则 **1**；n+=count |
| `GetCtlPoint(&pt)` | `444a40` | pts[0]/pts[2] 中点；返回 +0x54 非空 |
| `Qiujiao(int&,int&)` | `443ed0` | 拷贝 5 点+世界变换；*p1=**y=0 交线 x 最小**、*p2=最大（符号穿越线性插值+等 x 特判）；**返回=全点 x 跨度 maxX−minX**【Q-lablebox-3】 |
| `JIao_LineCircle(&a,&b,r)` | `4440c0` | 线段×圆(原点,r)：水平/竖直特判；一般解 `y=kx+b` 代入圆方程，判别 `(2kb)²−4(k²+1)(b²−r²)`；两交点按线段包围盒过滤后回写 a/b，返回位掩码 1/2 |
| `Qiujiao(float&,float&,r)` | `4446b0` | 拷贝+变换 5 点；逐边 `JIao_LineCircle(r)`；交点 x<0→`GetAngle_y(...,1,0)` 更新 *p1、x≥0→`GetAngle_y(...,0,0)` 更新 *p2（各取最大）；**返回 *p1+*p2**（弧可见角范围和） |
| `GetTextAngle(p,n,a,b,flags,esDS_HV*)` | `445980` | 排向=style+0x10&0xf：**0→(a+b)/2**；1/2 结合 `flags&0x40` 判镜像；`(style+0x10&0xc0)==0`→拷贝 pts[0..2] 扫 y=0 插值求角；余分支读 `esDS_HV`【Q-lablebox-4】 |
| `IsMirr(angle)` | `447580` | `DAT_1057f50c < angle ≤ DAT_1057f534` → 1 |
| `InitPts(f)` | `449100` | +0x40/owner 空→0；`Build`；返回 `max(int(√2·(fh/2)·f), int(½√(w²+h²)))` |
| `SetTextPos(pt,int,int,Matrix)` | `449200` | fh=字高；`bVar=(+0x1c&0x70)!=0x70`；+0x3c 缓存=fh/8 或 fh·DAT_1057f118（bVar 分支）；**+0x48=⌊fh/8⌋**（变→失效）；`Build`→按 bVar/param 组合用 +0x48、`line+0x40/+0x50`、`EQLine+0x44` 计算 (x,y)；`FUN_10052bd0`+`FUN_10027140`+`FUN_10027a30(pts,count)`；**返回 EquBox::Height** |
| `SetTextPos(pt,Matrix)` | `4494f0` | +0x54 非空→`FUN_10052bd0`+`FUN_10027140`+`FUN_10027a30(pts,count)` |
| `SetMatrix(x,y,Matrix)` | `448010` | 同上三连（显式原点版） |
| `OnMessage` | `449560` | 直通 `esEquBox::OnMessage` |
| `Load(page,subj,esDS_Txt*,int)` | `449580` | 门：pts/owner(0xe)/+0x40。**count>4**：param_4 且 `style+0x10&0x1000`→`LoadPen`→fill=1；param_4 且 `style+0x14`→实心刷→fill\|=2；有→`elfPathGeometry(fill)`+`AddPolygon(pts,5)`+Add。`esFormulaBox::OnLoad(...,(Matrix*)(this+0x4c))`。**count>6**：无笔则 LoadPen；`elfPathGeometry(1)`+（`style+0x2c` 字节==0→`AddExLines(pts+0x28,count−5)`；否则 `esScriber(字型=byte(+0x2c)\|ushort(+0x18)&0xff00, pts+0x28, count−5, …)`→`Load`）+Add |
| `Draw(render,Matrix,pen,int)` | `449990` | 门同上；`style=GetBzStyle(owner)`。param_4 且 style+0x14→`FillPolygon(FUN_1040e4b0(pts,5,matrix),5)`。Save+`MultiplyTransform(esMatrix(+0x4c,matrix))`：**`esFormulaBox::OnDraw`**；编辑态→`esSeg::IsSelected(owner)`→`DrawEdge`；Restore。param_4 且 `style+0x10&0x1000`→`DrawPolygon(pen, 变换点,5)`。count>6→n=count−5、buf=变换(pts+0x28)：`style+0x2c`==0→`DrawLines(pen,buf,n)`；否则 `esScriber::DrawTypedLines(render,pen,buf,0,n,字型,0,(buf==src),200)` |
| `SetMePoints_ForCCD(pt,float,Matrix)` | `445cc0` | 门 +0x40/owner；fh；`style+0x10&0x1000`→+0x48=⌊fh/8⌋（变→失效）；`Build`→w；**返回 diag=int(fh·√2)**；angle=`param·DAT_1057f528/DAT_1057f368`；IsMirr 区间时先绕原点预转 DAT_1057f528；x=（diag<w 时 (diag−w)/2+pt.x 否则 pt.x）；y=pt.y−fh−EquBox/2−**fh/10**−`style+0xc`；置原点→绕 pt 转 angle→矩阵→变换 |
| `SetMePoints_ForCCD_TB(p1,p2,int,int,float,Matrix)` | `445f10` | 两点变体（同 CCD 前段：+0x48 缓存、Build、旋转/定位；端点参数化） |
| `SetMePoints_ForAny(&p1,&p2,Matrix)` | `446140` | 通用两点布置（矩形+中点+角度；含可见性/±90° 镜像选择的大分支） |
| `SetMePoints_ForBJ(pt,float,int,int,tagPOINT*,Matrix)` | `4475c0` | 半径/角度标注布置：多分支点位解算+旋转定位；返回打包 flags |
| `SetMePoints_ForGongCa(pt,int&,int)` | `447e50` | 公差文字：`h'=⌊fh·DAT_1057f138⌋` 按 **100 对齐**（余数 `<0x33(51)`→+0 否则 +100）【Q-lablebox-5】；flag 且 *param==0→*param=h'；**+0x48=⌊fh/4⌋**（变→失效+`+0x3c=2×`）；`Build`→返回高度相关 |
| `SetMePoints_ForYX(p1,p2,ulong,Matrix)` | `448070` | 引线布置（flags&0x30 分支、旋转型）；角度常量 DAT_1057f50c/f534/f528；**返回 tagPOINT**（输出引点） |
| `SetMePoints_ForZJ(pt,float,int,int,tagPOINT*,Matrix)` | `448420` | 直径标注布置（6 点位推演+旋转；与 BJ 同构分支） |
| `SetMePoints_ForParen(p1,p2,float,int,Matrix)` | `448cd0` | 弧括号：极角规范化（0x168=360、0xb4=180），sin/cos 在两端点间布置文字 |

**怪癖**：
- **Q-lablebox-1** `Build` 只写 pts[0..4]、pts[6..7]；**pts[5] 不写**（引线起点，留给布置函数/加载）——alloc 0x40 是否清零未证，count≤5 时不读它。
- **Q-lablebox-2** `+0x4C` 双解释：dtor 按 `CComBSTR` 释放（读 4 字节指针），GetMatrix/OnLoad/Draw/SetTextPos 按 `Gdiplus::Matrix` 使用——若首 dword 非空则析构即崩；动态验证点（可能实际布局是 esFormulaBox 内嵌 BSTR + 矩阵重叠区）。
- **Q-lablebox-3** `Qiujiao(int&,int&)` **返回值=变换后全点 x 跨度**（非 y=0 交线跨度），参数才携带交线 min/max——调用方语义据此为准。
- **Q-lablebox-4** `GetTextAngle` 的 `(style+0x10&0xc0)==0` 早退分支不读 `esDS_HV`，余分支读（esDS_HV 结构待 S5 余部；0xc0 为竖直/镜像排向位）。
- **Q-lablebox-5** `SetMePoints_ForGongCa` "公差取整"阈值：`⌊fh·DAT_1057f138⌋ %100 < 51` → 取 100 下界否则进 100——阈值 51 为两点取整的具体实现。
- **Q-lablebox-6** `HitTest` 的 `SetSelInfo(sel, owner, 0xe)` 第三参经 `vtbl+0x54(0xe,0)` 取宿主；sel 三态（0x1b 盒内/0x18 盒内变体/7 引线）与 esSegLable 的 0x15/0x16 属不同族。

## 3. esLableBoxEx（10 个）（: esLableBox）

布局：`+0x5C/+0x60` tagPOINT（缓存锚偏移；ctor 清零）。CVL/CHL 布置函数物理地址夹在 esLableBox 函数之间（链接序），符号归 esLableBoxEx。

| 函数 | 入口 | 规格 |
|---|---|---|
| `ID / isKindOf / className / isOf` | `449c40 / 449c50 / 449cf0 / 449d00` | `"esLableBoxEx"`；isKindOf 不中→`esLableBox::isKindOf`；className→`esLableBox::ID`；isOf 仅自比 |
| `ctor()` | `449d90` | `esLableBox::esLableBox` + vftable + **+0x60=0、+0x5C=0** |
| `~esLableBoxEx()` | `449dd0` | `~esLableBox` |
| `IsEqual(obj,sheet)` | `449df0` | `esEquBox::IsEqual` 基；相等则：**`param+0x5c==0` 且 `this+0x60≠param+0x60`→不等，否则等**；**结果写回 this+0x5C**（副作用）【Q-lableboxex-1】 |
| `Serialize(arch,sheet,ver)` | `449e50` | `esFormulaBox::Serialize` + **8 字节 @+0x5C**（tagPOINT 写/读） |
| `SetMePoints_ForCVL(pt,int,float&,float&,ushort&,Matrix)` | `444ac0` | 弧长/弧高标注（CVL）：`Qiujiao(float)` 张角差与可用弦/高比较、`IsMirr`；flags **0x200/0x100** 分支；**角度写回 *p1/*p2、flags 写回 *p7**；经 Matrix 定位 |
| `SetMePoints_ForCHL(tagPOINT*,ushort&,Matrix,float)` | `4466f0` | 弧弦/弧高（CHL）：锚点 `param_1[2/3/6/7]`、`Qiujiao`、`IsMirr`；flags **0x80/0x100/0x200**；输出 ushort& |

**怪癖**：
- **Q-lableboxex-1** `IsEqual` 有副作用：读**对方** `+0x5c` 作开关、比较 `+0x60`，并把结果写回**自己** `+0x5C`——复制/比较路径若复用同对象会互相踩状态。
- **Q-lableboxex-2** CVL/CHL 地址夹在 esLableBox 函数之间（链接序），但符号归 esLableBoxEx（导出名/台账一致）——按名检索时注意地址不连续。

## 4. 后续依赖（未决 → 下游批次）

- `esFont` 字段裁决（+0x14 高度/颜色双解，Q-lable-4）→ 3.7 文本排版批；`esFontSheet::GetMathCharType` 语义（GetLableFreature 用）。
- `FUN_1007c700`（0x58B 双盒 esTextItem）与 `FUN_10095830`（0x48B）文本项类的归属/布局 → 3.7。
- `esDS_HV`（GetTextAngle 读，8 字节）与 `esDS_Txt`/`esDimenStyle` 全字段 → S5 余部。
- `esScriber`（引线字型化，Load/Draw 用）→ 后续批。
- `FUN_10027a30`（点数组世界变换）语义确认会影响 Q-lable-10 的最终结论 → 已在 esSeg-base（批 4）落定入口，本批沿用其"世界变换"解释。
