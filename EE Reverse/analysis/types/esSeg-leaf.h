// analysis/types/esSeg-leaf.h
// 绘图叶段族（esSegLine / esSegGon / esSegRect / esSegRectEx / esSegRoundRect / esSegCircel / esSegPoint）
// — 阶段 2 第六批（eslib.dll · 绘图核心 2/6）
//
// 证据：
//   [ev:pseudo] analysis/pseudo/eslib/esSeg-leaf.decomp.txt   (174/174 函数原样伪代码)
//   [ev:spec]   analysis/pseudo/eslib/esSeg-leaf.md           (布局/点序/交互吸附族/撤销码/Q 系列怪癖)
//   [ev:ledger] ledger/ledger.csv  eslib:<rva>（174 行 → status=decompiled）
//
// 谱系（本批定界）：
//   esSeg → esSegLines(批 7) → esSegGon → esSegLine          （Gon 是 Line 的父类）
//   esSegNative（中间层，符号折叠）→ esSegPoint
//   esSeg → esSegGemotry(批 4 esSeg-base.h) → esSegRect → esSegRectEx
//                                           → esSegRoundRect
//                                           → esSegCircel
// 布局（继承自 esSeg 基座）：+0x58 控制点数组 · +0x5C 计数 · +0x34/+0x38 显示点缓存 · +0x4C 矩阵
#pragma once

