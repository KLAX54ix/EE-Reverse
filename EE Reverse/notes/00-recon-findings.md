# EE (EduEditer) 逆向工程 — 阶段 0 侦察报告

日期：2026-10-16
工作目录：`D:\EE Reverse`
目标：`D:\educationeditor\EduEditer`（Editer.exe x86 / MFC）
参照文件：`D:\Douding\八下四边形分类汇编.wsd`（19,935,484 bytes）

---

## 1. REA（reverse-engineer-anything）可用性结论

**结论：REA MCP 服务器可用，但本机缺少原生反编译器，需补装 Ghidra 才能做静态反编译。**

### 已确认可用（live 会话实测）

| 项目 | 实测值 |
|---|---|
| 包名/版本 | `rea-agents` **6.5.0**（`D:\npm-global\node_modules\rea-agents`） |
| 服务器 | `rea` 6.5.0，启动于 2026-10-16T03:12:13Z |
| MCP 客户端 | `dsh-mcp-client` 0.0.1，协议 2026-07-28 |
| 工具总数 | **207** 个（cli 命令 153，prompts 6） |
| catalog 摘要 | tools_sha256 `805433f1…8ded`，combined `405725e7…a4f4` |
| skill 期望版本 | 42 |

实测成功的能力：
- `open_binary` 成功绑定 `Editer.exe`：format=pe，architecture=**x86**，
  sha256 `3b12a439eb00da965fb1232271683b653776d5bc54c8ec172f70dd20037ee2d8`
- `binary_session`：`target_support.status = "supported"`，managed=false
- managed 静态解析（`inspect_managed_artifact/members/boundaries`）— 本目标不适用（MFC 非 .NET）
- artifact/archive 图（`inspect_artifact` / `extract_artifact`）不可用（.wsd 非归档格式）
- **Frida 运行时插桩可用**：`list_frida_devices` 返回 local / socket / barebone 三设备
- `inspect_pe_resources`、`inspect_electron_*`、`inspect_go_binary`、`inspect_rust_binary` 等

### 已确认不可用（阻塞项）

`binary_overview` 返回 `provider_unavailable`，自动选择 provider 时三个候选全部被拒：

| provider | 状态 | 原因 |
|---|---|---|
| **ghidra** | `not_configured` | 未设置 `GHIDRA_INSTALL_DIR`（要求已解压的 **Ghidra 12.1.x**） |
| hopper | `unsupported_host` | Hopper 仅 macOS |
| ida | `not_configured` | 未设置 `REA_IDA_MCP_CONFIG` |

连带不可用：`analyze_function`、`procedure_pseudo_code`、`search_strings`、
`trace_feature`、`get_call_graph`、`xrefs`、`set_address_name` 等全部原生分析工具。

另外两个 REA 自带的“免反编译器”退路在本机也失败：
- `execute_rizin_command` → `ERR_REA_WINDOWS_NATIVE`（REA 未内置 Windows 版 rizin）
- `inspect_with_objdump` → `ERR_REA_WINDOWS_NATIVE`（无 objdump）

### 本机现状

| 工具 | 状态 |
|---|---|
| Ghidra | ❌ 未安装（**正在下载 12.1.4**，569,649,598 bytes） |
| JDK | ✅ `D:\java`，Java 24.0.1 x64 |
| IDA Pro | ✅ `D:\IDA`（7.5，含 `hexrays.dll` 反编译器 + `idapython3.dll`） |
| Python | ✅ 3.12（`C:\Program Files\Python312`） |
| Node/npx | ✅ `C:\Program Files\nodejs` |
| rizin / objdump / 7z / frida CLI | ❌ 全部不在 PATH |

### 修复路径

1. 解压 Ghidra 12.1.4 → `D:\EE Reverse\tools\ghidra_12.1.4_PUBLIC`
2. 设 `GHIDRA_INSTALL_DIR` 指向它
3. REA 的 MCP 服务器进程环境在启动时确定 → **用 REA CLI 在带该环境变量的新进程中跑原生分析**
   （`parseConfig` 读取 `env.GHIDRA_INSTALL_DIR`）；MCP 侧要生效需重启 MCP
4. 备选：本机 IDA 7.5 自带 Hex-Rays，可绕过 REA 直接 `idat.exe -A -S<script>` 批量反编译

---

## 2. 目标软件画像

`D:\educationeditor\EduEditer`（223 文件，108.7 MB）

