# EE (EduEditer) 绘图原理 — 已验证模型

日期：2026-10-16
目标：`D:\educationeditor\EduEditer\Editer.exe` (x86 MFC) + `eslib.dll`（绘图引擎，导出 16,123 个符号）
证据来源：
- 静态：Ghidra 12.1.4 headless 项目 `analysis\ghidra-proj`（程序 `/eslib.dll`，imageBase `0x10000000`），反编译输出 `analysis\decomp-shape.txt`
- 动态：Frida 17.23.3 直连 `Editer.exe`，在用户真实绘图时用 Interceptor 抓取寄存器与栈
- 端到端：`mcp-server\ee_mcp_server.py` 通过 MCP 协议实际作图，用户目视确认

---

## 1. 一句话结论

EE 的画布绘图在模型层极其简单：**创建 `esShapePath` 对象 → 填几何 → 挂进画布的双向链表**。
没有任何需要重建的绘图算法；引擎把构造、序列化、吸附、撤销全部作为导出方法提供。

---

## 2. 已验证的绘图链路

### 2.1 UI 真实绘图时引擎被调用的顺序（Frida 实测）

对每一次用户画图，捕获到完全一致的序列：

```
esShapeCreator::Initialize(toolId)           ← 选择工具
esShapeCreator::ClearCreateInfo()
esShapeCreator::GetCreateType()
esShapeCreator::SetCreateInfo(snapMgr, penInfo&, ulong)
esCanvas::AddItem(canvas, newShape, 1)       ← 把新图元挂进画布
```

实测寄存器（ia32 `__thiscall`，`this` 在 ECX，参数在栈上）：

| 调用 | ECX (`this`) | 栈参数 |
|---|---|---|
| `ShapeCreator::Initialize` | `0xaa79960` | `0x4701`（直线工具）/ `0x4281`（矩形工具） |
| `ShapeCreator::SetCreateInfo` | `0xaa79960` | `snapMgr=0xeff660`, `penInfo=NULL`, `type=0x4701` |
| `esCanvas::AddItem` | `0xa7729a8`（画布） | `shape=0x10562768`, `flags=1` |

**工具命令 ID（UI → 图元类型）**

| ID | 工具 |
|---|---|
| `0x4701` | 直线 |
| `0x4281` | 矩形 |
| `0x4284` / `0x4285` | 其他图形元素（未逐一确认） |

> 注意：UI 的直线工具与矩形工具**都**产出 `esShapePath`（vtable `0x6d77c344`），
> 不是 `esSegLine`/`esSegRect`。`esSegLine` 等是内部段对象，不是画布一级图元。

### 2.2 `esCanvas::AddItem` 的真身（反编译，RVA `0x1c45d0`）

```c
void esCanvas::AddItem(esCanvas *this, esShapeBase *shape, int flags) {
  if (flags == 0) {
    *(u32*)(shape + 0x44) = *(u32*)(this + 0x34);
    if (*(int*)(this + 0x38) == 0) *(esShapeBase**)(this + 0x38) = shape;
    else *(esShapeBase**)(*(int*)(this + 0x34) + 0x48) = shape;
    *(esShapeBase**)(this + 0x34) = shape;
  } else {
    if (*(int*)(this + 0x34) == 0) *(esShapeBase**)(this + 0x34) = shape;
    else *(esShapeBase**)(*(int*)(this + 0x38) + 0x44) = shape;
    *(u32*)(shape + 0x48) = *(u32*)(this + 0x38);
    *(u32*)(shape + 0x44) = 0;
    *(esShapeBase**)(this + 0x38) = shape;
  }
  esCalligraph::ResetLineWidth((esCalligraph*)shape, (int)this);
  if (*(int*)(shape + 0x3c) != 0) {
    SetSelObj(this, shape, 2);
    if (*(int*)(this + 0xa4) == 0) SetActive(this, shape);
  }
}
```

⇒ **纯链表插入**：画布 `+0x34` / `+0x38` 是链表首尾，图元 `+0x44`/`+0x48` 是 prev/next。
遍历画布即从头指针沿 `+0x48` 走。

### 2.3 `esShapePath::CreateFromPathData` （反编译，RVA `0x19fa10`）

```c
static esShapePath* __cdecl
esShapePath::CreateFromPathData(tagPOINT* pts, unsigned char* types,
                                int count, int close);
```

内部流程（已逐行核对）：

```c
obj = operator_new(0x74);                 // 对象大小 116 字节
__autoclassinit2(obj, 0x74);              // 清零
esShapePath::esShapePath(obj);            // 默认构造，RVA 0x19e0d0
*(u32*)(obj + 0x34) = 0x40700ff;          // 默认样式（描边色/线宽）
for (i = 1; i < count; i++) {
    t = types[i];
    if (t == 0x01 || t == 0x03) { ...; 在 pts[i-1] 处收一条段; local_40 = i-1; }
    if (t == 0x80 && segList) { if (close) CloseFigure(segList);
                                AddSegList(obj, segList); segList = NULL; }
    if (t == 0x03) i += 2;                // 三次贝塞尔一次吃 3 个点
}
if (segList) { if (close) CloseFigure(segList); AddSegList(obj, segList); }
if (*(int*)(obj + 0x60) == 0) {           // 一条段都没挂上
    析构并丢弃 → 返回 null              // ← 这是"返回 null"的唯一原因
}
```

