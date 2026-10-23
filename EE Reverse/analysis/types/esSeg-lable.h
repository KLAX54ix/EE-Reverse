// analysis/types/esSeg-lable.h
// 标注族（esSegLable / esLableBox / esLableBoxEx）
// — 阶段 2 第八批（eslib.dll · 绘图核心 4/6）
//
// 证据：
//   [ev:pseudo] analysis/pseudo/eslib/esSeg-lable.decomp.txt   (72/72 函数原样伪代码)
//   [ev:spec]   analysis/pseudo/eslib/esSeg-lable.md           (布局/三段文本/位置码/布置族/Q 系列)
//   [ev:ledger] ledger/ledger.csv  eslib:<rva>（72 行 → status=decompiled）
//
// 谱系（本批定界）：
//   esSeg(批 4 esSeg-base.h) → esSegLable（成员类型字 0x600d；内嵌 esEQLine @+0x80）
//   esFormulaBox(3.7) → esLableBox : esFormulaBox → esLableBoxEx
// 布局：
//   esSegLable ≥0xD8：+0x34/+0x38 显示点(6 槽/count=5；pt[5]=pt[0]+margin 锚)
//     · +0x58/+0x5C ctrl(1 点)/计数 · +0x60 flags(5B) · +0x68 wchar* 文本
//     · +0x6C ushort/+0x6E ushort 字体槽 · +0x70..0x72 段长 · +0x73 特性字节
//     · +0x74 对齐/位置码 · +0x78/+0x7C float 偏移 · +0x80 esEQLine · +0xD4 esFontSheet*
//   esLableBox ≥0x5C：+0x14 esTextLine* · +0x1c ushort · +0x24/+0x28 盒原点
//     · +0x2c 宽 · +0x3c/+0x48 ushort 缓存 · +0x40 esFontSheet* · +0x4c Matrix（Q-lablebox-2）
//     · +0x54 pts(8 槽)/+0x58 count（count>5 时 pts[5..] 为引线）
//   esLableBoxEx：+0x5C/+0x60 tagPOINT 锚缓存
// 类型字：0x600d esSegLable（成员）；esLableBox/Ex 无类型字（esEquBox 家族）
#pragma once

