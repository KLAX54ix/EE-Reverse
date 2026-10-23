# eslib 样式中枢 — 反编译规格（阶段 2 · 第五批 · 绘图核心 2/6）

- 模块：eslib.dll；函数：**149 个**（esStyleSheet 103 · esBrushInfo 34 · esPenInfo 12）
- 伪代码（原样）：`analysis/pseudo/eslib/esStyleSheet.decomp.txt`（matched=149 dumped=149）
- 类型头：`analysis/types/esStyleSheet.h`
- 台账：149/149 → `decompiled`（status-overrides）
- 角色：**S1 绘图链的样式中枢**。`esStyleSheet` 是文档全部样式表的集合（19 个子表 + 隐藏/考试/
  序列化状态）；`esBrushInfo` 是画布对象 Fill 的笔刷参数（也是图片索引载体）；`esPenInfo` 是
  描边参数（颜色/线宽/线型/端点帽），`esSeg::Draw` 的笔就由它产出（对照 ee-draw 的 `pen_mm`）。

## 0. 结构总览

**esStyleSheet 是「组合」型对象**：对象头从 +0x000 起依次内嵌 19 个 sheet（各 sheet 内部为
`esStyleList<T>` 派生表），每个子表的 ctor 都收到 owner `esStyleSheet*`（反指针）；+0x5F4 起为
brush 表，+0x850 起为状态区。字体表就在 +0x000 —— 即 ee-draw 里
`caretContext().fontSheet == pageLists()[].styleSheet` 的由来（同一对象）。

| 偏移 | 类型 | 说明 | 证据 |
|---|---|---|---|
| +0x000 | esFontSheet | 字体表（本对象第一个内嵌子表） | ctor `10304500`；`esFontSheet::GetFont((esFontSheet*)this,…)` 全文 |
| +0x5F4 | esBrushSheet | 刷子表 | ctor / SFlags bit 0x1000 |
| +0x614 | esColorSheet | 配色表 | ctor / bit 8；`GetDefaultColorScheme` 取 [0] |
| +0x634 | esBoxSheet | 框样式表 | ctor / bit 0x4000 |
| +0x654 | esEdgeSheet | 线型/外框表 | ctor / bit 0x8000 |
| +0x674 | esCellSheet | 单元格样式表 | ctor / bit 0x10 |
| +0x694 | esUIndentInfo | 缩进样式表（含悬挂） | ctor / bit 0x20 |
| +0x6B4 | esTabSheet | 制表位表 | ctor / bit 0x40 |
| +0x6D4 | esBulletSheet | 项目符号/编号表 | ctor / bit 0x100 |
| +0x6F4 | esBlockSheet | 文本块样式表 | ctor / bit 0x80 |
| +0x714 | esDropcapSheet | 首字下沉表 | ctor / bit 0x2000 |
| +0x734 | esParaStyleSheet | 段落样式表 | ctor / bit 0x200；`TackExamIndexs(+0x734,+0x6d4)` |
| +0x754 | esDimationSheet | 尺寸标注样式表 | ctor / bit 0x400 |
| +0x774 | esImageSheet | 图片表（brush 图片索引缓存来源） | ctor / bit 0x800；`GetImageIndex1` |
| +0x794 | esRoleSheet | 角色表 | ctor / bit 0x100000 |
| +0x7B4 | esMstPageSheet | 母版页表 | ctor / bit 0x2000000；`GetMstPageList` |
| +0x7D4 | esFmtPageSheet | 页面格式表 | ctor / bit 0x1000000 |
| +0x7F4 | esStringSheet | 字符串资源表 | ctor / bit 2 |
| +0x814 | esExamSheet | 考试样式表 | ctor / bit 1 |
| +0x840 | esStrRes (0x10B) | 字符串资源对象（4 dword，不参与 SFlags） | ctor/dtor `esStrRes::~esStrRes(+0x840)` |
| +0x850 | ulong | **版本号**（ctor/EndSerilize/SetAsCloneMode 恒复位 `0x2000837`） | ctor；`GetVersion` |
| +0x854 | ushort | 标志：bit0＝「文档已挂/考试 UI 模板就绪」 | ctor(L1946)；`GetAutoHeader` 门控 |
| +0x856 | ushort | 标志：bit0＝EndSerilize 需要 `TackExamIndexs` 收尾 | `SetAsExamUITemplates` L5164；`EndSerilize` |
| +0x858 | esExamStyle | 考试样式（选项布局/分隔符等） | ctor；`GetExamStyle` |
| +0x874/+0x878 | uint×2 | 隐藏状态位（bit17/19 答案、bit18/20 解答、bit3/4 解析…） | `GetHiddens`/`IsInvisiable*`/`RemoveHiddens` |
| +0x8E4 | esNoteStyle | 批注样式 | ctor/dtor；`GetNoteStyle` |
| +0x908 | esRoleList | 角色列表 | ctor / bit 0x40000000 |
| +0x91E | ushort | bit0：LoadForm 载入角色后置位 | `LoadForm` L5367 |
| +0x940 | esParaTmplList | 段落模板列表 | ctor / bit 0x20000000 |
| +0x958 | esAutoHeadList | 自动题头列表（kind→bullet 索引） | ctor / bit 0x80000000 |
| +0x968..+0x98B | 9×dword | 未命名状态块（ctor/op= 整体拷贝） | ctor L138-144 |
| +0x98C | esBaseDoc* | 宿主文档（`GetEpDocument`） | `GetEpDocument` |
| +0x990/+0x992 | short | 文档样式参数（ctor 默认 200/150=0x96） | ctor L1932；`SerializeDocumentStyle` |
| +0x994..+0x9B3 | uchar[0x20] | **段落隐藏位图**（32 字节，SFlags bit 0x10000 整体序列化） | `HidePara`/`GetHiddens`/`Serialize` |
| +0x9B4 | int | CloneMode 计数（`IsCloneMode` 直读） | `SetAsCloneMode` |
| +0x9B8 | enmSMode | 序列化模式（bit0=写；3/4=文件；5/6=考试） | `IsWriteMode`/`IsFileMode`/`IsReadMode`/`IsExamMode` |
| +0x9BC | ulong | **SFlags**：本轮序列化/收集哪些子表 | `SetStoreSFlags`/`Serialize` |
| +0x9C0 | esParaModel* | **共享 scratch 段落模型**（懒建 0x50；所有 Get/To/Make Model 复用同一实例）★Q1 | `ToModel`/`GetModel`/`MakeSimilarModel` |