**三种实测行为**

| points | types | close | 结果 |
|---|---|---|---|
| 4（首点重复） | `00 01 01 80` | 0 | 成功，但**少一条封边** |
| 4（首点重复） | `00 01 01 80` | 1 | 成功，完整闭合 ✅ |
| 4（首点重复） | `00 01 01 01` | 1 | **返回 null**（缺 0x80 条目） |

⇒ 规则：
1. `types[i] == 0x01` 在 `pts[i-1]` 收一条段；
2. **必须有一条显式 `0x80` 条目**，否则工厂析构对象并返回 null；
3. `0x80` 只有在 `close` 参数非 0 时才真正闭合，否则静默少一条边。

**GDI+ 兼容的图元约定**（本模型据此实现）

```
直线:     pts = [A, B]                     types = [00, 01]                      close=0
折线:     pts = [P0..Pn-1]                 types = [00, 01×(n-1)]                close=0
闭合多边形: pts = [V0..Vn-1, V0]            types = [00, 01×(n-1), 80]            close=1
圆:       72 边形闭合多边形（贝塞尔形式被引擎拒绝，见 §5）
```

### 2.4 `esShapePath` 内存布局（对象大小 `0x74`）

| 偏移 | 含义 | 实测值示例 |
|---|---|---|
| `+0x00` | vtable | `0x6d77c344` = `??_7esShapePath@@6B@` |
| `+0x04` | 类型/标志 | `0x330f` |
| `+0x08` | **所属画布回指针** | `0x0a7729a8` |
| `+0x10` | 对象 ID（挂入后由引擎分配） | 0 → 递增 |
| `+0x14`/`+0x18` | 缓存锚点 p1 | (12000, 17000) |
| `+0x1C`/`+0x20` | 缓存锚点 p2 | (22000, 23000) |
| `+0x24..0x30` | 缓存包围盒 L/T/R/B | (11300,16300,22700,23700) |
| `+0x34` | 样式 | `0x040700ff` |
| `+0x44` / `+0x48` | 链表 prev / next | — |

包围盒比顶点各外扩 **700 单位**，即描边半宽 → 默认线宽 1400 单位。

缓存几何需要引擎重算：调用 `?RecalcLayout@esShapePath@@MAEXXZ`（RVA 见导出）。
未调用时 `+0x14..+0x30` 全为 0，但仍能渲染。

---

## 3. 关键 API（全部为 eslib.dll 导出，可直接调用）

| 作用 | 导出名 | 调用约定 |
|---|---|---|
| 建路径图元 | `?CreateFromPathData@esShapePath@@SAPAV1@PAUtagPOINT@@PAEHH@Z` | `__cdecl`，RVA `0x19fa10` |
| 挂进画布 | `?AddItem@esCanvas@@QAEXPAVesShapeBase@@H@Z` | `__thiscall` |
| 取活动画布 | `?GetActiveCanvas@esPageList@@QBEPAVesCanvas@@H@Z` | `__thiscall` |
| 取所属文档 | `?GetDocument@esPageList@@QBEPAVesBaseDoc@@XZ` | `__thiscall` |
| 重算几何 | `?RecalcLayout@esShapePath@@MAEXXZ` | `__thiscall` |
| 画布宽/高 | `?GetWidth@esCanvas@@QBEHXZ` / `?GetHeight@esCanvas@@QBEHXZ` | `__thiscall` |
| 画布矩形 | `?GetFrameRect@esCanvas@@QAEABVzRect@@XZ` | `__thiscall` |
| 取形状链表 | `?GetShapeList@esCanvas@@QAEPAVesShapeList@@XZ` | `__thiscall` |
| 标记脏 | `?SetModifiedFlags@esCanvas@@UAEXH@Z` | `__thiscall` |

### 对象寻址（无需反编译即可定位活对象）

1. `eslib.dll` 导出 **537 个 vtable**（`??_7<Class>@@6B@`）→ 拿到类 vtable 地址；
2. 扫描可写内存中首字等于该 vtable 的地址 → 得到该类所有活对象。

实测（单文档）：`esDocument` 2 个、`esPageList` 5 个、`esCanvas` 200+、
`esSegLine` 500+、`esSegRect` 403、`esSegArc` 500+。

`esPageList` 内嵌于 `esDocument` 的 `+0xD00`；`esUndo` 内嵌于 `esPageList` 的 `+0x24`。

---

## 4. 引擎规模画像

`eslib.dll`（7.27 MB）导出 **16,123** 个符号：537 vtable、1,472 构造函数、
242 个 `Serialize`、55 个 `SetPointPos`。

