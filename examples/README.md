# 示例输出

本目录包含两个由本流水线真实运行产生的结果，选自 **中国科普博览**（中国科学院官方账号）的公开科普视频，用于快速了解输出格式与界面效果。内容不含任何推广信息。

## 示例列表

| 示例 | 章节 | 内容类型 |
|------|------|---------|
| [BV1zwtG6qELB · 同样的火电站，为什么冬天就比夏天"给力"？](BV1zwtG6qELB/analysis.html) | 6 章 | 热力学科普 |
| [BV17Atd6dESf · 你天生自带的 Bug 一直在骗你？？？](BV17Atd6dESf/analysis.html) | 5 章 | 图形学科普 |

两个示例覆盖了全部五种 SVG 图表类型：flow、timeline、matrix、decision_tree、causal。

每个示例目录内：

- `analysis.html` — 单文件离线笔记（章节卡片 + SVG 图表 + 目录导航），下载后双击即可离线打开
- `section_*.png` — 每章独立截图（Chrome headless + CDP clip 精确截取）
- `screenshot_full.png` — 整页长截图（由章节截图合并）
- `chapters.json` — AI 分章结果（对照 `assets/chapters.template.json` 的 schema）
- `metadata.json` / `state.json` — 阶段间数据传递的最小示例

## 脱敏处理

- 已移除音频、字幕与转写文本（体积与版权考虑）
- `metadata.json` 仅保留展示字段
- `state.json` 为最小化示例，只含相对路径，不含任何本机信息
- 视频标题、UP 主、BV 号等均为 B 站公开信息，仅作来源标注
