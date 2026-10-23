// analysis/types/esSeg-axis.h
// 轴族与曲线族（esSegAxis / esSegBezier / esSegCurve / esSegFreeBezier /
//              esSegSimpleSingleAxis / esSegSimpleAxis）
// — 阶段 2 第九批（eslib.dll · 绘图核心 5/6 · S6 轴/曲线）
//
// 证据：
//   [ev:pseudo] analysis/pseudo/eslib/esSeg-axis.decomp.txt   (112/112 函数原样伪代码)
//   [ev:spec]   analysis/pseudo/eslib/esSeg-axis.md           (两臂基点模型/三角波刻度/3n+1 控制点/标签盒/Q-axis-bez-sax)
//   [ev:ledger] ledger/ledger.csv  eslib:<rva>（112 行 → status=decompiled）
//
// 谱系（本批定界）：
//   esSeg(批 4 esSeg-base.h) → esSegAxis（成员类型字 0x5006；内嵌 esAxisObj @+0x6c）
//   esSegGon(批 6 esSeg-leaf.h) → esSegBezier（0x4703；3n+1 控制点）
//                                → esSegCurve（0x4708；BuildLines 平滑升格）
//   esSegBezier → esSegFreeBezier（0x4703 继承；+0x68 容量/+0x6c 容差/+0x70 闭合）
//   esSegRuler(未批 0x6007) → esSegSimpleSingleAxis（0x5002）→ esSegSimpleAxis（0x5001）
// 布局（spec §0 总表）：
//   esSegAxis（0x16c）：+0x34/+0x38 显示折线(两轴含刻度) · +0x44 byte 绘制模式 · +0x46 ushort 退化位
//     · +0x58 ctrl[3] · +0x5c=3 · +0x68 ushort 字体槽 · +0x6a byte 纵段点数（横段起点）
//     · +0x6b byte 活动标签(0..2 盒/≥3 标签) · +0x6c esAxisObj(0xdc) · +0x94/+0x98 float 组尺寸
//     · +0x148/0x14c/0x150 esFormulaBox*（0 原点/1 横轴/2 纵轴）· +0x154+i*8 标签偏移
//   esSegBezier：+0x3c/+0x40 前/后链接对象（首末锚删除许可/0x700000 链接标记）· +0x58/+0x5c ctrl(3n+1)
//   esSegFreeBezier：+0x68 int 容量(100) · +0x6c int 容差(&0xfff) · +0x70 bool 闭合(&0x8000)
//   esSegSimpleSingleAxis：+0x58 ctrl(2 点) · +0x68 float 角度 · +0x6c/+0x6e ushort 400 · +0x70 byte=1
//   esSegSimpleAxis：同上 + ctrl(3 点) · +0x70 byte=0（默认刻度全关）
// 类型字：0x5006 esSegAxis · 0x4703 esSegBezier · 0x4708 esSegCurve · 0x5002 esSegSimpleSingleAxis
//   （0x5003 别名）· 0x5001 esSegSimpleAxis；axis 两臂控制点见 spec §0（P1=(X左端x,Y端点y)、P2=(X端点x,Y下端y)）
#pragma once

