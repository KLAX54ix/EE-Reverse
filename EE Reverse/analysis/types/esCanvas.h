// analysis/types/esCanvas.h
// 画布对象族（esEmbedder / esCanvas）— 阶段 2 第十一批（eslib.dll · 嵌入画布 3.6a）
//
// 证据：
//   [ev:pseudo] analysis/pseudo/eslib/esCanvas.decomp.txt   (269/269 函数原样伪代码)
//   [ev:spec]   analysis/pseudo/eslib/esCanvas.md           (§0 布局总表 / §7.2 绘制 / §7.3 变换·剪贴板 / §8 撤销码 / Q-canvas-*)
//   [ev:ledger] ledger/ledger.csv  eslib:<rva>（269 行 → status=decompiled）
//
// 谱系与关键结构（本批定界）：
//   esEmbedder : esCharEx（类型字 +4=0x40；尺寸 0x44）—— 内嵌字符对象（画布的文本行身份）
//     +0x1a 字体槽 · +0x1c/+0x20 上/下留白 · +0x30 总宽 · +0x38 canvas 反引 ·
//     +0x3c 垂直对齐模式 · +0x40 内边距量 · +0x14 (SerializeForRevive)
//   esCanvas : esContainer（类型字 +4=0x2010；尺寸 0xe0）—— 插图画布
//     +0x34/+0x38 图形链首尾（节点 +0x44 next）· +0x40 host · +0x44 背景色 ·
//     +0x48 role · +0x4c flags · +0x50/+0x54 画布链 · +0x58/+0x5c 原点 ·
//     +0x60 esMatrixObj（Matrix @+0x64）· +0xa0 es3DSpace · +0xa4 active ·
//     +0xa8 内容实心矩形 · +0xb8..+0xc4 边距 LTRB · +0xc8 外框 ·
//     +0xd8 状态字 · +0xda/+0xdc 自定义边框点
//   宿主协议：canvas+0x40 ↔ esEmbedder+0x38 / esCvsAnchor+0x24（双向）；画布由 esCanvasList(0x2011) 持链
//   flags(+0x4c)：bit0-2 布局（内嵌/环绕）· bit3 followed · bit8-9 水平对齐 · bit12-13 边框型 ·
//     bit14 动态模式 · bit20 允许默认动画（详见 esCanvas.md §0 位表）
//   撤销码：esCanvas.md §8（0x202..0x216 · 0x511f · 0x523 · 0xf005/0xf006）
//
// 说明：本头文件只列声明 + RVA 锚点 + 一句话规格；逐步行为规格（证据/副作用/陷阱）
//       以 esCanvas.md 为准。RVA = entry − 0x10000000（与 dump `entry=` 一一对应，机检 269/269）。
//       virtual 标注依 dump 签名；重载归属未逐一核对，以 esCanvas.md 为准。
#pragma once

