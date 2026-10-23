// analysis/types/esSeg-arc.h
// 绘图弧族（esSegLines / esSegArcBase / esSegArc / esSegArc90 / esSegCircels /
//           esSegArcFace / esSegGonFace / esSegEllipseEx）
// — 阶段 2 第七批（eslib.dll · 绘图核心 3/6）
//
// 证据：
//   [ev:pseudo] analysis/pseudo/eslib/esSeg-arc.decomp.txt   (142/142 函数原样伪代码)
//   [ev:spec]   analysis/pseudo/eslib/esSeg-arc.md           (布局/三点定圆/弧拆分/环带/Q 系列怪癖)
//   [ev:ledger] ledger/ledger.csv  eslib:<rva>（142 行 → status=decompiled）
//
// 谱系（本批定界）：
//   esSegGemotry(批 4 esSeg-base.h) → esSegLines            （批 6 头曾前向声明；本批落定）
//     → esSegArcBase → esSegArc / esSegArc90
//                    → esSegGlow(后续批) → esSegCircels
//   esSegGon(批 6 esSeg-leaf.h) → esSegGonFace
//   esSegArcFace : esSeg（直派，不经 ArcBase；与 esSegArcRuler 同址折叠）
//   esSegEllipse(批 4 块 0x1011de80–0x1011fdxx) → esSegEllipseEx
// 弧族公共布局（esSegArcBase 起）：
//   +0x68 float r · +0x6C int dir · +0x70 float a0 · +0x74 float a1
//   · +0x78/+0x7C center(tagPOINT) · +0x80 float mid（GetMidAngle 缓存）
//   退化 |r|<1e−5 时角度字段直接存坐标（int→float，见 InitPoints/CheckCenterPoint）
// 类型字：0x42c1 esSegArc(0x98) · 0x4306 双角弧 · 0x4307 单角弧（整圆语义） ·
//   0x4282 esSegArc90(0x84) · 0x480f esSegArcFace(0x84) · 0x4c0e esSegGonFace(0x74) ·
//   0x6003 esSegCircels(0x8c) · 0x4a8a esSegEllipseEx(0x7c)
#pragma once