| 子系统 | 代表类 | 说明 |
|---|---|---|
| 图元 | `esShapePath`(73) `esSegLine` `esSegRect` `esSegArc*` `esSegPolygon` `esShapeGroup`(80) | 画布一级图元是 `esShapePath` |
| 交互绘图 | `esDrawingModifier`(39) `esShapeCreator`(10) `esSnapManager`(88) | 鼠标→吸附→构造 |
| 画布/页 | `esCanvas`(249) `esPageList`(107) `esDocPage`(85) | 链表 + 页管理 |
| 文本/公式 | `esTextUI`(274) `esPara`(200) `esSegFormulaBox`(37) `esSegTextBox`(21) | 字母标注与公式 |
| 渲染 | `esRender`(72) `D2DRenderTarget`(75) `esPainter` | GDI+ / Direct2D |
| 手写笔迹 | `esScriptBuilder`(52) `esCalligraph` `esScriptWorkshop` | **"Script" = 笔迹整形，不是宏语言** |
| 动画/角色 | `eaActor`(98) `eaAction` `esRole` `TAgent`(64) | 互动课件 |
| 题库/素材 | `esQBank`(55) `ee_qbank_download` | 含 `http://127.0.0.1:8080/api/rest` 线索 |

---

## 5. 已验证 / 未验证 / 已知限制

**已验证（用户目视确认）**
- 直线、折线、闭合多边形（三角形、矩形、平行四边形）——几何精确，包围盒可复算
- 圆——以 72 边形闭合路径实现；`RecalcLayout` 包围盒与理论圆外接矩形完全一致
- 画布边界查询（该文档活动画布 **62654 × 38400** 页面单位）
- 形状枚举（沿画布链表遍历）

**未验证 / 待补**
- 贝塞尔曲线：引擎拒绝全 0x03 类型数组（返回 null），尚未找到正确类型布局
- 文本/字母标注（A/B/C…）：需要 `esSegTextBox` / `esSegFormulaBox` 的创建路径
- 角度标记（直角符号、等角弧）：可用圆弧段构造，未实现
- 样式控制（颜色、线宽、填充）：`+0x34` 已定位为样式字，但字段位含义未解
- 画布尺寸调整：`?SetAsBorderRect@esCanvas@@QAEXHHHH@Z` 存在但未验证
- 撤销集成：直接 `AddItem` 绕过 `esUndo`，Ctrl+Z 可能无法撤销注入的图元
- 删除图元：未实现（可从链表摘除，需处理选择态）
- 页面单位换算：实测一图 X 10454..34454、Y 8012..25412；猜测约 1/100 mm，未证实

**环境风险（重要）**
- 崩溃根因已定位并修复：Frida `Memory.alloc` 的内存随 `NativePointer` 被 GC 释放，
  把指针转成字符串后第二次分配就会释放第一块，随后写入已释放内存 →
  `faulting module frida-agent.dll, 0xc0000005`。修复方式是**在一次 JS 调用内完成
  分配+填充+引擎调用**（见 `ee_bridge.js` 的 `createPath`）。
- 同一进程**只能挂一个 Frida 客户端**；REA 的 Frida 会话与本桥并用会互相干扰。
- 早期用 `esPageList::CreateObject` 批量探测 200 次会创建大量页对象并导致后续崩溃；
  该方法实为 `CreatePage(ushort)` 的薄封装，**不是图元工厂**，勿再调用。

---

## 6. 交付物

```
D:\EE Reverse\
├─ notes\
│   ├─ 00-recon-findings.md      阶段0：REA 可用性结论 + 目标画像 + .wsd 格式
│   └─ 01-drawing-model.md       本文档：已验证绘图模型
├─ bridge\
│   ├─ ee_bridge.js              ★ 注入 EE 的 Frida 桥（导出解析 + RPC）
│   ├─ ee_client.py              直连控制器（info/instances/call/chain）
│   ├─ ee_draw.py                ★ 绘图原语（createPath / addItem / 几何校验）
│   ├─ ee_hooks.js / ee_hooks2.js 绘图调用记录器
│   ├─ ee_hook_recorder.py       记录器驱动
│   ├─ discover.py / factory_scan.py / stage_test.py / inspect_shapes.py  侦察脚本
│   └─ probe1..3.js              早期运行时探针
├─ mcp-server\
│   ├─ ee_mcp_server.py          ★ MCP 服务器（stdio JSON-RPC，零依赖）
│   └─ test_client.py            冒烟测试
├─ recon\                        PE/字符串/导出表分析工具与导出清单
├─ analysis\
│   ├─ ghidra-proj\              ★ Ghidra 12.1.4 已分析项目（可反复反编译）
│   ├─ decomp-shape.txt          CreateFromPathData / AddItem / 构造函数 反编译
│   └─ hooks*.jsonl              Frida 抓取的绘图调用记录
└─ samples\ref-copy.wsd          参照文档副本（原文件从未改动）
```

### MCP 工具集（`ee-draw`，已注册进 DSH）