**SFlags（+0x9BC）位 → 子表**（证据 `SetStoreSFlags 10306180`；`Serialize 10306650` 按位读写）：

| 位 | 目标 | 位 | 目标 |
|---|---|---|---|
| 0x1 | +0x814 esExamSheet | 0x800 | +0x774 esImageSheet ★双版本门（见 §4.1） |
| 0x2 | +0x7F4 esStringSheet | 0x1000 | +0x5F4 esBrushSheet |
| 0x4 | +0x000 esFontSheet | 0x2000 | +0x714 esDropcapSheet |
| 0x8 | +0x614 esColorSheet | 0x4000 | +0x634 esBoxSheet |
| 0x10 | +0x674 esCellSheet | 0x8000 | +0x654 esEdgeSheet |
| 0x20 | +0x694 esUIndentInfo | 0x10000 | +0x994 隐藏位图 32B（raw，非子表） |
| 0x40 | +0x6B4 esTabSheet | 0x100000 | +0x794 esRoleSheet |
| 0x80 | +0x6F4 esBlockSheet | 0x1000000 | +0x7D4 esFmtPageSheet |
| 0x100 | +0x6D4 esBulletSheet | 0x2000000 | +0x7B4 esMstPageSheet |
| 0x200 | +0x734 esParaStyleSheet | 0x20000000 | +0x940 esParaTmplList |
| 0x400 | +0x754 esDimationSheet | 0x40000000 | +0x908 esRoleList |
|  |  | 0x80000000 | +0x958 esAutoHeadList |
|  |  | 0x10000000 | SerializeDocumentStyle（考试样式 + 文档级模型） |

**enmSMode（+0x9B8）**：`0=无`；`bit0=1` 写（1 内存写 / 3? 文件写）；`IsFileMode = (3,4)`；
`IsReadMode = 非0且bit0=0（即 2/4/6）`；`IsCopyMode=(1,2)`；`IsExamMode=(5,6)`；`IsLocked=非0`。

**全局单例**：`DAT_106c48ac`（esGlobalSheet，本质是静态 esStyleSheet）——
`GetGlobalSheet/GetGlobalStyleSheet/GetDefaultColorScheme/InitGlobalSheet/SaveDefaultStyles/
SaveAsDefaultExamStyles/GetBlanks` 全部打它；`SetTagFontMap` 写模块级 `m_pTagFonts`。

**版本魔数**：`0x2000837` 是"当前写版本"；ctor/copy/`EndSerilize`/`SetAsCloneMode` 都把它写回
+0x850；`GetVersion(NULL)` 也返回它。

## 1. esStyleSheet（103 个）

### 1.1 生命周期 / 全局

| 函数 | 入口 | 规格 |
|---|---|---|
| `ctor(doc)` | `10304500` | 依序构造 19 个子表（各传 owner=this）→ `FUN_10301b70`（状态区）→ `esExamStyle`/`esNoteStyle`/`esRoleList`/`esParaTmplList`/`esAutoHeadList` → `FUN_1032a4e0`；清 +0x994..+0x9C0 状态；version=0x2000837；+0x990=200 +0x992=0x96；+0x9B8=0；色表空则塞一个默认 esColorScheme；`+0x98C=doc` 且 doc≠0 → **+0x854|=1**；SetActiveFont(font[0],0xffffffff) |
| `ctor(copy)` | `1002c230` | 逐子表拷贝 ctor + 标量/列表/32B 位图全拷 |
| `dtor` | `103048b0` | 反向析构全部子表 + `esStrRes`；`+0x9C0` 模型先 `vtbl[0](1)` 释放 |
| `operator=` | `101fcf70` | 同序赋值；注意：**+0x5F4..+0x7F4 全部经 `esBlockSheet::operator=`**（符号折叠，见 §6） |
| ``default_constructor_closure`` | `1042c9f0` | `esStyleSheet(this, NULL)` 转 ctor `10304500` |

### 1.2 模式 / 版本 / 全局入口