namespace eslib {

// 跨批引用（本批不 dump；见各自头文件）
class esSeg;          // 基座，见 esSeg-base.h（批 4）
class esEQLine;       // esSegLable 内嵌 @+0x80（3.7）
class esFormulaBox;   // esLableBox 基类（3.7）
class esEquBox;       // esFormulaBox 基链（3.7）
class esTextLine;     // esLableBox 行容器（3.7）
class esFontSheet;
class esStyleSheet;
class esUndo;
class esPropManager;
class esStyleExchanger;
class esDimenStyle;   // 标注样式（S5 余部）
class esDS_Txt;
class esDS_HV;

// ============================================================
// esSegLable — 文字标签段（三段文本 + 内嵌 EQLine；24 项属性组 0xa00） [ev:pseudo ctor 0x3e8f40/0x3e8ff0]
// 类型字 0x600d（写 +4）；尺寸 ≥0xD8（末字段 +0xD4）
class esSegLable : public esSeg {
public:
    esSegLable& operator=(esSegLable const&);                  // 0xef80    【ILT 段】全字段拷贝（+0x68 文本指针浅拷贝，Q-lable-5）
    static wchar_t const* ID();                                // 0x3e8e00  L"esSegLable"
    virtual int isKindOf(wchar_t const*);                      // 0x3e8e10  this==0→0；不中→esSeg::isKindOf
    virtual int isOf(wchar_t const*);                          // 0x3e8eb0  仅自比
    esSegLable();                                              // 0x3e8f40  type=0x600d；+0x74=0
    esSegLable(zPoint, zwstr, ulong segLens, ushort slot, ushort f6c); // 0x3e8ff0  ulong 拆 4 字节写 +0x70..+0x73；+0x74=4
    virtual ~esSegLable();                                     // 0x3e9190  释放 +0x68(FUN_10528fdd,2) → ~EQLine → ~esSeg
    virtual void RecalcLayout();                               // 0x3e91e0  仅转发 esSeg::RecalcLayout（Q-lable-9）
    virtual void LoadProp(esPropManager*, ulong);              // 0x3e9200  组 0xa00：a01..a0e，a0a 高半字节≠0 时读出 −1
    void SetTextColor(ulong color, esStyleSheet*);             // 0x3e9560  font+0x14≠色→Clone+sheet 注册+undo 0xa01+换槽
    virtual int OnMessage(esMessage*, ulong);                  // 0x3e9600  type==0x113 特性匹配→vtbl+0x1c
    virtual void SaveProp(esPropManager*, ulong);              // 0x3e9660  字体克隆合并；文本更新 undo 0xa10；0x8123 死存
    virtual void Undo(ushort code, zArchive&, zArchive&);      // 0x3e9e10  0xa01/a0a/a0b/a0f/a11/a12；默认 esFormulaBox::CaretMove
    virtual void* GetTextData(int& sz);                        // 0x3e9fd0  消费性：[len0..2][text]；free +0x68（Q-lable-7）
    virtual void* Undata(ushort& code, void* data, int& sz);   // 0x3ea0b0  0xa10 恢复三段文本
    virtual void CollectStyles(esStyleSheet*) const;           // 0x3ea190  esUseInfo::CollectStyles(+0x6E,1)；版本升 0x1000202
    void Initialize(esFontSheet*);                             // 0x3ea1e0  +0xD4 惰性绑定
    virtual int HitTest(esHitTest*, int mode);                 // 0x3ea210  bit5→HitTestLines→7；盒内→0x15/0x16
    int HandMoveText(tagPOINT& pt, int mode);                  // 0x3ea2f0  拖拽设自定义对齐半字节+floats（undo a11/a12/a0a）
    virtual void Load(elfPage*, elfSubject*, tag_DRAWPARAM*);  // 0x3ea790  填充/边框/圆点(5/2 笔宽)+子矩形 Offset(pts[5])
    ulong GetLableFreature() const;                            // 0x3eac10  槽<<16|0x73&0xf0|MathCharType 位|段存在位
    virtual void Draw(esRender*, tag_DRAWPARAM*, Matrix const*);// 0x3ead30  填充/边框/文本/圆点(2×笔宽)（Q-lable-2）
    void GetEntersectInfo(zPoint, zPoint, double&, double&);   // 0x3eb140  锚点近端点→交线取参数最大
    void RecalcLayoutLable();                                  // 0x3eb390  三段文本→EQLine；+0xD4==0 直接返回
    virtual void Build(int n);                                 // 0x3ebd80  9 宫格/自定义位置码；pt[5]=pt[0]+margin（Q-lable-3/10）
    virtual int IsEqual(esObject*, esStyleSheet*);             // 0x3ec2c0  +0x7C==param+0x78（Q-lable-1）
    virtual void Serialize(zArchive&, esStyleSheet*, ushort);  // 0x3ec400  ver<0x1000202 / ver<0x2000735 降级规则
    virtual void CopyFrom(esObject const*, esStyleExchanger*); // 0x3ec6c0  槽经 GetFontIdx 重映射+文本深拷贝
};

// ============================================================
// esLableBox — 标注框（esEquBox 家族；文本行 + 包围多边形 + 引线） [ev:pseudo ctor 0x443920]
// 无类型字；点数组 8 槽：0–4 盒多边形（闭合）、>5 时为引线折线（pts[5..]）
class esLableBox : public esFormulaBox {
public:
    static wchar_t const* ID();                                // 0x4437d0  L"esLableBox"
    virtual int isKindOf(wchar_t const*);                      // 0x4437e0  this==0→0；不中→esFormulaBox::isKindOf
    virtual wchar_t const* className() const;                  // 0x443880  → esFormulaBox::ID
    virtual int isOf(wchar_t const*);                          // 0x443890  仅自比
    esLableBox();                                              // 0x443920  +0x1c=8；+0x54/+0x58=0
    virtual ~esLableBox();                                     // 0x4439b0  释放 +0x54；+0x4c 按 CComBSTR 析构（Q-lablebox-2）
    virtual Matrix* GetMatrix();                               // 0x4d70    return (Matrix*)(this+0x4c)【ILT 2 符号】
    virtual void Initialize(esStyleSheet*);                    // 0x443bb0  建 esTextLine（SetupFonts(L"0")→line+0x1e 槽）
    void InitText(zwstr s1, zwstr s2, zwstr s3, esFontSheet*);// 0x443a00  双盒 0x11000024：s2→First、s3→Last
    void UnionRect(zRect&);                                    // 0x443c70  UnionPoints(rect,pts,4)
    virtual int Build();                                       // 0x443ca0  盒多边形+pts6/7=±(w/2+fh/2)；pts[5] 不写（Q-lablebox-1）
    int Qiujiao(int&, int&);                                   // 0x443ed0  交线 min/max 出参；返回=全点 x 跨度（Q-lablebox-3）
    int JIao_LineCircle(tagPOINT&, tagPOINT&, int r);          // 0x4440c0  线段×圆(原点,r)；返回点掩码 1/2
    float Qiujiao(float&, float&, int r);                      // 0x4446b0  逐边角解；左半面→*p1、右半面→*p2；返回和
    int HitTest(esHitTest*, int mode);                         // 0x4448c0  盒内 0x1b/0x18；引线 7；owner=vtbl+0x54(0xe)
    void GetPts(int& n, tagPOINT* pts, uchar* flags);          // 0x444990  flags：idx 0/5→0 否则 1；n+=count
    int GetCtlPoint(tagPOINT*);                                // 0x444a40  pts[0]/pts[2] 中点
    float GetTextAngle(zPoint, int, float, float, ushort, esDS_HV*); // 0x445980  排向 style+0x10&0xf；0x40 镜像位
    int SetMePoints_ForCCD(zPoint, float, Matrix*);            // 0x445cc0  返回 diag=int(fh·√2)；y=py−fh−h/2−fh/10−style+0xc
    int SetMePoints_ForCCD_TB(zPoint, zPoint, int, int, float, Matrix*); // 0x445f10  两点变体
    int SetMePoints_ForAny(tagPOINT&, tagPOINT&, Matrix*);     // 0x446140  通用两点布置（镜像±90° 选择）
    int IsMirr(float angle);                                   // 0x447580  DAT_1057f50c < angle ≤ DAT_1057f534 → 1
    int SetMePoints_ForBJ(zPoint, float, int, int, tagPOINT*, Matrix*); // 0x4475c0  半径/角度标注布置；返回 flags
    int SetMePoints_ForGongCa(zPoint, int&, int);              // 0x447e50  公差按 100 对齐（阈值 51，Q-lablebox-5）；+0x48=fh/4
    void SetMatrix(int x, int y, Matrix*);                     // 0x448010  原点/矩阵/变换三连
    tagPOINT SetMePoints_ForYX(zPoint, zPoint, ulong, Matrix*); // 0x448070  引线布置（flags&0x30）；返回引点
    int SetMePoints_ForZJ(zPoint, float, int, int, tagPOINT*, Matrix*); // 0x448420  直径标注布置
    void SetMePoints_ForParen(zPoint, zPoint, float, int, Matrix*); // 0x448cd0  弧括号（极角 360/180 规范化）
    int InitPts(double f);                                     // 0x449100  max(int(√2·fh/2·f), int(½√(w²+h²)))
    int SetTextPos(zPoint, int, int, Matrix*);                 // 0x449200  +0x48=⌊fh/8⌋ 缓存；返回 EquBox::Height
    void SetTextPos(zPoint, Matrix*);                          // 0x4494f0  原点/矩阵/变换
    virtual int OnMessage(esMessage*, ulong);                  // 0x449560  直通 esEquBox::OnMessage
    void Load(elfPage*, elfSubject*, esDS_Txt*, int);          // 0x449580  填充/边框(0x1000)/引线（AddExLines 或 esScriber）
    void Draw(esRender*, Matrix const*, egPen*, int);          // 0x449990  FillPolygon/OnDraw/DrawEdge/DrawPolygon/DrawTypedLines
};

// ============================================================
// esLableBoxEx — 扩展标注框（+0x5C/+0x60 锚缓存；CVL/CHL 布置） [ev:pseudo ctor 0x449d90]
// 无类型字；CVL/CHL 地址夹在 esLableBox 之间（链接序，Q-lableboxex-2）
class esLableBoxEx : public esLableBox {
public:
    static wchar_t const* ID();                                // 0x449c40  L"esLableBoxEx"
    virtual int isKindOf(wchar_t const*);                      // 0x449c50  不中→esLableBox::isKindOf
    virtual wchar_t const* className() const;                  // 0x449cf0  → esLableBox::ID
    virtual int isOf(wchar_t const*);                          // 0x449d00  仅自比
    esLableBoxEx();                                            // 0x449d90  +0x5C/+0x60=0
    virtual ~esLableBoxEx();                                   // 0x449dd0  ~esLableBox
    virtual int IsEqual(esObject*, esStyleSheet*);             // 0x449df0  读对方 +0x5c、比 +0x60；结果写回自身 +0x5C（Q-lableboxex-1）
    virtual void Serialize(zArchive&, esStyleSheet*, ushort);  // 0x449e50  esFormulaBox::Serialize + 8B @+0x5C
    void SetMePoints_ForCVL(zPoint, int, float&, float&, ushort&, Matrix*); // 0x444ac0  弧长/弧高标注；flags 0x100/0x200 写回
    void SetMePoints_ForCHL(tagPOINT*, ushort&, Matrix*, float); // 0x4466f0  弧弦/弧高；锚点 [2/3/6/7]；flags 0x80/0x100/0x200
};

}  // namespace eslib
