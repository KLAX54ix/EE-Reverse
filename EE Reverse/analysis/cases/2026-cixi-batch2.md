# 慈溪 2025-2026 期末·第二批（Q7 / Q9 / Q13 / Q15 / Q16）

日期：2026-10-19。全部插在题干末尾原始插图之后，画布均为原生插入（frameType=0x1000，
默认 61340×30670），字体槽 11（FS Math Type italic），padding 400，math 1，笔宽 0.25mm。

> ⚠️ 下表是**第一次**画完时的句柄；Editer 重启/用户删除后，Q7/Q15/Q16 的最新句柄见文末
> 「2026-10-19 修正」表（Q9/Q13 以文档当前实际画布为准）。句柄会随文档重开变化，不要当永久 ID。

| 题 | 图型 | 约束来源 | 画布 | 形状数 | audit |
|---|---|---|---|---|---|
| Q7 | rectangle-on-incline | 题干 ∠CEF=α、BC=1、BD∥EF | 0x6850ee8 | 14 | PASS |
| Q9 | inscribed-triangle-median | 题干 ∠A=45°、D midpoint、G centroid、BC=2√2（inline 图） | 0x6850668 | 8 | PASS |
| Q13 | regular-pentagon | 题干 正五边形内接 ⊙O、连 OA/OB | 0x68527b8 | 11 | PASS |
| Q15 | circle-right-triangle | 题干 R=2、∠CAB=90°、CD⊥AO、AB=2OD | 0x6850b58 | 11 | PASS |
| Q16 | quadrilateral-diagonals | 题干 ∠ACD=90°、BE/DE=2/3、sin∠BDC=1/4、AB=4、AD=6 | 0x68577e8 | 9 | PASS |

## Q7 矩形木箱在斜面上

- **约束**：EF 水平地面，FG⊥EF；CD 在斜面 EG 上；矩形 ABCD；BD∥EF；∠CEF=α；BC=1。
- **推导**：设 α=30°（原图量取），u=(cosα,sinα)，n=(-sinα,cosα)；
  C 在斜面上取距离 s=1.2；D=C+cotα·u；B=C+n；A=B+cotα·u。
  由 BD∥EF ⇒ CD=cotα（因此 BD=1/sinα）。点 A 到 BD 的距离 = BC·sin(90°−α)=cosα
  （答案 A）。
- **画布坐标**（u_canvas=7500）：E(12000,28500), F(53250,28500), G(53250,4688),
  C(19794,24000), D(31044,17505), B(16044,17505), A(27294,11010)；α 弧 r=6750；
  F 处直角 L 形折线。
- **验证**：`check_spec` 6/6 PASS；`ee_audit_canvas` PASS（14 shapes：3 条外边 + 矩形 +
  虚线 BD + 直角折线 + α 弧 + 7 标注）。截图 `captures/cixi-q9view-printwindow-2.png`
  可见矩形/虚线/弧局部。

## Q9 圆内接三角形，中位线与重心

- **约束**：⊙O 内接 △ABC，∠A=45°；D=BC 中点；G=重心；连 GD；inline 图给出 BC=2√2。
- **推导**：∠A=45° ⇒ 对弧 BC 的圆心角 90°；BC=2R·sin45°=2√2 ⇒ **R=2**。
  A 可在优弧 BC 上任意（原图 A 偏右上，取 A=70°），B=225°、C=315°（BC 水平）。
  D=(0,-√2)，G=(A+B+C)/3；画 GD（G 在 AD 上，A-D-G 共线）。
- **画布**（u=6000，O=(30000,15000)，R_canvas=12000）：A(34104,3724),
  B(21515,23485), C(38485,23485), D(30000,23485), G(31368,16898)。
- **验证**：check_spec 6/6 PASS（∠BAC=45、BC=2√2、D 中点、G 重心、A-D-G 共线、OB=2）；
  audit PASS（8 shapes：圆 + 三角形 + GD + 5 标注）。

## Q13 正五边形内接于圆

- **约束**：正五边形 ABCDE 内接 ⊙O；连 AO、BO；求 ∠AOB=72°。
- **取点**（O=(30000,15000)，R_canvas=11000，按原图 D 在顶）：D=(30000,4000),
  C=(40463,11601), B=(36466,23899), A=(23534,23899), E=(19538,11601)。
- **验证**：check_spec 7/7 PASS（五边等长、∠AOB=72°、OA=OB=1）；
  audit PASS（11 shapes：圆 + 五边形 + OA/OB + O 加粗点 + 6 标注）。

## Q15 圆内接直角三角形与 AO 垂线

- **约束**：⊙O 半径 2；AB、AC 为弦，∠CAB=90°（⇒ BC 为直径）；连 OA、OB；
  过 C 作 AO 的垂线交 AO 延长线于 D；AB=2OD；求 AC。