| 函数 | 入口 | 规格 |
|---|---|---|
| `GetVersion()` | `100d0c70` | `this==NULL → 0x2000837`；否则 +0x850 |
| `GetSerialMode()` / `IsReadMode()` / `IsWriteMode()` / `IsFileMode()` / `IsCopyMode()` / `IsExamMode()` / `IsLocked()` | `1042c980 / 1042c9a0 / 1032a420 / 1032a3e0 / 101df5d0 / 100d00a0 / 10199050` | 见 §0 模式表（各位测试） |
| `IsCloneMode()` | `10199110` | 直读 +0x9B4 |
| `GetExamStyle()` / `GetNoteStyle()` / `GetEpDocument()` | `100b8b90 / 1036a4c0 / 100b8920` | 分别 `this+0x858 / +0x8E4 / *(doc*)0x98C` |
| `GetTagFont(sheet,id)` / `SetTagFontMap(map)` | `10304a80 / 1042c9e2` | 静态；`m_pTagFonts` 查 id→字体索引→font[索引] |
| `GetGlobalSheet()` / `GetGlobalStyleSheet()` / `InitGlobalSheet()` / `SaveDefaultStyles()` / `SaveAsDefaultExamStyles(sheet)` | `10308760 / 10308770 / 10308860 / 10308870 / 10308720` | 全局 `DAT_106c48ac`；SaveAsDefault 走 `elfSubject::GetAgent`→`CopyExamStyleFrom`→`esGlobalSheet::SaveAsFile` |
| `GetDefaultColorScheme()` | `10308790` | 线程守卫(`DAT_106cd954`)；全局色表 [0] 或静态默认 `DAT_106cd958` |
| `GetBlanks()` | `10305210` | 返回全局对象（反编译类型失真：实为 esBlankList 静态） |
| `GetDefaultExamFontheight()` | `1032ac20` | 恒 `0x41a`(1050) |
| `SetDefColorSchemeTo(mst)` | `10309290` | 全局色表逐项 Clone 注册到母版页；[0] 另 `SetColorScheme` |

### 1.3 隐藏系统（答案/解答/解析的可见性）

| 函数 | 入口 | 规格 |
|---|---|---|
| `HidePara(idx, mask, out)` | `10304b70` | 对 +0x994[idx] 逐位置 mask；out[idx] 亦置；返回是否有新位 |
| `GetHiddens(out)` | `10304be0` | 若 +0x874 bit19/18、+0x878 bit3 任一 → out[0x20]|=1/2/4；再判 32B 位图非零；有则整拷 8 dword 到 out；返回是否非空 |
| `RemoveHiddens(out)` | `10304d10` | 位图与 out 双向差量删除；清除 0x874/0x878 对应位时调 `FUN_10304eb0(9/10/0xb)`（撤销等） |
| `IsVisable(compos)` / `IsAnswerVisable(compos)` | `10304f60 / 10304f30` | visualstate!=0 → 0；否则按 `get_hide_index(kind,nibble)` 与 bit `(compos>>4)&7` 判 +0x994 位 |
| `IsHidden(compos)` | `10304fe0` | 同上但返回状态值 2；`IsHidden`∈{0,2} |
| `IsInvisiableMode()` / `IsInvisiable(st)` | `10305060 / 103050e0` | 0x874/0x878 的 6 位（9/10/0xb 状态）；见 `GetVisualState` |
| `GetVisualState(kind)7` | `103072d0` | kind 9: bit19=2、bit17=1；kind 10: bit18=2、bit20=1；kind 0xb: 0x878 bit3=2、bit4=1；否则 0 |
| `GetHiddenState()` | `103073a0` | 状态≠0 → 0x200/0x400/0x800 |
| `get_hide_index(kind,nib)` | `1032a450` | nib==3→kind+8；nib==4→kind+0x10；否则 kind |
| `GetHiddenIndex(compos)` | `1032a480` | `get_hide_index(compos>>28, (compos>>0x15)&7)` |

### 1.4 样式索引迁移（Convert*：旧 sheet → 本 sheet）

`ConvertParaIndex` `10305220`（总驱动：Clone 段落样式并转换 缩进/制表/符号/下沉/块/符号2 六个子索引后 Add）；
`ConvertTabIndex 10305390 · ConvertIndentIndex 103053e0 · ConvertBulletIndex 10305430 · ConvertEdgeIndex 103054c0 ·
ConvertImageIndex 10305530 · ConvertStringIndex 10305590 · ConvertBoxIndex 103055f0 · ConvertCellIndex 10305650 ·
ConvertDimeIndex 103056b0 · ConvertDropcapIndex 10305710 · ConvertBlockIndex 10305780 · ConvertColorSchemeIndex 103057f0 ·
ConvertFontIndex 1005e1a0`。
统一模式 = `src表[idx] → Clone →（递归转换内部引用）→ 本表`vtbl+8`(Add) → 新 idx`；
特殊：EdgeIndex(-1 直通；`esEdgeStyle::Convert` 双向重写)；Image/String/Box/Cell/Dime（src==this 直通，
不复制）；Font（`esFontSheet::ConvertIndex`）。

### 1.5 段落模型生成（★共享 scratch +0x9C0，全族 Q1）

