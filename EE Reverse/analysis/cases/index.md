# 插图案例索引

| id | 图型 | 试卷 / 题 | 约束笔记 | spec | 状态 |
|---|---|---|---|---|---|
| [2026-beilun-q10-fig2](2026-beilun-q10-fig2.md) | function-graph（抛物线） | 北仑 2024-2025 中考模拟·选择压轴 题10 图2 | [beilun-q10-constraints.md](../beilun-q10-constraints.md) | [bl-q10-fig2-constrained.json](../bl-q10-fig2-constrained.json) | ✅ 已画（约束式）；案例卡已建 |
| 2025-zhenhai-q1 | right-triangle | 镇海 2025-2026 期末·选择5 | 待补 | 待补 | ✅ 已画（重画 5 次，教训：像素坐标硬算） |
| 2025-zhenhai-q2 | coordinate-homothety | 镇海 2025-2026 期末·选择6 | 待补 | 待补 | ✅ 已画（10 路径含 6 虚线 + 9 标注） |
| 2025-zhenhai-q8 | equilateral-triangle（莱洛） | 镇海 2025-2026 期末·选择8 | 待补 | 待补 | ✅ 已画 |
| 2025-zhenhai-q5 | regular-octagon + parabola | 镇海 2025-2026 期末·选择10 | 待补 | 待补 | ✅ 已画（图1/图2） |
| [2026-cixi-q5](2026-cixi-q5.md) | coordinate-homothety | 慈溪 2025-2026 期末·选择5 | 案例卡内（题干 dump 已抽约束） | [2026-cixi-q5.json](../specs/2026-cixi-q5.json) | ✅ 已画（原生坐标轴 canvas `0x94edb88`，用户定样式：x/y 标注/无刻度数字/保留 O/样式4细箭头；check_spec 12/12 + audit PASS） |
| [2026-cixi-q7](2026-cixi-batch2.md) | rectangle-on-incline | 慈溪 2025-2026 期末·选择7 | batch2 §Q7 | [2026-cixi-q7.json](../specs/2026-cixi-q7.json) | ✅ 已画（14 shapes，audit PASS） |
| [2026-cixi-q9](2026-cixi-batch2.md) | inscribed-triangle-median | 慈溪 2025-2026 期末·选择9 | batch2 §Q9 | [2026-cixi-q9.json](../specs/2026-cixi-q9.json) | ✅ 已画（8 shapes，audit PASS） |
| [2026-cixi-q13](2026-cixi-batch2.md) | regular-pentagon | 慈溪 2025-2026 期末·填空13 | batch2 §Q13 | [2026-cixi-q13.json](../specs/2026-cixi-q13.json) | ✅ 已画（11 shapes，audit PASS） |
| [2026-cixi-q15](2026-cixi-batch2.md) | circle-right-triangle | 慈溪 2025-2026 期末·解答15 | batch2 §Q15 | [2026-cixi-q15.json](../specs/2026-cixi-q15.json) | ✅ 已画（11 shapes，audit PASS） |
| [2026-cixi-q16](2026-cixi-batch2.md) | quadrilateral-diagonals | 慈溪 2025-2026 期末·解答16 | batch2 §Q16 | [2026-cixi-q16.json](../specs/2026-cixi-q16.json) | ✅ 已画（9 shapes，audit PASS） |
| [2026-jiuxia-q1](2026-jiuxia-qzq-batch.md) | coordinate-linear + circle | 九下期中·选择压轴 Q1 | batch §Q1 | [q01.canvas.json](../specs/nb/q01.canvas.json) | ✅ 已画（canvas `0x2c2bdb8`，8 shapes，audit PASS；原生坐标轴） |
| [2026-jiuxia-q2](2026-jiuxia-qzq-batch.md) | coordinate-squares + hyperbola | 九下期中·选择压轴 Q2 | batch §Q2 | [q02.canvas.json](../specs/nb/q02.canvas.json) | ✅ 已画（`0x2c2c6f8`，17 shapes，audit PASS） |
| [2026-jiuxia-q3](2026-jiuxia-qzq-batch.md) | grid-triangles（魔尺） | 九下期中·选择压轴 Q3 | batch §Q3 | [q03.canvas.json](../specs/nb/q03.canvas.json) | ✅ 已画（`0x90e3660`，26 shapes，12 深灰填充，audit PASS） |
| [2026-jiuxia-q4](2026-jiuxia-qzq-batch.md) | circle-semicircle + quad | 九下期中·选择压轴 Q4 | batch §Q4 | [q04.canvas.json](../specs/nb/q04.canvas.json) | ✅ 已画（`0x90e20b0`，11 shapes，audit PASS） |
| [2026-jiuxia-q5](2026-jiuxia-qzq-batch.md) | grid-squares-fill | 九下期中·选择压轴 Q5 | batch §Q5 | [q05.canvas.json](../specs/nb/q05.canvas.json) | ✅ 已画（`0x90e0048`，21 shapes，2 浅灰填充，audit PASS；**残留测试字符 Z**，可 Ctrl+Z 撤销） |
| [2026-jiuxia-q6m](2026-jiuxia-qzq-batch.md) | circle-semicircle-tangent | 九下期中·多选6 | batch §多选6 | [q06m.canvas.json](../specs/nb/q06m.canvas.json) | ✅ 已画（`0x90e3258`，16 shapes，加粗点，audit PASS；BE=AG 强约束 cosθ=3/5） |

> 新增案例：复制 `README.md` 模板 → 写 `analysis/cases/<id>.md` → 在表里加一行。
> 图型标签用于检索：`equilateral-triangle`、`similar-triangle`、`circle-inscribed`、
> `coordinate`、`function-graph`、`grid`、`refraction`、`composite`。