| 工具 | 状态 |
|---|---|
| `ee_status` | ✅ 连接状态 / 引擎基址 / 活动画布 |
| `ee_canvases` | ✅ 列出所有候选画布与排序依据（画布选择确定化，§6 上方说明） |
| `ee_canvas_bounds` | ✅ 画布尺寸与框 |
| `ee_draw_line` `ee_draw_polyline` `ee_draw_polygon` `ee_draw_rect` | ✅ 走 `CreateFromPathData` |
| `ee_draw_circle` | ✅ **真 `esSegCircel`**（不是多边形近似），§7.1 |
| `ee_draw_arc` | ✅ 真 `esSegArc`，§7.9 |
| `ee_draw_label` | ✅ 字母标注，自动匹配文档字体与斜体，§7.8 |
| `ee_draw_angle_mark` | ✅ 直角符号 / 等角弧 / 双弧，§7.9 |
| `ee_list_shapes` | ✅ 带 vtable 类名校验，§7.6 |
| `ee_delete_shape` | ✅ 链表摘除，§7.2 |
| `ee_redraw` | ✅ 强制重绘（所有工具都会自动重绘） |
| `ee_diag` | ✅ 只读诊断：`canvases` `fontsheets` `hexdump` `readu32` `readstr` `vtname` `vtslots` `zwstr` `scantext` `shapecount` `recalc` `names` `expaddr` `call` `callvirt` `trace` `tracelog` |
| `ee_new_canvas` | ⚠️ **不可用**（需 UI 插入点上下文），§7.3、`02-next-steps.md` §2.1 |

所有绘图工具都接受可选的 `canvas` 参数覆盖自动选择。

---

## 7. 附录：原生圆形 / 删除 / 建画布（第二轮补充）

### 7.1 真圆形 = `esSegCircel`（不是多边形）

`CreateFromPathData` 只能造直线/贝塞尔路径，用 72 边形近似出来的圆**不是** EE 的圆形图元。
EE 自己的圆形工具产出的是 **`esSegCircel`**（注意 EE 源码里的拼写错误 Circel）。

实地取证：让用户用圆形工具画一个圆，然后扫描该形状的子对象，得到

```
esShapePath(0x971fa48)
  +0x40 -> esSegCircel(0xab3c078)
  +0x60 -> esSegList(0x9cd4740)
             +0x34/+0x38 -> esSegCircel(0xab3c078)
```

`esSegCircel` 内存布局（实测）：

| 偏移 | 含义 |
|---|---|
| `+0x00` | vtable `??_7esSegCircel@@6B@` |
| `+0x04` | **工具 ID `0x4284`**（圆形工具） |
| `+0x08` | 所属 `esSegList` |
| `+0x68` | **半径**（float） |
| `+0x6C` | 角度（float，默认 π/2） |
| `+0x70` `+0x74` | **圆心 x / y**（float） |

构造函数（未导出符号，但 **Ghidra 可定位**）：
`??0esSegCircel@@QAE@VPointF@Gdiplus@@MMPAVMatrix@2@@Z`
= `esSegCircel(Gdiplus::PointF center, float radius, float angle, Gdiplus::Matrix*)`

**构造流程**（与 `CreateFromPathData` 同构，只是把 `esSegGon` 换成 `esSegCircel`）：

```c
seg  = operator_new(0x100); __autoclassinit2(seg, 0x100);
       esSegCircel(seg, cx, cy, r, PI/2, NULL); *(u32*)(seg+4) = 0x4284;
list = operator_new(0x44);  __autoclassinit2(list, 0x44); esSegList(list);
       esSegList::AddSegObject(list, seg, 1);
shape= operator_new(0x74);  __autoclassinit2(shape, 0x74); esShapePath(shape);
       *(u32*)(shape+0x34) = 0x040700ff; esShapePath::AddSegList(shape, list);
       esCanvas::AddItem(canvas, shape, 1);
       esShapePath::RecalcLayout(shape);
```

**必须用 EE 自己的分配器**（`msvcrt.dll!??2@YAPAXI@Z`），否则引擎 delete 时会踩堆。
实测结果：`RecalcLayout` 给出的锚点框 = 圆心 ± 半径，与理论值完全一致，且 EE 稳定不崩。

### 7.2 删除图元（链表摘除）

`esCanvas::AddItem` 的反向操作，已实测可用：

```c
newer = *(shape+0x44);  older = *(shape+0x48);
if (newer) *(newer+0x48) = older; else *(canvas+0x38) = older;   // 头
if (older) *(older+0x44) = newer; else *(canvas+0x34) = newer;   // 尾
*(shape+0x44) = 0; *(shape+0x48) = 0;
```

⇒ 画布 `+0x38` = 最新（头），`+0x34` = 最早（尾）；图元 `+0x44` = 更新方向，`+0x48` = 更旧方向。
（对象本身泄漏，未 delete；不影响显示。）

### 7.3 建画布（**部分可用**）