| 函数 | 入口 | 规格 |
|---|---|---|
| `ToModel(line)` / `ToModel(line,compos)` | `10307d40 / 10307df0` | 懒建 +0x9C0 → `esParaLine::CopyStylesFrom(+0x9C0, line)` → 返回 +0x9C0（第二重载**忽略** compos 参数） |
| `GetModel(compos,style,line,flags)` | `103083c0` | `flags&1` 跳过 FindModel；命中→MakeSimilarModel，否则默认 |
| `GetModel(esPara,flags)` | `10308430` | FindModel 未中且 flags==0 且 compos 类≠0xd → MakeDefaultModel；返回后若 flags==0 → `SetFlags(+0x9C0, 6)` |
| `GetModel(tmplList,para,flags)` | `103084f0` | tmplList=NULL→用 +0x940；FindTmpl + `IsSelected` 命中 → Reset(+0x9C0, tmpl) + MakeSimilarModel |
| `FindModel(compos,style,a,b)` | `10308630` | FindTmpl(+0x940)+IsSelected → Reset + 返回 +0x9C0（否则 0） |
| `GetLevelModel(level,style,compos,fontIdx)` | `103081e0` | FindLevelTmpl 命中→Reset+SetFlags；未中→MakeDefaultModel + `AdjustLevelIndent` |
| `GetBulletModel(compos,line)` | `10307ea0` | 沿 +0x940 模板链找 `ESCOMPOS::CheckBullet` 命中者 → Reset(+0x9C0,tmpl) 再 MakeSimilarModel；否则 `MakeDefaultBullet` 换上 |
| `FindSimilaHead(…)` | `10308100` | 沿模板链找"自动题头"（bullet 字 0x7f、CheckParaType==2） |
| `MakeDefault(line,table)` | `10309710` | 表格(0x380)→复制现有模型分支；否则新建 font/paraStyle/indent（含 +0x20/+0x44 间距默认）写入 esPara |
| `MakeSimilarModel(compos,style,base)` | `10309a70` | 以 base 段落为模板做"相似模型"：题头/标题类全拷样式；否则逐位比较并重建（编号/考试头/对齐/悬挂/缩进侵蚀 `ErodeIndent`）；产 +0x9C0 |
| `MakeDefaultModel(compos,style)` | `1030a270` | 新建模型；**字号按 compos>>28 选表**（见 §5-Q4）；`MakeDefaultBullet(8,…)`、`MakeDefaultIndent`；填 +0x20=0x32/+0x44=0x96 |
| `MakeDefaultIndent(para,compos)` | `1030a5e0` | 种类→缩进/悬挂（魔数 -200/`0xff38`、-150/`0xff6a`、-100/`0xff9c`、-20/`0xffec`；每级 -150） |
| `MakeDefaultHead(compos,font)` / `MakeDefaultBullet(kind,compos,font)` | `1030aac0 / 1030ab10` | 见 §5-Q5 |
| `GetParaName(compos)` | `1030a940` | kind→AppString 资源 id 表（0x9b0..0x9b7、0x9b8..0x9ba、0x13d4、0x13d0..2） |
| `EnumDefaultParaModels(cb)` | `103090c0` | 正文 kind 0..5 + 考试头 1..3 逐类 MakeDefaultModel 后调回调 |
| `LoadAsDefaultParaTemples()` | `10309630` | 清 +0x940 后 `esBulletsManager` 局部 + EnumDefaultParaModels |

### 1.6 自动题头（AutoHead）

| 函数 | 入口 | 规格 |
|---|---|---|
| `FindAutoHeader(id)` / `GetAutoHeader(compos,mode)` / `GetAutoHead(compos)` | `10307860 / 10307ce0 / 1032a3b0` | GetAutoHead=`esAutoHeadList::Get(+0x958, compos feature)`；GetAutoHeader 另要求 +0x854 bit0 且 mode≠0 |
| `SetAutoHead(id,val,undo)` / `RemoveAutoHeader(id,val,undo)` / `UndataForAutoHead(id,data)` | `103079a0 / 103078c0 / 10307ae0` | 增删查改 + 撤销注册 **0x401(设)/0x402(删)/0x403(改)**；Undata 反做并返回需要记录的类码 |
| `EnumAuotHeader(cb)` | `10307c30` | 沿自动题头表枚举（回调经 `esBulletsManager` 辅助） |

### 1.7 序列化管线（详见 §4）

| 函数 | 入口 | 规格 |
|---|---|---|
| `BeginSerilize(mode,version)` | `10305e30` | CloneMode→return 0；写 +0x9B8=mode、+0x856=0；写模式→CreateBuffers，否则 ClearBuffers；+0x850=version；return 1 |
| `EndSerilize()` | `10305eb0` | ClearBuffers → `FUN_10301d60(0)` → **+0x856 bit0 → `esParaStyleSheet::TackExamIndexs(+0x734,+0x6d4)`** → 复位 0x856/0x850(=0x2000837)/0x9B8/0x9BC |
| `CreateBuffers()` / `ClearBuffers()` | `10305f30 / 10306070` | 对 19 个持 `esUseInfo` 子表逐个 `CreateBuffer/ClearBuffer`（+0x794/this/+0x674/+0x694/+0x6b4/+0x6f4/+0x6d4/+0x734/+0x754/+0x774/+0x614/+0x634/+0x654/+0x5f4/+0x7b4/+0x7d4/+0x7f4/+0x814/+0x714） |
| `SetStoreSFlags(mask)` | `10306180` | 按各子表 `GetCollectCount()!=0` 汇总 SFlags（表见 §0）；`0x10000000/0x10000` 由参数强制位；结尾 `&= (mask|0xffff)` |
| `SetLoadingSFlags(flags)` | `103065c0` | 版本门控掩码：`<0x1070614→&0x13103ffe`；`<0x109082c→&0x13103fff`；`<0x200012f→&0x33103fff`；否则 `&0xf311ffff` |
| `Serialize(arch,flags)` | `10306650` | **格式见 §4.1** |
| `SerializeDocumentStyle(arch,sel)` | `10306e50` | **格式见 §4.2**（含 11 个文档级历史模型的旧档回读） |
| `CollectDocStyles(mask)` | `10307410` | 按 mask 0x20000000/0x40000000/0x80000000/0x10000000 分别收集 tmpl/role/autohead/examstyle |
| `SupplementCollectStyles()` | `10307490` | 写序列化前补收集：遍历 7 张表，把被引用项标记进对应 esUseInfo（母版页/段落/符号/边框/下沉/块/刷子） |

### 1.8 文件存取 / 默认样式 / 考试模板

