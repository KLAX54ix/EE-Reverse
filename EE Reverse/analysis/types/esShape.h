// analysis/types/esShape.h
// 形状对象族（esShapeBase / esShapeLine / esShapeCap / esShapePath / esShapeGroup）
// — 阶段 2 第十批（eslib.dll · 绘图核心 6/6 · S1 形状核心）
//
// 证据：
//   [ev:pseudo] analysis/pseudo/eslib/esShape.decomp.txt   (253/253 函数原样伪代码)
//   [ev:spec]   analysis/pseudo/eslib/esShape.md           (§0 布局总表 / §4.1 重段型表 / §6 撤销码 / Q-shape-*)
//   [ev:ledger] ledger/ledger.csv  eslib:<rva>（253 行 → status=decompiled）
//
// 谱系（本批定界）：
//   esObject → esShapeBase（+0x34 flags · +0x40 seg · +0x44/+0x48 next/prev · +0x4c role）
//     ├ esShapeLine（0x3109；pen @+0x50，端饰 +0x5c/+0x5e）
//     └ esShapeCap（0x320b；+0x60 尺寸字）
//          ├ esShapePath（0x330f；+0x60/+0x64 段表链 · +0x68 brush · +0x6c liquid · +0x70 bright=100）
//          └ esShapeGroup（0x3008；+0x5c/+0x60 子链 · +0x64/+0x6a 链接点 · +0x74 esMatrixObj）
// 工厂尺寸（Group::CreateObject 3c6be0 权威表）：0x3908 Holder 0x68 / 0x320b Cap 0x60 / 0x3008 Group 0x84 /
//   0x3109 Line 0x5c / 0x330f Path 0x74 / 0x3700 Ole 0x88 / 0x3e00 Dime 0x50 / 0x3a03 Link 0x60 /
//   0x3a08 Control 0x50 / 0xb001 esSegGroupRect 0x78
// 类型字：0x3109 Line · 0x320b Cap · 0x3008 Group · 0x330f Path · 0x3908 Holder · 0x3a08 Control ·
//   0x3700 Ole · 0x3e00 Dime · 0x3a03 Link · 0xb001 组矩形伪段
// 段型→段类（Path 大 ctor 19e200，§4.1）：0xe1..e5xx 快速段 / 0x4087 Star / 0x410b/0x410c Spring ·
//   0x410d Coil / 0x4281 Rect / 0x4282 Arc90 / 0x4283 RoundRect / 0x4284 Circel / 0x4286 Polygon /
//   0x42c1·0x4306·0x4307 Arc / 0x4701 Line / 0x4702 Gon / 0x4703 Bezier / 0x4704 HVLine / 0x4705 RoundLine /
//   0x4708 Curve / 0x4712 FreeBezier / 0x4713 FreePoly / 0x4488 Wall / 0x4489 Pipe / 0x480f ArcFace /
//   0x4a8a EllipseEx / 0x4c0e GonFace（0x480f/0x4c0e 构造后默认刷 SetBrushObj）
#pragma once