```
Editer.exe          5.13 MB  x86 MFC 主程序（7 sections，.rsrc 27 MB）
EpAddin.dll          166 KB  OLE 服务器插件（"WORD图形插件 / OLE EP Word 插件"）
eslib.dll            6.94 MB  ★ 绘图/文档引擎，导出 16,123 个符号
eulib.dll            1.02 MB  ★ MFC 扩展框架（xMDIFrameWnd/xDialog），导出 3,305
eglib.dll            0.73 MB  ★ GUI 层（eg_gui：GCmdUI/GCmdUI/HDC），导出 837
zoro.dll                     ★ 基础库（zArchive/zList/zItem/zwstr），导出 1,536
eweb.dll / media.dll / doc2docx.exe / Register.exe / EE_Setup.exe
GdiPlus.dll / SDL2.dll / sqlite3.dll / zip.dll / zlib1.dll / ffmpeg 系列
Data\RES1..9.SDS, Res5.sds, extra.sds, STD001.SDS  ← 均为 OLE 复合文档 (D0CF11E0)
Templates\*.tpl, Masters\*.mst, Language\eduediter_*.wsd, Images\*.wsd
Example\*（含「十分钟EE从入门到精通2.05（公式编辑+绘图+PPT）.wsd」）
```

### Windows 注册

- `.wsd` → ProgID **`Editer`**，`shell\open\command = "…\Editer.exe" "%1"`
- ProgID **`Editer.Graphics`**（"EduEditer 图形"），CLSID `{905CE936-4A7A-4BE0-BAEB-BC3BDBFC233E}`，
  `Insertable`，`protocol\StdFileEditing\server = "…\Editer.exe"`
  ⇒ EE 是 **可插入 Word 的 OLE 服务器**
- 遗留路径 `D:\edu\EduEditer`（旧安装，TypeLib 仍指向该处）

---

## 3. `.wsd` 文件格式（初步）

**未加密、未整体压缩**（语言文件熵 2.2–4.7，含大量可读 UTF-16 字符串）。

头部（用户文件实测）：

```
00 "WSTUDIO7" 08 00 02 00 01 00 00 00 00 00 00   ← 魔数 + 版本字节
FF FE FF 00  × 12                                  ← 调色板/默认样式表
00×8  19 0C 46 00                                  ← 保存者/构建标识
"FS Math Type" / "PM Extra" / "Times New Roman" …  ← UTF-16 字体表
```

- 魔数 = `\0WSTUDIO<版本数字>`：实测存在 **WSTUDIO2 / 4 / 5 / 7**（示例文件为 2，图标为 4/5，当前文档为 7）
- 用户文件内嵌 **321 个 PNG**（`89 50 4E 47`，IHDR 校验通过，如 0x1A7 处 141×97 RGBA）
  与 **210 个 BMP** 候选 ⇒ 模糊原图以 PNG/BMP 原样存放
- 无任何 zlib 流可inflate（`78 9C/01/DA/5E` 全部失败）⇒ 对象图是自有二进制序列化，
  对应引擎里的 `zArchive` / `esXxx::Serialize(zArchive&, esStyleSheet*, unsigned short)`
- 文件尾部（0x12FF000 附近）熵降到 ~4，是结构化表区
- 引擎含 `esZipDocReader` / `GOleDoc` / `esOleObject` ⇒ 存在 OLE 文档与 zip 打包两条路径

---

## 4. ★ 核心发现：绘图引擎的内部 API 已全部导出

`eslib.dll` 以 **MSVC 修饰名**导出整套 C++ 文档/图形对象模型（16,123 项），
等于一份带完整签名的事实上的 SDK：

### 图形图元（可直接构造的对象类）

| 类 | 导出数 | 推测用途 |
|---|---|---|
| `esEQLine` | 49 | 几何/等分线 |
| `esSegLine` / `esSegLines` | 23 / 16 | 直线段 |
| `esSegArc( Base / Face / Ruler )` | 16 / 31 / 22 / 17 | 圆弧、扇形、量角器 |
| `esSegBezier` / `esBezier3` / `esCtrlBezier` / `esCurve` | 26 / 22 / 16 / 20 | 贝塞尔与曲线 |
| `esSegPolygon` | 21 | 多边形 |
| `esSegRect` / `esSegRoundRect` / `esSegGroupRect` | 33 / 22 / 22 | 矩形/圆角矩形/组合框 |
| `esAxisObj` / `esSegAxis` / `esSegSimpleAxis` | 40 / 36 / 16 | 坐标轴 |
| `esShapePath` / `esMoldPath` / `elfPathGeometry` | 73 / 17 / 47 | 路径/布尔形状 |
| `esCtrlPoint` / `esSegPoint` / `esLineHead` / `esConner` | 46 / 15 / 25 / 53 | 控制点/端点/箭头/角 |
| `esSegFormulaBox` / `esSegTextBox` / `esSegText` / `esShapeBox` | 37 / 21 / 20 / 13 | 公式框/文本框/标注 |
| `esGraph` | 59 | 函数图象 |
| `esSnapManager` | 88 | ★ 吸附对齐（精准作图的关键） |
| `esDrawingModifier` | 39 | 绘图修饰器 |
| `esCanvas` / `esDocPage` / `esPageList` | 249 / 85 / 107 | 画布/页面 |
| `esRender` / `D2DRenderTarget` | 72 / 75 | GDI+ / Direct2D 渲染 |

### 每个对象都导出完整生命周期方法（示例）