namespace eslib {

// 跨批引用（本批不 dump；见各自头文件）
class esSeg;              // 基座，见 esSeg-base.h（批 4）
class esSegGon;           // 见 esSeg-leaf.h（批 6）
class esSegRuler;         // esSegSimpleSingleAxis 基类（0x6007；未批）
class esAxisObj;          // esSegAxis 内嵌坐标几何体（0xdc；调用面见 spec §7）
class esFormulaBox;       // 标签盒（3.7）
class esBezier3;          // FitToBezierA/LinkBezier 静态助手（未批）
class esSnapManager;      // 吸附管理器
class esObjCheck;         // MovePoint 校验
class esHitTest;          // 命中测试
class esVertexList;       // GetCtlPts 输出列
class esVertexGroup;      // MoveAcmePoints 柄组
class esMessage;
class esUndo;
class esPropManager;
class esStyleExchanger;
class esStyleSheet;
class esRender;
class esObject;
class xzLbcList;
class elfPage;
class elfSubject;

// ============================================================
// esSegSimpleSingleAxis — 单线刻度尺（: esSegRuler；类型字 0x5002） [ev:pseudo ctor 0x16440/0x16470]
// 显示点 +0x34：[0..1]=轴线两端，[2..]=刻度对（每刻度 2 点，AddExLine/DrawPath）
class esSegSimpleSingleAxis : public esSegRuler {
public:
    esSegSimpleSingleAxis& operator=(esSegSimpleSingleAxis const&); // 0x10730  thunk → esSegRuler::operator=
    static wchar_t const* ID();                                    // 0x162f0  L"esSegSimpleSingleAxis"
    virtual int isKindOf(wchar_t const*);                          // 0x16300  不中→esSegRuler::isKindOf
    virtual int isOf(wchar_t const*);                              // 0x163b0  仅自比
    esSegSimpleSingleAxis();                                       // 0x16440  esSegRuler + type=0x5002
    esSegSimpleSingleAxis(zPoint);                                 // 0x16470  +0x5c=2；pts[1]=(x,x)【Q-sax-1】；+0x6c/+0x6e=400；+0x70=1
    virtual void Load(elfPage*, elfSubject*, tag_DRAWPARAM*);      // 0x17030  刻度对 AddExLine + LoadLine(pts,pts+1)
    virtual void Draw(esRender*, tag_DRAWPARAM*, Gdiplus::Matrix*);// 0x17240  egPath(pts+2,count−2) + DrawLine
    virtual int DoSnap(esSnapManager*);                            // 0x17400（protected）方向符 pts[1].y<pts[1].x【Q-sax-8】；SnapObj 0x1000
    virtual void GetLbcLines(xzLbcList*, Gdiplus::Matrix const*, int); // 0x175a0  单段（ILT ≡esSegSurface::GetLbcLines）
    void GetLR(int& left, int& right);                             // 0x175e0（protected）左=|p0.x−p1.x|−2000；右=|p1.y−p0.x|−2000【Q-sax-8】
    virtual int GetPts(tagPOINT*& pts, unsigned char*& flags);     // 0x176a0  type==0x5001→4 否则 2；分配拷贝（调用方释放）
    virtual void Build(int);                                       // 0x17780（protected）esSegRuler::GetBiaociPts + 端点 + 角度旋转 +0x68
};

// ============================================================
// esSegSimpleAxis — 十字轴（: esSegSimpleSingleAxis；类型字 0x5001） [ev:pseudo ctor 0x14870/0x148a0]
// 显示点 +0x34：[0..1]、[2..3]=两轴四端，[4..]=四向刻度对；控制点 3 个（[0]=交点、[1]/[2]=对角臂端）
class esSegSimpleAxis : public esSegSimpleSingleAxis {
public:
    esSegSimpleAxis& operator=(esSegSimpleAxis const&);            // 0x10820  thunk → esSegSimpleSingleAxis::operator=
    static wchar_t const* ID();                                    // 0x14720  L"esSegSimpleAxis"
    virtual int isKindOf(wchar_t const*);                          // 0x14730  不中→esSegSimpleSingleAxis::isKindOf
    virtual wchar_t const* className() const;                      // 0x147d0  【错名折叠→esSegSimpleSingleAxis::ID】【Q-axis-1】
    virtual int isOf(wchar_t const*);                              // 0x147e0  仅自比
    esSegSimpleAxis();                                             // 0x14870  esSegSimpleSingleAxis + type=0x5001
    esSegSimpleAxis(zPoint);                                       // 0x148a0  +0x6c/+0x6e=400；+0x70=0；+0x5c=3（3 控制点）
    virtual int SetPointPos(esSnapManager*, int, uint, Gdiplus::Matrix*); // 0x149a0  对称化(&8 max)+象限分配+中点重定+旋转
    virtual void MovePoint(zPoint, int, uint, esObjCheck*);        // 0x14d70  5 柄+保序夹紧四连【Q-sax-6】；&8 平移/等长缩放+角度 0x68
    virtual int DoSnap(esSnapManager*);                            // 0x151f0（protected）+0x70&3 门控网格吸附【Q-sax-2】；SnapObj 两段
    virtual void GetLbcLines(xzLbcList*, Gdiplus::Matrix const*, int); // 0x154b0  两段 FUN_1037fc10
    void GetLREx(int& nx, int& px, int& ny, int& py);              // 0x15510（protected）四向余量 −2000 clamp【Q-sax-4】
    virtual void Build(int);                                       // 0x15670（protected）GetBiaociPts + 4 端点 + 旋转 +0x68
    int GetBiaociPts(int nx, int px, int ny, int py, zPoint org, tagPOINT*& pts, unsigned char*& flags); // 0x15890（protected）三级刻度+中档位【Q-sax-3】；返回 count
    virtual void Load(elfPage*, elfSubject*, tag_DRAWPARAM*);      // 0x15d50  刻度对 AddExLine + LoadLine ×2
    virtual void Draw(esRender*, tag_DRAWPARAM*, Gdiplus::Matrix*);// 0x15fa0  egPath 刻度 + DrawLine ×2
    virtual int GetCtlPts(esVertexList*, int);                     // 0x16150  显示点逆序映射 safe[3..0]→pt[1..4]【Q-sax-7】
};

// ============================================================
// esSegBezier — 贝塞尔折线（: esSegGon；成员类型字 0x4703） [ev:pseudo ctor 0x114b00..0x114d30]
// 控制点 3n+1（锚+双柄三连组）；段操作：Insert/DelPoint1（重叠 2 点扩段）· Insert/DelPoint2（纯 3 点块）
class esSegBezier : public esSegGon {
public:
    esSegBezier& operator=(esSegBezier const&);                    // 0xf720  【ILT 8 符号：Bezier/Curve/HVLine/Line ×&&/const&】→ esSegGon::operator=
    virtual int MoveAcmePoints(esVertexGroup*, tagPOINT*, int);    // 0x1145e0  【ILT 4 符号】idx=(acme+4)>>2；pts[idx]=新点
    static wchar_t const* ID();                                    // 0x1149c0  L"esSegBezier"
    virtual int isKindOf(wchar_t const*);                          // 0x1149d0  不中→esSegGon::isKindOf
    virtual int isOf(wchar_t const*);                              // 0x114a70  仅自比
    esSegBezier();                                                 // 0x114b00  esSegGon + type=0x4703
    esSegBezier(zPoint);                                           // 0x114b30  2 控制点同点 +0x5c=2
    esSegBezier(Gdiplus::PointF*, int);                            // 0x114c20  +0x5c=(n/3)*3+1（钳 3k+1）
    esSegBezier(tagPOINT*, int);                                   // 0x114d30  原样 memcpy
    int CheckFirstLastLink(double eps);                            // 0x114e00  count>6 且首末相接→尾 3 搬首 3、count−=3、Build
    virtual int MovePointTo(esSeg*, zPoint, int, int);             // 0x114f00  拖段端=整段（3 点组）平移；undo 0xf2dc(0x20B)
    virtual int SetPointPos(esSnapManager*, int, uint, Gdiplus::Matrix*); // 0x1150f0  i==0→count−=4【Q-bez-1】；追加 3；<5 重建；镜像【Q-bez-3 族】
    virtual void MovePoint(zPoint, int, uint, esObjCheck*);        // 0x115580  锚→邻柄同 delta；柄&8→旋转邻点/double-delta【Q-bez-2】；首末 MoveLinkPoint
    virtual void UnitOtherMaxRect(zRect&);                         // 0x115940（protected）用控制点口径（ILT ≡esSegRoundLine）
    virtual void BuildLines(tagPOINT*, int);                       // 0x115a40（protected）n≤3 折线（fill=1）否则 (n/3)*3+1（fill=3）
    virtual int AddPoint(zPoint, int, int);                        // 0x115aa0  锚 ≤tol→2；段命中→InsertPoint1 + undo 0xf2ea
    virtual void* Undata(ushort&, void*, int&);                    // 0x115d80  0xf2ea↔0xf2eb、0xf2ec↔0xf2ed；否则 esSegGon::Undata
    void InsertPoint1(int idx, tagPOINT* pts);                     // 0x116040（protected）5 点替换 2 点扩段；free 0x8123
    void DelPoint1(int idx, tagPOINT* pts);                        // 0x116150（protected）InsertPoint1 逆操作
    void InsertPoint2(int idx, tagPOINT* pts);                     // 0x116290（protected）纯 3 点块插入
    void DelPoint2(int idx);                                       // 0x1163c0（protected）纯 3 点块删除
    tagPOINT* GetControlLine(int& outCount, int idx);              // 0x1164c0  显示点 (k−1,k,k+1)（闭合回绕）；*outCount=数量
    virtual void SnapPointWhenCreate(esSnapManager*) const;        // 0x1165f0  n=(count/3−1)*3+1；≥0x65 仅首点【Q-bez-5】
    virtual int DoSnap(esSnapManager*);                            // 0x1166b0（protected）<0x97 每 3rd 锚否则首末；SnapObj 0x2000【Q-bez-5】
    virtual int HitTestAcme(esHitTest*);                           // 0x116790  CheckMode(0x10)；锚 sel 0x10+idx；柄 sel 6
    virtual tagPOINT GetAcmePoint(int idx);                        // 0x116e60  idx 越界→solid-rect 中心；否则显示点
    virtual int GetCtlPts(esVertexList*, int);                     // 0x116f20  3k+1 修补【Q-bez-3】+三模式（编辑/显示点表/纯拷贝）
    virtual int DeletePoint(int idx, int mode);                    // 0x117a60  锚删段（undo 0xf2ed）；柄折回锚【Q-bez-6】；count<7 清空路径
};

// ============================================================
// esSegCurve — 平滑插值曲线（: esSegGon；成员类型字 0x4708） [ev:pseudo ctor 0x118010/0x118040]
// 外部喂采样点，BuildLines 用 get_curve 升为 3 连组后按 esSegBezier 布局显示；operator= 折叠于 0xf720
class esSegCurve : public esSegGon {
public:
    static wchar_t const* ID();                                    // 0x117ed0  L"esSegCurve"
    virtual int isKindOf(wchar_t const*);                          // 0x117ee0  不中→esSegGon::isKindOf
    virtual int isOf(wchar_t const*);                              // 0x117f80  仅自比
    esSegCurve();                                                  // 0x118010  esSegGon + type=0x4708
    esSegCurve(zPoint);                                            // 0x118040  esSegGon(x,y,x,y)（两点重合）
    virtual void BuildLines(tagPOINT*, int);                       // 0x118080（protected）n==2 直通；否则分配 3n+1 + get_curve 升格 + 闭合段回写
    void get_curve(tagPOINT p1, tagPOINT p2, tagPOINT p3, tagPOINT* out); // 0x1183a0（protected）重心参数化 + 张力系数 DAT_1057f170
    virtual int DoSnap(esSnapManager*);                            // 0x118640（protected）闭合→全点 SnapObj；开口→另吸首末
    virtual int AddPoint(zPoint, int, int);                        // 0x1186e0  esSegGon::InsertPoint(knot+1) + undo 0xf2ef【Q-bez-8】
};

// ============================================================
// esSegFreeBezier — 随手画自由曲线（: esSegBezier；type 继承 0x4703） [ev:pseudo ctor 0x11cdc0]
// 进度中 mode1 追加采样+即时抽稀；收笔 mode2 走 esBezier3::FitToBezierA 拟合
class esSegFreeBezier : public esSegBezier {
public:
    esSegFreeBezier& operator=(esSegFreeBezier const&);            // 0xfac0  实函数：基类 + +0x68/+0x6c/+0x70
    static wchar_t const* ID();                                    // 0x11cc70  L"esSegFreeBezier"
    virtual int isKindOf(wchar_t const*);                          // 0x11cc80  不中→esSegBezier::isKindOf
    virtual wchar_t const* className() const;                      // 0x11cd20  【错名折叠→esSegBezier::ID】【Q-axis-1】
    virtual int isOf(wchar_t const*);                              // 0x11cd30  仅自比
    esSegFreeBezier(zPoint, ulong);                                // 0x11cdc0  +0x70=(p&0x8000)!=0；+0x6c=p&0xfff；+0x68=100；malloc(100*8)；pts[0]=pts[1]=p
    void DelSamePoints();                                          // 0x11cee0（protected）count>2→FitToBezierA 抽稀；type 回写 0x4703【Q-bez-9】
    virtual void Build(int);                                       // 0x11cf30（protected）0→esSegGon::Build(0)；否则 SetPtInfo（开放折线）
    virtual int SetPointPos(esSnapManager*, int, uint, Gdiplus::Matrix*); // 0x11cf70  mode1 追加（±100 容量；≤3 点/步；末段阈值【Q-bez-9】）；mode2 收笔拟合
};

// ============================================================
// esSegAxis — 坐标轴（: esSeg；成员类型字 0x5006；内嵌 esAxisObj + 3 标签盒） [ev:pseudo ctor 0x3fd350]
// 显示折线 +0x34 = 纵段 [0..+0x6a) + 横段 [+0x6a..)（三角波刻度）；两臂控制点 +0x58[3] 见文件头
class esSegAxis : public esSeg {
public:
    esSegAxis& operator=(esSegAxis const&);                        // 0x108f0  esSeg::op= + +0x68/+0x6a/+0x6b + esAxisObj::op= + 3 盒指针浅拷贝【Q-axis-2】+ 6 float
    static wchar_t const* ID();                                    // 0x3fd210  L"esSegAxis"
    virtual int isKindOf(wchar_t const*);                          // 0x3fd220  不中→esSeg::isKindOf
    virtual int isOf(wchar_t const*);                              // 0x3fd2c0  仅自比
    esSegAxis();                                                   // 0x3fd350  esSeg + esAxisObj@+0x6c + +0x154 初始化器；type=0x5006；不清 +0x44
    virtual ~esSegAxis();                                          // 0x3fd430  3 盒释放 + ~esAxisObj + ~esSeg
    void Initialize(esStyleSheet*, esAxisObj*, ushort, ushort);    // 0x3fd4c0  字体槽 +0x68；3 控制点（[0]=(0,0)、[1]/[2]=端点−基点）；3× AddOrRemoveTextBox
    virtual void RecalcLayout();                                   // 0x3fd6e0  内容矩形 ∪ 3 盒 GetBounds ∪ 显示折线 → SetSolidRect/SetBoundingRect
    virtual void Build(int);                                       // 0x3fd8a0（protected）InitSize + 三角波刻度（每刻度净 500【Q-axis-3】）+ +0x6a + esAxisObj::Build + 3× SetTextBoxPostion
    virtual void Load(elfPage*, elfSubject*, tag_DRAWPARAM*);      // 0x3fe2e0  esAxisObj::Load + 臂 LoadLine/esScriber + 盒 OnLoad(flags&7)
    virtual void Draw(esRender*, tag_DRAWPARAM*, Gdiplus::Matrix*);// 0x3fe850  esAxisObj::Draw + 两臂 DrawLine/DrawTypedLines + 盒 OnDraw；预览态 +0x44=1
    ulong GerDrawFlags() const;                                    // 0x3fed40（private）bit0..2=盒存在∪臂非退化；末尾按退化位清除【Q-axis-5】
    tagPOINT GetTBOrg(int idx);                                    // 0x3feee0（protected）0→基点；1→(pt2.x−800, P0.y)【RevX→pt1.x+800】；2→(P0.x, pt1.y+800)【RevY→pt2.y−800】
    int HandMoveText(tagPOINT& pt, int mode);                      // 0x3ff000  idx<3：undo 0xb11(9B)→写 +0x154+idx*8；否则 esAxisObj 标签路径
    void SetTextBoxPostion(int idx);                               // 0x3ff560（protected）三分布局：d≥1→org+d；|d|≥eps→org−尺寸+d；|d|<eps→居中
    virtual void CollectStyles(esStyleSheet*) const;               // 0x3ff700  esUseInfo::CollectStyles(+0x68,1) + 3 盒
    virtual int IsEqual(esObject*, esStyleSheet*);                 // 0x3ff780  基类 + 字体槽 + esAxisObj + 盒成对
    virtual void Serialize(zArchive&, esStyleSheet*, ushort);      // 0x3ff890  esSeg + esAxisObj + +0x68 + 0x18B 偏移块 + 3 盒；掩码门 0x1060307（读）/无条件（写）
    virtual void CopyFrom(esObject const*, esStyleExchanger*);     // 0x3ffc50  ID 判型；esAxisObj::CopyFrom；字体槽重映射；3 盒克隆+绑 sheet
    virtual void GetLbcLines(xzLbcList*, Gdiplus::Matrix const*, int); // 0x3ffe30  按 +0x6a 拆两段提交【Q-axis-8】
    virtual int MoveAcmePoints(esVertexGroup*, tagPOINT*, int);    // 0x3fffd0  柄 kind>>2：0/1/2/3/4 = P0/pt2.x/pt1.x/pt1.y/pt2.y 分量写；CheckPointsPositon
    void GetAxisTransfrom(Gdiplus::Matrix&, tagPOINT);             // 0x4002c0  平移（目标≠基点）+ 缩放 +0x94/+0x98
    virtual void MovePoint(zPoint, int, uint, esObjCheck*);        // 0x400390  退化位折叠整体移动；5 柄分量写；CheckPointsPositon
    void CheckPointsPositon();                                     // 0x400860（protected）保序夹紧（400/1500/2000/4000 极限）
    virtual void unMPSave(zArchive&);                              // 0x400cd0  存盘刷新 +0x46 退化位；+0x94/+0x98 差分→undo 0xc54
    virtual void LoadProp(esPropManager*, ulong);                  // 0x400e60  组 0xc00：c28 字体槽/c29/c2a/c2b + c45..c47 盒存在位 + esAxisObj::LoadProp
    virtual void SaveProp(esPropManager*, ulong);                  // 0x400fd0  静态快照比对→0xc51/0xc52/0xc21..0xc3a/0xc53；盒增删→0xc48/0xc49
    int AddOrRemoveTextBox(esStyleSheet*, uchar, int, esUndo*);    // 0x4016d0（protected）增：undo 0xc48 + 建盒 + SetText(DAT_1069dd58+idx*2)；删：undo 0xc49
    virtual void* Undata(ushort&, void*, int&);                    // 0x401a30  c51/c52/c54/b11 交换；c48↔c49 盒重建/序列化；否则 esAxisObj::OnUndata→esSeg::Undata
    virtual int OnMessage(esMessage*, ulong);                      // 0x402060  3 盒 vtbl+0x48；任一处理→RecalcLayout
    virtual int HitTest(esHitTest*, int);                          // 0x4020f0  +0x44≠0→0；盒 1/2 需臂非退化；sel 0x17/0x18/0x1a/7
    esFormulaBox* GetActiveTBox();                                 // 0x402350  0x6b<3→盒[0x6b] 否则 0
    tagRECT GetActiveBoxRect();                                    // 0x402380  盒/标签 bounds → 4 角变换 → GetRectByPoints → 外扩 200
    virtual void Undo(ushort, zArchive&, zArchive&);               // 0x402580  0xc21..0xc3a/0xc53 字段映射【Q-axis-9】；default→esFormulaBox::CaretMove
    virtual int GetCtlPts(esVertexList*, int);                     // 0x402a00  5 柄 [基点,(pt2.x,P0.y),(pt1.x,P0.y),(P0.x,pt1.y),(P0.x,pt2.y)] 变换后入列
    virtual int DoSnap(esSnapManager*);                            // 0x402c10  基点吸附（阈值 0x200/0x20） + 两段 SnapLines 0x1000
};

}  // namespace eslib
