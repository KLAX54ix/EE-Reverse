# 九下期中选择压轴题 6 图（2026-10-19 批量）

- **文档**：`D:\EE Reverse\九下期中选择压轴题.wsd`（另一份同时打开的 `宁波2024-2025中考模拟卷选择压轴题.wsd` **不是**目标，用户已纠正）
- **图型**：coordinate-linear+circle / coordinate-squares+hyperbola / grid-triangles（魔尺）/
  circle-semicircle+quad（圆弧）/ grid-squares-fill（四纸片）/ circle-semicircle-tangent（多选6）
- **流程**：约束式 model spec（y↑数学单位）→ `tools/nb_build.py` → canvas spec（y↓画布单位）→
  `tools/nb_preview.py` 预览比对 → `tools/check_spec.py` PASS → EE 落笔 → `ee_audit_canvas` PASS
- **落笔画布**（本次进程）：
  | 题 | 画布 | shapes | 审计 |
  |---|---|---|---|
  | Q1 一次函数/圆 | `0x2c2bdb8` | 8（原生轴+3线+4标注） | PASS |
  | Q2 正方形+双曲线 | `0x2c2c6f8` | 17（原生轴+8边+81点折线+7标注） | PASS |
  | Q4 半圆/四边形 | `0x90e20b0` | 11（5线+129点弧折线+5标注） | PASS |
  | Q3 百变魔尺 | `0x90e3660` | 26（12 深灰填充三角+12 白三角+外框+内框） | PASS |
  | Q5 四张正方形 | `0x90e0048` | 21（2 浅灰填充+10 边+8 标注）**多一个测试字符 Z**（见负案例） | PASS（pen 归一后） |
  | 多选6 半圆切线 | `0x90e3258` | 16（6线+97点弧折线+加粗点O+8标注） | PASS |

## 约束（从题干抽取，绝不用像素反推）

1. **Q1**：直线 `y=−3/4x+3` 交 x 轴 A、y 轴 B；P 在 OB 上；C 在 AB 上，`∠OCP=90°`。
   取相切/极端情形 m=3 → A(0,3)、B(4,0)、P(3,0)、C=(2.4,1.2)（AB 上，`OC·CP=0` 残差 0）。
   自由参数：C 取使 ∠OCP=90° 的那个 P 位置（与印刷图一致）。
2. **Q2**：A(1,0)、B(0,2)；正方形 ABCD、DEFG（A→B→C→D，D→E→F→G）；E、F 在双曲线 `y=36/x` 上。
   推导：C=A+Rot(−90°)(B−A)=(2,3)、D=(3,1)；E=(9,4)、F=(6,10)；`x_E·y_E = 36 = x_F·y_F` ✓。
3. **Q3**：百变魔尺 = 24 个全等等腰直角三角形填满**空心** 4×3 矩形框（内框 3×2，框宽 1/2）；
   4(a+b)−4=24 ⇒ a+b=7 ⇒ 3 种。24 条斜边 = 外周长 14 + 内周长 10；面积 12−6=6=24×1/4。
4. **Q4**：AB 为直径的半圆，半径 1（量得 R=76.3px）；∠AOC=45°（C 在 135°）；D 在弧 BC。
   自由参数 θ_D=69.0°（原图 OD 线拟合 68.5°、弦 CD∩圆 69.8°）。
5. **Q5**：四张**互不相同**正方形纸片刚好填满矩形 ABCD，余下两块矩形阴影（右上 L 形 + 左下条）。
   整数网格解：边长 73/54/33/20，矩形 127×93，阴影条 6；面积恒等式 9734+1017+1060=11811=127×93 精确。
   由 `l=2(H−a)`、`2H=186`、`2a=146` 得周长(④)=4·20=80=2l ⇒ 答案 D。
6. **多选6**：半圆 O 直径 AB；BC 延长至 D 使 BC=CD；CE 切于 C 交 AD 于 E；BE 交圆于 F；
   AF 延长交 CE 于 G；**BE=AG**。取 A(−1,0)、B(1,0)、R=1，由 BE=AG 二分得 cosθ=3/5：
   C(3/5,4/5)、D(1/5,8/5)、E(−1/25,32/25)、F(87/425,416/425)、G(7/25,26/25)。
   恒等式：AD=AB、CE⊥AD、G 为 CE 中点、AE=4DE 全成立（按此题意四项皆真）。

## 数值自检

`tools/check_spec.py`：q01（含垂直/共线/在线段上）、q02、q03（96 checks：24 三角全等 1e-12 +
共边单一 24 环 + 20 万随机点密铺 0 失败）、q04（11 checks：OA=OB=OC=OD=1、AB=2、∠AOC=45° 残差 0）、
q05（39 checks，面积恒等式精确闭合）、q06m（20 checks，残差 ≤7e-15）——全部 `RESULT: PASS`。