`esTextUI::InsertCanvas()`（RVA 见导出）就是 Space+G 的实现，会返回新 `esCanvas*`。
实测：能定位到 5 个 `esTextUI` 实例并向每个调用，**全部返回 NULL**。
原因：Space+G 是**文本流内的命令**，需要一个有效的文本插入点/编辑上下文；脱离 UI 上下文时该函数不产出画布。

未走通，待办：改走"构造 `esCanvas` + `esTextUI::InsertCanvas(esCanvas*, int)`"，
或直接向窗口投递 Space+G 按键消息。当前 `ee-new-canvas` 工具因此**不可用**。

### 7.4 字母标注（**已定位构造，未实现**）

Ghidra 已还原出文本类构造函数（源码里这些符号**没有导出**，只能靠 Ghidra 定位）：

| 类 | 构造函数 | 入口 RVA |
|---|---|---|
| `esSegLable` | `esSegLable(zPoint, zwstr, ulong, ushort, ushort)` | `0x3e8ff0` |
| `esSegLable` | `esSegLable()` | `0x3e8f40` |
| `esSegText` | `esSegText(zPoint)` | `0x3e4870` |
| `esSegTextBox` | `esSegTextBox(zPoint, ushort)` | `0x3f4d30` |
| `esSegTextBox` | `CreateTextBox(esStyleSheet*, uchar)` | `0x3f51f0` |

`esSegText::text()` → `zwstr&`（`+0x70` 处是 EE 的字符串对象）。

**卡点**：`zwstr` 是 `zoro.dll` 里的自有字符串类，按值传参（12 字节）需要先搞清其布局并
用 EE 的分配器构造；另外 `CreateTextBox` 需要一个 `esStyleSheet*`（应从文档取）。
这两点解决后即可实现 `ee_draw_label`。直角符号与切点标记可用圆弧段 + 短线段组合实现。

### 7.5 第三轮实测：`esSegText` 建得出来但不渲染；EE 的字母是 EXE 里的类

按 §7.4 的思路实现了 `makeLabelShape`，结果：

- `esSegText` 对象创建成功，vtable `0x6d78d040`，类型字 `0x6006`
- `zwstr`（+0x70）内容实测为 **`"A"`**（len=1），`OnCreate` 也正确写入了字体句柄（+0x7C = 12）
- 挂进 `esShapePath` → `esCanvas::AddItem` 成功，EE 不崩
- **但画布上什么都不显示**：形状锚点框退化成 1400×1400（只有描边padding，文本测量结果为 0）

随后让用户用 EE 自己的方式加了一个字母，扫描画布链表发现该对象：

```
head = 0xadb5310  vtable = 0x8eb9ac   ← 位于 Editer.exe（0x660000..0xB8A000），不在 eslib！
        vtable[0..7] = 0x686890, 0x8b4950, 0x8b4956, 0x8b495c, ...
        +0x08 = 画布（布局与 esShapeBase 一致）
        +0x48 = 下一个图元（我的 label 形状）
```

⇒ **EE 画布上的字母/文本框是编译进 `Editer.exe` 的应用层类**，不是 `eslib.dll` 的类。
因此正确路线是**对 `Editer.exe` 单独做一次 Ghidra 分析**，定位该类的构造与初始化，
而不是继续在 eslib 里找。

另有一条重要旁证：**圆形工具与字母的插入都没有触发我 hook 的 `esCanvas::AddItem`**
（直线/矩形的绘制触发了）。说明画布插入存在**第二条路径**，尚未定位。

### 7.6 `ee_list_shapes` 的类校验（已修）

画布链表里可能混有 Editer.exe 定义的类。对这些对象调用 `esShapePath::RecalcLayout`
会破坏状态。`ee_list_shapes` 现在会先判断 vtable 是否落在 `eslib.dll` 映射区间内，
不在则只报告句柄与前 48 字节，**不再探测**。

### 7.7 第四轮：拿到 EE 自己建字母的完整配方（关键突破）

对 `Editer.exe` 单独做了一次 Ghidra 分析（123 秒），再用脚本反查
应用层 vtable `0x8eb9ac`（RVA `0x28b9ac`）的交叉引用，命中 **`FUN_00426480`**
（RVA `0x26480`）——这就是 EE 插入一个画布字母的函数。反编译还原出的配方：

```c
fontSheet = (**(code**)(*view + 0x68))();          // 从视图虚函数取 esFontSheet*

// 1) 外层"形状"包装：esShapeLine，不是 esShapePath！
shape = operator_new(0x5c);
esShapeLine::esShapeLine(shape);
*(void**)shape = esShapeLine::vftable;             // ← 运行时 0x8eb9ac
*(uint*)(shape + 0x34) |= 0x4001007;               // 样式

// 2) 文本段：esSegLable，大小 0xD8
seg = operator_new(0xd8);
zwstr tmp(otherText);                              // 按值传的 zwstr 预备
esSegLable::esSegLable(seg, zPoint, tmp, ...);     // 6 参构造（导出）
*(void**)seg = esSegLable::vftable;

esSegLable::Initialize(seg, fontSheet);            // ★ 之前漏掉的关键步骤
...(vtable+0x80)...                                // 定位/布局

*(esSegLable**)(shape + 0x40) = seg;               // 段挂在 shape+0x40
esObject::SetParent((esObject*)seg, shape);
```