namespace eslib {

// 跨批引用（本批不 dump；见各自头文件）
class esObject;
class esContainer;
class esCharEx;
class esUndo;
class esStyleSheet;
class esStyleExchanger;
class esRole;
class esRender;
class esHitTest;
class esSnapManager;
class esSnapObj;
class esMessage;
class esPropManager;
class esShapeBase;
class esShapePath;
class esShapeGroup;
class esShapeHolder;
class esShapeList;
class esShapeControl;
class esCanvasList;
class esCvsAnchor;
class esAcmeList;
class esSelState;
class esMatrixObj;
class es3DSpace;
class esRefLine;
class esGraphWorker;
class esGraphObject;
class esSeg;
class esSegList;
class esSegLinkLine;
class esCalligraph;
class esCtrlPoint;
class esPainter;
class elfPage;
class elfSubject;
class egGraphics;
class GDC;
class esEquBox;
class esSegImage;
class esFont;
class esFontSheet;
class esDrawInfo;
class esExamMD5s;
class esAreaBoder;
class esEdgeStyle;
class esColorScheme;
class esJunctor;
class esDrawingModifier;
class esPara;
class esMoldPath;
class esPenInfo;
class esBrush;
class esRgn;
class esBrushInfo;
class esTextBox;
struct tag_DRAWPARAM;
struct tagPOINT;
struct tagRECT;
struct zArchive;
struct zArray;

class esEmbedder;
class esCanvas;


// ============================================================
// esEmbedder（24 个） [ev:pseudo analysis/pseudo/eslib/esCanvas.decomp.txt]
// ============================================================
class esEmbedder : public esCharEx {
public:
    wchar_t GetSearchChar(wchar_t param_1);                       // 0x8370  恒返回 L'\x0e'（14）——"查找/替换"把整块画布当单一字符
    esEmbedder(esEmbedder* param_1);                              // 0x8390  esCharEx 拷贝 + +0x38(canvas) / +0x3c / +0x40 三字段
    esEmbedder& operator=(esEmbedder const&);                     // 0x83e0  同上（esCharEx::operator= + 三字段）
    wchar_t * ID(void);                                           // 0xa7710  L"esEmbedder"
    virtual int isKindOf(wchar_t* param_1);                       // 0xa7720  名匹配→1，否则 esCharEx::isKindOf
    virtual int isOf(wchar_t* param_1);                           // 0xa77d0  同上（isOf 语义）
    esEmbedder();                                                 // 0xa7860  esCharEx() + +4=0x40 + +0x38/+0x3c/+0x40=0
    esEmbedder(esCanvas* param_1);                                // 0xa78b0  同上 + +0x38=c；**c+0x40=this**（绑定回写）
    ~esEmbedder();                                                // 0xa7910  解绑：若有 canvas → c+0x40=0、c vtbl+0x5c(0,0)；~esCharEx
    void GetMd5ForExam(esExamMD5s* param_1);                      // 0xa7990  canvas 存在 → 内容/名字串交 esSelector 形成选择串 → FUN_1007c110 记 MD5（考题比对）
    void CreateItem(ulong param_1, esFontSheet* param_2);         // 0xa7a20  重绑 c+0x40=this；+0x1a = esFontSheet::GetCurFontIndex(fontSheet,0)（字体槽烘入，见 AGENTS 字体槽陷阱）
    virtual void CollectStyles(esStyleSheet* param_1, ushort param_2);  // 0xa7cc0  esCharEx::CollectStyles + canvas vtbl+0x10(sheet)
    esCanvas * CheckCanvasPosition(int param_1, int param_2);     // 0xa7d00  取本条字符内坐标（vtbl+0xc4）→ 与外框 +0xc8 原点求差 → 非零则 esCanvas::Offset 对齐；返回 canvas
    virtual void Load(elfPage* param_1, elfSubject* param_2, int param_3, int param_4, int param_5, float param_6);  // 0xa7db0  CheckCanvasPosition + canvas Load(page, subj)
    virtual void Draw(esRender* param_1, esDrawInfo* param_2, int param_3, int param_4, int param_5, float param_6);  // 0xa7df0  CheckCanvasPosition；esRender::IsShow(render, 0x80000000) → canvas Draw(render, show)
    void ResetObjSize(GDC* param_1, esFontSheet* param_2, int param_3, float param_4);  // 0xa7e40  尺寸核心：+0x40 = 字高 × DAT_1057ef78；+0x30 = 宽 + 2×+0x40；按 +0x3c 模式（0 默认 / <0 显式下基 / 1 上基 / 2 居中 / 3 顶 / 4 底）用画布轮廓高分配 +0x1c(顶)/+0x20(底) 留白；inline 与非 inline 分支
    void Undo(ushort param_1, zArchive* param_2, zArchive* param_3);  // 0xa8060  码 **0x202** ↔ +0x3c 经 zArchive 对换；else esCharEx::Undo
    int IsClickable(esStyleSheet* param_1);                       // 0xa80d0  amulet esSnapObj::Is(4) → 1（画布可点判定）
    virtual int OnMessage(esMessage* param_1, ulong param_2);     // 0xa8120  canvas vtbl+0x48；处理过 → 自身 vtbl+0x44(0)；末 esObject::OnMessage
    void * Undata(ushort* param_1, void* param_2, int* param_3);  // 0xa8180  直通 esObject::Undata
    virtual int IsEqual(esObject* param_1, esStyleSheet* param_2);  // 0xa81b0  esCharEx::IsEqual + canvas（+0x38 同 / 都空 / vtbl+0x4c）
    void SerializeForRevive(zArchive* param_1);                   // 0xa8240  存"跨档复活"引用：canvas 对象 id（或 0）+ 解引用；读回按 id 从 esStyleList（m_pUndo+8 ↓ +0x794）取回重绑；另存/读 +0x3c、+0x14
    virtual void Serialize(zArchive* param_1, esStyleSheet* param_2, ushort param_3);  // 0xa8330  主档：canvas 有无以标记字识别（读回 operator_new(0xe0) 建画布再反序列化绑定）；主表存在时 AddCanvas + 新画布按相对对象序入链；+0x3c、+0x14 双写
    virtual void CopyFrom(esObject* param_1, esStyleExchanger* param_2);  // 0xa8640  +0x3c 对齐；新建 canvas（0xe0）→ AddCanvas → canvas vtbl+0x24(srcCanvas, exchanger)（内容克隆）
};


// ============================================================
// esCanvas（245 个） [ev:pseudo analysis/pseudo/eslib/esCanvas.decomp.txt]
// ============================================================
class esCanvas : public esContainer {
public:
    int IsEmpty();                                                // 0x4550  +0x34==0（无图形）
    int page();                                                   // 0x13370  +0x3c ushort（**页码**，撤销码 0x208 同字段）
    Matrix * matrix();                                            // 0x13390  返回 (Matrix*)(this+0x64)（esMatrixObj 内嵌矩阵）
    int IsDynamicMode();                                          // 0x133c0  flags & 0x4000
    int IsLocked();                                               // 0x133f0  +0xd8 & 1
    void Lock();                                                  // 0x13420  +0xd8 |= 1（加锁）
    void Unlock();                                                // 0x13450  +0xd8 &= ~1（解锁）
    void SetState(ushort param_1);                                // 0x13480  +0xd8 |= m
    void RemoveState(ushort param_1);                             // 0x134b0  +0xd8 &= ~m
    ushort CheckState(ushort param_1);                            // 0x134e0  返回 +0xd8 & m（非零即含 m 段）
    esCvsAnchor * GetAnchor();                                    // 0x13500  +0x40 且 vtbl+8(ID) 判为 esCvsAnchor → 返回，否则 0
    esEmbedder * GetEmbedder();                                   // 0x13550  同上判 esEmbedder
    int IsAllowDefAnimat();                                       // 0x135a0  flags & 0x100000
    int IsInline();                                               // 0x135d0  flags & 7 == 0
    int IsWrapped();                                              // 0x13600  flags & 7 != 0
    int IsFollowed();                                             // 0x13630  flags & 8
    int IsHostedBox();                                            // 0x13660  +0x40 != 0
    int IsFloatBox();                                             // 0x13690  +0x54!=0 && +0x40==0 && +8!=0 && (+8)为类型 0x2011
    ulong GetExamMark();                                          // 0x136e0  flags & 0x30000
    ulong GetFrameType();                                         // 0x13700  flags & 0x3000
    ulong GetWrapMode();                                          // 0x13720  flags & 7
    int IsFixed();                                                // 0x13740  +8!=0 && +0x54==0
    int IsFixed(ushort param_1);                                  // 0x13780  +0x54==0 && +8!=0 && (+8)为指定类型
    ulong GetAlign();                                             // 0x137d0  flags & 0x300
    int GetWidth();                                               // 0x137f0  外框 +0xc8 矩形宽 / 高
    int GetHeight();                                              // 0x13810  外框 +0xc8 矩形宽 / 高
    es3DSpace * Get3DSpace();                                     // 0x13830  +0xa0
    esShapeList * GetShapeList();                                 // 0x13850  全局 m_shape_list 重置后返回（esShapeList::Reset(list,this)）
    esCanvas& operator=(esCanvas const&);                         // 0x13870  esContainer::operator= + +0x3c..+0xdc 全段拷贝（含 esMatrixObj/esRefLine 子对象赋值）
    esShapeBase * GetActive();                                    // 0x158e60  返回 +0xa4
    virtual wchar_t * className();                                // 0x1b2a60  直返 esContainer::ID()（= L"esContainer"）——画布对外类名走容器基名
    wchar_t * ID(void);                                           // 0x1c3670  L"esCanvas"（静态）
    virtual int isKindOf(wchar_t* param_1);                       // 0x1c3680  名 == ID() → 1；否则转 esContainer::isKindOf
    virtual int isOf(wchar_t* param_1);                           // 0x1c3720  仅与 ID() 比较（不上溯父类）
    esCanvas();                                                   // 0x1c37b0  默认构造：esContainer + 子对象 esMatrixObj(@+0x60) / esRefLine(@+0x70)；类型字 0x2010
    esCanvas(esCanvas* param_1);                                  // 0x1c3890  拷贝构造（524B）：基类拷贝 + 全字段 + 子对象拷贝
    esCanvas(int param_1, int param_2);                           // 0x1c3aa0  默认构造 + SetAsBorderRect(0,0,w,h)（→ 边框 0x1000）
    ~esCanvas();                                                  // 0x1c3bb0  析构（285B）：反绑宿主 → 子对象/边框点回收（细节复核后补）
    void TransferFrom(esShapeGroup* param_1);                     // 0x1c3cd0  整段搬迁：组 +0x5c 首/+0x60 尾链 → 本画布链尾；节点 +0x44 为链 next
    void SetAsBorderRect(int param_1, int param_2, int param_3, int param_4);  // 0x1c3d60  写外框 +0xc8；边框类型置 0x1000
    void Initialize();                                            // 0x1c3dc0  字段初始化（边距/状态/链清空；细节复核后补）
    void OnAllowDefAnimat();                                      // 0x1c3eb0  切换 flags 0x100000 + 撤销码 0x20e
    void SetAsDefaultEmbeddedStyle();                             // 0x1c3f20  内嵌默认样式：四边距全 400
    void OnEdit(int param_1, int param_2);                        // 0x1c3f70  编辑期快照：静态 DAT_106cd038(flags)/DAT_106cd248(矩形)；退出对比 &0x30f+矩形 → 按宿主类型记 Rec_Data（未改动不记）
    int Delete3DSpace();                                          // 0x1c41f0  释放 +0xa0（es3DSpace）置 0
    int Create3DSpace();                                          // 0x1c4260  懒建 es3DSpace（operator_new(2000)）→ +0xa0
    int CreateChildLable(zPoint param_1, int param_2, int param_3);  // 0x1c4320  在 pt 建子标签图形挂链尾
    void OnActive_(int param_1);                                  // 0x1c43a0  激活态切换（高亮/控制点注册）
    void OnSetTextUI(esObject* param_1);                          // 0x1c4430  TextUI 变更 → +0xd8 |= 4（TextUI dirty）
    void SetModifiesForHost();                                    // 0x1c44b0  通知宿主已修改：清 +0xd8 宿主待通知位（bit3=8）
    void SetModifiedFlags(int param_1);                           // 0x1c4540  +0xc=1；按 m 置 +0xd8 交互/通知位
    void UpdateAnchorPostion(esStyleSheet* param_1);              // 0x1c4590  同步锚点（esCvsAnchor）位置
    void AddItem(esShapeBase* param_1, int param_2);              // 0x1c45d0  **mode==0 头插 / !=0 尾插**；ResetLineWidth(item,this)；item 已选中（item+0x3c）→ SetSelObj，且无活动图形时 SetActive
    virtual void Insert(esObject* param_1, esObject* param_2, int param_3);  // 0x1c46a0  **mode==0**：无 ref 尾插、有 ref 插到 ref 前；**!=0**：无 ref 头插、有 ref 插到 ref 后（与 AddItem 次序相反，见 Q-canvas-4）
    int GetCustomBorderPtCount();                                 // 0x1c4820  +0xda ushort
    void GetOutlineInfo(esAreaBoder* param_1);                    // 0x1c4850  导出轮廓到 esAreaBoder：有点 → 点集路径；无点 → 边距/外框路径
    esSegImage * IsImageFigure();                                 // 0x1c48b0  遍历图形链找图像段（esSegImage）并返回（图像直通判定）
    esCanvas * GetNextBox(int param_1);                           // 0x1c49a0  画布链漫游：dir==0 用 +0x50(next)（尾节点回环取列表首的 next，语义照实见 Q-canvas-3）；dir!=0 用 +0x54(prev)，prev==列表首时回环取 +0x3c(尾)；结果==自身 → 0
    int ShrinkageMargin(int param_1);                             // 0x1c4a70  按内容包围与外壳计算可收缩边距量
    void SetOutlineInfo(esAreaBoder* param_1);                    // 0x1c4c30  逆操作（1761B）：**边框类型由点模式决定** —— 模式 0x2000 → 自定义点（记点数、分配 +0xdc 数组）；否则按边距写入（**存储 = 引擎值/4**，含 <400 时的默认/清零特判）；local_c 模式值 <<12 写入 flags；末 SetModifiedFlags + InvalidateState
    void SetMargin(int param_1, int param_2, int param_3, int param_4);  // 0x1c5320  直写 +0xb8/+0xbc/+0xc0/+0xc4
    void SetMargin(zRect* param_1);                               // 0x1c5350  从矩形（L/T/R/B 序）写四边距
    void ResetCanvasBoder();                                      // 0x1c5390  边距归零 + 边框类型清除
    int AdjustEdeg(int param_1, zPoint param_2);                  // 0x1c54a0  矩形边框（须 0x1000）边距调节：**cm<0 = 提交** —— 当前边距与静态快照 DAT_106cd028.. 比对，差异边记撤销（0x204 L / 0x205 T / 0x206 R / 0x207 B，旧值）；m_pUndo==0 时只存快照返回 1。**cm>=0 = 拖动** —— 取 GetFrameRect 按 cm 改一边为 pt（x：0/2/4 左边、1/3/6 右边；y：0/1/5 上、2/3/7 下），重算边距（含"快照 L&R 均为 0 → 双侧同动"特判）→ vtbl+0x44(0) 重排
    void SetBorder(zPoint param_1, int param_2);                  // 0x1c57c0  **仅 frame==0（无边框）时**生效：以内容盒（solid 外扩 400、去原点平移）为基准按 cm 求该边距（左 0/2/4、右 1/3/6、上 0/1/5、下 2/3/7；clamp ≥0），变更边记撤销；末尾 eaAct 活动态变化 → vtbl+0x44(0)
    tagPOINT * GetOutlinePoints(int* param_1, int param_2, int param_3);  // 0x1c5a10  输出**绝对**轮廓点（调用方 free）：非自定义 → GetOutlineRect 平移 (dx,dy) 输出 4 角（分配 5 点，末点闭合）；自定义 → +0xda 点数，每点 = +0xdc[i] **+ 内容实心中心** + (dx,dy)，末点闭合
    void DrawSelState(esRender* param_1, int param_2);            // 0x1c5bc0  mode==0：边框 0x2000 且有点 → GetOutlinePoints 构 egPath → esRender::FillSelPath；否则 FillSelRect(GetOutlineRect)。mode!=0 → FillSelRect(实心矩形)
    void RestoreSelInfo(void* param_1, int param_2);              // 0x1c5d30  恢复选择态（589B）：清 +0xa4；blob 头 ushort=位图**字数**，按图形序号逐位回写 +0x3c；其后的 zArchive 流 ReadInt32=活动对象 ID → esUndo::GetAt(m_pUndo,id) + vtbl+8(esShapeBase::ID()) 校验后写 +0xa4；有活动 → InvalidateState+State+esAcmeList::Serialize 续读辅助列表；收尾仍无活动 → 全链 +0x3c=0+Invalidate
    void * GetSelInfo(int* param_1);                              // 0x1c5f80  序列化选择态（711B）：仅 IsFocused() && +0xa4 且选中数>0 才产出；位图按**全链序号**置位（字数=ceil(总数/16)）→ zArchive：WriteWord 字数、位图、活动 GetID、acme 列表（空则 WriteWord 0）→ detach 缓冲返回，长度出参
    void GetGrapColors(zArray<unsigned_long>* param_1, ulong param_2);  // 0x1c6250  沿图形链调 vtbl+0x9c(arr,mask)，取首个非零即返回
    void FillBackround(esRender* param_1);                        // 0x1c62a0  背景填充：+0x44(色) 与 +0x40(宿主) 皆非空；刷=MakeBrushColor(render,+0x44,0xff)；GetGraphics(render,0) 填 +0xa8 内容矩形
    int SaveAsMetafile(wchar_t* param_1, int param_2, HDC__* param_3, esStyleSheet* param_4);  // 0x1c63a0  转存图元文件（904B）：GetOutputRect → 无活动且边框 0x1000 再 Deflate 400 / 否则 Inflate 200 → GetDeviceCaps(0x58/0x5a)→epCalcScaleXY(100)→FUN_10052f50(0,0,w,h)；type<3 → GDI+ Metafile(emfType=5/4/3) → DrawToMetafile；type>=3 → SaveDC → FUN_10199210(hdc,…) → DrawToMetafile → GetHENHMETAFILE → RestoreDC → EmfToWmf → CopyMetaFileW(path)
    HENHMETAFILE__ * CreateEnhMetafile_FormCurSel(HDC__* param_1, esStyleSheet* param_2, EmfType param_3);  // 0x1c6730  用当前选择建增强图元：GetOutputRect；无活动 → 标记 1；有活动 → 外扩 200；转 CreateEnhMetafile
    HENHMETAFILE__ * CreateEnhMetafile(HDC__* param_1, tagRECT* param_2, esStyleSheet* param_3, EmfType param_4, int param_5);  // 0x1c67e0  SaveDC → GetDeviceCaps → epCalcScaleXY(100) → FUN_10052f50 → FUN_10199210(hdc,…7,type) → DrawToMetafile → 取 HENHMETAFILE → RestoreDC
    void DrawToMetafile(Metafile* param_1, tagRECT* param_2, float param_3, float param_4, esStyleSheet* param_5, int param_6);  // 0x1c69a0  图元文件上作画（671B）：新 egGraphics(0x3c) 挂 metafile 图像；flag && +0x44 → 背景色清屏；Save→Translate(−left,−top)→esPageRender→**逐链（flag‖+0x3c 且类型 &0xf000!=0x7000）vtbl+0x74**→Restore
    int GetOutputRect(tagRECT* param_1);                          // 0x1c6c50  输出矩形（376B）：无活动 → 内容 +0xa8（**无边框 Inflate 200 / 有边框 Deflate 200**）；有活动 → 选中（跳 0x7000）solid 并集，全空→0；宽或高 < **101** → 0
    void CreateDotmap(esStyleSheet* param_1);                     // 0x1c6dd0  点阵化（1486B）：GetOutputRect（需 w,h>799）→ Inflate 800 → /100 → 建位图 → 白底+SetSmoothingMode(1)+esPageRender → 逐**选中**（跳 0x7000）vtbl+0x74 → 逐像素（步长 4B）：亮度加权 (r×0x1e+g×0x3b+b×0xb)×a/0x639c < 200 → 建**点对象 esShapeLine(pt,0x6001,0)**（笔 0xffcccccc、宽 0x96）尾插+SetUnAddInfo、+0x3c=0
    Bitmap * CreateBitmap(esStyleSheet* param_1, int param_2, tagRECT* param_3, int param_4, int param_5);  // 0x1c73c0  位图渲染：GetOutputRect → 活动有无定全选标记 → 四边 Inflate(param_3) → epCalcScaleXY(0,0,param_2,param_2,100) → 建位图（format 0x22009/0x26200a）→ 背景：+0x44 有 alpha 直清、否则 0xff02（param_4 时先褪白 0xffffff）→ Translate → param_5==0 时 SetInterpolationMode(5) → esPageRender → 逐（全选或选中，跳 0x7000）vtbl+0x74
    virtual void Load(elfPage* param_1, elfSubject* param_2);     // 0x1c7810  进页面渲染：无图形或 IsInvisiable → 返回；固定画布 → 按 role 键名 NewSubj；非固定 → solid→NewSubj、外框 Deflate 100→SetRectB(rect,矩阵)；role 表演类 → NewPerfrom；宿主+背景色 → AddRectangle；逐图形可装载者 vtbl+0xa0(page,subj)
    virtual void Draw(egGraphics* param_1, int param_2, int param_3, int param_4, int param_5, int param_6, int param_7, int param_8, int param_9, esStyleSheet* param_10, esColorScheme* param_11);  // 0x1c7a50  缩放绘制：Save；scale=param_4/param_8；param_6..9∩solid；esPageRender(gfx,sheet,scale,scale)；SetColorScheme；GetGraphics(0)→BeginDraw→Translate(param_2/scale,param_3/scale)→Draw(render,0)→EndDraw
    virtual void Draw(GDC* param_1, int param_2, int param_3, int param_4, int param_5, int param_6, int param_7, int param_8, int param_9, esStyleSheet* param_10, esColorScheme* param_11);  // 0x1c7c40  GDI 绘制（5253B）：SaveDC→SetMapMode(8)→Window/Viewport Ext·Org（param_8/param_4×10、param_2/param_6）→param_6..9∩solid→esPageRender(gdc,sheet)→BeginDraw→Draw(render,0)→EndDraw→ReleaseGraphics→RestoreDC
    void DrawDropOutline(esRender* param_1);                      // 0x1c7e30  拖放轮廓：外框→IsVisible→笔 0xff04 虚线 3；矩形框→DrawRectangle；自定义点→GetOutlinePoints→DrawLines（回闭合点）
    void DrawEditCtrlStates(esRender* param_1);                   // 0x1c7fd0  编辑态：动态模式或（活动+选择态）才画；ModifyTransfrom+GetBoundsForUpdate→LPM(4)（render+0x54&0x10 时 ×10）→Inflate→IsVisible；非 &0x10：动态→esSegBase::Build；+0x54&2→DrawCtrlServer 否则 DrawControlVertex；非动态→esAcmeList::Draw。&0x10：DrawControlVertex；活动 0x3a08→esShapeControl::DrawCtrlState
    void DrawEditRelevants(esRender* param_1);                    // 0x1c8180  编辑辅助：非固定：render+0x54&0x100→DrawDropOutline；&8→外框 IsVisible→DrawOutline(1)；否则 DrawFrame
    void DrawCtrlServer(esRender* param_1);                       // 0x1c8230  控制服务：State→SetExSelBound(render+0x78)→活动图形；acme 空→0；helper vtbl+0x34(render,state+0x1c,state+0x20,active,…)
    int IsVisibleIllustration();                                  // 0x1c8300  可见性：无宿主→0；沿 amulet 链：esSnapObj::Is(4) 命中→段 ID→IsHidden→0；tag 0x2020 且 ID=esCanvas→递归；全过→1
    int IsInvisiable();                                           // 0x1c83f0  无宿主→0；amulet 空或 vtbl+0x74(1)!=0→1；否则 0（Draw 早退判据）
    virtual void DrawForInternal(esRender* param_1, function<void(esMoldPath*, esPenInfo*, esBrush*, Gdiplus::Matrix*)> param_2);  // 0x1c8450  内部绘制（197B）：Save→ModifyTransfrom→逐链 vtbl+0xb4(render,0)→Restore
    uint InToCanvas(egGraphics* param_1);                         // 0x1c8520  Save+ModifyTransfrom，返回还原令牌（与 DrawForInternal 成对）
    virtual void Draw(esRender* param_1, int param_2);            // 0x1c8550  主绘制（5190B）：IsInvisiable→跳；无图形且无画布链后继且无宿主→跳；活动==this 且状态&2→跳；宿主且 mode→DrawOutline(0)；InToCanvas+SetDynamicMode+PushDrawPoint；render+0x54&0x70000 且活动≠this：宿主+无图形+非3D+0x1000边框→DrawAdjustbleBorder；清 render+0x54 低段（0xfff8ffff）；AuxColor 存取→DrawGraphics→还原→PopDrawPoint/Restore
    void DrawOutline(esRender* param_1, int param_2);             // 0x1c86d0  轮廓：GetOutlinePoints 闭合；mode0：非 &8→笔 0x3fff7f00（LPM）DrawPolygon；mode≠0：笔 0xff04 虚线 3 画多边形→WorldToPage→GDC：点数组空（矩形）→顶点+边中点方块，否则各点方块（尺寸 render+0x10）
    void DrawGraphics(esRender* param_1);                         // 0x1c8ac0  图形链绘制：宿主+背景色→FillBackround；3D 空间非空→（固定：3Dspace.Draw / 非固定：视口 Deflate 再 Draw）；正常→逐 vtbl+0x74；render+0x54&0x100000（灰化）→共享链：SetGrayMode(0)+整体 Draw+还原；否则逐子 SetGrayMode(选中且非活动画布?0:1)
    void DrawControlVertex(esRender* param_1);                    // 0x1c8c70  控制点（618B）：State；动态→state|=0x200；FUN_101ae3f0 起；FUN_1000e650(0x10) 分支：逐图形 vtbl+0xb0 有控制点→包围可见→vtbl+0x78(...,0x400000,state+0x18,state+0x14)；否则含图像→DrawClipBox；+0x3c 标志→ResetPos(是否活动)→vtbl+0x78(...)；FUN_101aebd0 收
    void DrawAdjustbleBorder(esRender* param_1);                  // 0x1c8ee0  可调边框把手（1181B）：宿主+无图形+非3D+活动≠this→临时改字体（+0x14=0x7f01）画资源串 0xa1c（提示字形）；GetGraphics(1)→WorldToPage→Save→ResetTransform→笔（活动==this：GetColor(0xff04)&0x2fffffff+点划；否则 &0x3fffffff+SetLineCap(1,1,0)）→四角 L 形把手+四边中点短横
    void DrawCanvasFrame(esRender* param_1);                      // 0x1c9650  画布框（1320B）：宿主非空才画；原点/矩阵零→helper 直画（FUN_100dedf0 4 路）；尺寸→角标长 CalceCornerSize；**未聚焦**：色 0xaf04/0x7f03；**聚焦**：色 0x7f3f3f3f/0x7fcccccc 画 7 点角标折线×4+边短划；**锁定**：四边中点叉标+白笔
    int CalceCornerSize(int param_1, int param_2);                // 0x1ca6a0  角标长 = min(w/4, h/4)，再与 w/10 取小
    void DrawScaleBoxFrame(esRender* param_1);                    // 0x1ca740  空闲缩放框（555B）：solid→WorldToPage；right/bottom+1；GDC Attach→SetROP2(6)→DrawRectangle→还原 ROP→Deflate(1,1)→**8 手柄**（margin=render+0x10）：四角+四边中点定位→BitBlt 0x330008 打柄
    int HitTestCanvasFrame(esHitTest* param_1, int param_2);      // 0x1ca9a0  边框命中（142B）：IsFixed→0；amulet 空或 tag **0x2012**→0；CheckMode(0x20)：非 0→HitTestGlobalBoxFrame(1)；0：amulet tag **0x2011**→HitTestEdgeFrame 否则 HitTestGlobalBoxFrame(mode)
    int HitTestGlobalBoxFrame(esHitTest* param_1, int param_2);   // 0x1caa30  整框命中（452B）：mode=CheckMode(0x20)；mode0：框 0x1000→外框矩形，param_2==0 且 HitTestEdgeFrame→1；非 0x1000：宿主+无活动+框0→0，否则 solid。mode≠0→外框。**宿主非空且 esSnapObj::Is(host,0x40)→直接 0**；Inflate(DAT_1057f408/ht+0x30)→内环内→0；再 Inflate→外环内→SetSelInfo(mode?0x1e:0x1d)→1
    void DrawFrame(esRender* param_1);                            // 0x1cac00  框绘制（206B）：非固定+amulet 非 0x2012：+0x54&0x20（拖动中）→宿主 0x40 族→不画，否则 DrawGlobalBoxFrame；否则 tag 0x2011→DrawCanvasFrame；再否则 宿主空/有活动/框非0→DrawGlobalBoxFrame，全否→DrawScaleBoxFrame
    void DrawGlobalBoxFrame(esRender* param_1);                   // 0x1cacd0  整框绘制：框 0x1000→DrawAdjustbleBorder+外框，否则 solid 矩形；+0x54&0x20 时取 amulet GetActive==this 定状态 2、用外框；色按状态掩码（0→&0x3fffffff、1→&0x7fffffff、2→原色）取 GetSchemeColor(1)；阴影刷 0x13、笔宽 DAT_1057f4b0/scale、矩形外扩 2×宽→Save→SetRenderingOrigin(0,0)→DrawRectangle→Restore；锁定且有 helper→vtbl+0x14(render,rect,state)
    int EnumParagraphs(esStyleSheet* param_1, function<int(esPara*)> param_2, ulong param_3);  // 0x1caf60  段落枚举：逐链节点：esShapeHolder→holder EnumParagraphs、esShapeGroup→group EnumParagraphs；回调返回非零即返回 1，链尽→0
    void EnumSelectedItem(function<int(esShapeBase*)> param_1);   // 0x1cb0f0  遍历图形链，对选中图形（+0x3c!=0）调回调；回调返回 0 中止
    void ToFixColor(esColorScheme* param_1);                      // 0x1cb180  颜色固化（导出/打印以外的颜色方案转换；简）
    virtual void LoadProp(esPropManager* param_1, ulong param_2);  // 0x1cb1d0  组 0x10000000 → 0x100 段：0x101 wrap / 0x102 followed / 0x103 align / 0x104→bit0x80 / 0x105→bit0x800 / 0x106 布局模式；组 0x20000000 → 0x200 段：0x201 边框类型 / 0x202 宿主 +0x3c / 0x204..0x207 边距（值/4）/ 0x212 +0x44
    void * GetOutlineUndoInfo(int* param_1);                      // 0x1cb550  打包轮廓撤销 blob：点数+点集+外框矩形+边距矩形
    void * SetOutlineUndoInfo(void* param_1, int* param_2);       // 0x1cb670  解包应用（撤销恢复）
    void ChangeFitureLayout(uint param_1, esStyleSheet* param_2);  // 0x1cb810  mode0→(wrap3,align1)；mode1→(wrap2,align3)；mode2/3→(wrap0,align0)+followed=1；mode4→边框类型 0x1000/0；按新旧 flags 决定撤销记录；prop 0x106 写回 mode
    virtual void SaveProp(esPropManager* param_1, ulong param_2);  // 0x1cbaf0  镜像 LoadProp：逐字段比较变更 → AddItem 记录 + 相应撤销码（0x204..0x207 边距回写 ×4 等）
    int CheckLayoutChange(ulong param_1, int param_2);            // 0x1cc2a0  (oldFlags&0xf)==(new&0xf) 且 wrap==0 且 mode∈{2,3} → MoveEmbeddedCanvas（插入点重定位）；wrap 内嵌↔环绕跨界 → OnQuickLayout / SetAsEmbeddFiture / SetAsAnchorFiture 宿主迁移
    void MoveEmbeddedCanvas(esStyleSheet* param_1, int param_2);  // 0x1cc470  重嵌宿主：沿 +0x40 宿主链找 esPara；GetActiveShow<2（段级）→ **跨段搬迁**：esPara::GetNextVisible/GetPrevVisible 找目标 → Rec_Data **0x511f**（3×ID：父/属性对象/段）→ detach + insert → 样式居中化（HorzAlign=2）+ nature 继承（邻段 nature∈[8,12] 沿用否则 0）→ ResetParaSIdx；否则（单元格内）→ 新建空段（esPara 0x80）挂 paraBox → ResetCompos → 新 esEmbedder(0x44) → CreateItem(0x40,sheet) → esText::AddChrObj → vtbl+0x44(0)
    void OnQuickLayout(esStyleSheet* param_1, int param_2);       // 0x1ccac0  宿主重建总入口：无宿主→返回；沿链找段；RemoveEnvoy 拔旧宿主。**环绕态（flags&7!=0）**：必要时拆分/换段后建 **esCvsAnchor(0x2c)** → AddChrObj → anchor vtbl+0x44(1)；**内嵌态**：确保段样式居中（不居中则 ResetParaSIdx）或新建居中段（param_2==2 前插、否则后插），再建 esEmbedder(0x44) → CreateItem(0x40,sheet) → AddChrObj → vtbl+0x44(0)
    int IsExtArea();                                              // 0x1cd0b0  无宿主（+0x40==0）时：父不是 esCanvasList（0x2011）→ 1；四边距全 0 → 1；否则 0。有宿主 → 0
    zRect GetBoundsForUpdate(ulong param_1);                      // 0x1cd140  焦点 → GetBounding，否则 GetSolidRect；并入活动图形 6 点（+0x10..+0x34，经 esDrawingModifier::GetActiveShape）
    zRect GetSelBounds(int param_1);                              // 0x1cd390  组活动（0x3a08）或 mode → 包围矩形；否则选中实心并集
    int CheckOperationFeasible(ushort param_1);                   // 0x1cd4e0  选中 0x330f → EnumSegments 逐段检查；否则段 vtbl+0xd8
    void ModifyTransfrom(Graphics* param_1);                      // 0x1cd5f0  原点 +0x58/+0x5c 非零→平移 (x,y,0)；FUN_10027a90()==0（无绑定上下文）→合并矩阵 +0x64（GDI+ Graphics 静态默认上下文）
    void ModifyTransfrom(egGraphics* param_1);                    // 0x1cd670  同上显式版：TranslateTransform(原点)+MultiplyTransform(+0x64)
    void ModifyTransfrom(GDC* param_1);                           // 0x1cd6f0  克隆 +0x64；原点非零→FUN_10052bd0(x,y,1)；epModifyDeviceTransfrom(GDC, 矩阵)（原点与上下文皆无→早退）
    void ToExternal(Point* param_1, int param_2);                 // 0x1cd800  GetMatrix→FUN_10027a30 应用（内部→外部，点数组 n 个）
    void ToExternal(PointF* param_1, int param_2);                // 0x1cd890  同上（浮点 FUN_100279d0）
    int ToInternal(Point* param_1, int param_2);                  // 0x1cd920  GetMatrix→可逆判定 FUN_10027480()（==0→不改动返回 0）→求逆 FUN_10027330→应用（外部→内部）
    int ToInternal(tagRECT* param_1);                             // 0x1cd9f0  同上→epTransfromRect（照实恒返回 1）
    void ToExternal(tagRECT* param_1);                            // 0x1cdac0  GetMatrix→epTransfromRect（内部矩形→外部）
    int ToInternal(PointF* param_1, int param_2);                 // 0x1cdb50  同 1cd920（浮点）
    void GetMatrix(Matrix* param_1);                              // 0x1cdc20  拷贝 +0x64 矩阵后 append Translate(+0x58,+0x5c)
    void ConvertAsInternal(esShapeBase* param_1);                 // 0x1cdca0  shape vtbl+0x70(画布矩阵, 0)（图形坐标 → 画布内部）
    void RecalcLayout();                                          // 0x1cdd50  **本批核心算法**（1993B）：① 遍历图形链，seg 类型 0x6010 先调 seg vtbl+0x44(0)（图像重排）；② 内容包围并集（活动图形 6 点并入）+ 矩阵变换；③ 外框 +0xc8：0x1000 时内扩 400 + 边距夹持，且 **L==R → 设为"水平居中"、T==B → "垂直居中"**；④ 内容实心 +0xa8；SetSolidRect/SetBoundingRect（外扩 100）；⑤ InvalidateState；宿主变化 → SetModifiesForHost 或置 +0xd8 bit3 延迟
    void SelectFromRect(tagRECT* param_1, uint param_2, int param_3);  // 0x1ce520  框选：**mode==0** 增量加入（AcmeList 交互态：候选 = sel==期望值 || sel!=0；命中判定 0x330f 走 EnumSegments 段级、有段走 FUN_101aed00；命中 → shape+0x3c=1；末尾 OnEndAdd/UpdateState）；**mode!=0** 全量重算：flags&4 置位 = 仅处理**原未选**，否则全部；flags&8 → 外扩 1 相交即选，否则全含（IsContain）；末尾 SetActive(首个选中) + InvalidateState
    int IsEqualRoleName(wchar_t* param_1);                        // 0x1cea00  +0x48 role 名比较
    ushort SetRole(esStyleSheet* param_1, wchar_t* param_2);      // 0x1cea30  无活动图形：无 role 且名非空 → esRole::CreateRole(this,sheet,1) + SetName + ResetLineWidth(role,this)；返回码：已有 role→**0x2020**；新建且 IsFixed→**0xffff**、非固定→**类型字 0x2010**。有活动图形：第一遍对选中（+0x3c!=0 && +0x4c==0 && 型!=0x3a08）探测 esShapeBase::SetRole 类型字（不一致→0xfffe、无→0）；第二遍赋名（单只＝原名，多只＝L"%s%d" 从 1 递增）；**role+0x14 = role 索引**（撤销 0x523 载体）
    int DeleteRole();                                             // 0x1cec90  撤销码 **0x523**（2 字节 role 索引 word；无 role=0xffff）→ esRole::Release + +0x48=0
    void SetActive(esShapeBase* param_1);                         // 0x1ced10  换活动：旧 OnActive(0) / 新 OnActive(1) → +0xa4=shape
    void CancelAllSelect();                                       // 0x1ced70  全图形 +0x3c=0；有活动 → OnActive(0)；+0xa4=0；InvalidateState
    int RemoveEnvoy();                                            // 0x1cede0  esChrObj::RemoveSelf(+0x40)（宿主字符自文本摘除）+ +0x40=0
    void ChangePerspective(ulong param_1, ulong param_2);         // 0x1cee20  视角透视切换（393B）：需 m1!=m2 且有选择态；以选择矩形中心建矩阵（源/目标 SetViewMode，目标乘 FUN_10027140(1)）；OnEdit 包裹逐选中 vtbl+0x70(matrix,m_pUndo)
    void LoadSelectShapes(esDrawingModifier* param_1);            // 0x1cefb0  装载选择到图形工作器：逐选中 esGraphWorker::Add(mod,shape,1,8)+vtbl+0x6c(mod,1)
    void MakeArray(ulong param_1, int param_2, int param_3, int param_4, int param_5, esStyleSheet* param_6);  // 0x1cf010  阵列复制（802B）：需活动+选择态；GetCurrentData 捕获；ny==0→nx 份沿 (dx,dy) 递推 OnPast；nx==0→ny 份；否则 nx×ny 网格（跳过原点份）；收尾：旧尾之后的**新副本全选 +0x3c=1**、+0xa4=+0x38（尾）、InvalidateState、锚点 Rec_Data(1)
    void RotateSelected(ulong param_1, int param_2, float param_3, tagPOINT param_4, int param_5, esStyleSheet* param_6);  // 0x1cf450  旋转/旋转复制（822B）：需尾非空+θ≥ε+选择态；param_2==0→n−1；n<1 → 纯旋转（矩阵θ：有 acme→MutplayEx 否则 MultiplyMatrix(0x455,1)）；否则：param_2==0→原选择转 (n+1)θ，!=0→清选不转；副本 i=1..n 各 OnPast(iθ)；收尾同 MakeArray（全选新副本+active=尾+锚点 Rec_Data）
    void CopyMove(Matrix* param_1, esStyleSheet* param_2);        // 0x1cf8b0  原位粘贴：GetCurrentData→SetSelObj(0,3)→OnPast(hMem,matrix,sheet)→GlobalFree→锚点 Rec_Data
    int OnPreOffsetSelected(int* param_1, int* param_2);          // 0x1cf930  拖动预校正（366B）：宿主非 0x40 族→0；无活动→0；全选时要求框 0x1000、用外框（Deflate 400）夹住选择矩形修正 dx/dy；返回仍有位移否
    int MultiplyMatrix(Matrix* param_1, int param_2, int param_3);  // 0x1cfaa0  选中矩阵变换：矩阵恒等则 0；逐选中：0x3a03→esSegLinkLine::CheckRomoveLink，vtbl+0x70(matrix,m_pUndo)；links→UpdateLinkPotions(0)；有处理→1
    void TransfromOrgine(Matrix* param_1);                        // 0x1cfb40  选择原点随矩阵：state+0x1c/+0x20 变换后不同→记撤销 **0x210** 写回
    int GetBoxDesc(int param_1);                                  // 0x1cfbe0  行内基线描述（排版）：单节点链按类型取基线——公式框/图像段/固定画布三类来源（GetBaseLine 等）；输出基线点集与底距；无效→-1
    void UpdateLinkPotions(int param_1);                          // 0x1cfff0  连线点刷新：逐链 0x3a03（未选中或 all）→esSegLinkLine::CheckLinkPointEx
    void Undo(ushort param_1, zArchive* param_2, zArchive* param_3);  // 0x1d0050  分发：0x204..0x207 边距 L/T/R/B（int 交换）· 0x208 页码（直接 return）· 0x20e flags +0x4c · 0x210 选择态点 state+0x1c（State 空→return）· 0x212 背景色 +0x44（直接 return）；有改动（0x204..0x207/0x20e）且宿主非空→host vtbl+0x44(0)；default→esFormulaBox::CaretMove（ILT 兜底）
    void * Undata(ushort* param_1, void* param_2, int* param_3);  // 0x1d02e0  按码重建+翻转码：0x208 页码回写+宿主通知 · 0x216 建 0x18 矩阵 blob（6 值） · 0xf005 解组回散→翻 0xf006 · 0xf006 建组（esShapeGroup 0x84+esSegGroupRect 0x78）按 ID 表 Append+Insert+SetGroupInfo→翻 0xf005 · 0x209 宿主通知+SetOutlineUndoInfo · 0x20a 删点→翻 0x20b · 0x20b 插回→翻 0x20a · 0x20c 单点改（存旧 12B） · 0x20d 全体偏移取反（8B） · 0x21f 宿主同步 · 0x214 摘锚→翻 0x215 · 0x215 建锚（esCvsAnchor 0x2c+AddChrObj）→翻 0x214 · 0x523 role 索引对换；default→esObject::Undata
    void Offset(int param_1, int param_2);                        // 0x1d1030  非固定画布整体平移：若有图形+锚点+followed → dx/dy **取整到 400（1mm）网格**；+0x58/+0x5c += d + OffsetObjRect + 外框偏移
    int SetOffset(int param_1, int param_2);                      // 0x1d1130  绝对设置（差量应用同 Offset）；非固定；有变更返回 1
    void Translate(int param_1, int param_2, MatrixOrder param_3);  // 0x1d11c0  矩阵平移：有 undo 时先存 **0x216**（0x18=6×float 矩阵）；按 MatrixOrder 应用；vtbl+0x44(0)；AcmeList::UpdatePoints
    int IsPtInFrameRect(tagPOINT param_1);                        // 0x1d1290  ToInternal 后 PtInRect(GetFrameRect)
    zRect * GetFrameRect();                                       // 0x1d12c0  若 eaProject::GetActiveFrame(this)!=0 → 调 vtbl+0x64 刷新；返回 **+0xc8 矩形**（权威外框）
    double GetAngle();                                            // 0x1d12f0  epCalcAngle(矩阵@+0x64)
    int Rotate(int param_1, float param_2, uint param_3);         // 0x1d1330  非固定：**0 开始**（快照矩阵→静态 DAT_106cd010..、记基角 DAT_106cd00c/008）；**1 拖动**（角=基角+ang；非 flags&4 时按步长 DAT_1057f450（flags&8→DAT_1057f0b4）取整；绕外框中心旋转）；**2 提交**（矩阵与快照异 → 记 **0x216** 旧矩阵）——用第三组文件级静态（见 §8 注）
    esShapeGroup * CreateGroupObj(ulong param_1, short param_2, short param_3, ulong param_4);  // 0x1d1650  成组：统计选中（排除 0x3a08；另计"有 role 联动项"）；弹窗校验（无选中/单选/条件不符）；CheckRemoveControlAndLinkInfo(2) + OnEdit(1,0) → 新 esShapeGroup(0x84)+SetRectObject → 逐只 detach + Append（首只先 Insert），控制项先通知其 +0x40 对象 → InitGroupInfo + CreateUserLinkPoints + Regroup → vtbl+0x44(0) + 记 **0xf005**（ID 数组）→ OnEdit(0,0)
    void ReGroup(ulong param_1);                                  // 0x1d1940  对选中组（0x3008）逐个 esShapeGroup::Regroup(g,1,flags)
    void TransferTo(esCanvas* param_1, int param_2, int param_3);  // 0x1d1990  整画布内容搬迁：建平移矩阵 → 逐图形 detach → vtbl+0x70(矩阵,0)（过到目标坐标系）→ 追加进目标画布（AddItem(dst,shape,1)）
    void UnGroupObj();                                            // 0x1d1a90  解组：需活动图形；OnEdit(1,0) + CheckRemoveControlAndLinkInfo(3) + 清活动 → 逐选中组 esShapeGroup::UnGroup(g,this) + 删组对象 → OnEdit(0,0) + vtbl+0x44(0)
    int MoveToTop(int param_1);                                   // 0x1d1b70  层序提升：头→尾遍历记 local_18＝最近选中；遇未选且已有锚 → esUnMove(0x18) + esUndo::Rec_Add + detach + Insert(shape, local_18, 0)（插到锚**前**）；mode0（相交检查）/mode1 移动后清锚；返回是否动过
    int MoveToUnder(int param_1);                                 // 0x1d1d00  层序下压：尾→头遍历记 local_3c＝最近选中；遇未选 → esUnMove + detach + Insert(shape, local_3c, 1)（插到锚**后**）
    esCanvas * GetOwnCanvas();                                    // 0x1d1ec0  从宿主沿 amulet 向上找"所属画布"：tag 0x40 + ID esCvsAnchor → +0x24；tag 0x81 + ID esEmbedder → +0x38；否则 0（**tag 与 ctor 写入值 0x40 的矛盾见 Q-canvas-22**）
    esCanvasList * GetOwnList(int param_1);                       // 0x1d1fb0  归属列表（122B）：+8==0→up 时经 GetOwnCanvas 递归上找；+8!=0 且 vtbl+8(ID)==esCanvasList::ID()→返回 +8，否则 0
    esCanvas * GetFixedCanvas();                                  // 0x1d2030  固定画布（57B）：GetOwnList(1) 的 +0x38 首画布且 IsFixed→返回
    int IsFocused();                                              // 0x1d2070  焦点判定（esSelState）
    int SetActive();                                              // 0x1d20b0  置活动（选择态）
    int SetFocus();                                               // 0x1d20e0  置焦点
    int InvalidateState();                                        // 0x1d2140  选择状态失效
    esSelState * State();                                         // 0x1d2180  返回 esSelState*（画布级选择管理器）
    esAcmeList * GetAcmeList();                                   // 0x1d21c0  返回 AcmeList（顶点选择链）
    int IsSelectedAllItems();                                     // 0x1d2200  全选判定
    uint MakeEdgeStyle(esStyleSheet* param_1, esEdgeStyle* param_2);  // 0x1d2240  由连接线生成边样式
    void MirrSel(ulong param_1, int param_2);                     // 0x1d2340  镜像选中：需选择态；选择中心；按 axis 取 (1,0,0,−1) 或 (−1,0,0,1) 翻转矩阵（DAT_1057f0b4/5d0），绕中心平移-翻转-回移；mode 时再 SetViewMode 叠加；经 MultiplyMatrix(0x455,1) 施加
    int Alignment_ForGrid(uint param_1, ulong param_2, zPoint param_3, int param_4);  // 0x1d25d0  对齐网格：需活动；选中排除 0x3a03；dir 0/1/2/3=左/右/上/下取参考边对 pt；残差 = round(v/grid)×grid−v；非零→逐个 vtbl+0x70+UpdateLinkPotions+活动帧刷新；grid==0→1
    void SetDynamicMode();                                        // 0x1d2b00  切换动态模式：flags +0x4c ^= 0x4000
    int SelectAllEqualShapeTypes();                               // 0x1d2b40  同类型全选：遍历未选中图形，FUN_101d2c00(+0x40) 与活动同类→SetSelObj(shape,2)；有→1
    void SetHorzAlign(ushort param_1, int param_2);               // 0x1d2d10  水平对齐三态：①无活动（有宿主或非固定）：内容矩形按 0x100 左/0x200 中/0x300 右 Translate(delta,0,1)；②有活动：选中并集（排 0x3a03）→平移矩阵 vtbl+0x70+UpdateLinkPotions（OnEdit 包裹）；③宿主+环绕：改 flags 对齐位（wrap 子模式 2/3/4），变更→撤销 **0x20e**+vtbl+0x44
    int Alignment(uint param_1, ulong param_2, int param_3);      // 0x1d3120  对齐主函数（4888B，批内最大之一）：需活动；选中排 0x3a03（活动为连线时特判）；mode 0..5=按活动框对齐（左/上/下/右/垂直中/水平中）；6/7=水平/垂直等距分布（≥3 只）；≥8=等宽/等高（位表）；应用期逐只 vtbl+0x70(matrix)+UpdateLinkPotions，OnEdit 包裹；返回 1
    void CheckRemoveControlAndLinkInfo(uint param_1);             // 0x1d4460  控制/连线清理：逐链：+0x40 为 esCtrlPoint→RemoveCtrlPoints(mode)；否则 esShapeGroup→RemoveLinkPoints(mode)
    void AppendGraphics(void* param_1, esStyleSheet* param_2);    // 0x1d4530  共享内存续贴（3885B）：zSharedMemory(0x100) Attach→zArchive：ReadByte==4→ReadDWord 对象 id→esObject::IsCanRead→BeginSerilize(2,id)→Serialize sheet(0x10ffff)→读矩形→SetSelObj(0,3)→OnPast(arc,sheet,NULL,NULL,0)→EndSerilize
    void * GetCurrentData(esStyleSheet* param_1);                 // 0x1d4680  复制捕获→共享内存：无图形→0；WriteByte(4)+BeginSerilize(1,0x2000837)；IsFocused&&+0xa4→只捕选中否则全链；esPtrExchanger 注册+写 sheet+0x850；Serialize(0x10ffff)；矩形=聚焦?选择:内容；写对象数；逐（+0x3c 匹配标记）vtbl+0x40(arc,sheet,2)；EndSerilize→Close→Detach 返回句柄
    void OnPast(void* param_1, Matrix* param_2, esStyleSheet* param_3);  // 0x1d48e0  共享内存粘贴（309B）：Attach→ReadByte(4)→ReadDWord→BeginSerilize(2,id)→Serialize sheet→读矩形→6 参 OnPast 核心→EndSerilize
    void OnPast(zArchive* param_1, esStyleSheet* param_2, esUndo* param_3, Matrix* param_4, int param_5);  // 0x1d4a20  粘贴核心（602B）：有活动→清选；ReadDWord 对象数→循环：ReadWord 类型→vtbl+0x58 CreateObjByType→ResetLineWidth→vtbl+0x40 反序列化→（flag!=0 且 0x3a08→弃）；0x3908 holder 需 NormalObject 成功；+0x3c=1→AddItem 尾插+SetUnAddInfo；收尾指针回填→vtbl+0x44(0)
    virtual void CollectStyles(esStyleSheet* param_1);            // 0x1d4c80  样式收集：esContainer::CollectStyles；role +0x48 非空→vtbl+0x10(sheet)
    virtual int OnMessage(esMessage* param_1, ulong param_2);     // 0x1d4cc0  role +0x48 vtbl+0x48(msg,flag) 处理过→vtbl+0x44(0)；再 esContainer::OnMessage
    virtual int IsEqual(esObject* param_1, esStyleSheet* param_2);  // 0x1d4d20  等价判定：esObject::IsEqual；role 同空/同有（有→vtbl+0x4c）；refLine vtbl+0x4c；边距 +0xb8 memcmp(0x10)（自定义点→比点数+点集）；图形链逐只 vtbl+0x4c；长度相等
    virtual void Serialize(zArchive* param_1, esStyleSheet* param_2, ushort param_3);  // 0x1d4ee0  见 §0 序列化说明（版本分叉 + 边框三态 + 子对象流）
    virtual void CopyFrom(esObject* param_1, esStyleExchanger* param_2);  // 0x1d5530  逐字段拷贝 + 图形链重建（各 obj vtbl+0x24）+ refLine/matrix + 边框点数组深拷
    int GetNextObjID();                                           // 0x1d5720  +0x50==0 → 0；否则 esObject::GetID(+0x50,0)（**下一画布**的导出 ID）
    void Detach();                                                // 0x1d5760  从画布链摘除（列表 +0x38/+0x3c 首尾修补、邻节点 +0x50/+0x54 改指）+ esCanvasState::OnRemove
    int IsDeletable();                                            // 0x1d5850  托管且有边框（L/R/B/T 差 > 2000 = 5mm）且**正在编辑激活** → 不可删；否则可删
    esObject * DeleteSlef(int param_1, int param_2);              // 0x1d5910  链尾特判 + vtbl+0x38 自毁 / 交容器删除协议
    void SetUnDelInfo();                                          // 0x1d59a0  清"不可删"标记
    uint DeleteSel();                                             // 0x1d59c0  删除选中集：若"无活动 或 全部已选"且 IsDeletable → 画布自毁协议返回 2；否则（不可整体删）→ SetSelObj(0, mode0) 把**全部图形**标选（= 退化为清空内容）。然后 SetActive(0)、CheckRemoveControlAndLinkInfo(1)、逐选中图形：有 undo → 图形 vtbl+0x14（删除记录）→ vtbl+0x38 自毁 → vtbl(1)；末画布 vtbl+0x44(0)；返回 1
    esShapeBase * SetSelObj(esShapeBase* param_1, int param_2);   // 0x1d5b00  选择集操作：**0**=全选（并激活，含 param 或首只）· **1**=取消选 param_1 · **2**=选中并激活 · **3（或 param==0）**=清空全选（可保留 param_1 选中并激活）· **4**=切换；尾部：活动对象空/未选 → 从链尾（+0x38 经 +0x48）回扫首个选中设为活动；SetFocus + InvalidateState + AcmeList::Clear；返回新活动
    void LoadSnapLines(esSnapManager* param_1, zRect param_2, int param_3, int param_4);  // 0x1d5ce0  装填吸附侧线：候选 X = 选区左右边 + 中心（|宽|>阈值 才加中心）；候选 Y 同理；逐图形（param_7 过滤：0 全部 / 1 跳过活动 / 2 跳过已选）对准距 ≤ 阈值者取 vtbl+0x68 对齐点集，逐点与候选 X（AddSideLine 0）/ Y（AddSideLine 1）差 ≤ 阈值 → 加线
    void SnapSnapPoint(int param_1, esSnapManager* param_2);      // 0x1d6050  吸附点管线：IsSnapable(0x10000000) 时先对组（0x3008，最大盒 +400）做**连接点吸附**（GetLinkPts → SnapLinkPoints）；再按 cmd 过滤图形（0x465 只喂首个接受者；0x1f42/0x1f43 跳过活动；0x452..455/0x45c..45f 或 snapType&0x71 跳过已选；其余全遍历）→ 逐只 shape vtbl+0x90(mgr,1)
    int HitTestGraphics(esHitTest* param_1);                      // 0x1d6280  先 HitTestNormal 命中 → 1；否则同列表活动画布（esCanvasList::GetActive）→ HitTestCanvasFrame 命中 → 1；锁定 → 0；固定 → -1；否则设矩阵（GetMatrix + FUN_101df370）后：内容空且宿主 tag 检查 0x81 通过且点在外框内 → SetSelInfo(0x1d) → 1；默认 -1（tag 语义见 Q-canvas-22）
    int HitTestNormal(esHitTest* param_1);                        // 0x1d6440  点 → 内部坐标；外框按半径（ht+0x24 ×3 或 ×4 分支）膨胀 PtInRect；命中 → CheckMode(0x10) 转 HitTestCtrlPoint；CheckMode(5) → 非动态 HitTestAcme / 动态 HitTestVertex；再测内区矩形 → HitTestObjClick
    int HitTestScaleBox(esHitTest* param_1);                      // 0x1d65e0  空闲态缩放手柄：仅 无活动图形 + frame==0 + 有宿主；实心外扩半径处 8 柄（**0 TL·1 TR·2 BR·3 BL·4 L中·5 T中·6 R中·7 B中**）→ SetSelInfo(0x33, this, i) → 1
    void ScaleFrame(tagRECT* param_1, int param_2);               // 0x1d6780  外框拖缩：实心去原点求宽高（低于静态下限放弃）；mode<4 用**对角比**等比、≥4 用宽/高比（各 clamp ≥ 静态下限）；锚点=对角手柄（同 0..7 编号）；矩阵=平移到锚→缩放→平移回；退化（行列式 0）时 OnEdit(1,0) → 快照静态 → 非 1×1 记 **0x216** → vtbl+0x44(0)；正常时矩阵 to_inside 写 +0x64 → 逐图形 vtbl+0x70(矩阵, m_pUndo) → TransfromOrgine
    int HitTestEdgeFrame(esHitTest* param_1);                     // 0x1d6cd0  编辑框边/角：非固定 + frame 0x1000；最近边取 0 左/1 右/2 上/3 下（阈值 ht+0x28）；角柄=左缘(0,2)/右缘(1,3)/上缘(0,1)/下缘(2,3)（**TL,TR,BL,BR** 编号），边中点=4 L/5 T/6 R/7 B；中点柄仅"父非 esCanvasList 或未聚焦"可用；有宿主 → 码 0x1f（否则 0x20）；CornerSize = CalceCornerSize/2（有宿主）；无宿主未命中柄 → SetSelInfo(0x1d) 整框；有宿主 → 0（交 HitTestGraphics/ObjClick 兜底）
    int IsPointInsideOutlines(zPoint param_1);                    // 0x1d7220  内含判定：无宿主 → 外框**内缩 400** PtInRect；有宿主 → GetOutlineRect（frame==0 时再按边距内缩）；自定义点 → 粗判后 esGraph::IsPtInGon(点集+闭合)
    int HitTestOutlines(esHitTest* param_1);                      // 0x1d73b0  轮廓命中：无宿主 → 0；点集补闭合点；逐**顶点** HitTestPoint → SetSelInfo(0x31 自定义 / 0x32 矩形, idx) + set_return_point；无自定义时再测**边中点**（idx+4，码 0x32）；自定义时 HitTestLines 命中轮廓线 → 0x21；最后 IsPtInGon → 8（内部区域）
    int HitTestExPoints(esHitTest* param_1);                      // 0x1d76f0  扩展选择点：State 空→0；先测选择态点 state+0x1c → 0x1c；SetExSelBound 重建后取活动图形：8 顶点分奇偶两遍 HitTestPoint → 0xe；活动 9 点多边形（shape+0x40）IsPtInGon → 0xc；再 8 点 HitTestPointEx → 0xd
    int HitTestCtrlPoint(esHitTest* param_1);                     // 0x1d7a80  控制点：State 空→0；半径 = ht+0x24 的 3 倍；遍历图形（vtbl+0xb0 有控制点且非活动）：包围命中且 vtbl+0x98(ht,1) → 记录拖拽原点（state+0x18/+0x14）返回 1；否则外扩（右/下 3r）再判：锚点 = vtbl+0x68 对齐点 → SetSelInfo(0x13, shape) + 原点记录
    void BreakLines();                                            // 0x1d7d40  直通 AcmeList::BreakLines
    int TestConnect(esJunctor* param_1, esJunctor* param_2, int param_3);  // 0x1d7d70  AcmeList::TestLink(j1,j2)；返回"列表存在"
    int ConnectLines(esJunctor* param_1);                         // 0x1d7db0  junctor 位判定（vtbl(0)&1）→ junctor vtbl+8(undo) 执行连接 → AcmeList::Clear → 1
    int IsWrittingCanvas();                                       // 0x1d7e20  无宿主 + 父为 esCanvasList + 父 +0x38==this + 父类判型通过 → 1（"正在书写的画布"）
    int RemoveAcmeByPoint(zPoint param_1);                        // 0x1d7ea0  AcmeList::RemoveAcme(x,y,10) → UpdateState → 1
    int SelectAcmeByPoint(zPoint param_1, int param_2, int param_3);  // 0x1d7ef0  AcmeList 按点选：clear → 清；遍历（已选或 all 才测，包围外扩 25）：0x330f → EnumSegments 逐段、有段 → 段级命中 → shape+0x3c=1；末 OnEndAdd+UpdateState；返回状态或画布脏位
    int HitTestVertex(esHitTest* param_1);                        // 0x1d8170  顶点模式（动态）：还原 ht 上下文（state +0x18/+0x14/+8）；逐已选图形 vtbl+0x98(ht, 0x400000) → 顶点子判定（101d82e0）
    int HitTestAcme(esHitTest* param_1);                          // 0x1d8380  AcmeList::HitTest 优先；否则还原上下文；CheckMode(4)==0 → 逐已选 vtbl+0x98(ht,0x400000)；否则仅活动图形（其 seg 为 esSegImage 时 vtbl+0x98(ht,0)）；IsClicked：起点变化 → ht+0x48=1 + 更新 state 原点；**SetActive(candidate)**
    int HitTestFirstObjClick(esHitTest* param_1);                 // 0x1d8650  首击穿透：外框 CheckRectL → selinfo(0)；逐已选图形实心 CheckRectL + vtbl+0x8c → 返回 esTextBox::GetModelBox(ht)
    int HitTestObjClick(esHitTest* param_1);                      // 0x1d8740  对象点击：不可见→0；实心 CheckRectL；**空画布**：非固定且聚焦→0，否则 SetSelInfo(1,this)→1；有图形：按"无活动→先未选 / 有活动→先已选"两遍：占位段（IsPlaceHolder && HitTestHolders）命中直接 1；vtbl+0x8c 命中：未选 → SetSelInfo(1,shape)+ht+0x44=shape；已选且 ht+0x40&8 置位 → SetSelInfo(3,shape)+ht+0x44；已选且未置位 → 仅在特定编辑上下文（宿主 tag0x40、非 0x1000 框、state 活动、GetEditState==0x452、模型盒不在 0x14..0x1b）仍 1；IsClicked → 清 state 原点
    int AddBorderPoint(zPoint param_1, int param_2, int param_3);  // 0x1d8b10  自定义边框加点：先查距现有点 ≤dist → 0；再逐边求点到线距 ≤dist → mode==0 记撤销 **0x20a**（int 索引＝插入位序）→ InsertBorderPoint(i+1, pt−中心) → 1
    void InsertBorderPoint(int param_1, zPoint param_2);          // 0x1d8e00  数组扩容插入：count+1、新分配、memcpy 前后段、写 +0xdc[idx]（**相对中心坐标**）、释放旧数组
    int RemoveBorderPoint(int param_1);                           // 0x1d8f00  收缩删除：**count≥4 才允许**；count−1、memmove；数组不缩容；返回 1
    int AddNewPoint(zPoint param_1, int param_2, int param_3, int param_4);  // 0x1d8f90  统一加点入口：flag==0 → ToInternal 后对**选中图形**（实心外扩 p6 内 PtInRect）调 esShapeBase::AddPoint，返回 1 即中止；flag!=0 → AddBorderPoint
    int DelBorderPoint(zPoint param_1, int param_2, int param_3);  // 0x1d9090  自定义边框删点：count≥4 且有点；GetOutlinePoints 逐点距 ≤dist → mode==0：OnEdit(1,1) + 记撤销 **0x20b**（12 字节：索引+坐标）→ RemoveBorderPoint → vtbl+0x44() → OnEdit(0,1)；返回 1
    int Clips(zPoint param_1, int param_2, int param_3, int param_4, int param_5);  // 0x1d9290  夹线/剪切（本批最大 2801B）：命中首个**未选** 0x330f 的段 → 宿主图形；probe==0 && m_pUndo 时：无命中 → 无活动返回 0、有活动 SetSelObj(NULL,3) 清选返回 1；命中 → OnEdit(1,0) → input checker 喂段（无活动=全部段链、有活动=仅命中图形；seg vtbl+0xb4(cmd,0,isClosed)）→ 容器拆路（两路 get_path，decomp 均显实参 0，疑 0/1 var 复用）→ CheckValid/InitPropertys → 主路：mode==0 或存在第二路/宿主链非空 → RemoveControlAndLinkPoints(宿主)，第二路插入+SetUnAddInfo，第一路按 mode 弃或插入+HoldLine(mode,…) 夹线；宿主段链仅剩单段（*(*(宿主+0x60)+0x40)==0）→ 删整个图形，否则删命中段（amulet）；宿主被掏空且 IsDeletable → **画布自毁**返回 1；否则 vtbl+0x44(0)+OnEdit(0,0)。probe!=0 或无 undo → 返回"是否命中"
    void HoldLine(int param_1, esShapePath* param_2, esUndo* param_3);  // 0x1d9d90  夹线笔型切换：mode1 ↔ 笔型(kind)!=0 → kind 置 0、宽 +0x14（<0x1e 加否则夹 0x32）；mode2 ↔ kind==0 → 置 3、宽 −0x14（≥0x1f 减否则 10）；变更记 shape 撤销 **0x507 线型 / 0x506 宽度**（esShape.md §6.1）；状态不匹配 → 仅 SetSelObj(path,3)
    int HeBing(int param_1);                                      // 0x1d9ee0  合并同态路径：需活动 0x330f + 选中数 ≥2；选中含非 0x330f → 0；按 IsClosedEx 4 类计数，**类别数 ≥2 拒合**；mode0：目标=活动 → 逐其余选中 RemoveControlAndLinkPoints → 逐段链（head +0x60、next +0x40）esUnMove+Rec_Add → detach → AddSegList(目标) → 源掏空销毁 → vtbl+0x44(0)+SetActive(目标) → 1；mode!=0 → 1（探测）
    int FenJie(int param_1);                                      // 0x1da1d0  分解多段路径：选中 0x330f 且段链非空（+0x60 != +0x64）；mode0：逐只 → RemoveControlAndLinkPoints → 逐段链（原文从 [+0x60]+0x40 起、next +0x40）新建 esShapePath 拷贝(0x74)（样式字取原 +0x34）→ Insert(新, 下一节点, 0)+SetUnAddInfo → esUnMove+Rec_Add → detach → AddSegList(新) → 新片 +0x3c=1（选中）；原图形 vtbl+0x44(0)；末画布 vtbl+0x44(0)；返回是否分解过
    esObject * SearchUp(uint param_1);                            // 0x1da430  kind==**0xb**（画布类别）→ 返回自身；否则 esObject::SearchUp
    esShapeHolder * FindVideoPlaceHolder();                       // 0x1da460  找视频占位：esShapeHolder（0x3908）且其段（+0x40）类型字 == **-0x5001**（0xafff）且 flags &0x2000 → 返回该对象
    esRgn * MakeRgn(int param_1, int param_2);                    // 0x1da4c0  GetWrapMode()<5 才产出：GetOutlineRect；followed → (dx,dy) 相对外框原点；自定义边框点 → GetOutlinePoints（count）→ esRgn 点集工厂 100693f0（临时数组 free）；否则矩形偏移后 10069390；wrap≥5 → 0
    zRect * GetOutlineRect();                                     // 0x1da680  有活动帧 → 先 GetSolidRect(this,1) 刷新；恒返回 +0xc8（与 GetFrameRect 同源）
    void InitCreateRgn();                                         // 0x1da6b0  全图形样式字清 **bit31**（填充标记复位）
    esShapeBase * CreateFillRgn(zPoint param_1, esBrushInfo* param_2, int param_3, int param_4);  // 0x1da6f0  油漆桶：brush 空 / 画布空 / 点在外框外 → 0；ToInternal；按"有无活动"匹配选择态遍历：0x3008 组 → GetFillBorders 命中；含 LBC 线图形 → 0x330f+有刷+IsRgnClicked 命中 → 同刷同色 → **返回 0**、undo&&m_pUndo → UpdateBrush 换刷 → 返回旧填充图形。无旧填充 → FUN_10381ad0(点) 由轮廓生成新路径 + SetBrushObj；mode!=0 找 bit31 同刷邻路 FUN_10383740(1) 合并（旧路删）；新路 +0x34 |= 0x80000000；有旧填充图形 → InitPropertys 继承；Insert(新, 命中, 1)+SetUnAddInfo → 新图形
    int LinkClose(int param_1);                                   // 0x1dad30  多线连接闭合（活动须 0x330f）：选中含非 0x330f → **-3**；无未闭合选中 → -1；mode0：逐选中段链 FUN_10386e60(seg, isClosed) → 收束 FUN_10386ff0（失败 **-2**）→ RemoveControlAndLinkPoints 全 → 建 esCalligraph（活动拷贝 0x74）+ResetLineWidth → 逐只删源图形 → FUN_103872d0 装配（失败 0）→ CloseFigure + 样式 |0xff + NormalRing → AddItem+SetUnAddInfo+SetSelObj(3)+vtbl+0x44(0)；mode!=0 → 0
    void OffsetCtrolPoint(esSeg* param_1, esSeg* param_2, int param_3);  // 0x1db0a0  每个 0x3a08 控制点对象 → esCtrlPoint::OffsetCtrolPoint
    int DeleteControlPoints();                                    // 0x1db100  控制点批量删除：先扫链首连续选中段（允许 0x3a08 / 控制专组 0x3008，否则停）；**全链皆控制物件且 IsDeletable → 画布自毁返回 1**；否则 OnEdit(1,0) 逐选中：0x3a08 → SetLinkUndo(0xf2f1) 删节点；0x3008 非专组 → RemoveControls；专组 → 删节点（含链修复+active 重设）→ vtbl+0x44(0)+OnEdit(0,0)；无活动 → SetActive(最后保留者)；返回是否动过
    void RemoveControlPoints(esSeg* param_1);                     // 0x1db360  全 0x3a08 → esCtrlPoint::RemoveCtrlPointWith(ctrl, seg)
    void RemoveControlAndLinkPoints(esShapeBase* param_1);        // 0x1db3b0  除 shape 外全 0x3a08 → RemoveCtrlPointWith(ctrl, shape)；shape 为 0x3a08 且有 undo → SetLinkUndo(0xf2f1)；0x3008 → RemoveAllLinkPoints；0x3a03（esSegLinkLine）→ RemoveLinkInfo(0)/(1)
    void RemoveAllControlAndLinkPoints();                         // 0x1db490  全 0x3a08 → esSeg::RemoveControlLink；0x3008 → RemoveAllLinkPoints
    int CuttingByLBCLine(esStyleSheet* param_1, zPoint param_2, int param_3, int param_4, int param_5);  // 0x1db500  用 LBC 线切割：命中首个未选 0x330f（段级含 vtbl+0x8c）/含 LBC 线图形；命中**已选**图形 → 0；flags==-1 探测 → 1；对每个选中 0x330f CuttingPath 成功：flags&0x40 删被切图形；有成功且 flags&0x80 → 删切割线 → vtbl+0x44(0) → 1；否则 0
    int GraphicOperation(esStyleSheet* param_1, zPoint param_2, int param_3, int param_4, int param_5);  // 0x1db880  布尔运算：命中未选闭合 0x330f；op==-1 探测 → 1；OnEdit(1,0)；op&0xf==3 链式逐只 FUN_101dc300(选中, 累积, op)（空结果止）；否则逐只与命中图形运算（任一空则整体失败，弹 0xa1f → 0）；无结果弹 0xa20（非 6 → 0）；op&0x40 && op&0x80 + 画布无边框(flags&0x1000==0) + 链上无旁图形 → **画布自毁返回 1**；清选 → 每结果 CopyPropFrom+Insert+SetSelObj(2)+SetUnAddInfo → op&0x40 删操作数、op&0x80 删命中图形 → vtbl+0x44(0)+OnEdit(0,0) → 1
    int BreakShape(esStyleSheet* param_1);                        // 0x1dc400  断开图形：需活动；对每个选中取 vtbl+0xac 的"断开对象"：无内容（+0x40==0）→ 直接释放；否则 Insert(对象, 原, 1)+SetUnAddInfo+SetSelObj(2)（0x330f 时样式 |0xff）→ RemoveControlAndLinkPoints(原) → 原图形销毁；返回断数
    int Cutting(esStyleSheet* param_1, esShapeBase* param_2, int param_3);  // 0x1dc550  cutter 无 LBC 线 → 0；对每个选中图形（vtbl+8(ID) 类型自校通过者）CuttingPath 成功 → 原图形销毁；任一成功 → 1
    int CuttingPath(esStyleSheet* param_1, esShapePath* param_2, esShapeBase* param_3, int param_4);  // 0x1dc640  切割引擎：target/cutter 段分别喂 input checker →（mode==0 且 target 闭合 ? FUN_10383590 : FUN_103834f0）→ 逐结果路径：空段释放；非空 CopyPropFrom → target 未闭合或 !bVar1&&!IsReallyClosed → OpenCanvas，否则 CloseFigure → Insert(结果, target, 0)+SetUnAddInfo、+0x3c=1；active==target → 改指首结果；返回是否产出
    void EraseSelectedItems(esStyleSheet* param_1, esShapePath* param_2);  // 0x1dc990  橡皮主流程：活动须 0x330f；ConvertAsInternal(活动→eraser)+CloseFigure+OnEdit(1,0)+清活动；逐选中 0x330f：无刷 → EraseLines、有刷 → EraseRegion；结果非空 → +0x3c=1+设为活动；画布空且 IsDeletable → **自毁**；否则 OnEdit(0,0)
    esShapePath * EraseRegion(esStyleSheet* param_1, esShapePath* param_2, esShapePath* param_3);  // 0x1dcaf0  区域擦除：shape/eraser 段喂 checker（FUN_103813a0 各一次）→ FUN_10383740(2) 产新路径 → 非空 CopyPropFrom(shape) → OnItemErased(shape, 新)；引擎失败（空）→ 返回原 shape 不变
    esShapePath * OnItemErased(esShapePath* param_1, esShapePath* param_2);  // 0x1dcc20  擦除收尾：RemoveControlAndLinkPoints(orig)；result 非空 → Insert(result, orig, 1)+SetUnAddInfo+vtbl+0x44(0)+orig 销毁+SetActive(result) → result；空 → 释放 result+orig 销毁+vtbl+0x44(0) → 0
    esShapePath * EraseLines(esStyleSheet* param_1, esShapePath* param_2, esShapePath* param_3);  // 0x1dcd00  线条擦除：shape/eraser 段喂 checker → FUN_10381470(eraser 命令) 产新线路径 → CopyPropFrom + 结果样式字清 **bit 0x1000** → OnItemErased
};

} // namespace eslib
