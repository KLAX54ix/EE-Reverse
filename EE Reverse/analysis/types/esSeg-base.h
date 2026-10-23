// analysis/types/esSeg-base.h
// 绘图对象模型基座（esSegBase / esSeg / esSegList / esSegObj / esSegItem(s) / esSegGemotry）
// — 阶段 2 第四批（eslib.dll · S1）
//
// 证据：
//   [ev:pseudo] analysis/pseudo/eslib/esSeg-base.decomp.txt   (147/147 函数原样伪代码)
//   [ev:spec]   analysis/pseudo/eslib/esSeg-base.md           (谱系/工厂表/序列化/Q1–Q10)
//   [ev:ledger] ledger/ledger.csv  eslib:5a90..  status=decompiled
//
// 谱系：esGraphObject → esSegBase → esSeg → <全部具体段类>（77+ 类，见 SegType 工厂表）
// 持有链：esSeg ↳ esSegList(0x2030) ↳ esShapePath(0x330f) ↳ esCanvas(0x2020)
#pragma once

namespace eslib {

// ============================================================
// 类型字（esSeg::Create 工厂表全量；编码带层级语义：<0x4000 容器/列表层，>=0x4000 叶段）
// [ev:spec §2.1 / §8-Q10]
enum class SegType : unsigned short {
    // --- 容器/列表层（不可由工厂创建）---
    Canvas        = 0x2020,   // esCanvas      （S3 批）
    SegList       = 0x2030,   // esSegList     本批
    ShapePath     = 0x330f,   // esShapePath   （S1 批）