**两条决定性结论**：

1. **字母的外层图元是 `esShapeLine`（0x5C 字节），不是 `esShapePath`。**
   这解释了为什么我把 `esSegText` 塞进 `esShapePath` 完全不显示 —— 容器类就错了。
2. **必须调 `esSegLable::Initialize(esFontSheet*)`**。而且 `esSegLable` 的默认构造
   在 RVA `0x3e8f40`、6 参构造 `esSegLable(zPoint, zwstr, ulong, ushort, ushort)`
   **已导出**（`??0esSegLable@@QAE@VzPoint@@Vzwstr@@KGG@Z`）。

**Editer.exe 静态链接了引擎的形状层**：`esShapeLine::vftable` 与它的构造函数都在
`Editer.exe` 里（Ghidra 基址 0x400000；运行时基址 0x660000，即
`运行时 = Ghidra地址 - 0x400000 + 0x660000`），而 `eslib.dll` **没有导出**
`esShapeLine` 的构造函数。所以实现时要按运行时地址调用 EXE 内的那份。

**`ee_draw_label` 的落地路线（下一步）**：

1. vtable 扫描取一个活着的 `esFontSheet` 实例（或试 NULL）
2. `operator_new(0x5C)` + EXE 内 `esShapeLine` 构造 + 设 vtable + 样式 `|= 0x4001007`
3. `operator_new(0xD8)` + `esSegLable(zPoint, zwstr, ...)`（zwstr 需在目标进程内构造后按其 ABI 传）
4. `esSegLable::Initialize(seg, fontSheet)`
5. `*(u32*)(shape+0x40) = seg` + `esObject::SetParent(seg, shape)`
6. `esCanvas::AddItem(canvas, shape, 1)` + `RecalcLayout`

直角符号与切点标记可在此之后用短线段/圆弧段组合实现。




---

### 7.8 第五轮：字母标注打通（已用截图目视验证）

§7.7 的路线大方向正确，但有三个关键点是错的/缺失的。下面是从 Ghidra 反编译
（`analysis\decomp-draw.txt`）+ 运行时内存比对 + 截图验证得到的**完整可用配方**
（实现：`ee_bridge.js` 的 `makeLabelShape`；工具：`ee_draw_label`）。

> 先纠正 §7.7 的一处错误：**eslib.dll 确实导出了 `esShapeLine`**
> （`??0esShapeLine@@QAE@XZ`、`?__autoclassinit2@esShapeLine@@QAEXI@Z`、
> `??_7esShapeLine@@6B@` = RVA `0x56c654`），不需要去调 Editer.exe 里的那份。

```
shape = esShapeLine (0x5C)             style |= 0x4001007
seg   = esSegLable  (0xD8)
        ctor(zPoint, zwstr, ulong feature, ushort fontIndex, ushort padding)
        Initialize(fontSheet)          // 只做一件事：把 fontSheet 存进 seg+0xD4
        Build(1)                       // 只算多边形：seg+0x34 = 6 点数组, +0x38 = 5
        esEQLine::AppendString(seg+0x80, text, len, fontSheet, 0)   // 仅当 feature=0
shape+0x40 = seg ; esObject::SetParent(seg, shape)
esShapeBase::OnCreate(shape, styleSheet)
shape->vtbl[0x64]()                    // 虚拟 RecalcLayout（不是 esShapePath 那个导出！）
esCanvas::AddItem(canvas, shape, 1)
```

### 四个关键点

1. **`zwstr` 必须按值传递，不能传指针。**
   `??0esSegLable@@QAE@VzPoint@@Vzwstr@@KGG@Z` 的栈参数依次是
   `zPoint(8B) + zwstr(12B) + ulong(4B) + ushort(4B) + ushort(4B)`。
   `zwstr` 实测布局 `{wchar_t* buf; int len; int cap}`（12 字节；`?Str@zwstr@@QBEQA_WXZ`
   返回的正是 buf）。只传一个指针时引擎读到 `{ptr, 0, 0}` → **len=0 → 文本为空，
   而且不抛任何错误、几何也照常算出来**。在 Frida 里把 12 字节拆成 3 个 `int` 声明，
   栈布局就与按值传结构体完全一致。
   ctor 会把文本 `lstrcpyW` 到 **`+0x68`（一个独立的 `wchar_t*` 缓冲区）**，所以
   "+0x68 里有正确文本" **不能**用来判断标签能渲染。

2. **真正画字的是 `seg+0x80` 处内嵌的 `esEQLine`。**
   `esSegLable::Draw`（RVA `0x3ead30`）整体被 `*(int*)(this+0xD4) != 0`（字体表指针）守卫，
   随后用 `esEQLine::Draw((esEQLine*)(this+0x80), render, 0, pt[5].x, pt[5].y, 0, ...)` 出字。
   ctor 只构造 EQLine（vtable 已就位）却**从不给它内容**，`Build` 也不碰它。

