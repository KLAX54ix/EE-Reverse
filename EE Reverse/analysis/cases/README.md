# 插图案例库（Case Library）— 经验外置的载体

**目的**：skill 只做"方法 + 路由 + 闸门"；每道题的具体经验（约束怎么抽、自由参数怎么选、
推导公式、数值残差、最终 spec、踩过什么坑）写进这里，按图型检索，不要求预先写成全集。

## 使用协议（skill 会强制要求）

**画之前**
1. 从题干文字里抽约束，判断图型（等边/相似/圆内接/坐标系/函数图象/网格/光学…）。
2. 打开 `analysis/cases/index.md`，按图型选 1–3 张最接近的案例卡读完。
3. 复用案例里的"约束 → 推导 → 数值自检"骨架，只改自由参数。

**画之后（必须写回）**
1. 按本文件末尾模板新增一张 `analysis/cases/<year>-<paper>-<question>.md`。
2. 把 `tools/check_spec.py` 的输入 spec 存到 `analysis/specs/<id>.json`
   （或复用 `analysis/*.json` 并把路径写进案例卡）。
3. 更新 `index.md` 表格。
4. 若用户纠正过，末尾"负案例"必须写清楚：错在哪、根因、以后怎么机械检查。

**用户纠正 = 三件事（同一轮内完成）**
1. 失败手册新增一行（症状 → 根因 → 动作）；
2. 若可机械判定，扩展 `tools/check_spec.py` 或 MCP `ee_audit_canvas`；
3. 案例卡新增"负案例"一节。

## 案例卡模板

```markdown
# <paper> 题<q> <简短标题>

- **图型**：equilateral-triangle / similar-triangle / circle-inscribed / coordinate /
  function-graph / grid / refraction / composite
- **来源**：题干 dump（段落锚点/原文片段）
- **约束**（从题干抽取，绝不用像素反推）：
  1. ...
- **自由参数**（题面未规定的量，允许从原图量）：尺度 U、原点、朝向角 …
- **推导**（只保留最小自由参数）：
  - ...
- **数值自检**（`tools/check_spec.py` 结果，贴 PASS 表）：
  ```
  PASS equal ...
  PASS angle ...
  RESULT: PASS
  ```
- **最终 spec**：`analysis/specs/<id>.json`（含 `points` + `checks`）
- **落笔**：`ee_draw_figure { ... }`（关键参数：pen_mm、font_index/face、padding、math）
- **验证**：`ee_audit_canvas` 输出 / 截图 / 用户验收
- **负案例（踩过的坑）**：
  - 错法：… → 现象：… → 根因：… → 以后用哪条检查拦住
```

## 索引维护

`index.md` 一行一张卡；未完成/待补的也先占位，避免"没写就是没有"。