| 函数 | 入口 | 规格 |
|---|---|---|
| `SaveParaStylesToFile(path)` | `10305870` | 打开文件 → 头 `zwstr("EduerParaSyles")` → `BeginSerilize(1,0x2000837)` → `CollectDocStyles(0xa0000000)` → 写 version → `Serialize(0xa000ffff)` → EndSerilize |
| `LoadParaStylesFromFile(path)` | `10305a60` | 校验头字符串；`esObject::IsCanRead(dw,1)` → `BeginSerilize(2,dw)` → `Serialize` → EndSerilize |
| `LoadDefault(mask)` / `LoadForm(src,mask)` | `10309380 / 103093b0` | 从全局 sheet 载入：mask 1=段落模板列表、2=角色表（+0x91E bit0）、4=考试样式（+清 0x874/0x878 位）、8=自动题头；末尾 FindModel+SetActiveFont |
| `SetAsExamUITemplates(docId,paraIdx)` | `103089c0` | 清 +0x940；从段落样式 +0x734 克隆生成"题头模型"并注册 **kind 8..0xc**（0xc→kind 8）；建 **【题目】/【答案】/【解析】** 三个文字符号（黑/蓝/蓝字体克隆）；**+0x854|=1** |
| `LearnBullet(src,dst,flags)` | `10308880` | 目标符号非自动时：flags&0xc 学习编号风格（&8 去编号；否则同号不同步→从源 Clone 编号）；flags&0x300 且自动→清零 |
| `CompBullet(a,b)` | `10305d60` | 同索引→0x400；比较 +0x1a 符号索引与 `esBultStyle::CompStyle` |
| `BuilderAnswer(flag,str)` | `103071b0` | 依 flag 位把选项字母（`esExamStyle::GetChoice`）拼到 str（NeedToSeparation 时加 `,`） |
| `GetChoiceMinOffset()` / `GetChoiceLineRightSpace()` | `10304ad0 / 10304b20` | `字体高(esExamStyle+0x26字体) × 字节(+0x18>>16 / +0x14>>8) /10` |
| `CopyExamStyleFrom(src)` | `10305840` | `esExamStyle::CopyFrom(+0x858…)双表索引重写` |
| `GetMstPageList(mgr)` | `10307150` | 枚举 +0x7B4 母版页表 |
| `SetAsCloneMode(n)` | `10305cb0` | 变则写 +0x9B4=n；n≠0→ClearBuffers、version=0x2000837、清 0x9BC/0x856/0x9B8；返回旧值 |
| `ToEpColor(color,kind)` | `103051b0` | 版本 <0x1070311 →（<0x106070b 时 `esSetting::ToEpColor(旧)`）+ `NormalEpColor` |

## 2. esBrushInfo（34 个）

**布局**（0x158B；Clear `100e2280`/Clone `100e2450`/CopyTo `100e2970` 全字段证据）：

| 偏移 | 类型 | 含义 | 证据 |
|---|---|---|---|
| +0x00 | ulong | 0 层标志（Clear 置 `0x00008000`/`0x00800000` 两位；FillRect 暂时改 bit5-7） | `Clear` L610-611；`FillRect` |
| +0x04 | ulong | 保留 | ctor/Clone |
| +0x08 | uchar | **刷子类型码**（见下表） | `IsType`/`GetTypeFlags` |
| +0x0C | ulong | 颜色（纯色） | `SetAsSolidBrush` |
| +0x10/+0x14 | ulong×2 | 图案/渐变参数 | `IsEqual` case 2/0x14 |
| +0x18/+0x1C | float | 角度/焦点（渐变/聚光） | `InitAsSpotlight`；`IsEqual` 0x13 |
| +0x20..+0x77 | byte[0x58] | 渐变/图案数据数组 1（0x16 dword） | `Clone` 循环 |
| +0x78..+0xCF | byte[0x58] | 数组 2 | 同上 |
| +0xD0 | float/ulong | （Clear 置常量 DAT_1057efc4） | `IsEqual` 0x15 |
| +0xD4/+0xD8/+0xDC | ulong×3 | 参数字（渐变） | `IsEqual` 0x13 |
| +0xE0..+0x137 | byte[0x58] | 数组 3（聚光双色 `MakeEpColorForLight` 写 +0xE0/+0xE4） | `InitAsSpotlight` |
| +0x138 | ulong | 参数字（聚光=2） | `InitAsSpotlight` |
| +0x13C | uchar | 子标志（图案预览色?） | `IsEqual` 0x14 |
| +0x13D | uchar | **整体 alpha**（默认 0xFF） | Clear/ctor |
| +0x140 | ulong | **可用位掩码**（NormalMasks=GetTypeFlags；bit24 保留"已初始化"） | `NormalMasks`/`IsUsable` |
| +0x144 | ulong | **禁用位掩码** | `IsUsable`/`OnChange` |
| +0x148 | ulong | 变更位掩码（OnChange 置位；ResetFlags 强制 |=1） | `OnChange`/`ResetFlags` |
| +0x14C | esImage* | 图 1（AddRef/Release，dtor/ Clear 释放） | `SetImage1`/`GetImage1` |
| +0x150 | esImage* | 图 2 | `SetImage2`/`GetImage2` |
| +0x154/+0x156 | ushort | 图 1/2 在 esImageSheet 的**索引缓存**（0xFFFF=未缓存） | `GetImageIndex1/2` |

**类型码（+0x08）与掩码**（`GetTypeFlags 100e1f30`）：`0` 无；`1` 纯色→0x3；`2` 图案→0x400d；
`0x13` 渐变（聚光同码）→0x7a341；`0x14` 二级图像（+0x13C）→0x401d；`0x15` 双图（图2+浮点参数）→0xf82881；
`0x16` 单图（ctor(esImage*) 默认）→0xf82401。