3. **`feature`（ctor 的 `ulong`，即 `esSegLable::GetLableFreature`）决定引擎是否自己填 EQLine：**

   | feature | 引擎行为 | 必须做 |
   |---|---|---|
   | `0` | **不填**（EQLine 的 `+0x0C`/`+0x30` 保持 0） | 自己调 `esEQLine::AppendString`，否则**几何正确但什么都不画** |
   | `≠0` | **会填**（`+0x30` = byte0 个字符） | **不要**再 append，否则画出**两份字母** |

   实测 `feature = 1` 与 `0x80000001` 都可用。**默认取 `0x80000001`**：它使
   `+0x70 = 0x01`、并由 `Build` 推出 `+0x73 = 0x84`，与用户自己那个标签完全一致。

   ⚠️ **★ 2026-10 修正（反编译 + 活进程实测，旧结论已推翻）**：这个 `ulong` **不是原子
   feature word**，而是**逐段字符数 + flags**：byte0→`+0x70`（主文本字符数）、
   byte1→`+0x71`（标注点后缀）、byte2→`+0x72`（边框后缀）、byte3→`+0x73`
   （flags，`0x80` = 数学化）。`RecalcLayoutLable` 只 append `+0x70` 个字符 ——
   **byte0 写 1 时 "ABC" 只出 "A"**；桥现在按文本长度自动写 byte0（`opts.k` 只当
   flags 模板），实测 A/AB/ABC 宽度 741/1482/2223、item 数 1/2/3，`Build` 反复调用
   幂等（`ClearAllContent` 先清后填）。**字体槽绝不能塞进这个 ulong**（旧写法
   `(槽<<16)|1` 把槽写进 byte2 → 多字符截断的根因）。`GetLableFreature` 的
   `(fontSlot<<16)|…` 公式是**对话框方向**的合成（读 `+0x6e`），不是 ctor 参数语义。
   `AppendString` 必须放在**整条流水线的最后**（`OnCreate`/`RecalcLayout`/`AddItem`
   之后再布局会清掉已 append 的内容），而且
   **不要靠"猜 feature"来决定是否 append —— 直接读 EQLine 的 `+0x30` 计数**：
   `ee_bridge.js` 就是这样做的（`opts.appendText` 默认 `auto`／`true` 强制／`false` 禁用），
   因此两种 feature 都不会出现"空白"或"双字母"。

4. **字体槽 `+0x6e` 决定正体还是斜体 —— 这就是"字母样式"的来源。**
   `esSegLable::Draw` 用 `esFontSheet::GetFont(fontSheet, *(ushort*)(this+0x6e), mode)` 取字体；
   ctor 的第 4 个按值参数（`ushort`）写进 `+0x6e`。
   同一个文档里实测：**槽 0 = 正体，槽 13 = 斜体**（用户自己插的字母用的就是 13）。
   而 `+0x6c`（第 5 个参数）是 padding，用户标签为 `400`。

   ⚠️ **只有"引擎自己填 EQLine"这条路（feature≠0）才吃 `+0x6e`**；
   手动 `AppendString` 用的是它自己的第 4 个参数，所以
   "feature=0 + 手动 append + fontIndex=13" 仍然是**正体**。
   想拿到斜体就必须走 feature≠0 那条路。

   `ee_draw_label` 会自动从画布上**已有的标签**读出 `+0x6e`/`+0x6c` 并套用
   （`ee_bridge.js` 的 `labelFontIndex`，靠子段类型字 `0x600d` 识别，
   因此对 eslib 实例和 Editer.exe 自己那份拷贝都有效），
   于是新画的字母与文档里手插的字母**字体、字号、斜体完全一致**；
   画布上没有标签可抄时，回落到**字体表解析**（★ 2026-10）：按 `font_face`
   （默认 Times New Roman）+ `font_italic`（默认 true）经 `ee_fonts` 同款探测自动找槽，
   再失败才用槽 0（正体）。也可用 `font_index` / `padding` 显式覆盖。

### `[Label]` 就是 `esShapeLine`

用户标签对象的 vtable 是 `0x8eb9ac`（位于 Editer.exe），其槽位全是 `jmp [IAT]` 导入桩。
逐槽解析（`ee_diag vtslots` → `hexdump` 桩 → 读 IAT）后得到：
`+0x64 RecalcLayout@esShapeBase`、`+0x6C LoadLines@esShapeBase`、
`+0x70 AppendMatrix@esShapeBase`、`+0x74 Draw@esShapeBase`、
`+0x7C GetLineList@esShapeBase`、`+0x80 MatrixProc@esShapeBase` ——
**与 eslib 的 `??_7esShapeLine@@6B@` 逐槽一致**。
再加上两边对象的大小（0x5C）、类型字（`+0x04 = 0x3109`）、样式（`0x04001007`）、
子段位置（`+0x40`）、包围盒 padding（1000）全部相同 ⇒ **同一个类**，
不需要去 Editer.exe 里另找一套实现。