- **精确解**（`analysis/cixi/meas-fig19.json` model_points，旋转 +30° 对齐原图）：
  A=(-0.5,0.866), B=(0.5,0.866), C=(-0.5,-0.866), D=(0.25,-0.433), O=(0,0)（R=1 单位）。
  R=2 ⇒ AB=2, OD=1, AC=2√3（答案）。
- **画布**（u=12000/单位，O=(30000,15000)）：A(19608,9000), B(40392,9000),
  C(19608,21000), D(35196,18000)；圆 r=12000。
- **验证**：check_spec 7/7 PASS（BC 直径、∠CAB=90、CD⊥AO、A-O-D 共线、AB=2OD、
  OD=0.5、AC=√3 的 R=1 版本）；audit PASS（11 shapes：圆 + 5 线段 + 5 标注）。

## Q16 四边形对角线交点

- **约束**：四边形 ABCD，AC、BD 交于 E；∠ACD=90°；BE/DE=2/3；sin∠BDC=1/4；
  AB=4，AD=6；求 AC。
- **条件来源**：题干两个 inline 图（fig20 BE/DE=2/3、fig21 sin∠BDC=1/4），
  用实测图 fig22 反算 BE/DE≈0.662、sin∠BDC≈0.225 验证成立。
- **精确解**：设 C=(0,0), A=(a,0), D=(0,d), B=(x,y)；由 BE/DE=2/3 ⇒ y=-2d/3；
  sin∠BDC=1/4 ⇒ x=d√(5/27)；AD=6、AB=4 解得
  **d=3.674234614, a=4.743416490, x=1.581138830, e=0.948683298**；
  **AC=a=3√10/2≈4.7434**。
- **画布**：先旋转 -50°，平移 C=(22000,17000)，u=3000：
  A(31147,27901), B(19420,25357), C(22000,17000), D(30444,9915), E(23829,19180)；
  C 处直角 L 形（沿 CA/CD 各 1300 单位）。
- **验证**：check_spec 6/6 PASS（∠ACD=90、AB=4、AD=6、B-E-D 共线、BE=2/5BD、DE=3/5BD）；
  audit PASS（9 shapes：四边形 + 两对角线 + 直角折线 + 5 标注）。

## 本轮教训（重要，已写入 skill）

1. **插画布的真正闸门**：`gotoText` 停在题干段末尾时，题干里的 **inline 公式图**会让
   `bef()` 非空；此时直接 `insertCanvasNative` 会把画布插进题干中间（Q16 首插就犯了这个错）。
   正确做法：**先按 VK_DOWN 直到当前段落 `text == ""`，再在该空段落里检查 `bef()`/按 RIGHT**，
   找到原图 canvas 后才插入。
2. **误插画布可以用 Ctrl+Z 干净撤销**（2026-10-19 实测：Q16 误插后 Ctrl+Z，再读段落结构
   恢复为「题干 → 空图段 → 大题标题」，四张已画好的画布形状全部无损）。无需关文档重来。
3. 批量画多题时：**每画完一题焦点会转到画布**；下一次插入前必须先用鼠标点一下正文文字
   （`tools/click_doc.ps1 <shotX> <shotY>`），否则 `ee_new_canvas` 报 all IsValid=0。
4. `gotoText` 无法跨过**已插入的画布**（VK_DOWN 返回 0）；批量作业时要从**当前题下方的文字**
   重新点击定位，而不是从上面的题一路 gotoText。

## 2026-10-19 修正（用户验收后重画）

用户删除 Q7/Q9/Q15 旧画布后重画；Q16 旧画布也已删除，一并重画。

| 题 | 新画布 | 修正 | shapes / audit |
|---|---|---|---|
| Q7 | `0x95b18a0` | 2026-10-19 第二次原生重画（Editer 重启后）：普通线/标注照旧；α 弧 = 服务端 `ee_draw_angle_mark(kind:"arc")` 的原生 `esSegArc` 0x4307；F 直角 = 原生 `esSegHVLine` 0x4704 | 14 / PASS |
| Q15 | `0x94e0560` | 2026-10-19 斜直角最终版：D 直角用**内缩**局部 3 点 `[(s,0),(s,-s),(0,-s)]` + Gdiplus 矩阵，两臂不贴边；12 对象 PASS |
| Q16 | `0x31dc1e0` | 2026-10-19 斜直角最终版：AB 水平，C 直角用内缩局部 3 点 + 矩阵；9 对象 PASS |

**教训**：
- 角度/直角标记一律用 `ee_draw_angle_mark`；`ee_draw_figure.paths` 的点数 >2 时**默认 close**。
- `meas-fig*.json` 的 `model_points` 可能已是图像坐标（y 向下）；落笔前先用题干不变量（垂直/中点/比值）数值验证。
- 嵌入画布不能用 `SetSelObj`+`DeleteSel` 删除（实测 system error）；安全做法是请用户在页面上选中画布按 Delete；误插到题干里的画布可 Ctrl+Z 撤销。