| 函数 | 入口 | 规格 |
|---|---|---|
| `ctor()` / `ctor(esImage*)` / `ctor(ulong color)` | `100e1d90 / 100e1dd0 / 100e1e40` | 清空；image 版=type 0x16+α=0xFF+SetImage1+NormalMasks(1)；color 版=type 1 |
| `dtor` | `100e1ea0` | 释放图 1/2（`FUN_10027530`） |
| `GetTypeFlags(code)` | `100e1f30` | 静态；类型→掩码表（上表） |
| `NormalMasks(on)` | `100e1ff0` | +0x140/+0x148 =（旧值 & 0x1000000）\| 类型掩码 [\|0x1000000]；+0x144 清（on→0，否则保留 bit24） |
| `ResetFlags(on)` | `100e2090` | +0x140 重置；+0x148 &= (掩码\|0x1000000) 后 **\|=1** |
| `SetAsSolidBrush(color)` | `100e2140` | 先清；color==0→type 0；否则 type1 + α 继承（0→0xFF）+ `+0xC = color \| (无α→0xff00 / 有→0xff000000)`★Q6 + NormalMasks(0) |
| `SetAsSolidBrushEx(color)` | `100e21e0` | 同上但 α 取 color>>8 或 >>24 的低字节 |
| `Clear()` | `100e2280` | 释放两图；+0x154/6=0xFFFF；type/色归零；+0xD0=常量；三数组 memset；+0x140/144/148=0；α=0xFF（**注意 +0x00 被置 0x8000/0x800000 两位**） |
| `InitCreate()` | `100e2420` | 仅 +0x154/6=0xFFFF |
| `Clone()` | `100e2450` | 新 0x158 全字段拷贝（数组逐 dword）+ 图 AddRef；索引缓存复位 0xFFFF |
| `operator=` / `operator==` / `operator!=` / `IsEqual` | `100e2680 / 100e26e0 / 100e26a0 / 100e2700` | `IsEqual`：type/α 必等；纯色比 +0xC；渐变比 +0x138/+0xD8/+0xD4/+0x18/+0x1C；0x14 先比 +0x13C 再并 2 分支；0x15 比 `memcmp(0..8)`+浮点+`IsEqualImage2`；0x16 比 memcmp+`IsEqualImage1` |
| `CopyTo(dst)` | `100e2970` | 全字段拷贝 + SetImage1/2（AddRef） |
| `InitAsSpotlight(color,scheme,flag1,flag2)` | `100e2af0` | 类型 0x13；EP 色 → RGB→HSV 提亮/压暗 ±25% → `MakeEpColorForLight` 写 +0xE0/+0xE4；flag2→清色/图 |
| `SetImage1/2` / `GetImage1/2` / `GetImageIndex1/2` | `100e2d90/100e2e40/10431fc0/10431fe0/100e33a0/100e3410` | 设图 AddRef/Release + 缓存失效；取索引时懒查 `esImageSheet(+0x774)` 并缓存 |
| `IsEqualImage1/2` | `100e3480/100e34d0` | 指针同或 `esImage::IsEqual` |
| `FillRectEx(gdc,rect,scheme)` | `100e2ef0` | **在栈上建整个临时 esStyleSheet(0x9c8)** → 类型正规化（1/2/0x13/0x14 直通；其他→纯色；0x15 需图2；0x16 需图1）→ `esBrush::CreateFromBrushInfo` → GDC SaveDC/裁剪 → `esPageRender`+`SetColorScheme` → 生成 esBrush → `vtbl+0x84(Draw)` → RestoreDC；结束恢复 0x154/6 缓存 |
| `FillRect(gdc,rect,alpha,scheme)` | `100e3320` | 暂存 α 与 +0x00 bit5-7 → FillRectEx → 恢复 |
| `Save(path)` / `Load(path)` | `100e3520 / 100e36c0` | AppData 目录 + 文件名（`epGetAppDataPath`）文件读写；`Serialize(1)`/`Serialize(0)` |
| `Serialize(arch)` | `100e38d0` | **格式见 §4.3** |
| `IsType(code)` / `IsUsable(mask)` | `10431ef0 / 10431f30` | `IsUsable`：`(0x140&mask)!=0 && (0x144&mask)==0` |
| `OnChange(mask)` | `10431f70` | `+0x140\|=mask`、`+0x148\|=mask`、`+0x144&=~mask` |

## 3. esPenInfo（12 个）

**布局**（0x0C；`Reset 103da410`/`CopyTo 103da440`/`Serialize 103da470`）：

| 偏移 | 类型 | 含义 | 证据 |
|---|---|---|---|
| +0x00 | ulong | **颜色**（`esRender::MakeSolidColor(颜色,0xff)`；默认 `0xff01` 亮绿） | `Reset`/`CreatePen` |
| +0x04 | ulong | 样式位：低 8 位=虚线型（`SetPenDash`）；bit8-11=起端帽；bit12-15=末端帽；bit16=自动线宽 | `GetDashCap`/`CreatePen` |
| +0x08 | int | **线宽**（1 单位 = 1/400mm；默认 0x50=80=0.2mm；ee-draw `pen_mm 0.25`→100） | `Reset`；TLS 对照 ee_bridge |