    // --- 叶段（工厂 3e1070 可创建）---
    Star          = 0x4087,   // esSegStar          0x84
    Spring        = 0x410b,   // esSegSpring        0x74 (0x410c 别名)
    Coil          = 0x410d,   // esSegCoil          0x70
    Rect          = 0x4281,   // esSegRect          0x70
    Arc90         = 0x4282,   // esSegArc90         0x84
    RoundRect     = 0x4283,   // esSegRoundRect     0x6c
    Circel        = 0x4284,   // esSegCircel        0x8c
    Unk4285       = 0x4285,   // （未命名 FUN_1011dfc0）0x7c
    Polygon       = 0x4286,   // esSegPolygon       0x7c
    Arc           = 0x42c1,   // esSegArc           0x98 (0x4306/0x4307 别名)
    Wall          = 0x4488,   // esSegWall          0x6c
    Pipe          = 0x4489,   // esSegPipe          0x70
    Line          = 0x4701,   // esSegLine          0x68
    Gon           = 0x4702,   // esSegGon           0x68
    Bezier        = 0x4703,   // esSegBezier        0x68
    HVLine        = 0x4704,   // esSegHVLine        0x68
    RoundLine     = 0x4705,   // esSegRoundLine     0x6c
    Curve         = 0x4708,   // esSegCurve         0x68
    ArcFace       = 0x480f,   // esSegArcFace       0x84
    EllipseEx     = 0x4a8a,   // esSegEllipseEx     0x7c
    GonFace       = 0x4c0e,   // esSegGonFace       0x74
    SimpleAxis    = 0x5001,   // esSegSimpleAxis    0x74
    SimpleSingleAxis = 0x5002,// esSegSimpleSingleAxis 0x74 (0x5003 别名)
    ArrowLines    = 0x5004,   // esSegArrowLines    0x6c
    Glow          = 0x5005,   // esSegGlow          0x8c
    Axis          = 0x5006,   // esSegAxis          0x16c  ★S6
    Point         = 0x6001,   // esSegPoint         0x68
    Unk6002       = 0x6002,   // （未命名 FUN_10013dd0）0x74
    Circels       = 0x6003,   // esSegCircels       0x8c
    SectionLine   = 0x6004,   // esSegSectionLine   0x6c
    Surface       = 0x6005,   // esSegSurface       0x6c
    Text          = 0x6006,   // esSegText          0x84
    Ruler         = 0x6007,   // esSegRuler         0x74
    ArcRuler      = 0x6009,   // esSegArcRuler      0x78
    RulerTextA    = 0x600a,   // esSegRulerTextA    0x7c
    RulerTextB    = 0x600b,   // esSegRulerTextB    0x7c
    Lable         = 0x600d,   // esSegLable         0xd8  ★S5
    MatchMan      = 0x600e,   // esSegMatchMan      0x130
    Bond          = 0x6010,   // esSegBond          0x70
    LinkPoint     = 0x7001,   // esSegLinkPoint     0x8c
    CtrlGroupMove = 0x7002,   // esCtrlGroupMove    0x8c
    CtrlPoint     = 0x7101,   // esCtrlPoint        0x8c
    CtrlLineMove  = 0x7102,   // esCtrlLineMove     0x8c (0x7103/0x7104 别名)
    CtrlXYAny     = 0x7105,   // esCtrlXYAny        0x8c
    CtrlXYMove    = 0x7106,   // esCtrlXYMove       0x9c
    CtrlScale     = 0x7107,   // esCtrlScale        0x8c
    CtrlRotate    = 0x7108,   // esCtrlRotate       0xa4
    CtrlScRot     = 0x7109,   // esCtrlScRot        0x98
    CtrlDot       = 0x710a,   // esCtrlDot          0x90
    CtrlGon       = 0x710b,   // esCtrlGon          0x90
    CtrlBezier    = 0x710c,   // esCtrlBezier       0x90
    CtrlAnyRot    = 0x710d,   // esCtrlAnyRot       0x94
    HDim          = 0x8001,   // esHDim             0x84
    VDim          = 0x8002,   // esVDim             0x8c
    AnyBZ         = 0x8003,   // esSegAnyBZ         0x84
    NumberBZ      = 0x8004,   // esSegNumberBZ      0x88
    Diameter      = 0x8006,   // esSegDiameter      0x98
    Radius        = 0x8007,   // esSegRadius        0x98
    Djbz          = 0x8008,   // esSegDjbz          0x84
    Yxbz          = 0x8009,   // esSegYxbz          0x80
    OI            = 0x800a,   // esSegOI            0x8c
    Paren         = 0x800b,   // esSegParen         0x88
    Rough         = 0x800c,   // esSegRough         0x8c
    OT            = 0x800d,   // esSegOT            0x8c
    CuttingLine   = 0x800e,   // esSegCuttingLine   0x90
    Tolerance     = 0x800f,   // esSegTolerance     0x9c
    HVBZ          = 0x8103,   // esSegHVBZ          0x84
    LinkLine      = 0x9001,   // esSegLinkLine      0x78
    ElbowLinkLine = 0x9002,   // esSegElbowLinkiLine 0x80
    BezierLink    = 0x9003,   // esSegBezierLink    0x80
    LinkHVLine    = 0x9404,   // esSegLinkHVLine    0x78
    Table         = 0xa001,   // esSegTable         0x7c
    FormulaBox    = 0xa002,   // esSegFormulaBox    0x7c  ★S5
    TextBox       = 0xa004,   // esSegTextBox       0x78
    PlaceHolder   = 0xa008,   // esSegPlaceHolder   0x7c (0xafff 别名)
    Image         = 0xa010,   // esSegImage         0x98
    Video         = 0xa030,   // esSegVideo         0xa8
    Audio         = 0xa040,   // esSegAudio         0x9c
    Photo         = 0xa100,   // esSegPhoto         0x98
    GroupRect     = 0xb001,   // esSegGroupRect     0x78
    Frame         = 0xc081,   // esSegFrame         0x68
    RectEx        = 0xd083,   // esSegRectEx        0x70
};
// 未列入：GetPtsObj 特判的 0x1000/0x1002/0x2001/0x1003（尺寸标注非段类，见 spec §2.2/Q9）

// ============================================================
// 点标志（esSeg::m_ptFlags / esSegObj flags 语义）[ev:pseudo GetSegLines 3e3990]
//   0 = 断开（收束当前段） 1 = 直线连接 3 = 三次贝塞尔（占 3 个控制点）
constexpr unsigned char PTF_BREAK = 0;
constexpr unsigned char PTF_LINE  = 1;
constexpr unsigned char PTF_BEZ   = 3;

// get_path 输出包 [ev:pseudo e8e0]
struct tag_EPPATH {
    /* +0x00 */ tagPOINT*      pts;
    /* +0x04 */ unsigned char* flags;
    /* +0x08 */ int            count;
    /* +0x0C */ int            owned;   // 1=指向对象自身 +0x34（勿释放） 0=变换临时副本
};

// ============================================================
// esGraphObject — 抽象基类（+0x00..+0x33 由 esGraphObject/esObject 族占据；本批仅确界）
class esGraphObject { /* vptr + 通用对象字段（后续批细化） */ };

// ============================================================
// esSegBase — 段基座：类型字 + "安全点"缓存 [ev:pseudo ctor 3e42b0]
class esSegBase : public esGraphObject {
    /* +0x04 */ unsigned short m_type;       // 类型字（Create 最后写入；<0x4000=容器层）
    /* +0x34 */ tagPOINT*      m_safePoints; // "安全点"缓存（懒建：Build；dtor free）
    /* +0x38 */ int            m_safeCount;  // 与 +0x34 配对
public:
    esSegBase();                                             // 0x3e42b0
    virtual ~esSegBase();                                    // 0x3e42f0  free(+0x34)
    esSegBase(esSegBase const&);                             // 0xe7b0    浅拷贝 +0x34/+0x38
    static char const* ID();                                 // 0x3e4170
    virtual int isKindOf(char const*);                       // 0x3e4180
    virtual int isOf(char const*);                           // 0x3e4220
    virtual int Build(int force) { return 0; }               // 0x5a90 【ILT stub ×38，勿直调 Q2】
    tagPOINT* get_safe_points(Gdiplus::Matrix* m);           // 0xe680  无缓存→Build(0)
    void      get_path(tag_EPPATH*, Gdiplus::Matrix*);       // 0xe8e0  打包 safer points
    esSegBase* GetPtsObj();                                  // 0xe6e0  尺寸类取上属对象 Q9
    virtual void OnMovePoint(tagPOINT, int, int);            // 0xe750
    virtual int  SetPointPos(unsigned, tagPOINT*);           // 0xe790  恒 return 2 【ILT ≡esSegLable】
    int  GetTotalMatrixEx(Gdiplus::Matrix*);                 // 0x3e4330 沿 amulet 复合（canvas 终止）
    int  GetTotalMatrix(Gdiplus::Matrix*, int, int);         // 0x3e4490 先跳容器层（<0x4000）
    void get_line_by_ratio(tagPOINT&, tagPOINT&, float t);   // 0x3e4610 t<1 内推 / ≥1 外推
};

// ============================================================
// esSeg — 叶段基类：链 + 矩阵 + 控制点/逐点标志 [ev:pseudo ctor 1043b0 / dtor 104460]
class esSeg : public esSegBase {
    /* +0x3C */ esSeg*         m_next;     // esSegList 侵入链
    /* +0x40 */ esSeg*         m_prev;
    /* +0x44 */ unsigned char  m_flag44;   // ctor 置 0
    /* +0x46 */ unsigned short m_flag46;   // ctor 置 0
    /* +0x48 */ esMatrixObj    m_matrix;   // 0x10B；+0x4C = Gdiplus::Matrix 数据
    /* +0x58 */ tagPOINT*      m_ctrlPts;  // 控制点（编辑手柄；只序列化这份）
    /* +0x5C */ unsigned short m_ctrlCount;
    /* +0x60 */ unsigned char* m_ptFlags;  // PTF_* 逐点标志
    /* +0x64 */ esSeg*         m_alias;    // 双向别名（组 ⇄ 代表对象）
public:
    static esSeg* Create(unsigned short type);               // 0x3e1070 未知→zApiThrowMemoryException Q1
    esSeg();                                                 // 0x1043b0
    virtual ~esSeg();                                        // 0x104460
    esSeg& operator=(esSeg const&);                          // 0xec40
    static char const* ID();                                 // 0x104270
    virtual int isKindOf(char const*);                       // 0x104280
    virtual int isOf(char const*);                           // 0x104320
    virtual int AddPoint(zPoint, int, int) { return 0; }     // 0x12460 【ILT stub，具体类 override】
    virtual void BreakLine(int*, int) { }                    // 0x6690 【ILT stub ×31 Q2】
    // --- 点集/几何 ---
    int  GetVertex(unsigned short idx, tagPOINT& out);       // 0xeb30  +0x58[idx]
    void step(int, int, float); void step(float, float, float); void step(tagPOINT, tagPOINT, float); // 0xeb80/eba0/ebd0
    tagPOINT* GetPoints(int& count);                         // 0x107af0 安全点（返回{+0x34,+0x38}不拷贝）
    int  GetPts(tagPOINT*& pts, unsigned char*& flags);      // 0x106200 分配拷贝（调用方 free）
    int  GetPath(tagPOINT*, unsigned char*, int start);      // 0x1057b0 从 start 拷贝
    void SetPtInfo(tagPOINT*, unsigned char*, int, int fill, int doT); // 0x1065d0 pts==+0x58 先深拷贝
    void AddLines(tagPOINT*, int n);                         // 0x107ff0 追加密控制点（realloc）
    virtual int  Build(int);                                 // 0x107dc0 SetPtInfo(+0x58,NULL,n,1,1)
    int  BuildEx(esSeg*, float t);                           // 0x107ce0 与另一段逐点插值（morph）
    void ResetPointsForCreate();                             // 0x107df0 vtbl+0x7C(1)
    void MirrPts();                                          // 0x107c10 控制点反序（新分配）
    void MovePoint(tagPOINT, int, int);                      // 0x1cf80 【ILT ≡esSegSurface::MovePoint】
    void AnyMove(Gdiplus::PointF, Gdiplus::PointF);          // 0x109060 拖动控制点
    void AnyMove(tagPOINT, int, int);                        // 0x109270
    void GetbendingPoints(tagPOINT[3], tagPOINT[3], tagPOINT[3], tagPOINT&, int); // 0x106980
    void GetbendingPoints(tagPOINT*, double, int);           // 0x106e00
    void GetCtlPts(esVertexList*, int type);                 // 0x106820 esVertexInfo 入列
    tagPOINT* GetArrowPos(int, int, unsigned short);         // 0x107b30 【全局静态 scratch Q3】
    int  GetAcmePoint(int);                                  // 0x1080c0
    int  GetPointInfo(int idx);                              // 0x1081d0 角色表 1=中 3=首 5=尾
    int  GetJiaoCount(...tag_POINTD pt);                     // 0x107830 左射线交点计数（点选/圈选）
    // --- 变换 ---
    tagPOINT Invert(tagPOINT);                               // 0xea00 用 +0x4C 矩阵
    tagPOINT Invert(Gdiplus::PointF);                        // 0xea50
    tagPOINT InvertF(tagPOINT);                              // 0xeac0
    void TransformPoints(tagPOINT*, int) const;              // 0xe9e0
    void AppendMatrix(esMatrixObj const&);                   // 0x108b00
    void SetMatrixElements(double a, double b, double c, double d, double e, double f); // 0x108b40
    int  MatrixProc(int);                                    // 0x108bf0
    // --- 查询/命中 ---
    int  IsEqual(esSeg*, esStyleSheet*);                     // 0x107510 基类+计数+矩阵+memcmp
    int  IsClosed(int);                                      // 0x108850
    int  IsClosedEx();                                       // 0x108910 shape+0x34 & 0x9000
    int  IsCyclical();                                       // 0x1089b0
    int  IsSelected(int render);                             // 0x1087c0
    esShapeBase* GetOwner();                                 // 0x104fd0 amulet 上溯跳过 0x2030
    esObject* SearchUp(int id);                              // 0x105050
    int  IsPPline(unsigned long*);                           // 0x105080 type&0x100 → owner esSegList
    int  IsFeasible(int q);                                  // 0x104d30
    int  GetNextObjID();                                     // 0x105580
    int  HitTest(esHitTest*, int);                           // 0x1067c0
    int  HitTestAcme(esHitTest*, int);                       // 0x1066f0
    int  SnapPoint(esSnapManager*);                          // 0x1055b0
    // --- 链接/生命周期 ---
    void SetAlias(esSeg*);                                   // 0x105010 双向 m_alias
    int  Append(esSeg*);                                     // 0x1050f0 【就地合并+去重 Q4】
    void Detach();                                           // 0x107e80 从 esSegList 摘除
    void DeleteSlef(int, int);                               // 0x107f50
    void OnPreMovePoint(esGraphWorker*, int);                // 0x105650
    void RemoveControlLink();                                // 0x108fd0
    void OnMessage(unsigned, esGraphWorker*);                // 0x109040
    int  OnBreakLine(int);                                   // 0x104d90 转 esShapePath（undo esUnMove）
    // --- 绘制/加载（S1 动态桥对照）---
    void Draw(eg_graphics::egRender*, DRAWPARAM*, Gdiplus::Matrix*); // 0x1063c0 egPath(m_safePoints)+笔/刷 ★
    void Load(elfPage*, elfSubject*, DRAWPARAM*);            // 0x1062b0
    void LoadPath(esMoldPath*);                              // 0xe970
    void LoadShape(etShape*);                                // 0x107e10
    void LoadObjPoints(esLineList*, int);                    // 0x105840 按 flags==0 切段 → esSegObj
    int  GetLineLength();                                    // 0x1059e0
    int  AddPartPath(esMoldPath*, int len, int dir);         // 0x105ab0
    void GetLbcLines(xzLbcList*, Gdiplus::Matrix*, int);     // 0x1056c0 PTF_* 输出
    virtual void GetRgnPts(tagPOINT*&, unsigned char*&, int&);// 0x107800 默认同 GetPts
    // --- 序列化/撤销/布局 ---
    virtual void Serialize(zArchive&);                       // 0x1075d0 格式见 spec §7.1
    virtual void CopyFrom(esObject*, esExchanger*);          // 0x107710
    virtual void unMPSave(zArchive&);                        // 0x108c10 写1/读4|6 Q8
    virtual void Undata(int id, void*, unsigned*);           // 0x108eb0 undo 0xf2dc
    virtual void RecalcLayout();                             // 0x108a30 InflateRect(400,400)
    void SetModifiedFlags(int);                              // 0x106520 释放显示点缓存（0x8123 Q7）
    // --- 静态拟合 ---
    static esSeg* FromBezer(Gdiplus::PointF*, int);          // 0x104520 三点→圆/弧；退化 NULL Q5
};

// ============================================================
// esSegList — 多段折线容器（侵入式双向链）[ev:pseudo ctor 1b00d0；AddSegObject 1b0330]
class esSegList : public esGraphObject {
    /* +0x34 */ esSeg* m_head;
    /* +0x38 */ esSeg* m_tail;
    /* +0x3C */ esSegList* m_next;   // 兄弟链（挂 esShapePath 内）
    /* +0x40 */ esSegList* m_prev;
public:
    esSegList();                                             // 0x1b00d0
    esSegList(tagPOINT*, unsigned char*, int, int);          // 0x1b0130 FitToBezierOrLine 规整
    virtual ~esSegList();                                    // 0x1b0260
    static char const* ID();                                 // 0x1aff90
    virtual int isKindOf(char const*);                       // 0x1affa0
    virtual int isOf(char const*);                           // 0x1b0040
    esSegList& operator=(esSegList const&);                  // 0x10510
    virtual esSeg* CreateObject(unsigned short type) const;  // 0x19dec0 【ILT ≡esShapeBase】
    int  GetNextObjID();                                     // 0x1a6830
    void AddSegObject(esSeg*, int pos);                      // 0x1b0330 0=头插 else 尾插
    int  Append(esSeg*);                                     // 0x1b03d0 tail 合并（esSegGon 先规整）
    void AddPts(tagPOINT*, int n);                           // 0x1b0590 n==2 追加/新建 Gon；n==4 贝塞尔
    void Insert(esObject*, esObject*, int mode);             // 0x1b0b60
    void RemoveAllItems();                                   // 0x1b0770
    void SetFirstItem(esSeg*, int undo);                     // 0x1b07e0 循环旋转；undo 0x524
    void DropItemsTo(esSegList*);                            // 0x1b1630
    void Replace(esSeg*, tagPOINT*, int);                    // 0x1b1230 新建 Bezier 顶替
    int  Relist(esSeg*, esSeg*, int flag);                   // 0x1b08b0 → 新 esShapePath
    void ConnectClose();                                     // 0x1b0c90
    void LinkEqualLines(int);                                // 0x1b0e50 0x4701→0x4702 升级
    void CloseFigure();                                      // 0x1b16a0 补闭合边
    void RecalcLayout();                                     // 0x1b0a50 全链并集
    int  IsInvalidate();                                     // 0x1b02b0 空链/宽高<10
    int  SnapPoint(esSnapManager*);                          // 0x1a69b0
    void LoadVertext(esVertexList*);                         // 0x1a6a00
    void LoadPath(esMoldPath*, float ratio, Gdiplus::Matrix*);// 0x1a6a40 按总长比例截取
    void MirrPts();                                          // 0x1b11c0
    void ExecuteCommand(int cmd);                            // 0x1b1120 cmd==1 → MirrPts
    void OnMessage(unsigned, esGraphWorker*);                // 0x1b1150
    void Detach();                                           // 0x1a6860
    void DeleteSlef(int, int);                               // 0x1a6910
    void Undata(int id, void*, unsigned*);                   // 0x1a6c20 undo 0x524
    virtual esObject* Clone();                               // 0x1b04f0 CloneObject(...,0x2030)
    int  IsEqual(esObject*, esStyleSheet*);                  // 0x1b1350
    virtual void CopyFrom(esObject*, esExchanger*);          // 0x1b1580
    virtual void Serialize(zArchive&);                       // 0x1b13f0 格式见 spec §7.2
};

// ============================================================
// esSegObj — 无 vptr 纯数据助手（深拷贝点+标志容器）[ev:pseudo ctor 3e3760]
struct esSegObj {
    /* +0x00 */ int            m_reserved;  // 0
    /* +0x04 */ tagPOINT*      m_pts;       // dtor free
    /* +0x08 */ unsigned char* m_flags;     // dtor free（PTF_*）
    /* +0x0C */ int            m_count;
    /* +0x10 */ unsigned short m_flags2;
    esSegObj(tagPOINT*, unsigned char*, int n);              // 0x3e3760 flags NULL → 自造 [0]=0 余 1
    ~esSegObj();                                             // 0x3c4a50
    esSegObj* Colon(int dx, int dy);                         // 0x3e3800 深拷贝平移；flags2|=3
    int  GetSegLines(esShapePath*);                          // 0x3e3990 0=收束段 1=AddPts(2) 3=AddPts(4)
    void TransformPoints(Gdiplus::Matrix*);                  // 0x3e3b70
};

// ============================================================
// esSegItem / esSegItems — 段临时点表链 [ev:pseudo ctor 12150 / 121c0]
struct esSegItem {
    /* +0x00 */ tagPOINT* m_pts;    // dtor free
    /* +0x04 */ int       m_count;
    /* +0x08 */ esSegItem* m_next;
    esSegItem();  ~esSegItem();                              // 0x12150 / 0x12180
};
struct esSegItems {
    /* +0x00 */ esSegItem* m_first;
    /* +0x04 */ esSegItem* m_last;
    esSegItems(); ~esSegItems();                             // 0x121c0 / 0x121f0
    void AddItem(tagPOINT*, int n);                          // 0x4cf4e0 尾接
    void RemoveAllItems();                                   // 0x4cf590
};

// ============================================================
// esSegGemotry — esSegNative 系（中间父类符号被折叠；行为上当 esSeg 用）[ev:pseudo 110f20]
class esSegGemotry : public esSeg /* : esSegNative（推定）*/ {
public:
    esSegGemotry();                                          // 0x110f20
    virtual ~esSegGemotry();                                 // 0xed00 【ILT ≡esSegNative::~】
    esSegGemotry& operator=(esSegGemotry const&);            // 0xed20 【ILT ≡esSegPoint::operator=→esSegFrame】
    static char const* ID();                                 // 0x110dd0
    virtual int isKindOf(char const*);                       // 0x110de0 上溯 esSegNative
    virtual int isOf(char const*);                           // 0x110e90
    static char const* className();                          // 0x110e80 【ILT ≡esSegPoint::className】
    virtual int BreakLine(int*, int);                        // 0x110f40 摘出→新建 esSegList→重塑
};

} // namespace eslib