namespace eslib {

// 跨批引用（本批不 dump；见各自头文件）
class esSegGemotry;   // 基座，见 esSeg-base.h（批 4）
class esSegGon;       // 见 esSeg-leaf.h（批 6）
class esSegGlow;      // esSegCircels 的基类（后续批）
class esSegEllipse;   // esSegEllipseEx 的基类（批 4 块 0x1011de80–0x1011fdxx）

// ============================================================
// esSegLines — 全族公共点链工具（显示点缓存 + 前后链 + 控制点数组 + 拆链/联点） [ev:pseudo ctor 0x111350]
// 无自身构造类型字；尺寸同基座
// 布局：+0x34/+0x38 显示点缓存（ptr/count）· +0x3C/+0x40 前/后链对象 · +0x58 ctrl · +0x5C 计数(ushort)
class esSegLines : public esSegGemotry {
public:
    static char const* ID();                                  // 0x111210  "esSegLines"
    virtual int isKindOf(char const*);                        // 0x111220  this==NULL→0；不中→esSegGemotry
    virtual int isOf(char const*);                            // 0x1112c0  仅自比
    esSegLines& operator=(esSegLines const&);                 // 0xf6c0    【ILT 2 符号】→ esSegGemotry::operator=
    esSegLines();                                             // 0x111350  空点链（+0x58=0,+0x5C=0）
    virtual tagPOINT GetStartPoint();                         // 0x111390  0x4307/cnt<2→显示[0]；否则 ctrl[0] 世界化
    virtual tagPOINT GetEndPoint();                           // 0x111480  断开→显示[末]；否则 ctrl[cnt−1] 世界化
    int  GetEndPointIndex();                                  // 0x111570  (+0x5C)−1
    esSegLines* GetBackObj();                                 // 0x111590  +0x40 或链表尾（类型字&0x100→NULL）
    esSegLines* GetNextObj();                                 // 0x111600  +0x3C 或链表头
    virtual void Undo(ushort, zArchive&, zArchive&);          // 0x111670  0xf2e8：type 旧值往返
    virtual void OnMovePoint(zPoint, int, uint, esObjCheck*); // 0x1116e0  仅链上且 type!=0x4307；idx0→back、末位→next 联动
    virtual void CheckIntoRing(esUndo*);                      // 0x111810  0x4701→0x4702；0x4307→0x4306 仅链上【Q-lines-1】
    virtual void MoveLinkPoint(uint flags, esObjCheck*);      // 0x1118c0  flags&0x300 时联动邻链端点（资格判定 103e36b0）
    virtual void BreakLine(int*, int);                        // 0x111a80  断口拆链（bit1=idx0/bit2=末位；内部断口→esSegList 重排）
};

// ============================================================
// esSegArcBase — 弧族基类（控制点 3 点 + 角度字段双表示） [ev:pseudo ctor 0x124330/0x124350/0x1243d0]
// 无自身类型字；尺寸 0x84（esSegArc 扩至 0x98）
// 布局：+0x68 float r · +0x6C int dir(1/0) · +0x70 float a0 · +0x74 float a1 · +0x78/+0x7C center · +0x80 float mid
class esSegArcBase : public esSegLines {
public:
    virtual char const* className() const;                    // 0x10e230  【ILT 2 符号，含 esSegGon】→ esSegLines::ID()
    esSegArcBase& operator=(esSegArcBase const&);             // 0xf8a0    拷 +0x68..+0x80 七字段（换序防混叠）
    virtual ~esSegArcBase();                                  // 0xf3b0    【ILT 5 符号 → ~esSegCircel 折叠名】
    static char const* ID();                                  // 0x1241f0  "esSegArcBase"
    virtual int isKindOf(char const*);                        // 0x124200  不中→esSegLines
    virtual int isOf(char const*);                            // 0x1242a0  仅自比
    esSegArcBase();                                           // 0x124330
    esSegArcBase(ushort type);                                // 0x124350  +0x6C=1（dir 默认 1）
    esSegArcBase(zPoint, ushort);                             // 0x1243d0  3 控制点全=pt；+0x5C=3；center=pt
    virtual void GetBreakLines(esSegList*, int, int*, int);   // 0x124510  弧/gon 两路线；拆段写 0x4306/0x4307【Q-arcbase-1】
    static int GetCircleOrg(tagPOINT* pts, tagPOINT* outOrg, int* outDir); // 0x124b90  三点定圆（弦中垂线；近共线→0）
    void UnitOtherMaxRect(zRect*);                            // 0x124f00  世界化 center 后扩 rect
    void InitPoints();                                        // 0x124fa0  0x4306 且 |r|<1e−5→坐标↔角度；否则三角度点
    void MovePoint_4Points(zPoint, int, uint, esObjCheck*);   // 0x125140  四点模型拖动（idx0/1/2 角/径，idx3 平移）【Q-arcbase-2】
    void MirrPts();                                           // 0x125780  dir 翻转 + a0/a1、pts[0]/pts[2] 交换
    virtual void unMPSave(zArchive&);                         // 0x125860  撤销码 a0→0xf2d1/a1→0xf2d2/r→0xf2d3/dir→0xf2d5/center→0xf2d6
    virtual void Undo(ushort, zArchive&, zArchive&);          // 0x125a30  0xf2d1..0xf2d6 往返
    virtual int SetPointPos(esSnapManager*, int, uint, Gdiplus::Matrix*); // 0x125ba0  mode1→a0=a1=mid=angle；mode2→a1；尾 ResetSnapPointPos
    void CheckArcDirection(int mode, int which);              // 0x125d60  方向归一/对径选择；mode==0 时 r<0→−r 或 cached±π
    void Get3Points(tagPOINT* out3);                          // 0x125ff0  拷 ctrl 0/1/2 原样
    tagPOINT GetCenterPoint();                                // 0x126080  center 经 FUN_10027a30 世界化
    virtual void OnCreate(esStyleSheet*);                     // 0x1260e0  InitPoints
    void CheckCenterPoint(int idx);                           // 0x126100  三分支重排（P0==P2 退化/10<r≤50000 半弦/P0≠P2 弦垂线）
    virtual void BuildEx(esSeg* src, float t);                // 0x126ad0  守卫→Build；step 插值；三点→GetCircleOrg_For3P
    void BuildArc(zPoint, float r, float a0, float a1, int dir); // 0x1270f0（protected）esBezierArc 采样；0x4282 扩 2 点；n<1→两点退化
    virtual void Build(int);                                  // 0x127360  r≤0→退化 2/1 点；否则 esBezierArc 采样 + flags
    int  GetDefaultPtOrg(tagPOINT*);                          // 0x127710  世界化 center；返回 1
    virtual void GetLbcLines(xzLbcList*, Gdiplus::Matrix*, int); // 0x127750  退化 0x4306→单线 [P0,末]；否则圆登记
    tagPOINT GetPointFromAngle(double angle);                 // 0x127960  x=cx+r·sin(a)、y=cy−r·cos(a)（a=0→上，屏幕顺时针）
    virtual int IsEqual(esObject*, esStyleSheet*);            // 0x127a90  基类+矩阵+dir/r/a0/a1/center
    virtual void Serialize(zArchive&, esStyleSheet*, ushort); // 0x127b70  存序 dir,r,a0,a1,center；版本门 0x107010d
    virtual void CopyFrom(esObject const*, esStyleExchanger*); // 0x127de0 同 ID→拷 dir/r/a0/a1/center
    float GetMidAngle();                                      // 0x127e80  【Q-arcbase-3】r<0 就地取正；mid 按方位 ±π
    virtual void SnapFarPoints(esSnapManager*, tagPOINT, int, int); // 0x12bb10  按类型分派垂/水平侧线登记
};

// ============================================================
// esSegArc — 弧（0x42c1/0x4306/0x4307 多用） [ev:pseudo ctor 0x1280d0..0x128290]
// 尺寸 0x98；+0x84 int 环缓存在场标记 · +0x88/+0x8C、+0x90/+0x94 两等待吸附点
class esSegArc : public esSegArcBase {
public:
    static char const* ID();                                  // 0x127f90  "esSegArc"
    virtual int isKindOf(char const*);                        // 0x127fa0  this==NULL→0；不中→esSegArcBase
    virtual int isOf(char const*);                            // 0x128040  仅自比
    esSegArc& operator=(esSegArc const&);                     // 0xf910    ArcBase + 拷 +0x84..+0x94
    esSegArc();                                               // 0x1280d0  +0x84=0
    esSegArc(zPoint, ushort);                                 // 0x128110
    esSegArc(Gdiplus::PointF, float r, float angle, Gdiplus::Matrix*); // 0x128150  type=0x4307（单角，整圆语义）【Q-arcbase-4】
    esSegArc(Gdiplus::PointF, float r, float a0, float a1, Gdiplus::Matrix*, int dir); // 0x128290  type=0x4306（双角）
    virtual int SetPointPos(esSnapManager*, int, uint, Gdiplus::Matrix*); // 0x1283d0  0xe401/0xe402 Snap 预置态 + 0x4306/0x42c1 交互
    int Connect(esSegArc* other);                             // 0x128880  圆心+链邻互指+角度配对（容差 1e−5）→塌缩
    virtual int GetCtlPts(esVertexList*, int);                // 0x128b90  环缓存 2 点 + 开放/闭合点序（flags 0xeb66xxxx）
    virtual void Build(int);                                  // 0x129300  ArcBase::Build + +0x84=0；闭弧吸附命中→缓存 2 点
    virtual int DoSnap(esSnapManager*);                       // 0x1294d0  r≤10 只比心；r>10 圆心/端点/0x100 四点收尾
    virtual int MoveAcmePoints(esVertexGroup*, tagPOINT*, int); // 0x129b10  开放 0x4306 idx1→0；0x4307 idx0/2；闭合→Ring/Cricel
    virtual void MovePoint(zPoint, int, uint, esObjCheck*);   // 0x129f30  开放→3/4 点 + MoveLinkPoint；闭合→Invert+Ring/Cricel
    void MovePoint_Ring(zPoint, int, uint, esObjCheck*);      // 0x12a0d0  【Q-arc-2】入口 dir=1；idx2 平移；center=mid(P1,pt)
    void MovePoint_Cricel(zPoint, int, uint, esObjCheck*);    // 0x12a5c0  【Q-arc-2】dir=1；P1=2·center−P0（对径）
    void MovePoint_3Points(zPoint, int, uint, esObjCheck*);   // 0x12a820  【Q-arc-1】直写模式（r==0 时角度字段存坐标）
};

// ============================================================
// esSegArc90 — 90° 弧（0x4282） [ev:pseudo ctor 0x12af00/0x12af30]
// 尺寸 0x84（无新字段；+0x84 未用）
class esSegArc90 : public esSegArcBase {
public:
    virtual char const* className() const;                    // 0x1c080  【ILT 3 符号，含 Arc/Glow】→ esSegArcBase::ID()
    esSegArc90& operator=(esSegArc90 const&);                 // 0xf980    → esSegArcBase::operator=
    virtual ~esSegArc90();                                    // 0xf700    【ILT 12 符号】→ ~esSegArcBase
    static char const* ID();                                  // 0x12adc0  "esSegArc90"
    virtual int isKindOf(char const*);                        // 0x12add0  不中→esSegArcBase
    virtual int isOf(char const*);                            // 0x12ae70  仅自比
    esSegArc90();                                             // 0x12af00  转发基类
    esSegArc90(zPoint, ushort);                               // 0x12af30
    virtual void GetBreakLines(esSegList*, int, int*, int);   // 0x12af60  状态机：3 弧（force 0x4307）+ 2 esSegGon
    virtual int GetCtlPts(esVertexList*, int);                // 0x12b5c0  4 点 [P0,P1,P2,center]
    virtual void MovePoint(zPoint, int, uint, esObjCheck*);   // 0x12b710  纯转发 MovePoint_4Points（41 字节）
    virtual void GetLbcLines(xzLbcList*, Gdiplus::Matrix*, int); // 0x12b740  开口尾段（末两显示点）登记
    virtual int DoSnap(esSnapManager*);                       // 0x12b800  【Q-arc90-1】双 SnapObj（0x4000 + 尾 0x1000）；SnapPoints([P0,P2])
};

// ============================================================
// esSegCircels — 同心圆环组（0x6003；双亲链 ArcBase→esSegGlow→Circels） [ev:pseudo ctor 0x1af70/0x1afb0]
// 尺寸 0x8c；+0x84 float 内半径（起始半径）· +0x88 float 环距（ctor 默认 0x4b0=1200 单位=3mm）· +0x68 r（末半径）
class esSegCircels : public esSegGlow {
public:
    virtual ~esSegCircels();                                  // 0xf790    【ILT 5 符号】→ ~esSegArc90
    esSegCircels& operator=(esSegCircels const&);             // 0x10bc0   → esSegGlow::operator=
    static char const* ID();                                  // 0x1ae20   "esSegCircels"
    virtual int isKindOf(char const*);                        // 0x1ae30   不中→esSegGlow
    virtual char const* className() const;                    // 0x1aed0   → esSegGlow::ID()
    virtual int isOf(char const*);                            // 0x1aee0   仅自比
    esSegCircels();                                           // 0x1af70   +0x88=0x4b0
    esSegCircels(zPoint);                                     // 0x1afb0   +0x84=0
    virtual int DoSnap(esSnapManager*);                       // 0x1b5f0   逐环 SnapObj（环数=步长/环距+1，余数>10 且环距<内径→+2）
    virtual void GetLbcLines(xzLbcList*, Gdiplus::Matrix*, int); // 0x1b960  逐环回归线登记
    virtual void Load(elfPage*, elfSubject*, tag_DRAWPARAM*); // 0x1bb80   直通 esSeg::Load
    virtual void Draw(esRender*, tag_DRAWPARAM*, Gdiplus::Matrix*); // 0x1bbb0 直通 esSeg::Draw
    virtual void Build(int);                                  // 0x1bbe0   r/内半径夹≥100；逐环 GetPts；flags 环首 0 余 3
    virtual void LoadProp(esPropManager*, ulong);             // 0x1be80   组 0x1b00 / 项 0x1b01=环距>>2【Q-circels-1】
    virtual void SaveProp(esPropManager*, ulong);             // 0x1bed0   内半径撤销码 0xf2d4；CheckWrite(+0x88)
};

// ============================================================
// esSegArcFace — 圆弧环面（0x480f；esSeg 直派；与 esSegArcRuler 同址折叠） [ev:pseudo ctor 0x1e010/0x1e060]
// 尺寸 0x84；+0x68 ushort 幅宽（默认 500 单位=1.25mm）· +0x6A byte 翻向 · +0x6C 环带点(2n+1)
//   · +0x70 环带 flags · +0x74 点数(2n+1)
class esSegArcFace : public esSeg {
public:
    static char const* ID();                                  // 0x1ded0  "esSegArcFace"
    virtual int isKindOf(char const*);                        // 0x1dee0  不中→esSeg（直派）
    virtual int isOf(char const*);                            // 0x1df80  仅自比
    esSegArcFace& operator=(esSegArcFace const&);             // 0x10ee0   esSeg::operator= + 拷 +0x68..+0x80
    esSegArcFace();                                           // 0x1e010   type=0x480f
    esSegArcFace(zPoint);                                     // 0x1e060   +0x5C=3 三点全=pt；+0x68=500
    virtual ~esSegArcFace();                                  // 0x1e1a0   free +0x6C/+0x70 + esSeg::~esSeg（直调）
    virtual int GetRgnPts(tagPOINT**, unsigned char**);       // 0x1e200   memcpy 环带点；flags 源疑为 +0x6C【Q-arcface-1】
    virtual void RecalcLayout();                              // 0x1e2b0   环带优先；GetPathBounds→SetSolidRect/SetBoundingRect
    virtual void Load(elfPage*, elfSubject*, tag_DRAWPARAM*); // 0x1e370   填充=环带 elfPathGeometry(2)；描边=显示点
    virtual void Draw(esRender*, tag_DRAWPARAM*, Gdiplus::Matrix*); // 0x1e550 填充 egPath(环带)+vtbl+0x78；描边 DrawPath
    virtual void LoadProp(esPropManager*, ulong);             // 0x1e6e0   组 0x1a00 / 项 0x1a01=幅宽>>2、0x1a02=翻向
    virtual void SaveProp(esPropManager*, ulong);             // 0x1e740
    virtual void Undo(ushort, zArchive&, zArchive&);          // 0x1e7e0   0x1a01↔+0x68、0x1a02↔+0x6A；else esFormulaBox::CaretMove
    virtual int IsEqual(esObject*, esStyleSheet*);            // 0x1e880   基类 + +0x68/+0x6A
    virtual void Serialize(zArchive&, esStyleSheet*, ushort); // 0x1e8f0   基类 + +0x68/+0x6A
    virtual void CopyFrom(esObject const*, esStyleExchanger*); // 0x1e970  isOf(ID)→拷 +0x68/+0x6A
    virtual int SetPointPos(esSnapManager*, int, uint, Gdiplus::Matrix*); // 0x1e9f0 开放 P2 / 闭合 P1；mode≠1→2
    virtual void Build(int);                                  // 0x1eb10   幅宽 ±500；内弧+外弧反序（+0x74=2n+1）；显示=内弧一半
    // --- esSegArcRuler 同址折叠（2 符号组）---
    virtual void BreakLine(int*, int);                        // 0x18c00   循环首点回填 pts[2]=pts[0]；undo 0xf2ff【Q-arcface-2】
    virtual void* Undata(ushort&, void*, int&);               // 0x18cd0   0xf2ff→同旋转；else esSeg::Undata
    virtual void MovePoint(zPoint, int, uint, esObjCheck*);   // 0x19a40   pts[idx]=pt；cyclical 首末同步
    void CheckCenterPoint(int idx);                           // 0x19b00   弦中点（y 等/x 等/旋转法）
};

// ============================================================
// esSegGonFace — 多边形环面（0x4c0e；esSegGon 子类） [ev:pseudo ctor 0x3f26d0/0x3f2710]
// 尺寸 0x74；+0x68 ushort 幅宽（默认 500）· +0x6A byte 翻向 · +0x6C 内缩点数组 · +0x70 计数
class esSegGonFace : public esSegGon {
public:
    static char const* ID();                                  // 0x3f2590  "esSegGonFace"
    virtual int isKindOf(char const*);                        // 0x3f25a0  不中→esSegGon
    virtual int isOf(char const*);                            // 0x3f2640  仅自比
    esSegGonFace& operator=(esSegGonFace const&);             // 0x10d70   esSegGon::operator= + 拷 4 字段
    esSegGonFace();                                           // 0x3f26d0  type=0x4c0e；不写 +0x68/+0x6A【Q-gonface-1】
    esSegGonFace(zPoint);                                     // 0x3f2710  +0x68=500、+0x6A=0
    virtual ~esSegGonFace();                                  // 0x3f2780  free +0x6C + 基类（不折叠）
    virtual int GetRgnPts(tagPOINT**, unsigned char**);       // 0x3f27c0  用 +0x70 计数；flags 全 1 后 [0]=0
    virtual void RecalcLayout();                              // 0x3f2880  内缩点优先→GetPathBounds→SetSolidRect/SetBoundingRect
    virtual void Undo(ushort, zArchive&, zArchive&);          // 0x3f2970  0x1a01/0x1a02；else esSegLines::Undo
    virtual void CopyFrom(esObject const*, esStyleExchanger*); // 0x3f2a10 基座 + +0x68/+0x6A
    virtual void Build(int);                                  // 0x3f2a90  free +0x6C；outline 边偏移 ±幅宽；顶点 GetJiaoDians；尾接基类
    int GetJiaoDians(tagPOINT* out, zPoint, zPoint, zPoint);  // 0x3f2dc0  miter=±幅宽·tan(d/2)；clamp ±5000；返回 0/1/2【Q-gonface-2】
    virtual void Load(elfPage*, elfSubject*, tag_DRAWPARAM*); // 0x3f3140  双 elfPathGeometry(0x40)+AddExLines
    virtual void Draw(esRender*, tag_DRAWPARAM*, Gdiplus::Matrix*); // 0x3f3310 liquid→AddLines+esLiquid::OnDraw；fill/pen
};

// ============================================================
// esSegEllipseEx — 椭圆延伸（0x4a8a；esSegEllipse 子类） [ev:pseudo ctor 0x1d9b0/0x1d9e0]
// 尺寸 0x7c；显示点=14=两组 7 点贝塞尔（内/外轮廓）
class esSegEllipseEx : public esSegEllipse {
public:
    esSegEllipseEx& operator=(esSegEllipseEx const&);         // 0x10dc0   → esSegEllipse::operator=
    static char const* ID();                                  // 0x1d860   "esSegEllipseEx"
    virtual int isKindOf(char const*);                        // 0x1d870   不中→esSegEllipse 链
    virtual char const* className() const;                    // 0x1d910   → 父 esSegEllipse::ID
    virtual int isOf(char const*);                            // 0x1d920   仅自比
    esSegEllipseEx();                                         // 0x1d9b0   父 ctor + type=0x4a8a
    esSegEllipseEx(zPoint);                                   // 0x1d9e0
    virtual void Load(elfPage*, elfSubject*, tag_DRAWPARAM*); // 0x1da20   两带环轮廓 AddExBeziers(+0x34,7) + (+0x34 偏移 +0x30,7)
    virtual void Draw(esRender*, tag_DRAWPARAM*, Gdiplus::Matrix*); // 0x1dd60 填充 vtbl+0x78；dash→两段式 DrawBeziers【Q-ellipseex-1】
};

}