### 为什么以前"看不到字母"

两个独立原因，都不要再犯：

1. `zwstr` 按指针传 → 文本长度为 0（空标签，几何照常正确）；
2. 即使文本进了 `+0x68`，EQLine 没被填 → `esSegLable::Draw` 什么也不画。

**调试手法（本轮靠它定位）**：`ee_diag trace` 用 Frida Interceptor 挂
`ShapeBase::Draw / ShapePath::Render / ShapeLine::Render / SegLable::Draw / IsVisible`，
再做一次 `PrintWindow` 触发绘制，然后读 `ee_diag tracelog`。
三个字母与用户标签的调用链逐帧一致
（`Draw → IsVisible(ret=1) → Render → SegLable::Draw`）⇒ 证明"被画了但画不出内容"，
从而把范围锁进 `esSegLable::Draw` 内部。

---

### 7.9 第六轮：角度标记（直角符号 / 等角弧）

两块都已完成并截图验证（`ee_draw_angle_mark` 的 right / arc / double 三种 kind）。

### 直角符号：不需要新原语

直角标记就是一条**三段开口折线**——从顶点沿两条边各取 `size` 长度，围成缺一边的小正方形：

```
u = 单位向量(V→A)        w = 单位向量(V→B)
p0 = V + u*s             p1 = V + (u+w)*s        p2 = V + w*s
```

用已有的 `CreateFromPathData`（`types = [0x00, 0x01, 0x80]`、`close = 0`）画 `p0→p1→p2` 即可。

### 等角弧：`esSegArc`

导出：`??0esSegArc@@QAE@VPointF@Gdiplus@@MMMPAVMatrix@2@H@Z`（RVA `0x128290`）
= `(PointF 圆心, float 半径, float 起始角, float 终止角, Matrix*, int flags)`。
对象大小 **0x98**（`operator_new(0x98)` + `__autoclassinit2(x, 0x98)`），
类型字 `+0x04 = 0x4306`，字段：`+0x68` 半径、`+0x70` 起始角、`+0x74` 终止角、
`+0x78`/`+0x7C` 圆心、`+0x80` 中间角。
容器与圆形完全一致：`esSegList` + `esShapePath` + `esCanvas::AddItem`。

**三个反直觉的点（都实测确认）：**

| 现象 | 结论 |
|---|---|
| 传 45.0（度），`+0x74` 却存成 `1.017703` | 角度是**弧度**。`+0x74 = epNormalAngle360P(45.0)`，而这个函数就是 `x mod 2π`（45 mod 2π = 1.017703）。它本身也是导出的：`?epNormalAngle360P@@YAMM@Z`（RVA `0x1f5ab0`） |
| 画出来的弧整体转了 90° | 引擎的 **0° 指向页面上方**：`engine_angle = page_angle + 90`，其中 `page_angle = atan2(dy, dx)` 是通常的 y 向下约定 |
| 想要 45° 却画了 300° 以上 | 引擎从**第一个角朝负方向**扫到第二个角，所以要把区间的**上界传在前面** |

正确的调用姿势（`ee_mcp_server.py` 的 `arc()`）：

```python
sweep = (end - start + 180) % 360 - 180        # 归一到 (-180, 180]
lo, hi = min(start, start + sweep), max(start, start + sweep)
makeArcShape(cx, cy, r, radians(hi + 90), radians(lo + 90))
```

> **验证手法（比截图快得多）**：弧的 `p1`/`p2` 就是它**两个端点**，
> 把这两个点与按公式算出的期望区间比对即可确认扫描范围。
> 例：圆心 (8000,8000)、r=1600、页面上 0°→45°，端点应为 (9600,8000) 与 (9131,9131)。
> 注意弧的 3 个内部点是控制点（`+0x5c = 3`），不要拿它们当整圆 bbox 用。

---

## 8. 下一步建议

1. ~~**字母标注**~~ —— ✅ 已完成，见 §7.8（含斜体样式自动匹配）
2. ~~**角度标记**~~ —— ✅ 已完成，见 §7.9（直角符号 / 等角弧 / 双弧）
3. **`ee_new_canvas`** —— 唯一还没打通的"必需人工步骤"，见 `02-next-steps.md` §2.2
4. **样式控制** —— 解 `+0x34` 样式字与 `esPenInfo` 结构，支持颜色/虚线/线宽
5. **真正的贝塞尔曲线** —— 找到正确的 GDI+ 类型布局（平滑函数图象所需要）
6. **撤销集成与删除** —— 走 `esUndo` / `esCanvas::DeleteSel`，让 agent 的改动可 Ctrl+Z
7. **坐标体系** —— 打通页面单位 ↔ 毫米，让 agent 能按真实尺寸作图
8. **`.wsd` 直接生成**（备选路线）—— 若日后要批量离线产出，可复用本模型 + `zArchive`