namespace eslib {

// 跨批引用（本批不 dump；见各自头文件）
class esObject;
class esUndo;
class esPropManager;
class esStyleSheet;
class esStyleExchanger;
class esSnapManager;
class esHitTest;
class esVertexList;
class esVertexInfo;
class esRender;
class esMessage;
class esRole;
class esSeg;
class esSegList;
class esSegObj;
class esLineList;
class esMoldPath;
class esBrush;
class esBrushEx;
class esBrushInfo;
class esSolidBrush;
class esLiquid;
class esMatrixObj;
class esTextMaker;
class etShape;
class etGroup;
class esBulletsManager;
class elfPage;
class elfSubject;
class xzLbcList;
struct zPoint;
struct tagPOINT;
struct tagRECT;
struct tag_DRAWPARAM;
struct zArchive;

// ============================================================
// esShapeBase — 全部形状的基类（类型字见文件头；本批 58 函数） [ev:pseudo 116a0..1a8ec0]
// 链/角色/flags/包围盒骨架；具体框架（线/填充/组）由派生类实现
class esShapeBase : public esObject {
public:
    virtual ulong GetShapeType() const;                            // 0x116a0  【?GetShapeType=0xc】0x3008→0；无段→0xffff；否则 esLineHead::GetFontIndex（字槽）
    virtual void DrawForInternal(...);                             // 0x116f0  默认空（派生覆盖）
    virtual int IsClosed() const;                                  // 0x11710  flags&0x1000
    virtual int IsCyclic() const;                                  // 0x11740  flags&0x8000
    virtual int IsClosedEx() const;                                // 0x11770  闭合判定扩展（含包络）
    virtual int IsPlaceHolder() const;                             // 0x117c0  是否占位符对象
    virtual int IsPtInPt(...);                                     // 0x11810  点包含判定
    esShapeBase();                                                 // 0x11870  默认构造
    esShapeBase& operator=(esShapeBase const&);                    // 0x118f0
    static wchar_t const* ID();                                    // 0x19b330  L"esShapeBase"
    virtual int isKindOf(wchar_t const*);                          // 0x19b340  仅自比（基类无祖先比对）
    virtual int isOf(wchar_t const*);                              // 0x19b3e0
    esShapeBase(esSnapManager*, ushort type, ulong flags);         // 0x19b470  主构造（type 写入 +4）
    virtual void CollectStyles(esStyleSheet*) const;               // 0x19b4e0  role 样式收集
    virtual ~esShapeBase();                                        // 0x19b540
    virtual int CheckEndDrawing(...);                              // 0x19b5e0  绘制结束检查（画图过渡态）
    virtual void LoadLbcLines(xzLbcList*, Gdiplus::Matrix const*, int); // 0x19b940  默认空
    virtual int IsEqual(esObject*, esStyleSheet*);                 // 0x19b9a0  type 字相等
    virtual int GetTotalMatrix(Gdiplus::Matrix&, ...);             // 0x19ba70  连父链总矩阵
    virtual int IsContainLBCLines() const;                         // 0x19bc00
    virtual void Serialize(zArchive&, esStyleSheet*, ushort);      // 0x19bc90  基类字段（链序由封装层管）
    virtual void CopyFrom(esObject const*, esStyleExchanger*);     // 0x19bdc0
    esShapeBase* SearchUp(ushort type);                            // 0x19c160  沿 next 链找类型
    virtual int AddPoint(...);                                     // 0x19c190  默认不支持（0）
    virtual int OnMessage(esMessage*, ulong);                      // 0x19c2f0  默认 0
    int GetNextObjID();                                            // 0x19c460  取后继对象 ID
    void Detach();                                                 // 0x19c490  拆链（手工对象禁用的元凶区域，见项目铁律）
    void DeleteSlef();                                             // 0x19c5a0  【原符号名拼写】自删（引擎内部）
    virtual void OnItemModified(ulong);                            // 0x19c630  项变更回调（链刷新）
    virtual void RecalcLayout();                                   // 0x19c720  基类版：包围盒 + **外扩 400**（Path/Group 不复用外扩）
    virtual int HitTest(esHitTest*, int);                          // 0x19c7c0  基类命中：段命中 → 选码 7
    virtual tagPOINT GetOrg() const;                               // 0x19c970  对象原点
    virtual void GetCtrInfo(...);                                  // 0x19ca80  默认空
    virtual void BreakCyclic();                                    // 0x19db50  清 0x8000（cyclic）
    virtual int IsLoadable() const;                                // 0x19dba0
    virtual void Load(elfPage*, elfSubject*, tag_DRAWPARAM*);      // 0x19dc10  默认空
    virtual void Draw(esRender*, tag_DRAWPARAM*, Gdiplus::Matrix*);// 0x19dc20  默认空
    virtual void GetLineList(esLineList*, int);                    // 0x19dc60  默认空
    virtual void GetCommonSidePoints(...);                         // 0x19dca0  公共侧点（闭合吸附）
    virtual void LoadLines(...);                                   // 0x19ddc0  默认空
    virtual void AppendMatrix(Gdiplus::Matrix const&, esUndo*);    // 0x19de20  默认空
    virtual void MatrixProc(int);                                  // 0x19de70  默认空
    virtual int SnapPoint(esSnapManager*);                         // 0x1a5d10  默认 0
    virtual int HitTestAcme(esHitTest*);                           // 0x1a5d90  默认 0
    virtual int IsPtInMaxBox(tagPOINT);                            // 0x1a5e20
    virtual void LoadEdge(etGroup*, Gdiplus::Matrix const*);       // 0x1a5e90  默认空
    virtual void Insert(...);                                      // 0x1a60a0  默认空
    virtual int OnCreate(esStyleSheet*);                           // 0x1a60d0  样式字写入（批 8 已实证：必须返回含 oncreate 步骤）
    virtual int HitTestForRole(esHitTest*, ...);                   // 0x1a6cb0  0x3a08→0；否则 vtbl+0x8c 转发
    virtual int HitTestObjClick(esHitTest*, int);                  // 0x1a6cf0  转发 vtbl+0x8c
    virtual int IsRgnClicked(esHitTest*, ...);                     // 0x1a6e50  区域命中（role/batch）
    virtual void LoadProp(esPropManager*, ulong);                  // 0x1a7cf0  默认空
    virtual void SaveProp(esPropManager*, ulong);                  // 0x1a7f20  默认空
    virtual void DeleteRole();                                     // 0x1a8ca0  role 释放
    virtual void OnActive(int);                                    // 0x1a8d20  激活回调
    virtual void Undo(ushort, zArchive&, zArchive&);               // 0x1a8d70  基类撤销（默认空）
    virtual void SetRole(esRole*);                                 // 0x1a8e10  role 挂接 + 注册
    virtual void* Undata(ushort&, void*, int&);                    // 0x1a8ec0  ILT：esObject::Undata
};

// ============================================================
// esShapeLine — 线段/折线（: esShapeBase；类型字 0x3109） [ev:pseudo 11a20..1a20a0]
// pen @+0x50（色 0xff01/样式/宽 0x50）；+0x5c/+0x5e 端饰；OnStructure 17 种轻段型
class esShapeLine : public esShapeBase {
public:
    esPenInfo GetPenInfo() const;                                  // 0x11a20  取 pen（源对象复制用）
    virtual ~esShapeLine();                                        // 0x11a40
    esShapeLine();                                                 // 0x11a60  默认构造
    esShapeLine& operator=(esShapeLine const&);                    // 0x11ad0  ILT 折叠（&&/const& 同址）
    static wchar_t const* ID();                                    // 0x1a0720  L"esShapeLine"
    virtual int isKindOf(wchar_t const*);                          // 0x1a0730  不中→esShapeBase::isKindOf
    virtual int isOf(wchar_t const*);                              // 0x1a07e0  仅自比
    esShapeLine(esSnapManager*, ushort, ulong);                    // 0x1a0870  type=0x3109
    esShapeLine(tagPOINT, tagPOINT, ulong);                        // 0x1a0900  两点线
    esShapeLine(tagPOINT const&, ushort type, ulong);              // 0x1a09a0  单点/点型（0x6001 加粗点主通道，批 8 实证）
    esShapeLine(esSnapManager*, tagPOINT const&, ushort, ulong);   // 0x1a0a20  【点画主入口】
    virtual int OnStructure(int, ...);                             // 0x1a0ad0  17 种轻段型（0x600a/0x600b flags=1 覆盖默认；0x600e flags=7）
    virtual void Load(elfPage*, elfSubject*, tag_DRAWPARAM*);      // 0x1a1270
    virtual void Render(esRender*);                                // 0x1a1320
    virtual esShapePath* GrapConvert();                            // 0x1a1400  0x6001/0x600a/0x600b→0（不可转填充）
    virtual int IsEqual(esObject*, esStyleSheet*);                 // 0x1a1610  pen 相等
    virtual void ToFixColor(int);                                  // 0x1a1680  pen 换色
    virtual void Serialize(zArchive&, esStyleSheet*, ushort);      // 0x1a1700
    virtual void CopyFrom(esObject const*, esStyleExchanger*);     // 0x1a1780
    virtual int GetSnapPoints(tagPOINT*, tagRECT&);                // 0x1a17f0  端点吸附
    virtual void GetColors(...);                                   // 0x1a1b50  pen 色入列
    virtual void LoadProp(esPropManager*, ulong);                  // 0x1a1bb0  pen/端饰道具
    virtual void SaveProp(esPropManager*, ulong);                  // 0x1a1d00
    virtual void Undo(ushort, zArchive&, zArchive&);               // 0x1a20a0  pen/端饰/0x50d flags
};

// ============================================================
// esShapeCap — 封口图形基座（: esShapeBase；类型字 0x320b） [ev:pseudo 11d20..1a2cc0]
// +0x60 尺寸；+0x5c/+0x5e 端饰字；Serialize 仅 flags&0x30 才写端饰
class esShapeCap : public esShapeBase {
public:
    virtual ~esShapeCap();                                         // 0x11d20
    esShapeCap();                                                  // 0x11d40  默认构造
    esShapeCap& operator=(esShapeCap const&);                      // 0x11d90
    static wchar_t const* ID();                                    // 0x1a2190  L"esShapeCap"
    virtual int isKindOf(wchar_t const*);                          // 0x1a21a0  不中→esShapeBase::isKindOf
    virtual wchar_t const* className() const;                      // 0x1a2240  【错名折叠→esShapeCap::ID】【Q-shape-14】
    virtual int isOf(wchar_t const*);                              // 0x1a2250  仅自比
    esShapeCap(esSnapManager*, ushort, ulong);                     // 0x1a22e0  type=0x320b
    virtual void Load(elfPage*, elfSubject*, tag_DRAWPARAM*);      // 0x1a2340
    virtual void Render(esRender*);                                // 0x1a2400
    esShapeCap(esSnapManager*, ushort, ulong, ...);                // 0x1a2500  616B 段型 switch 分发（0x5006 无 case=Q-shape-11）
    virtual int IsEqual(esObject*, esStyleSheet*);                 // 0x1a27b0  type+端饰
    virtual void Serialize(zArchive&, esStyleSheet*, ushort);      // 0x1a2820  仅 flags&0x30 写 +0x5c/+0x5e
    virtual void CopyFrom(esObject const*, esStyleExchanger*);     // 0x1a28a0
    virtual void LoadProp(esPropManager*, ulong);                  // 0x1a2920  组 0x500：0x508..0x50b
    virtual void SaveProp(esPropManager*, ulong);                  // 0x1a2a00  undo 0x508..0x50b 系列
    virtual void Undo(ushort, zArchive&, zArchive&);               // 0x1a2c20  0x508..0x50b 交换
    virtual esObject* GetTextObj();                                // 0x1a2cc0  内嵌文本对象（端饰文字）
};

// ============================================================
// esShapePath — 自由路径/填充图形（: esShapeCap；类型字 0x330f） [ev:pseudo 11f80..1a9b80]
// 段表链：表 esSegList(0x44)，组 +0x60 首表/+0x64 尾表；段链 next@seg+0x3c；+0x68 brush/+0x6c liquid/+0x70 bright
class esShapePath : public esShapeCap {
public:
    int IsEmpty() const;                                           // 0x11f80  +0x60==0
    void SetBright(uchar);                                         // 0x11fb0  this[0x70]=b
    esShapePath(esShapePath const&);                               // 0x11fd0  浅拷（不深拷贝段表/笔刷）
    esShapePath& operator=(esShapePath const&);                    // 0x12040  ILT：Cap op= + 5 字段浅拷
    void AddSegObject(esSeg*, int mode);                           // 0x19beb0  首段直挂（空→建表）
    void NormalRing(esUndo*);                                      // 0x19bf70  EsBulletsManager + EnumSegments 收尾
    int SnapPoint(esSnapManager*);                                 // 0x19bff0  逐表吸附
    int SnapFarPoints(esSnapManager*, int, int, int);              // 0x19c090  solid 外扩 range 内逐段 vtbl+0x70
    void AddSegList(esSegList*);                                   // 0x19c380  表入尾链 + ResetLineWidth
    int AddSegListEx(esSegList*);                                  // 0x19c3f0  空表销毁返 0；否则挂链返 1
    void RemoveAllPts();                                           // 0x19c6b0  清全部段表（free）
    virtual void LoadProp(esPropManager*, ulong);                  // 0x19cbf0  单表单段级联 + 0x500 刷/0x600 液体
    virtual void SaveProp(esPropManager*, ulong);                  // 0x19cdb0  镜像（undo 0x601/0x602/0x502）
    virtual void* Undata(ushort&, void*, int&);                    // 0x19d100  0x520/0x521/0x522/0x601/0x602/0x502 交换族
    virtual void GetCtrInfo(...);                                  // 0x19d410  控制点信息（0x25410000 型补点）
    virtual int HitTestLiquidAcme(esHitTest*);                     // 0x19d5f0  液体点 0x12
    virtual int HitTestAcme(esHitTest*);                           // 0x19d6c0  液体 0x12 + 段端点重定向
    void GetLiquidCtlPointInfo(...);                               // 0x19d9e0  液体控制点（0x50610000）
    virtual esSeg* CreateObject(ushort type);                      // 0x19dee0  0x2030→esSegList 否则 esSeg::Create
    static wchar_t const* ID();                                    // 0x19df80  L"esShapePath"
    virtual int isKindOf(wchar_t const*);                          // 0x19df90  不中→esShapeCap::isKindOf
    virtual int isOf(wchar_t const*);                              // 0x19e040  仅自比
    esShapePath();                                                 // 0x19e0d0  type=0x330f；flags=0x40700ff；+0x70=100
    esShapePath(esShapePath const&, int deep);                     // 0x19e140  deep→InitPropertys
    esShapePath(esSnapManager*, ushort, ulong);                    // 0x19e200  4075B 重段型工厂（§4.1）；末 AddSegObject(seg,1)
    esShapePath(tagPOINT*, uchar*, int);                           // 0x19f470  点串构造（types&3：3=Bezier/1=Line；末位&0x80→CloseFigure）
    virtual ~esShapePath();                                        // 0x19f830  RemoveAllPts + brush/liquid 释放
    virtual void ToFixColor(int);                                  // 0x19f8f0  Line 版 + brush vtbl+0x68
    int EnumSegments(...);                                         // 0x19f930  逐表逐段 std::function 访客
    static esShapePath* CreateFromPathData(tagPOINT*, uchar*, int, ...); // 0x19fa10  freehand/粘贴路径重建
    virtual void RecalcLayout();                                   // 0x1a0150  各表 rect Union（不外扩）[Q-shape-20]
    void UpdateFillBounds();                                       // 0x1a0280  brush 矩阵 → esBrushEx::SetDestRect
    void InitPropertys(esShapeBase*, int deep);                    // 0x1a0350  属性初始化（brush Create/liquid Clone/pen 拷贝）
    void CopyPropFrom(esStyleSheet*, esShapeBase*, int);           // 0x1a04f0  属性复制（图片刷 ResetImageSize / role Clone）
    virtual void ConnectClose();                                   // 0x1a5bf0  flags 置闭合 + 逐表 esSegList::ConnectClose
    void LoadPtsList(esShapePath* dst);                            // 0x1a5c80  全部表迁给 dst（整链搬）
    virtual void Insert(esSegList*, esSegList*, int mode);         // 0x1a5f50  表插链
    int CheckValid();                                              // 0x1a6120  空表 free 清理 + 计数 [Q-shape-15]
    virtual int IsReallyClosed(int tol);                           // 0x1a61f0  首末段点距 dx/dy ≤ tol
    virtual void GetLineList(esLineList*, int);                    // 0x1a62d0  折线化（单段直转 / 多段 esSeg::GetPath）
    virtual esShapePath* GrapConvert();                            // 0x1a64c0  esLineList→新路径（弧线拟合）
    void OpenCanvas(esUndo*);                                      // 0x1a6680  flags&0x1000→undo 0x50d + 置 0x30
    virtual void CloseFigure(int);                                 // 0x1a66e0  补连线段 + flags 置闭合
    virtual int HitTestObjClick(esHitTest*, int);                  // 0x1a6d30  选码 7/8/0xb [Q-shape-19]
    void SetSolidBrush(ulong color);                               // 0x1a6f20  **仅空槽创建 esSolidBrush** [Q-shape-16]
    virtual void AppendMatrix(Gdiplus::Matrix const&, esUndo*);    // 0x1a6fb0  段链 + brush + role
    virtual void MatrixProc(int);                                  // 0x1a70a0  段链 + brush + role
    void LoadMoldPath(esMoldPath*, int fillMode);                  // 0x1a7150  逐表 LoadPath + EndGeometry
    virtual void LoadEdge(etGroup*, Gdiplus::Matrix const*);       // 0x1a71d0  etShape + SetAttribut(pen, brush, bright)
    virtual void SetModifiedFlags(ulong);                          // 0x1a7300  ILT ≡ esObject::SetModifiedFlags（esTopTable 同折叠）
    virtual int GetSnapPoints(tagPOINT*, tagRECT&);                // 0x1a7320  单段/闭合分派；0x4306 弧补圆心
    virtual void Render(esRender*);                                // 0x1a7530  Save/GobackToDrawPoint/DrawGraphics/Restore
    void DrawGraphics(esRender*, Gdiplus::Matrix const&);          // 0x1a75f0  首段 &0x800→段自绘 [Q-shape-18]
    virtual void DrawForInternal(...);                             // 0x1a76b0  esMoldPath 变体（fillmode=flags&0x4000）
    virtual void Load(elfPage*, elfSubject*, tag_DRAWPARAM*);      // 0x1a77b0  NewSubj + 首段 &0x800 分派
    void LoadForNormal(elfPage*, elfSubject*);                     // 0x1a78b0  AddPen + brush/liquid Load + MoldPath Load
    void DrawForNormal(...);                                       // 0x1a7a30  刷填充 vtbl+0x78 / liquid OnDraw / pen 描边
    virtual void LoadLbcLines(xzLbcList*, Gdiplus::Matrix const*, int); // 0x1a7c70  IsClosed + 逐段 vtbl+0xb4
    virtual int IsEqual(esObject*, esStyleSheet*);                 // 0x1a8220  Cap + 亮位 + brush/liquid + 逐表
    virtual void Serialize(zArchive&, esStyleSheet*, ushort);      // 0x1a8370  旗标 bit1/2/8/0x10/0x20；加载先 RemoveAllPts
    virtual void CopyFrom(esObject const*, esStyleExchanger*);     // 0x1a8ab0  逐表复制 + brush/liquid 克隆
    void LoadBrush(zArchive&, esStyleSheet*);                      // 0x1a8c40  ReadByte 刷型 → esBrush::Create
    virtual int CompMatrix(Gdiplus::Matrix&, ...);                 // 0x1a8fa0  组合矩阵（全链单段→0）
    virtual void SetBrush(esBrush*);                               // 0x1a91f0  换刷（free 旧；**允许 NULL**）[Q-shape-16]
    virtual void GetColors(...);                                   // 0x1a9240  mask&8 → 实心刷色
    void ResetPicSize();                                           // 0x1a92e0  图片刷目标框重设
    int IsEqualBrush(esBrushInfo*);                                // 0x1a94d0  esBrush::IsEqual(+0x68, info)
    void UpdateBrush(esStyleSheet*, esBrushInfo*);                 // 0x1a94f0  协议掩码 info+0x148（undo 0x520/0x521/0x522）
    void SetBrushObj(esBrushInfo*, esStyleSheet*, Gdiplus::Matrix*); // 0x1a9820  CreateFromBrushInfo + 矩阵 + UpdateFillBounds
    virtual void Undo(ushort, zArchive&, zArchive&);               // 0x1a99f0  liquid 先 → Cap::Undo
    virtual void CollectStyles(esStyleSheet*) const;               // 0x1a9a40  base + brush + 逐表
    virtual int OnMessage(esMessage*, ulong);                      // 0x1a9ab0  逐表 vtbl+0x48
    int SetLiquidHight(int, esSnapManager*);                       // 0x1a9b20  液体高度（h==1 直设）
    int GetBrushInfo(esBrushInfo*);                                // 0x1a9b80  刷信息查询
};

// ============================================================
// esShapeGroup — 组合（: esShapeCap；类型字 0x3008） [ev:pseudo 12840..3cb910]
// 子链 +0x5c/+0x60（next/prev@+0x44/+0x48）；+0x64/+0x6a 链接点；+0x74 esMatrixObj（矩阵层 flags 位 27）
class esShapeGroup : public esShapeCap {
public:
    int IsPackage() const;                                         // 0x12840  打包判定
    esShapeGroup& operator=(esShapeGroup const&);                  // 0x12870  Line op= + 6 字段 + esMatrixObj::op=
    static wchar_t const* ID();                                    // 0x3c5920  L"esShapeGroup"
    virtual int isKindOf(wchar_t const*);                          // 0x3c5930  不中→esShapeCap::isKindOf
    virtual int isOf(wchar_t const*);                              // 0x3c59d0  仅自比
    esShapeGroup(esSnapManager*, ushort, ulong);                   // 0x3c5a60  type=0x3008；esMatrixObj@+0x74
    virtual ~esShapeGroup();                                       // 0x3c5b20  子链 + 矩阵对象释放
    virtual void ToFixColor(int);                                  // 0x3c5c70  逐子 vtbl+0xa4
    void SetRectObject(esSeg*);                                    // 0x3c5cb0  包络段 esSegGroupRect(0x78)
    void Append(esShapeBase* child);                               // 0x3c5d60  入尾链 + 道具位合并（&0xcff0000>>0x10）
    virtual void Insert(esShapeBase*, esShapeBase*, int);          // 0x3c5e00  子链插入
    void RecalcGroupRect();                                        // 0x3c5f30  组矩形重算
    virtual void RecalcLayout();                                   // 0x3c6270  子链 + 包络 + 矩阵层
    void RemoveAll();                                              // 0x3c63f0  清子链
    void ReleaseMatrixLayer();                                     // 0x3c6460  非 1:1 才释放矩阵层
    void RelaseAllTransfrom();                                     // 0x3c64f0  【原符号名拼写】重置变换（undo 0xf0d/e/f）
    void GetMatrix(Gdiplus::Matrix&);                              // 0x3c6890
    int GetMatrixEx(...);                                          // 0x3c68c0
    int GetTotalMatrixEx(Gdiplus::Matrix&, ...);                   // 0x3c6940  连父链总矩阵
    virtual void AppendMatrix(Gdiplus::Matrix const&, esUndo*);    // 0x3c6a30  级联子链
    virtual void MatrixProc(int);                                  // 0x3c6ac0
    virtual void OnMovePoint(...);                                 // 0x3c6b30  组控制点拖动
    virtual esShapeBase* CreateObject(ushort type);                // 0x3c6be0  组工厂（尺寸表见文件头）[Q-shape-23]
    void GetRectPoints(tagPOINT*);                                 // 0x3c6fe0  包络角点
    void GetLinkPts(tagPOINT*);                                    // 0x3c7060  +0x6a==0→16 点 else +0x64 数组 [Q-shape-21]
    virtual int GetSnapPoints(tagPOINT*, tagRECT&);                // 0x3c72c0  29B 转发吸附
    virtual int SnapPoint(esSnapManager*);                         // 0x3c72e0  子链递归
    int SnapPointProc(...);                                        // 0x3c73e0  子链逐对象
    virtual int GetBrushInfo(esBrushInfo*);                        // 0x3c7640  子对象刷信息
    esLiquid* GetLiquidObj();                                      // 0x3c76d0  子链找液体
    void RemoveAllLinkPoints();                                    // 0x3c7740
    void RemoveLinkPoints(...);                                    // 0x3c77c0
    void RemoveLinkPoint(int);                                     // 0x3c79a0  链节点 0xC
    void AddLinkPoint(...);                                        // 0x3c7a50
    tagPOINT GetLinkPoint(int);                                    // 0x3c7af0
    int CheckRectModify(...);                                      // 0x3c7cd0  包络框校验
    void LoadLinkLines(...);                                       // 0x3c7da0  59B 转发
    void LoadLines(...);                                           // 0x3c7de0  47B 转发
    void UnionLinks(...);                                          // 0x3c7e10  链接点并入包围盒
    virtual void LoadLbcLines(xzLbcList*, Gdiplus::Matrix const*, int); // 0x3c7e90
    void GetFillBorders(...);                                      // 0x3c7f90  填充边界（递归）
    virtual void GetLineList(esLineList*, int);                    // 0x3c80c0  子对象合并线表
    virtual void GetCtrInfo(...);                                  // 0x3c8380  包络 + 子控制点
    int HitTestAcmeProc(esHitTest*);                               // 0x3c8640  模型框 0x7002 → esCtrlPoint 系列
    virtual int HitTestAcme(esHitTest*);                           // 0x3c8950
    virtual void CollectStyles(esStyleSheet*) const;               // 0x3c8b00
    virtual int OnMessage(esMessage*, ulong);                      // 0x3c8b50
    int EnumParagraphs(...);                                       // 0x3c8bc0  子链段落枚举
    virtual void LoadEdge(etGroup*, Gdiplus::Matrix const*);       // 0x3c8cf0  逐子 vtbl+0x6c
    virtual void DrawForInternal(...);                             // 0x3c8e40  逐子 vtbl+0x3c
    virtual void Draw(esRender*, tag_DRAWPARAM*, Gdiplus::Matrix*);// 0x3c8f30  逐子 vtbl+0x2c
    virtual void Render(esRender*);                                // 0x3c8fd0  flags&0x1000000 子跳过 [Q-shape-22]
    virtual void Load(elfPage*, elfSubject*, tag_DRAWPARAM*);      // 0x3c91b0  NewSubj + 逐子 vtbl+0x90
    int GetShapeCount() const;                                     // 0x3c93e0  子链计数
    virtual int IsBatchble() const;                                // 0x3c9470  可合批查询
    virtual int HitTestForRole(esHitTest*, ...);                   // 0x3c94c0  逐子 vtbl+0x84
    virtual int HitTestObjClick(esHitTest*, int);                  // 0x3c9610  包络框 + repeater DeflateRect
    virtual void LoadProp(esPropManager*, ulong);                  // 0x3c98e0  子透传 + 组 0x800：0x801..0x809
    virtual void SaveProp(esPropManager*, ulong);                  // 0x3c9b60  镜像（undo 0xf0b/c/11/12）
    void Regroup(...);                                             // 0x3c9f80  清矩阵层重组
    virtual void GetColors(...);                                   // 0x3c9fd0  逐子收集
    int IsCtrolOnly() const;                                       // 0x3ca020  仅控制点对象
    int GetGroupHandel(int);                                       // 0x3ca090  组把手
    tagPOINT GetStartPoint(...);                                   // 0x3ca180  包络起始点
    tagPOINT GetAlignPoint(int);                                   // 0x3ca450  对齐点
    esShapeGroup* GetCreateCtrlObj(...);                           // 0x3ca670  控制点对象集
    void LoadUserStymbol(...);                                     // 0x3ca770  用户符号装载
    virtual int IsEqual(esObject*, esStyleSheet*);                 // 0x3ca9c0  Cap + 子链逐对
    virtual void Serialize(zArchive&, esStyleSheet*, ushort);      // 0x3caac0  829B；版本迁移 <0x1070511/<0x1070615
    virtual void CopyFrom(esObject const*, esStyleExchanger*);     // 0x3cae10  逐子 CreateObject+CopyFrom
    void InitGroupInfo(...);                                       // 0x3cafa0
    void CreateUserLinkPoints(...);                                // 0x3cb070  +0x64 数组/+0x6a 计数
    int FindGroupMoveOffset(...);                                  // 0x3cb1b0  拖动吸附偏移
    esShapeBase* FindObj(int id);                                  // 0x3cb280  按 ID 查子对象
    void SetGroupInfo(...);                                        // 0x3cb2c0
    int GetUnGroupInfo(...);                                       // 0x3cb3b0  解组信息（0x100 归档）
    void RemoveControls(...);                                      // 0x3cb580  undo 0xf10/0xf2f1
    void UnGroup(...);                                             // 0x3cb730  undo 0xf006
    virtual void* Undata(ushort&, void*, int&);                    // 0x3cb910  0xf0d/e/f、0xf10、0x2、0x804 交换族
};

}  // namespace eslib