## 落笔关键参数

- `pen_mm=0.25`（引擎 100）；label `padding=400`、`math=1`；字母字体槽 = 本档 `FS Math Type` 斜体
  **slot 11**（本档无 Times New Roman）；每张画布都用**显式 font_sheet/style_sheet**（本档 `0xa800d30`）。
- 原生坐标轴：`makeNativeAxisShape(rect, origin, 1, 1, fs)` → `addItem` → `recalcShape` → `styleAxisShape(shape, fs)` → `recalcShape`。
  rect/origin 见 `q01/q02.canvas.json`（`ee_draw_axis` 在同一进程内因 label_context 取不到字体槽会崩，故直接调桥 RPC）。
- 折线/弧一律 **close:false**，弧=预采样折线（Q2 81 点、Q4 129 点、多选6 97 点）。
- 加粗点用 `dots`（引擎 `esShapeLine(pt,0x6001,…)`，修后 pen=160 = 0.40mm）。
- 填充用 `paths[].fill`（`true`=浅灰 0xCACACA、`"dark"`=深灰 0xA0A0A0），落笔后确认 `GetBrush` 非空
  （Q3 12 个、Q5 2 个全部 `filled:true`）。
- 插入位置：每题 **选项行行首**（光标到选项行 → `VK_LEFT` 到行首 → `insertCanvasNative`），
  渲染上等于"原图之后、选项之前"。

## 验证

`ee_audit_canvas` 六张全 PASS：labels `formatWord=0xffff0003`、包裹盒 3009–3481 宽（正常单字母）、
pen 全 100、dot 160、填充 brush 非空；`count` 与设计一致（Q5 因多一个字符为 21）。

## 负案例（踩过的坑）

1. **`nb_build` 对 >2 点折线未显式 close=false** → `ee_draw_figure` 默认按"闭合多边形"建，
   Q2 双曲线被追加一条从末端回首端的**弦**（肉眼一眼错）。→ 已在 `nb_build` 对所有
   polylines/arcs/curves 强制 `close:false`；写任何折线一律显式带 close。
2. **`ee_draw_axis`/`ee_draw_figure` 在新插入画布上可能取不到 fontSheet**（画布不在
   `canvasCandidates` 且光标在画布内 → `label_context` 回落 `caretContext` 失败 → fs=0x0 →
   `makeNativeAxisShape` 访问违例崩调用）。→ 直接 `ee_diag` 调桥 RPC 并**显式传本档 fontSheet**；
   draw_figure 给每个 label 传 `font_sheet`/`style_sheet`。
3. **同一画布上两次 lablestyle 会互相覆盖**：`draw_figure` 的标签样式是**整张画布**批量写，
   后一次 `math=0/font=0` 把先前 `math=1/font=11` 的字母也改掉。
   → 混字体时：`draw_figure` 只放数学斜体标签，另一类用 **`ee_draw_label` 逐个加**（它走
   `makeLabelShape`，**不做画布级样式**，实测不影响其他标签）。
4. **测试字符 Z 残留**：为验证「ee_draw_label 是否波及画布其他标签」在同一画布上加了一个 Z；
   该字符**无法程序删除**（`esUndo` 无 `UnBack` 导出；`esCanvas::DeleteSel` 对嵌入对象会 system error），
   用户又拒绝删除（怕闪退）。→ 教训：**任何试验字符不要落在正式画布上**（用废纸画布）；
   多出来的字符只能请用户 **Ctrl+Z** 一次撤销（引擎自带撤销是安全的，与 Delete 不同）。
5. **插入画布后光标必然掉出正文**（焦点转去画布，`IsValid=0`）：桥内 `SendMessage` 模拟点击
   **不可靠**，本会话沙箱还禁止 `SetCursorPos`/`SendInput`（外部注入无效）。
   → 现实节奏 = **每题由用户点一次正文/选项行**；不要试图 hack `esTextUI+0xdc` 的 IsValid 标志、
   也不要在画布模式下按方向键（本会话因此**崩溃两次**，未保存内容全丢）。
6. **跨已插入画布走位会被挡住**：`OnKeyDown(VK_DOWN)` 在下一段含新画布时返回 0。
   → 不要"从头一路走到底"，每题重新点一次选项行再插。
7. 文档结构：`[题干段] → [空段，内嵌原图 canvas] → [选项段]`；插在**选项行首**最稳
   （插在空段时 `GetBefEmbeder()` 可能非空，需先按 `VK_RIGHT` 找到原图 canvas 之后再插）。
