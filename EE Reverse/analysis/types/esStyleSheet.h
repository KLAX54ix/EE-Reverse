// analysis/types/esStyleSheet.h
// 文档样式中枢（esStyleSheet / esBrushInfo / esPenInfo）
// — 阶段 2 第五批（eslib.dll · 绘图核心 S1 · 2/6）
//
// 证据：
//   [ev:pseudo] analysis/pseudo/eslib/esStyleSheet.decomp.txt   (149/149 函数原样伪代码)
//   [ev:spec]   analysis/pseudo/eslib/esStyleSheet.md           (结构总览/SFlags/序列化/Q1–Q12)
//   [ev:ledger] ledger/ledger.csv  eslib:18c0..  status=decompiled
//
// 角色：esStyleSheet = 文档全部样式表的组合对象（19 个内嵌子表 + 状态区）；
//       esBrushInfo  = 画布对象填充参数（也是 esImageSheet 索引缓存载体）；
//       esPenInfo    = 描边参数（esSeg::Draw 之笔的来源；ee-draw pen_mm 对应 +0x08）。
// 地址注释为 RVA（= Ghidra 地址 − 0x10000000）。
#pragma once

namespace eslib {

// ---- 不透明前置声明（布局归各自批；本批只确界内嵌偏移）----
class esFontSheet; class esBrushSheet; class esColorSheet; class esBoxSheet;
class esEdgeSheet; class esCellSheet; class esUIndentInfo; class esTabSheet;
class esBulletSheet; class esBlockSheet; class esDropcapSheet; class esParaStyleSheet;
class esDimationSheet; class esImageSheet; class esRoleSheet; class esMstPageSheet;
class esFmtPageSheet; class esStringSheet; class esExamSheet;
class esStrRes; class esExamStyle; class esNoteStyle; class esRoleList;
class esParaTmplList; class esAutoHeadList; class esParaModel; class esBaseDoc;
class esColorScheme; class esImage;
class esParaLine; class esMstPageManager; class esBulletStyle;   // 引用方（各自批细化）
class zArchive;

// ============================================================
// 常量 / 枚举
// ============================================================

// 当前写版本魔数（ctor/copy/EndSerilize/SetAsCloneMode 恒复位；GetVersion(NULL) 返回）
constexpr unsigned long STYLESHEET_VERSION = 0x2000837;

// 序列化模式 enmSMode（+0x9B8）[ev:spec §0]
//   IsWriteMode = (mode & 1)；IsReadMode = mode≠0 && !(mode&1)；
//   IsFileMode = {3,4}；IsExamMode = {5,6}；IsCopyMode = {1,2}；IsLocked = mode≠0
enum class SerialMode : unsigned long {
    None      = 0,
    MemWrite  = 1,
    MemRead   = 2,
    FileWrite = 3,
    FileRead  = 4,
    ExamWrite = 5,
    ExamRead  = 6,
};

// SFlags（+0x9BC）：本轮序列化/收集哪些子表 [ev:spec §0「位→子表」表 / SetStoreSFlags 0x306180]
enum class StoreFlags : unsigned long {
    ExamSheet     = 0x00000001,   // +0x814 esExamSheet
    StringSheet   = 0x00000002,   // +0x7F4 esStringSheet
    FontSheet     = 0x00000004,   // +0x000 esFontSheet
    ColorSheet    = 0x00000008,   // +0x614 esColorSheet
    CellSheet     = 0x00000010,   // +0x674 esCellSheet
    UIndent       = 0x00000020,   // +0x694 esUIndentInfo
    TabSheet      = 0x00000040,   // +0x6B4 esTabSheet
    BlockSheet    = 0x00000080,   // +0x6F4 esBlockSheet
    BulletSheet   = 0x00000100,   // +0x6D4 esBulletSheet
    ParaSheet     = 0x00000200,   // +0x734 esParaStyleSheet
    DimationSheet = 0x00000400,   // +0x754 esDimationSheet
    ImageSheet    = 0x00000800,   // +0x774 esImageSheet（双版本门，见 spec §4.1/Q9）
    BrushSheet    = 0x00001000,   // +0x5F4 esBrushSheet
    DropcapSheet  = 0x00002000,   // +0x714 esDropcapSheet
    BoxSheet      = 0x00004000,   // +0x634 esBoxSheet
    EdgeSheet     = 0x00008000,   // +0x654 esEdgeSheet
    HiddenBits    = 0x00010000,   // +0x994..+0x9B3 raw 32B（非子表）
    RoleSheet     = 0x00100000,   // +0x794 esRoleSheet
    DocStyle      = 0x10000000,   // SerializeDocumentStyle（考试样式+文档级模型）
    FmtPageSheet  = 0x01000000,   // +0x7D4 esFmtPageSheet
    MstPageSheet  = 0x02000000,   // +0x7B4 esMstPageSheet
    ParaTmplList  = 0x20000000,   // +0x940 esParaTmplList
    RoleList      = 0x40000000,   // +0x908 esRoleList
    AutoHeadList  = 0x80000000,   // +0x958 esAutoHeadList
};

// ============================================================
// esStyleSheet — 组合对象：19 个内嵌子表 + 状态区（本批仅确界）
//   字体表就在 +0x000 —— 即 ee-draw `caretContext().fontSheet == pageLists()[].styleSheet` 的由来。
class esStyleSheet {
    /* +0x000 */ esFontSheet       m_fontSheet;       // 字体表（◆ 大表，到 +0x5F4）
    /* +0x5F4 */ esBrushSheet      m_brushSheet;      // 刷子表
    /* +0x614 */ esColorSheet      m_colorSheet;      // 配色表
    /* +0x634 */ esBoxSheet        m_boxSheet;        // 框样式表
    /* +0x654 */ esEdgeSheet       m_edgeSheet;       // 线型/外框表
    /* +0x674 */ esCellSheet       m_cellSheet;       // 单元格样式表
    /* +0x694 */ esUIndentInfo     m_uIndentInfo;     // 缩进样式表（含悬挂）
    /* +0x6B4 */ esTabSheet        m_tabSheet;        // 制表位表
    /* +0x6D4 */ esBulletSheet     m_bulletSheet;     // 项目符号/编号表
    /* +0x6F4 */ esBlockSheet      m_blockSheet;      // 文本块样式表
    /* +0x714 */ esDropcapSheet    m_dropcapSheet;    // 首字下沉表
    /* +0x734 */ esParaStyleSheet  m_paraSheet;       // 段落样式表
    /* +0x754 */ esDimationSheet   m_dimationSheet;   // 尺寸标注样式表
    /* +0x774 */ esImageSheet      m_imageSheet;      // 图片表（brush 图片索引缓存来源）
    /* +0x794 */ esRoleSheet       m_roleSheet;       // 角色表
    /* +0x7B4 */ esMstPageSheet    m_mstPageSheet;    // 母版页表
    /* +0x7D4 */ esFmtPageSheet    m_fmtPageSheet;    // 页面格式表
    /* +0x7F4 */ esStringSheet     m_stringSheet;     // 字符串资源表
    /* +0x814 */ esExamSheet       m_examSheet;       // 考试样式表
    /* +0x840 */ esStrRes          m_strRes;          // 0x10B（4 dword；不参与 SFlags）
    /* +0x850 */ unsigned long     m_version;         // = STYLESHEET_VERSION
    /* +0x854 */ unsigned short    m_flags854;        // bit0 文档已挂/考试 UI 模板就绪
    /* +0x856 */ unsigned short    m_flags856;        // bit0 EndSerilize 需 TackExamIndexs
    /* +0x858 */ esExamStyle       m_examStyle;       // 考试样式（选项布局/分隔符）
    /* +0x874 */ unsigned long     m_hidden874;       // 隐藏状态位（bit17/19 答案…）
    /* +0x878 */ unsigned long     m_hidden878;       // （bit3/4 解析…）
    /* +0x8E4 */ esNoteStyle       m_noteStyle;       // 批注样式
    /* +0x908 */ esRoleList        m_roleList;        // 角色列表（SFlags 0x40000000）
    /* +0x91E */ unsigned short    m_flag91E;         // bit0 LoadForm 载入角色后置位
    /* +0x940 */ esParaTmplList    m_paraTmplList;    // 段落模板列表（SFlags 0x20000000）
    /* +0x958 */ esAutoHeadList    m_autoHeadList;    // 自动题头列表（SFlags 0x80000000）
    /* +0x968..+0x98B */ unsigned long m_unk968[9];   // 未命名状态块（ctor/op= 整体拷贝）
    /* +0x98C */ esBaseDoc*        m_doc;             // 宿主文档（GetEpDocument）
    /* +0x990 */ short             m_docStyleA;       // 文档样式参数（ctor 默认 200）
    /* +0x992 */ short             m_docStyleB;       // （ctor 默认 0x96=150）
    /* +0x994 */ unsigned char     m_hiddenBits[0x20];// 段落隐藏位图（SFlags 0x10000 整体序列化）
    /* +0x9B4 */ int               m_cloneCount;      // CloneMode 计数（IsCloneMode 直读）
    /* +0x9B8 */ SerialMode        m_smode;           // 序列化模式
    /* +0x9BC */ unsigned long     m_sflags;          // StoreFlags 集合
    /* +0x9C0 */ esParaModel*      m_scratchModel;    // ★共享 scratch 段落模型（懒建 0x50）Q1

public:
    // --- 生命周期 / 全局 ---
    esStyleSheet(esBaseDoc* doc);                      // 0x304500 建 19 子表；色表空→默认方案
    esStyleSheet(esStyleSheet const&);                 // 0x2c230  逐子表拷贝 ctor
    ~esStyleSheet();                                   // 0x3048b0 反向析构 + 释放 scratch
    esStyleSheet& operator=(esStyleSheet const&);      // 0x1fcf70 【+0x5F4..+0x7F4 全经 esBlockSheet::operator=（折叠）】
    // static (default_constructor_closure)            // 0x42c9f0 转 ctor(doc=NULL)
    // --- 模式 / 版本 ---
    unsigned long GetVersion();                        // 0xd0c70  this==NULL → 0x2000837
    unsigned long GetSerialMode();                     // 0x42c980
    int  IsReadMode();                                 // 0x42c9a0
    int  IsWriteMode();                                // 0x32a420  mode & 1
    int  IsFileMode();                                 // 0x32a3e0  {3,4}
    int  IsCopyMode();                                 // 0x1df5d0  {1,2}
    int  IsExamMode();                                 // 0xd00a0   {5,6}
    int  IsLocked();                                   // 0x199050  mode != 0
    int  IsCloneMode();                                // 0x199110  直读 +0x9B4
    int  SetAsCloneMode(int n);                        // 0x305cb0  变则写 +0x9B4；重置 version/SFlags/SFlags856/smode
    // --- 查询 / 全局入口 ---
    esBaseDoc*        GetEpDocument();                 // 0xb8920   *(doc*)0x98C
    esExamStyle*      GetExamStyle();                  // 0xb8b90   this+0x858
    esNoteStyle*      GetNoteStyle();                  // 0x36a4c0  this+0x8E4
    static int  GetTagFont(esStyleSheet*, int id);     // 0x304a80  m_pTagFonts 查 id→font[索引]
    static void SetTagFontMap(void* map);              // 0x42c9e0  模块级 m_pTagFonts
    int   GetChoiceMinOffset();                        // 0x304ad0  字体高 × (esExamStyle+0x18>>16)/10
    int   GetChoiceLineRightSpace();                   // 0x304b20  字体高 × (esExamStyle+0x14>>8)/10
    int   GetDefaultExamFontheight();                  // 0x32ac20  恒 0x41a(1050)
    static void* GetBlanks();                          // 0x305210  （反编译类型失真：实为 esBlankList 静态）
    int   GetMstPageList(esMstPageManager*);           // 0x307150  枚举 +0x7B4
    unsigned long ToEpColor(unsigned long color, int kind); // 0x3051b0 版本<0x1070311 旧色域转换
    int   CopyExamStyleFrom(esStyleSheet*);            // 0x305840  esExamStyle::CopyFrom 双表索引重写
    int   CompBullet(esBulletStyle*, esBulletStyle*);  // 0x305d60  同索引→0x400；CompStyle
    int   BuilderAnswer(unsigned long flag, void* str); // 0x3071b0 依 flag 拼选项字母（NeedToSeparation 加 ','）
    // --- 隐藏系统（答案/解答/解析可见性）---
    int  HidePara(int idx, unsigned char mask, unsigned char* out); // 0x304b70 +0x994[idx] 置位
    int  GetHiddens(unsigned char* out);               // 0x304be0 874/878 位 → out[0..]; 32B 位图整拷
    int  RemoveHiddens(unsigned char* in);             // 0x304d10 双向差量删除（撤销码 9/10/0xb）
    int  IsAnswerVisable(unsigned long compos);        // 0x304f30
    int  IsVisable(unsigned long compos);              // 0x304f60  visualstate==0 时查位图
    int  IsHidden(unsigned long compos);               // 0x304fe0  返回状态值 2
    int  IsInvisiableMode();                           // 0x305060
    int  IsInvisiable(int state);                      // 0x3050e0
    int  GetVisualState(int kind);                     // 0x3072d0  kind9/10/0xb 的 6 位状态
    int  GetHiddenState();                             // 0x3073a0  状态≠0 → 0x200/0x400/0x800
    int  get_hide_index(int kind, int nib);            // 0x32a450  nib3→kind+8；nib4→kind+0x10
    int  GetHiddenIndex(unsigned long compos);         // 0x32a480  get_hide_index(compos>>28, (compos>>0x15)&7)
    // --- 样式索引迁移（src 表 → 本表；统一 Clone→转换→Add→新 idx）---
    int ConvertFontIndex(esFontSheet* src, int idx);   // 0x5e1a0
    int ConvertParaIndex(esStyleSheet* src, int idx);  // 0x305220 总驱动（含 6 子索引）
    int ConvertTabIndex(esStyleSheet* src, int idx);   // 0x305390
    int ConvertIndentIndex(esStyleSheet* src, int idx);// 0x3053e0
    int ConvertBulletIndex(esStyleSheet* src, int idx);// 0x305430
    int ConvertEdgeIndex(esStyleSheet* src, int idx);  // 0x3054c0  -1 直通；esEdgeStyle::Convert 双向
    int ConvertImageIndex(esStyleSheet* src, int idx); // 0x305530  src==this 直通
    int ConvertStringIndex(esStyleSheet* src, int idx);// 0x305590  同上
    int ConvertBoxIndex(esStyleSheet* src, int idx);   // 0x3055f0  同上
    int ConvertCellIndex(esStyleSheet* src, int idx);  // 0x305650  同上
    int ConvertDimeIndex(esStyleSheet* src, int idx);  // 0x3056b0  同上
    int ConvertDropcapIndex(esStyleSheet* src, int idx);// 0x305710
    int ConvertBlockIndex(esStyleSheet* src, int idx); // 0x305780
    int ConvertColorSchemeIndex(esStyleSheet*, int);   // 0x3057f0
    // --- 段落模型生成（★全部复用 +0x9C0 同一实例，返回值随时被覆盖 Q1）---
    esParaModel* ToModel(esParaLine* line);            // 0x307d40  CopyStylesFrom(+0x9C0, line)
    esParaModel* ToModel(esParaLine* line, unsigned long compos); // 0x307df0 【compos 被忽略 Q12】
    esParaModel* GetBulletModel(unsigned long compos, esParaLine* line); // 0x307ea0 模板链 CheckBullet
    int   FindSimilaHead(esParaModel*);                // 0x308100  bullet 字 0x7f + CheckParaType==2
    esParaModel* GetLevelModel(int level, int style, unsigned long compos, int fontIdx); // 0x3081e0
    esParaModel* GetModel(unsigned long compos, int style, esParaLine* line, int flags); // 0x3083c0 flags&1 跳 FindModel
    esParaModel* GetModel(void* esPara, int flags);    // 0x308430  未中 → MakeDefaultModel；flags==0 → SetFlags(6)
    esParaModel* GetModel(void* tmplList, void* para, int flags); // 0x3084f0 tmplList=NULL→用 +0x940
    esParaModel* FindModel(unsigned long compos, int style, int a, int b); // 0x308630 命中返回 +0x9C0 否则 0
    int   MakeDefault(esParaLine* line, int table);    // 0x309710  表格(0x380)分支 or 新建 font/para/indent
    esParaModel* MakeSimilarModel(unsigned long compos, int style, esParaModel* base); // 0x309a70 产 +0x9C0
    esParaModel* MakeDefaultModel(unsigned long compos, int style); // 0x30a270 字号按 compos>>28 选表 Q4
    void  MakeDefaultIndent(esParaLine*, unsigned long compos); // 0x30a5e0 魔数 -200/-150/-100/-20，每级 -150
    int   GetParaName(unsigned long compos);           // 0x30a940  kind→AppString id 表（0x9b0..）
    int   MakeDefaultHead(unsigned long compos, int font);  // 0x30aac0
    int   MakeDefaultBullet(int kind, unsigned long compos, int font); // 0x30ab10 符号字码表 Q5
    int   EnumDefaultParaModels(int cb);               // 0x3090c0  正文 kind 0..5 + 考试头 1..3
    int   LoadAsDefaultParaTemples();                  // 0x309630  清 +0x940 后枚举默认
    // --- 自动题头（AutoHead；undo 码）---
    int  FindAutoHeader(int id);                       // 0x307860
    int  RemoveAutoHeader(int id, int val, int undo);  // 0x3078c0  undo 0x402
    int  SetAutoHead(int id, int val, int undo);       // 0x3079a0  undo 0x401
    int  UndataForAutoHead(int id, void* data);        // 0x307ae0  undo 0x403（反做并返回类码）
    int  EnumAuotHeader(int cb);                       // 0x307c30
    int  GetAutoHeader(unsigned long compos, int mode);// 0x307ce0  需 +0x854 bit0 且 mode≠0
    int  GetAutoHead(unsigned long compos);            // 0x32a3b0  esAutoHeadList::Get(+0x958, feature)
    // --- 序列化管线（格式见 spec §4.1/§4.2）---
    int  BeginSerilize(unsigned long mode, unsigned long version); // 0x305e30 CloneMode→0 拒绝
    void EndSerilize();                                // 0x305eb0 +0x856 bit0 → TackExamIndexs（Q3）；复位状态
    void CreateBuffers();                              // 0x305f30 19 子表 esUseInfo 建缓冲
    void ClearBuffers();                               // 0x306070
    unsigned long SetStoreSFlags(unsigned long mask);  // 0x306180 按 GetCollectCount 汇总 → StoreFlags
    unsigned long SetLoadingSFlags(unsigned long flags);// 0x3065c0 版本门控掩码 &0x33103fff 等
    void Serialize(zArchive& arch, unsigned long flags);            // 0x306650 【双写 SFlags 校验 Q8；image 双版本门 Q9】
    void SerializeDocumentStyle(zArchive& arch, int sel);           // 0x306e50 考试样式 + +0x990/+0x992
    int  CollectDocStyles(unsigned long mask);         // 0x307410  0x20000000/0x40000000/0x80000000/0x10000000
    int  SupplementCollectStyles();                    // 0x307490 遍历 7 张表标 esUseInfo
    // --- 文件存取 / 默认样式 / 考试模板 ---
    int  SaveParaStylesToFile(char const* path);       // 0x305870 头 "EduerParaSyles"（原文拼写）→ Serialize(0xa000ffff)
    int  LoadParaStylesFromFile(char const* path);     // 0x305a60 校验头 → Serialize(0xa000ffff)
    int  SaveAsDefaultExamStyles(esStyleSheet*);       // 0x308720  → esGlobalSheet::SaveAsFile
    static esStyleSheet* GetGlobalSheet();             // 0x308760  全局单例 DAT_106c48ac
    static esStyleSheet* GetGlobalStyleSheet();        // 0x308770
    static esColorScheme* GetDefaultColorScheme();     // 0x308790  线程守卫；色表[0] 或静态默认
    void InitGlobalSheet();                            // 0x308860
    void SaveDefaultStyles();                          // 0x308870
    int  LearnBullet(esBulletStyle* src, esBulletStyle* dst, int flags); // 0x308880 编号风格学习
    int  SetAsExamUITemplates(int docId, int paraIdx); // 0x3089c0 建【题目】/【答案】/【解析】；+0x854|=1 Q3
    int  SetDefColorSchemeTo(esMstPageSheet*);         // 0x309290 全局色表逐项 Clone 注册母版页
    int  LoadDefault(unsigned long mask);              // 0x309380 mask 1/2/4/8 → 从全局 sheet 载入
    int  LoadForm(esStyleSheet* src, unsigned long mask);// 0x3093b0 载入角色后 +0x91E bit0
};

// ============================================================
// esBrushInfo — 填充笔刷参数（0x158B）[ev:pseudo Clear/Clone/CopyTo 全字段]
class esBrushInfo {
    /* +0x00 */ unsigned long    m_flags;      // Clear 置 0x00008000/0x00800000；FillRect 暂改 bit5-7
    /* +0x04 */ unsigned long    m_reserved;
    /* +0x08 */ unsigned char    m_type;       // BrushType
    /* +0x0C */ unsigned long    m_color;      // 纯色（α 编码怪癖 Q6）
    /* +0x10 */ unsigned long    m_pat1;       // 图案/渐变参数字
    /* +0x14 */ unsigned long    m_pat2;
    /* +0x18 */ float            m_angle;      // 渐变角度
    /* +0x1C */ float            m_focus;      // 聚光焦点
    /* +0x20 */ unsigned char    m_data1[0x58];// 渐变/图案数组 1（0x16 dword）
    /* +0x78 */ unsigned char    m_data2[0x58];// 数组 2
    /* +0xD0 */ float            m_d0;         // Clear 置常量
    /* +0xD4 */ unsigned long    m_d4;
    /* +0xD8 */ unsigned long    m_d8;
    /* +0xDC */ unsigned long    m_dc;
    /* +0xE0 */ unsigned char    m_data3[0x58];// 数组 3（聚光双色）
    /* +0x138 */ unsigned long   m_d138;       // 聚光=2
    /* +0x13C */ unsigned char   m_sub;        // 0x14 分支子标志
    /* +0x13D */ unsigned char   m_alpha;      // 整体 α（默认 0xFF）
    /* +0x140 */ unsigned long   m_maskOk;     // 可用掩码（bit24 哨兵 Q7）
    /* +0x144 */ unsigned long   m_maskNo;     // 禁用掩码
    /* +0x148 */ unsigned long   m_maskChg;    // 变更掩码（OnChange 置位；ResetFlags 强制 |=1）
    /* +0x14C */ esImage*        m_image1;     // AddRef/Release
    /* +0x150 */ esImage*        m_image2;
    /* +0x154 */ unsigned short  m_imgIdx1;    // esImageSheet 索引缓存（0xFFFF=未缓存）
    /* +0x156 */ unsigned short  m_imgIdx2;
public:
    esBrushInfo();                                     // 0xe1d90  清空
    esBrushInfo(esImage* img);                         // 0xe1dd0  type 0x16 + α=0xFF + SetImage1
    esBrushInfo(unsigned long color);                  // 0xe1e40  type 1
    ~esBrushInfo();                                    // 0xe1ea0  释放图 1/2
    static unsigned long GetTypeFlags(int code);       // 0xe1f30  类型→掩码表
    void NormalMasks(int on);                          // 0xe1ff0  +0x140/0x148 = 旧&0x1000000 | 掩码
    void ResetFlags(int on);                           // 0xe2090  +0x148 &= 掩码|0x1000000 后 |=1
    void SetAsSolidBrush(unsigned long color);         // 0xe2140  color==0→type0；否则 type1（α|0xff00 Q6）
    void SetAsSolidBrushEx(unsigned long color);       // 0xe21e0  α 取 color>>8 或 >>24
    void Clear();                                      // 0xe2280  释放两图；+0x154/6=0xFFFF；flags 置位
    void InitCreate();                                 // 0xe2420  仅 +0x154/6=0xFFFF
    esBrushInfo* Clone();                              // 0xe2450  全字段拷贝 + 图 AddRef；索引缓存复位
    esBrushInfo& operator=(esBrushInfo const&);        // 0xe2680
    int operator==(esBrushInfo const&) const;          // 0xe26e0
    int operator!=(esBrushInfo const&) const;          // 0xe26a0
    int IsEqual(esBrushInfo*);                         // 0xe2700  type/α 必等 + 各类型专属比较
    int CopyTo(esBrushInfo* dst);                      // 0xe2970  全字段 + SetImage1/2
    int InitAsSpotlight(unsigned long color, esColorScheme*, int f1, int f2); // 0xe2af0 type 0x13；HSV±25%
    int SetImage1(esImage*);                           // 0xe2d90  缓存失效
    int SetImage2(esImage*);                           // 0xe2e40
    int FillRectEx(void* gdc, void* rect, esColorScheme*); // 0xe2ef0 ★栈上建整个 esStyleSheet(0x9c8) Q10
    int FillRect(void* gdc, void* rect, int alpha, esColorScheme*); // 0xe3320 暂存 α→FillRectEx→恢复
    int GetImageIndex1();                              // 0xe33a0  懒查 esImageSheet(+0x774) 并缓存
    int GetImageIndex2();                              // 0xe3410
    int IsEqualImage1(esImage*);                       // 0xe3480  指针同 || esImage::IsEqual
    int IsEqualImage2(esImage*);                       // 0xe34d0
    void Save(char const* path);                       // 0xe3520  AppData 路径；Serialize(1)
    void Load(char const* path);                       // 0xe36c0  Serialize(0)
    void Serialize(zArchive& arch);                    // 0xe38d0 【byte 版本≥0x81 + 字段 + 内嵌图，spec §4.3】
    int  IsType(int code);                             // 0x431ef0
    int  IsUsable(unsigned long mask);                 // 0x431f30  (0x140&mask)!=0 && (0x144&mask)==0
    int  OnChange(unsigned long mask);                 // 0x431f70  0x140|=; 0x148|=; 0x144&=~
    esImage* GetImage1();                              // 0x431fc0
    esImage* GetImage2();                              // 0x431fe0
};

// 刷子类型码（+0x08）与 NormalMasks 掩码表 [ev:pseudo GetTypeFlags 0xe1f30]
enum class BrushType : unsigned char {
    None     = 0x00,   // 掩码 0
    Solid    = 0x01,   // 0x3
    Pattern  = 0x02,   // 0x400d
    Gradient = 0x13,   // 0x7a341（聚光同码）
    Image2   = 0x14,   // 0x401d（二级图像）
    TwoImage = 0x15,   // 0xf82881（图 2 + 浮点参数）
    OneImage = 0x16,   // 0xf82401
};
constexpr unsigned long BRUSH_MASK_SENTINEL = 0x1000000;  // bit24「掩码体系已启用」哨兵 Q7

// ============================================================
// esPenInfo — 描边参数（0x0C；esSeg::Draw 之笔）[ev:pseudo Reset/CreatePen]
//   单位 1/400mm：Reset 宽=0x50(80)=0.2mm；ee-draw pen_mm 0.25 → 100。
class esPenInfo {
    /* +0x00 */ unsigned long m_color;   // 默认 0xff01 亮绿；CreatePen → MakeSolidColor(color,0xff)
    /* +0x04 */ unsigned long m_style;   // 低8位=虚线型；bit8-11=起端帽；bit12-15=末端帽；bit16=自动线宽
    /* +0x08 */ int           m_width;   // 线宽（1/400mm）
public:
    esPenInfo();                                       // 0x3da3f0
    esPenInfo(esPenInfo const&);                       // 0x18c0 【ILT 折叠：≡ operator= ≡ esImageModifiers::operator=(&&)】
    int  IsVisible();                                  // 0x270e0  color!=0 && width>=1
    int  get_pen_width(int idx);                       // 0x3da3c0  16 项表 <<2；越界→1
    void Reset();                                      // 0x3da410  色=0xff01、样式=0、宽=0x50
    void CopyTo(esPenInfo* dst);                       // 0x3da440
    void Serialize(zArchive& arch);                    // 0x3da470  三 dword 直写（spec §4.4）
    int  GetDashCap();                                 // 0x3da4f0  起末帽相同才给（0x100→0/0x200→2/0x300→3）
    int  GetStarCap();                                 // 0x3da570
    int  GetEndCap();                                  // 0x3da5f0
    void* CreatePen(void* render, int noStar, int noEnd); // 0x3da670 【modelbox→调试绿 0xff007f00 Q11】
    void* CreateSolidPen(void* render);                // 0x3da880  观察模式宽度=0
};
constexpr unsigned long PEN_DEFAULT_COLOR = 0xff01;
constexpr unsigned long PEN_DEBUG_GREEN   = 0xff007f00;
constexpr int           PEN_DEFAULT_WIDTH = 0x50;   // 80 = 0.2mm

} // namespace eslib