```cpp
virtual void esSegTolerance::Draw(esRender*, tag_DRAWPARAM*, Gdiplus::Matrix const*);
virtual void esSegTolerance::Load(elfPage*, elfSubject*, tag_DRAWPARAM*);
virtual H  esSegTolerance::SetPointPos(esSnapManager*, int, unsigned, Gdiplus::Matrix*);
virtual void esSegTolerance::MovePoint(zPoint, int, unsigned, esObjCheck*);
virtual void esSegTolerance::Serialize(zArchive&, esStyleSheet*, unsigned short);
virtual void esSegTolerance::Undo(unsigned short, zArchive&, zArchive&);
virtual void esSegTolerance::CopyFrom(esObject const*, esStyleExchanger*);
virtual H  esSegTolerance::IsEqual(esObject*, esStyleSheet*);
```

⇒ **构造/落盘/吸附/撤销/复制全都可编程调用**，不必从汇编层重建绘图算法。

### 命令分发层

- `esObject::ExecuteCommand(H)`、`esSegList::ExecuteCommand(H)`、`TProKpr::ExecuteCommand(H, unsigned)`
- `esStage::ExcuteCommand(unsigned short)`、`esStage::OnStageCommand(unsigned short)`
- `xCommandParameters::m_nCmdID / m_dwParam / m_intParam / m_strParam`
  ⇒ UI 是**命令 ID + 参数**驱动，命令 ID 表可从 `Editer.exe` 的 `.rsrc`（27 MB 菜单/工具栏）提取

### 其他值得注意的子系统

- `esScriptBuilder` / `esScriptWorkshop` / `esCalligraph` / `eGlyphType`
  ⇒ "Script" 指**手写笔迹/书法**（`FittingForLine/Rect/Ellips/Roundrect/Arrow/Dot/Point`，
  `DownEvent`、`AlignToAngle`）——是"涂鸦自动整形"功能，**不是宏语言**，勿误判
- `esQBank` / `ee_qbank_download` / `ee_qbank_load_folder` / 字符串 `http://127.0.0.1:8080/api/rest`
  ⇒ 题库与在线素材，含本地 REST 线索
- `esRole` / `esRoleItem` / `eaActor` / `eaAction` / `TAgent`
  ⇒ 角色/动画/自动代理（互动课件）
- `esOleObject` / `esShapeOle` / `GOleDoc` / `OleLoad|OleSave|OleCreateFromData`
  ⇒ OLE 嵌入链路

---

## 5. 可用的"开放接口"候选路径

| # | 路径 | 原理 | 优点 | 缺点 |
|---|---|---|---|---|
| **A** | **EMF 中转** | EE 支持导入/导出 EMF、WMF（文件过滤器实测存在），EMF 是标准矢量格式 | 立即可用、坐标绝对精确、无需注入 | 图形在 EE 内是否保持可编辑的矢量对象待验证；"控制 EE"程度低 |
| **B** | **进程内桥接（Frida / 注入 DLL）** | Attach `Editer.exe` → 调用 `eslib.dll` 导出的 `esXxx` 类方法，直接向活动页增删图元 | 真正的"改装+开放接口"；对象与手工绘制完全一致、可编辑可撤销 | 需摸清文档/画布对象获取路径；注入有稳定性风险 |
| **C** | **`.wsd` 离线读写** | 逆向 `zArchive` 序列化，直接生成/修改 `.wsd` | 无需运行 EE，可批量 | 工作量最大；版本 WSTUDIO2→7 兼容复杂 |
| **D** | **OLE 自动化** | `Editer.Graphics` OLE 服务器 | 官方支持的互操作 | 仅支持嵌入/编辑，非 IDispatch 自动化脚本接口，可编程性弱 |

推荐：**A 作快速可用层 + B 作主线**，C 视需要补。

---

## 6. 待决问题

1. 允许我**启动 Editer.exe 并 attach Frida** 做运行时观测吗？（会在屏幕上打开 EE）
2. 允许在 EE 安装目录**写入探针/代理 DLL**吗？（DLL 劫持注入需要；也可只用 Frida 免改文件）
3. 首个交付优先级：先"能画出精确图形"（A），还是先"开放完整接口"（B）？
4. `.wsd` 测试是否使用副本（避免污染 `八下四边形分类汇编.wsd`）？——建议是。

---

## 7. 已产出的工具脚本

- `recon\peinfo.py` — PE 导入/导出/节表解析（无依赖）
- `recon\analyse_exports.py` — MSVC 修饰名 → 类/方法清单归类
- `recon\probe.py` — 字符串/hexdump/zlib/字节直方图
- `recon\wsd_probe.py` — `.wsd` 容器结构、熵图、内嵌图像签名、deflate 尝试
- `recon\eslib_exports.txt`（16,123 行）、`eulib_exports.txt`、`eglib_exports.txt`、`zoro_exports.txt`、`EpAddin_exports.txt`