| 函数 | 入口 | 规格 |
|---|---|---|
| `esPenInfo(copy)` | `100018c0` | 三 dword 拷贝；**与 `esPenInfo::operator=`、`esImageModifiers::operator=(&&)` 同址折叠**（§6） |
| `ctor()` / `Reset()` / `CopyTo(dst)` | `103da3f0 / 103da410 / 103da440` | Reset：色=0xff01、样式=0、宽=0x50 |
| `IsVisible()` | `100270e0` | `color!=0 && width>=1` |
| `get_pen_width(idx)` | `103da3c0` | 16 项表 `pen_widths[idx]<<2`；越界→1 |
| `GetDashCap()` / `GetStarCap()` / `GetEndCap()` | `103da4f0 / 103da570 / 103da5f0` | 起/末帽相同才给 DashCap（0x100→0、0x200→2、0x300→3）；LineCap 编码 0→0x10(NoAnchor)、0x100→1、0x200→2、0x300→3，缺省 0x10 |
| `CreatePen(render,noStar,noEnd)` | `103da670` | 有 modelbox（文本框）→**调试绿 0xff007f00** + LPM 线宽；否则颜色+宽（bit15=像素宽模式、bit14=固定宽）；`+4&0xff` 虚线→SetPenDash；bit16→`SetAsAutoWidthMode` 且宽度×常量；bit8-15≠0→SetLineCap(起/末, DashCap；参数 non-zero 则强制 0x10) |
| `CreateSolidPen(render)` | `103da880` | 纯色笔；观察模式宽度=0 |
| `Serialize(arch)` | `103da470` | **格式见 §4.4** |

## 4. 序列化格式

### 4.1 esStyleSheet::Serialize（`10306650`）

```
版本 = +0x850；SFlags = +0x9BC

旧格式（版本 < 0x107020f）——无 SFlags，按条件直排子表:
  >0x1060609 : [0x794 esRoleSheet]
  [this+0 esFontSheet][0x674][0x694][0x6b4]
  [0x6f4+0x714 联排 serialize_for_old][0x6d4][0x734][0x754][0x774]
  >0x106070a : [0x614][0x5f4][0x7d4][0x7b4]（>0x107010d 再 [0x7f4]）

新格式（版本 >= 0x107020f）:
  读: 版本<0x1090528 → SetLoadingSFlags(0xf311ffff)
      否则 [dword SFlags][dword SFlags]，两值不等 → +0x9BC=0 + zApiThrowMemoryException ★Q8
  写: SupplementCollectStyles → SetStoreSFlags(flags) → [SFlags][SFlags]（双写防损）
  之后按 SFlags 位依序:
    版本>0x200022f & 0x800 → [0x774]        // 双版本门：两半各覆盖一半版本区间
    0x1→[0x814] 0x2→[0x7f4] 0x4→[this] 0x8→[0x614] 0x4000→[0x634] 0x8000→[0x654]
    0x10→[0x674] 0x20→[0x694] 0x40→[0x6b4]
    0x80: 版本<0x109082b → [0x6f4 联排 dropcap]；否则 0x2000→[0x714] 再 0x80→[0x6f4]
    0x100→[0x6d4] 0x200→[0x734] 0x400→[0x754]
    版本<0x2000230 & 0x800 → [0x774]       // 另一半
    0x1000→[0x5f4] 0x100000→[0x794] 0x1000000→[0x7d4] 0x2000000→[0x7b4]
    0x20000000→esParaTmplList::Serialize  0x40000000→esRoleList::Serialize
    0x80000000→esAutoHeadList::Serialize   0x10000000→SerializeDocumentStyle
    0x10000→[raw 32B @+0x994]（stream vtbl+0xC 读 / +8 写）
```

### 4.2 SerializeDocumentStyle（`10306e50`）

```
读: 版本>=0x1090326 → esExamStyle::Serialize；否则旧 8B/12B 读+索引重写
    版本<0x109072b → 追加读 11 个文档级历史模型（esParaModel::SerializeForHistory 0..0xa）→ esParaTmplList::Add
    版本>0x109082b → 读两 short → +0x990/+0x992
写: esExamStyle::Serialize(+0x858) + [short +0x990][short +0x992]
```

### 4.3 esBrushInfo::Serialize（`100e38d0`）

```
写: [byte 版本=DAT_1069d7d0(≥0x81)]
    [byte type][dword 0xC][dword 0x10][dword 0x14]
    [float 0x18][float 0x1C][float 0xD0]
    [dword 0xD4][dword 0xD8][dword 0xDC]
    [0x58B @0x20][0x58B @0x78][0x58B @0xE0]      // 三次流直写
    [dword 0x138][byte 0x13C][byte 0x13D]
    [byte 图掩码: bit0=图1 bit1=图2] → esImage::Serialize
    [raw 8B @this+0]
读: [byte 版本] 若 <0x81 或 >DAT_1069d7d0 → return 0（拒绝）
    同序读回；图掩码→esImage::FromArchive + SetImage1/2
    收尾: +0x154/6=0xFFFF、masks 清零、NormalMasks(0)
```

### 4.4 esPenInfo::Serialize（`103da470`）

```
写: [dword color][dword style(+4)][dword width(+8)]；读: 同序三 dword。
```

### 4.5 文件包装

`SaveParaStylesToFile`/`LoadParaStylesFromFile`：文件头字符串 **`"EduerParaSyles"`（原文拼写如此，
少一个 t）**，随后 version dword，再 `Serialize(0xa000ffff)`/读侧同参。esBrushInfo 的 `Save/Load`
则直接 `Serialize(1)/(0)` 到 AppData 路径文件。

## 5. 怪癖（Q1–Q12，差分/RE-UNKNOWNS 候选）

- **Q1 ★共享 scratch 段落模型（+0x9C0）**：`ToModel/GetModel/FindModel/GetLevelModel/GetBulletModel/
  MakeSimilarModel/MakeDefaultModel` 全部复用**同一个** `+0x9C0` 实例并直接返回其指针——
  **两次调用间返回值随时被覆盖**；调用方若同时用两个模型即踩踏。（对应 esSeg 批 Q4 的同类作风）