namespace eslib {

// 中间层占位（不属本批 dump；细节分别见 esSeg-base.h 与后续批）
class esSegNative;   // esSegPoint 的基类（symbol 折入 esSeg 系）
class esSegLines;    // esSegGon 的基类（15 个函数留待后续批）

// ============================================================
// esSegLine — 两点直线 + 12 种"线约束"交互吸附模式 [ev:pseudo ctor 0xeb80/0xebb0/0xebf0]
// 尺寸 0x68（无新字段：+0x58 两点、+0x5C=2）
// ★ 对象可承载**任意类型字**（ctor 直写）：type==0xe100..0xe10b 时 SetPointPos 进入约束分派，
//   0xe100→SetAngleLine · e101→SetVertical · e102→SetCVertical · e103→SetMeanLine ·
//   e104→SetTangent · e105→SetPingLine1 · e106→SetPingLine2 · e107→SetVLine ·
//   e108→SetHTangent · e109→SetVTangent · e10a→SetGongTangent · e10b→SetCurveTangent
class esSegLine : public esSegGon {
public:
    static char const* ID();                                  // 0xea40  "esSegLine"
    virtual int isKindOf(char const*);                        // 0xea50  → esSegGon::isKindOf
    virtual int isOf(char const*);                            // 0xeaf0
    esSegLine();                                              // 0xeb80  esSegGon + type=0x4701
    esSegLine(zPoint, unsigned short type);                   // 0xebb0  type 任意（0xe1xx 交互模式入口）
    esSegLine(zPoint, zPoint, Gdiplus::Matrix*);              // 0xebf0  矩阵空→AnyMove(a,b,1,0)
    esSeg* GetClipLine(double t1, double t2);                 // 0xeca0  P(t)=p0+(p1−p0)t；已存在→NULL
    virtual int SetPointPos(esSnapManager*, int, uint, Gdiplus::Matrix*); // 0xeec0  按 type−0xe100 分派
    // --- 约束模式实现（protected；返回码 1=自由点更新 / 2=吸附命中+type 复位 0x4701 / 4=已锁定）---
    int SetAngleLine(esSnapManager*, int, uint, Gdiplus::Matrix*);    // 0xf2c0  定角
    int SetGongTangent(esSnapManager*, int, uint, Gdiplus::Matrix*);  // 0xf4c0  公切
    int SetVertical(esSnapManager*, int, uint, Gdiplus::Matrix*);     // 0xf6d0  竖直
    int SetTangent(esSnapManager*, int, uint, Gdiplus::Matrix*);      // 0xf800  切线（静态暂存 +0x218/0x21c）
    int SetCurveTangent(esSnapManager*, int, uint, Gdiplus::Matrix*); // 0xfad0  曲线切线
    int SetCVertical(esSnapManager*, int, uint, Gdiplus::Matrix*);    // 0xfbf0  连心竖直
    int SetMeanLine(esSnapManager*, int, uint, Gdiplus::Matrix*);     // 0xfea0  中线
    int SetVLine(esSnapManager*, int, uint, Gdiplus::Matrix*);        // 0x110110 垂线
    int SetPingLine1(esSnapManager*, int, uint, Gdiplus::Matrix*);    // 0x110300 平行线1
    int SetPingLine2(esSnapManager*, int, uint, Gdiplus::Matrix*);    // 0x110530 平行线2
    int SetHTangent(esSnapManager*, int, uint, Gdiplus::Matrix*);     // 0x1106e0 水平切
    int SetVTangent(esSnapManager*, int, uint, Gdiplus::Matrix*);     // 0x110900 竖直切
    virtual int  MoveAcmePoints(esVertexGroup*, tagPOINT*, int);      // 0x110b10 type==0x4702→esSegBezier 系
    virtual void MovePoint(zPoint, int, uint, esObjCheck*);           // 0x110ba0 单点链→ExtendingLine；尾 MoveLinkPoint
    virtual void BuildEx(esSeg* src, float t);                        // 0x110c50 点数等→逐点 step 插值
};

// ============================================================
// esSegGon — 折线/多边形（本批最大族） [ev:pseudo ctor 0xe2d0/0xe300/0xe5f0]
// 尺寸 0x68；+0x58 控制点（ushort 计数 +0x5C）
class esSegGon : public esSegLines {
public:
    int GetPointCount();                                      // 0xeb10  【ILT ≡ esSeg::GetVertexCount】
    esSegGon& operator=(esSegGon const&);                     // 0xf6e0  → esSegLines::operator=
    static char const* ID();                                  // 0xe180  "esSegGon"
    virtual int isKindOf(char const*);                        // 0xe190  → esSegLines::isKindOf
    virtual int isOf(char const*);                            // 0xe240
    esSegGon();                                               // 0xe2d0  type=0x4702
    esSegGon(tagPOINT*, int n, Gdiplus::Matrix*);             // 0xe300  operator new(count*8) 拷贝点
    esSegGon(zPoint, zPoint);                                 // 0xe5f0  2 点版
    virtual void BreakLine(int*, int);                        // 0xe3f0  闭合→点数组旋转；undo 0xf2ff
    static esSegGon* FromBezer(Gdiplus::PointF*, int);        // 0xe6d0  每 3 点取一建折线
    int  CheckFirstLastLink(double eps);                      // 0xe800  首尾重复点合并（count−−）
    void ResetMatrix();                                       // 0xe8e0  type 0x4701→0x4702 + 复位矩阵
    esSegGon* Normatllize();                                  // 0xe930  0x4701/0x4704 → Gon 化拷贝
    virtual void SnapFarPoints(esSnapManager*, tagPOINT, int, int); // 0x112140 登记垂/水平辅助线
    int  LinkTo(esSegGon* other);                             // 0x112240 同型联线（0x4704 要求轴向）
    virtual void SnapPointWhenCreate(esSnapManager*) const;   // 0x1124b0 中点吸附（count<0x14）
    virtual int  DoSnap(esSnapManager*);                      // 0x1125d0 集 A 全点+中点；其它类型首末点
    virtual void* Undata(ushort&, void*, int&);               // 0x1127a0 undo 0xf2ef/0xf2ee/0xf2ff
    void AppendPoint(zPoint);                                 // 0x112a80 共线→替换末点，否则追加
    int  GetSnapPoints(tagPOINT*, zRect&, int lenient);       // 0x112b20 【Q-gon-2 非稳健简化轮廓】
    void FitLines(int a, int b);                              // 0x112fc0  esBezier3::FitToBezierA
    virtual int  AddPoint(zPoint, int flag, int d);           // 0x113020 命中线段→InsertPoint；undo 0xf2ef/0xf2e8
    void InsertPoint(int idx, zPoint);                        // 0x1133d0 【ILT ≡esSegLinkHVLine】【Q-gon-1】
    void DelPoint(int idx);                                   // 0x1134e0 【ILT ≡esSegLinkHVLine】【Q-gon-1】
    virtual int  DeletePoint(int idx, int probe);             // 0x1135e0 闭合且 count≤4 拒绝；可能自毁；undo 0xf2ee
    int  GetNextPoint(int idx, tagPOINT* out);                // 0x1139d0
    virtual void GetBreakLines(esSegList*, int, int*, int);   // 0x113b40 逐段 Create+AddLines+矩阵克隆
    int  GetBackPoint(int idx, tagPOINT* out);                // 0x113d40
    void GetNearPt(tagPOINT&, int idx, int flag);             // 0x113ea0 阈值 0x259=601
    virtual void BuildEx(esSeg* src, float t);                // 0x114090 计数等→逐点 step；否则 Build(0)
    virtual void BuildLines(tagPOINT*, int n);                // 0x1141b0 SetPtInfo + 接管所有权（delete[]）
    virtual void Build(int);                                  // 0x114210 vtbl+0xF0(+0x58,+0x5C)
    virtual int  MovePointTo(esSeg*, zPoint, int which, int noundo); // 0x114240 undo 0xf2dc(16B)
    virtual int  SetPointPos(esSnapManager*, int, uint, Gdiplus::Matrix*); // 0x114360 【ILT ≡esSegPipe】【Q-gon-1/3】
    virtual tagPOINT GetAcmePoint(int idx);                   // 0x114500 pts[idx] 世界化
    int  SetAcmePoint(int idx, tagPOINT);                     // 0x114570
    void ExtendingLine(zPoint, int which);                    // 0x114660 水平延长（which∈{0,1}）
    virtual void MovePoint(zPoint, int, uint, esObjCheck*);   // 0x114830 孤点两段→ExtendingLine；闭合首末同步
};

// ============================================================
// esSegRect — 轴对齐矩形（Acme 8 点交互 + 锁定比例缩放） [ev:pseudo ctor 0x109c50..]
// 尺寸 0x70；+0x68 byte 样式（低 3 位 Acme 样式；bit4 与样式 1 联动）
//              +0x6c float s=锁定比 W/H（ResetLockedScale）
// Acme 点序：0=TL 1=BR 2=TR 3=BL 4=L-mid 5=R-mid 6=T-mid 7=B-mid
class esSegRect : public esSegGemotry {
public:
    static char const* ID();                                  // 0x109b00 "esSegRect"
    virtual int isKindOf(char const*);                        // 0x109b10 → esSegGemotry::isKindOf
    virtual int isOf(char const*);                            // 0x109bc0
    // className() 见 esSegCircel（5 符号折叠：Circel/Lines/Polygon/Rect/RoundRect）
    esSegRect& operator=(esSegRect const&);                   // 0xf070  → esSegGemotry +0x68/0x6c
    esSegRect();                                              // 0x109c50
    esSegRect(zPoint const&, unsigned short type);            // 0x109c90 退化（两点同值、"跟随光标"）
    esSegRect(tagRECT*);                                      // 0x109d90 type=0x4281；+0x68=0x11
    esSegRect(zPoint const&, zSize const&);                   // 0x109ea0
    void GetRectPoints(tagPOINT* out5);                       // 0x109fb0 TL,TR,BR,BL,TL
    virtual void GetBreakLines(esSegList*, int, int*, int);   // 0x10a0e0 断口 bitmask；esSegHVLine 拼段
    tagPOINT GetPointAt(int idx);                             // 0x10a440（protected）
    void SetRect(long l, long t, long r, long b);             // 0x10a590
    void SetRect(tagRECT*);                                   // 0x10a600
    virtual int  SetPointPos(esSnapManager*, int, uint, Gdiplus::Matrix*); // 0x10a680 【Q-rect-1：0xa010 走锁定比】
    virtual int  MoveAcmePoints(esVertexGroup*, tagPOINT*, int);           // 0x10a9a0
    virtual void MovePoint(zPoint, int, uint, esObjCheck*);                // 0x10aa40
    virtual void unMPSave(zArchive&);                         // 0x10ab50 读回变化→记录 0x2202
    virtual void LoadProp(esPropManager*, ulong);             // 0x10abe0 组 0x2200 / 项 0x2201 = style&7
    void SetAcmeStyle(int k);                                 // 0x10ac30 style=(style&0xf8)|k
    zRect GetRect() const;                                    // 0x10ac60
    virtual void SaveProp(esPropManager*, ulong);             // 0x10acd0 (item&7)==1→置 bit4，否则清
    virtual void Undo(ushort, zArchive&, zArchive&);          // 0x10ada0 undo 0x2201 swap byte / 0x2202 swap float
    tagPOINT* GetCurAcmePoints(int& n);                       // 0x10ae50（protected）style&7：4→NULL / 0→8 / 1→4 / 2→2 / 其余→2
    virtual int  DoSnap(esSnapManager*);                      // 0x10b3c0（protected）【Q-rect-2：i=0 读 pts[−1]】
    uint ClipRect(esRender*);                                 // 0x10b5e0 egPath+CloseFigure→SetClip
    virtual int  GetCtlPts(esVertexList*, int);               // 0x10b6b0 n==2 时索引对 {2·(style&7),+1}
    virtual int  IsEqual(esObject*, esStyleSheet*);           // 0x10b7e0 基类 && style && s
    virtual void Serialize(zArchive&, esStyleSheet*, ushort); // 0x10b850 byte 样式 + float s；版本门 0x106070a
    virtual void CopyFrom(esObject const*, esStyleExchanger*);// 0x10b8f0
    virtual void BuildEx(esSeg*, float);                      // 0x10b960 两点逐分量插值→5 点
    virtual void Build(int);                                  // 0x10bba0（protected）5 点 TL,TR,BR,BL,TL
    // --- 静态几何（protected）---
    static void get_scale(double s, double& dx, double& dy);  // 0x10bd10 |s|≥eps；m=max(|dx/s|,|dy|) 等比化
    static void MovePointForLock(tagPOINT*, zPoint, int idx, float s);   // 0x10be20 对边反推
    static void MovePointForFree(tagPOINT*, zPoint, int idx, uint flags); // 0x10c100 flags&8→成对对称
    void ResetLockedScale();                                  // 0x10c430 s=|W|/|H|
};

// ============================================================
// esSegRectEx — 扩展矩形（子类；未新增字段） [ev:pseudo ctor 0x109770/0x1097a0]
// 尺寸 0x70；用途 = 可命中内部/边线、尺寸交换撤销
class esSegRectEx : public esSegRect {
public:
    static char const* ID();                                  // 0x109630 "esSegRectEx"
    virtual int isKindOf(char const*);                        // 0x109640 → esSegRect::isKindOf
    virtual int isOf(char const*);                            // 0x1096e0
    esSegRectEx& operator=(esSegRectEx const&);               // 0xf3d0 → esSegRect::operator=
    esSegRectEx();                                            // 0x109770 type=0xd083
    esSegRectEx(zPoint, zPoint);                              // 0x1097a0 type=0xd083；count=2；+0x68=0
    zSize GetRectSize();                                      // 0x109880 zSize(|R−L|,|B−T|)
    void SetRectSize(int w, int h);                           // 0x109910 TopLeft 回写；pts[1]=TL+(w,h)
    virtual int  HitTest(esHitTest*, int);                    // 0x1099d0 7=边上 / 8=内部
    virtual void* Undata(ushort&, void*, int&);               // 0x109a50 undo 0x5fe（尺寸交换语义）
};

// ============================================================
// esSegRoundRect — 圆角矩形（12 顶点环 + 4 角半径） [ev:pseudo ctor 0x11ff40/0x11ffd0/0x1200f0]
// 尺寸 0x6c；+0x68 = 指针 → 4 个 int 半径 [0]=TL [1]=TR [2]=BR [3]=BL（16B）
// 12 点环：0=(L,midY) 1=(midX,T) 2=(R,midY) 3=(midX,B)；4..11 = 四角弧端点（绕行 0→4→5→6→7→8→9→10→11→0）
class esSegRoundRect : public esSegGemotry {
public:
    virtual int IsEqual(esObject*, esStyleSheet*);            // 0x119340 基类 && memcmp(半径,0x10)
    virtual void Serialize(zArchive&, esStyleSheet*, ushort); // 0x1193b0 半径块 16B 原始读写
    virtual void CopyFrom(esObject const*, esStyleExchanger*);// 0x119410
    static char const* ID();                                  // 0x11fe00 "esSegRoundRect"
    virtual int isKindOf(char const*);                        // 0x11fe10 → esSegGemotry::isKindOf
    virtual int isOf(char const*);                            // 0x11feb0
    esSegRoundRect& operator=(esSegRoundRect const&);         // 0xf5f0 → 基类 + 拷 +0x68 指针
    esSegRoundRect();                                         // 0x11ff40 type=0x4283；alloc 半径【Q-RoundRect-2 未清零】
    esSegRoundRect(zPoint const&);                            // 0x11ffd0 半径清零；两点同值（退化）
    esSegRoundRect(zPoint const&, zSize const&, int round);   // 0x1200f0 四半径=round
    virtual ~esSegRoundRect();                                // 0x120230 free(+0x68)
    virtual void GetBreakLines(esSegList*, int, int*, int);   // 0x120270 每直段一个 esSegGon；角弧→esSegArc
    virtual int  DoSnap(esSnapManager*);                      // 0x120890（protected）中心 0x40 + 4 侧中点 8
    virtual void unMPSave(zArchive&);                         // 0x120b40 半径块比较→Rec 0xf2f8
    virtual void* Undata(ushort&, void*, int&);               // 0x120c20 undo 0xf2f8（半径 16B 交换）
    virtual int  SetPointPos(esSnapManager*, int, uint, Gdiplus::Matrix*); // 0x120cb0 拖 (R,B)；flags&8 正方形；四半径=min(|W|,|H|)/4
    virtual void MovePoint(zPoint, int, uint, esObjCheck*);   // 0x120f60 flags&8 且 idx<4→对称拉伸；4..11→SetRound
    void SetRound(int corner, zPoint, zPoint, zPoint, uint flags); // 0x1213c0（protected）【Q-RoundRect-1 越界读】
    static int SetPoints(tagPOINT*, unsigned char*, int idx, zPoint p1, zPoint p2, zPoint p3); // 0x121570 t=0.5523 弧近似
    virtual int  GetCtlPts(esVertexList*, int);               // 0x121720 12 环 → esVertexInfo(...,0xc,this)
    static tagPOINT* GetVertexPoints(tagPOINT*, ulong* radii);// 0x1217f0（protected）生成 12 点环
    virtual void BuildEx(esSeg*, float);                      // 0x121cd0 2 ctrl + 4 半径插值
    virtual void Build(int);                                  // 0x121e50（protected）GetVertexPoints→BuildShape
    void BuildShape(tagPOINT* v);                             // 0x121ec0（protected）TL,TR,BR,BL；SetPtInfo(...,0,1)
};

// ============================================================
// esSegCircel — 圆（Bezier 弧采样 + 圆族交互模式） [ev:pseudo ctor 0x122260/0x1222f0/0x1223b0]
// 尺寸 0x8c；+0x68 float r · +0x6c float angle · +0x70/+0x74 float 圆心 · +0x78 int closed
//              +0x7c..+0x88 两个端点（closed 时 Invert 后坐标）
// ★ 0xe280..0xe289 交互模式分派：0xe280→ForR；{e281,e284,e285,e289}→For3Q；
//   {e282,e283,e288}→For2Q；{e286,e287}→For1Q；其余→Normal
class esSegCircel : public esSegGemotry {
public:
    virtual ~esSegCircel();                                   // 0xf050 【ILT 4 符号折叠】
    esSegCircel& operator=(esSegCircel const&);               // 0xf810 → 基类 + 拷 +0x68..+0x88（9 dword）
    virtual char const* className() const;                    // 0x109bb0 【ILT 5 符号折叠】→esSegGemotry::ID()
    static char const* ID();                                  // 0x122120 "esSegCircel"
    virtual int isKindOf(char const*);                        // 0x122130 → esSegGemotry::isKindOf
    virtual int isOf(char const*);                            // 0x1221d0
    esSegCircel();                                            // 0x122260 type=0x4284；+0x78=0、+0x6c=0
    esSegCircel(zPoint, unsigned short type);                 // 0x1222f0 type 任意（0xe28x 交互模式入口）
    esSegCircel(Gdiplus::PointF, float r, float angle, Gdiplus::Matrix*); // 0x1223b0
    void SetCircleFromPt(Gdiplus::PointF);                    // 0x122470（protected）r=距离；角=GetAngle_y(心→pt)
    virtual void GetLbcLines(xzLbcList*, Gdiplus::Matrix*, int); // 0x1224f0 登记线标注通道
    virtual int  GetDefaultPtOrg(tagPOINT*);                  // 0x122580
    virtual int  GetCtlPts(esVertexList*, int);               // 0x1225e0 closed→2 端点(owner=NULL) + {圆心,圆上起点}
    virtual int  IsEqual(esObject*, esStyleSheet*);           // 0x1228e0 【Q-circel-1：angle 比对方 r】
    virtual void GetBreakLines(esSegList*, int, int*, int);   // 0x122980 【Q-circel-2：断口 0→esSegArc 强制 0x4307】
    virtual void Serialize(zArchive&, esStyleSheet*, ushort); // 0x122ac0 float r, cx, cy, angle
    virtual void CopyFrom(esObject const*, esStyleExchanger*);// 0x122b90
    virtual int  DoSnap(esSnapManager*);                      // 0x122c20（protected）SnapObj 0x4000；心 0x40；起点 2；0x100 四象限
    virtual int  SetPointPos(esSnapManager*, int, uint, Gdiplus::Matrix*); // 0x123070 按 type 分派（见类注）
    virtual void SnapFarPoints(esSnapManager*, tagPOINT, int, int); // 0x123150 圆心辅助线
    int  CreateCircelForR(esSnapManager*, int, uint, Gdiplus::Matrix*);      // 0x123240（protected）
    int  CreateCircelFor1Q(esSnapManager*, int, uint, Gdiplus::Matrix*);     // 0x123380（protected）
    int  CreateCircelFor2Q(esSnapManager*, int, uint, Gdiplus::Matrix*);     // 0x123490（protected）
    int  CreateCircelFor3Q(esSnapManager*, int, uint, Gdiplus::Matrix*);     // 0x123590（protected）
    int  SetPointPos_Normal(esSnapManager*, int, uint, Gdiplus::Matrix*);    // 0x1236b0（protected）
    virtual int  MoveAcmePoints(esVertexGroup*, tagPOINT*, int);             // 0x123780 计数字段 0→SetCircleFromPt 否则移心
    virtual void MovePoint(zPoint, int, uint, esObjCheck*);   // 0x123840 flags&8+idx0→旋角；idx1→移心；否则 SetCircleFromPt
    virtual void unMPSave(zArchive&);                         // 0x123930 角/r/心 三码独立→0xf2d0/0xf2d3/0xf2d6
    virtual void Undo(ushort, zArchive&, zArchive&);          // 0x123aa0 swap 角/r/心
    virtual void BuildEx(esSeg*, float);                      // 0x123be0 心 step 插值、r 线性插值
    virtual void Build(int);                                  // 0x123e60（protected）esBezierArc→SetPtInfo(n,3,1)；闭合探测→+0x78
};

// ============================================================
// esSegPoint — 点（加粗点；宿主 esShapeLine 0x3109） [ev:pseudo ctor 0x3e8530/0x3e8560]
// 尺寸 0x68；+0x58 控制点（1×tagPOINT）· +0x5C=1
// 类型字：0x6001 实点（工厂）；临时交互模式 0xE001/0xE002/0xE003（吸附落定后复位为 0x6001）
// ★ 勘误：早前误记为 0x6001/0x6002/0x6003（实为 0xE0xx，反编译按带符号短整型显示为 -0x1fff..）
class esSegPoint : public esSegNative {
public:
    static char const* ID();                                  // 0x3e83f0 "esSegPoint"
    virtual int isKindOf(char const*);                        // 0x3e8400 → esSegNative::isKindOf
    virtual int isOf(char const*);                            // 0x3e84a0
    esSegPoint();                                             // 0x3e8530 type=0x6001
    esSegPoint(zPoint, unsigned short type);                  // 0x3e8560
    virtual ~esSegPoint();                                    // 0x3e8610
    virtual int  SetPointPos(esSnapManager*, int, uint, Gdiplus::Matrix*); // 0x3e8630 按 type 分派【Q-point-3】
    virtual int  DoSnap(esSnapManager*);                      // 0x3e89c0（protected）IsSnapable(2)→首点 SnapPoint
    virtual int  GetCtlPts(esVertexList*, int);               // 0x3e8a30 → esSegArcRuler::GetCtlPts
    virtual void Build(int);                                  // 0x3e8a50（protected）→ esSeg::Build
    virtual void RecalcLayout();                              // 0x3e8a70（protected）笔宽(min 50)方形包围【Q-point-1】
    virtual void Load(elfPage*, elfSubject*, tag_DRAWPARAM*);// 0x3e8b90 实心圆（半宽=max(线宽,50)）【Q-point-1/2】
    virtual void Draw(esRender*, tag_DRAWPARAM*, Gdiplus::Matrix*); // 0x3e8d00 FillEllipse(x−w,y−w,2w,2w)【Q-point-1/2】
};

} // namespace eslib