- **Q2** `WriteMode` 判定是 `mode&1`（模式 1/3/5 全是写）——`IsCopyMode/IsFileMode/IsExamMode`
  与它交叉分类，存在"文件写/考试写"等组合。
- **Q3** `EndSerilize` 的 `TackExamIndexs` 依赖 +0x856 bit0（由 `SetAsExamUITemplates` 置位）：
  **未走过考试 UI 模板化的文档不会重建考试索引**。
- **Q4** `MakeDefaultModel` 字号表（compos>>28→字号）：`0→0x41a, 1→0x708, 2→0x5dc, 3→0x578,
  4→0x4b0, 5→0x41a+粗体bit16, 6→0x41a, 7→0x4b0, 其他→0x41a`（=1050/1800/1500/1400/1200 单位）。
- **Q5** `MakeDefaultBullet` 的符号字符码：0x7f=自动题头标记；0x44=圆点（kind3 或 param3）；
  '、'(kind5/kind0xf 默认)；"附录:"(kind7)；"(...)"(考试 kind 默认)；kind 0xf 另有卷名/答案/解析
  三态（【】字符串在 `SetAsExamUITemplates` 生成）与 `|=0x80` 自动位。
- **Q6 ★颜色 α 编码怪癖**：`SetAsSolidBrush` 在"高字节 0"时写 `color|0xff00`（不是常规
  `|0xff000000`）——**EE 的 epColor 位布局与 COLORREF 不同**，直接按 0xAARRGGBB 理解会错；
  差分复核项。
- **Q7** esBrushInfo 三个掩码（0x140/0x144/0x148）里 **bit24（0x1000000）被 NormalMasks/ResetFlags
  特殊保留**（"掩码体系已启用"哨兵）。
- **Q8 ★SFlags 双写校验**：新版 Serialize 读侧若两 dword 不等 → **清零 SFlags 并抛异常**
  （防半截档）；写侧同值写两遍。
- **Q9** `+0x774 esImageSheet` 的序列化有**两个互斥版本门**（`>0x200022f` 早排 / `<0x2000230` 晚排）
  ——恰好互补，等价于无条件；旧格式分支同理（放到 `0x754` 之后）。
- **Q10** `FillRectEx` **每次调用在栈上构造一个完整 esStyleSheet**(0x9c8B)——重则在文本拉框/表格
  绘制路径上放大；且会临时改写 this（α、类型归 1、清 +0x18/0x1C），结束后恢复图索引缓存。
- **Q11** `esPenInfo::CreatePen` 在"文本框"（有 modelbox）场景用**硬编码调试绿 0xff007f00 + LPM
  线宽**（写死发给 egPen）——文本框描边色不取自 penInfo，差分时别误判。
- **Q12** `ToModel(line,compos)` 的 compos 参数**完全被忽略**（两个重载函数体 164B 等价）——
  按签名使用会得到与预期无关的模型。

## 6. 符号折叠（同址多符号；解导入面时防误读）

| 地址 | 本批符号 | 折叠群（节选） |
|---|---|---|
| `18c0` | esPenInfo::esPenInfo(copy) | `esPenInfo::operator=`、`esImageModifiers::operator=(&&)` |
| `esBlockSheet::operator=` | 本批被用于 **所有** 子表赋值（+0x5F4..+0x7F4 的 esBrushSheet/esColorSheet/… 全部显示为 `esBlockSheet::operator=`） | 疑似模板/ILT 收敛：各 sheet 的 `operator=` 共体 |
| `10022000` | 析构清理辅助（EnumAuotHeader/DefaultParaModels/RemoveHiddens 内共用） | `TLaterParam::~`/栈展开辅助族 |
| `1031cd60/cd90/cc90/cdc0/ce40/cee0` | 自动题头表底层（增/删/枚举/查 id/设 map/查 map） | 模板收敛（esAutoHeadList 内联） |

## 7. 与动态桥（ee-draw）的相关性（S1 对照点）

- **线宽单位**：`esPenInfo::Reset` 宽=0x50(80=0.2mm)；ee-draw `pen_mm=0.25` → 100 —— 与本批
  1 单位=1/400mm 完全吻合；`ee_draw_circle` 的"默认 80 要改 100"就是照顾这里。
- **填充通道**：桥里 `esShapePath::SetSolidBrush(color)` 的底层即 esBrushInfo：
  `SetAsSolidBrush` 写 type=1/+0xC 颜色/+0x13D α + masks —— "GetBrush() 非空才算填上"对应
  +0x140 掩码 bit 与 brush 对象被挂进 shape 的 brush 槽两个条件。
- **加粗点（dots）**：走引擎自身 `esShapeLine(pt,0x6001,flags)` 构造，其笔参即 esPenInfo
  （颜色/宽/帽），这也是"手工拼装对象会坏链"教训的旁证：样式字/笔刷槽都由这些表驱动。
- **图片填充**：brush 类型 0x15/0x16 持 esImage*，序列化时内嵌（`esImage::Serialize`）——
  导出/重画插图中的位图资源走这条链。
- **隐藏系统**：答案/解析可见性由 +0x874/+0x878/+0x994 位图控制（教师版/学生版切换），
  重画时不要清这些位（会影响"显示答案"状态）。

---

**遗留（待后续批/差分）**：+0x968..0x98B 九 dword 状态块用途、+0x00 旗标 0x8000/0x800000
语义、Q6 α 编码、Q7 bit24 语言、笔宽表 `pen_widths` 常量、`esBrush::CreateFromBrushInfo` 输出类
（esSolidBrush/esHatchBrush/esGradientBrush）族（后续批 esShape/brush 族时核）。
