---
name: bilibili-analyze
description: 分析B站视频 - 下载元数据音频封面、Whisper转写、AI分章+SVG图表、离线HTML笔记、截图切片。适用于深度学习/技术教程类视频的深度内容拆解。
tags: [bilibili, video-analysis, whisper, transcription, chinese]
---

# Bilibili Video Deep Analyzer

> 版本：**1.1.0**  |  详见 [`VERSION`](VERSION) 与 [`CHANGELOG.md`](CHANGELOG.md)

从 B站链接到离线 HTML 笔记的全自动分析流水线。

## 触发条件

满足任一即激活此技能：
- 用户提供 `b23.tv` 或 `bilibili.com/video/` 链接并要求分析/总结/做笔记
- 用户要求下载 B站视频、提取字幕
- 用户提到 `bilibili-analyze`

## 整体流程

交互式流程图见 [`assets/workflow.html`](assets/workflow.html)（可直接用浏览器打开）。

```
B站链接 → [并行] 元数据+音频+封面
       → ffmpeg 转 mp3 → ffprobe 验时长
       → 字幕优先（有CC则跳过Whisper）
       → Whisper 转写 (优先 faster-whisper，回退 openai-whisper)
       → 按内容分章 → 动态生成 SVG 图表
       → 构建单页离线 HTML (内联 CSS+SVG)
       → Chrome headless 整页截图 → CDP clip 切片
       → 写入 Obsidian vault (可选，如已配置)
```

## Obsidian 导出（可选）配置

Phase 5 可将分析结果导出到你自己的 Obsidian vault。路径完全由参数指定，不依赖任何固定位置：

| 参数 | 环境变量 | 默认值 | 说明 |
|------|---------|--------|------|
| `--vault` | `BILIBILI_ANALYZE_VAULT` | 无（二者至少提供一个） | Obsidian vault 根目录 |
| `--notes-dir` | — | `bilibili-notes` | vault 内笔记相对目录 |
| `--attachments-dir` | — | `bilibili-attachments` | vault 内附件相对目录 |

导出的笔记 frontmatter 含 `title` / `source` / `up` / `date` / `duration` / `bv`，`tags` 使用 YAML 多行列表。B 站标签若带 `#`（如 `#雨创计划`），脚本会自动去掉前导 `#` 并加引号，否则 Obsidian 会把后面整行当注释，属性面板只剩半截。

## 环境依赖

执行前必须检测以下工具，缺失则提示用户安装：

| 工具 | 最低版本 | 安装命令 |
|------|---------|---------|
| yt-dlp | 2024+ | `pip install yt-dlp` |
| ffmpeg | 6.0+ | `winget install ffmpeg` (Windows) / `apt install ffmpeg` (Linux) |
| ffprobe | 匹配 ffmpeg | 随 ffmpeg 一起安装 |
| Python | 3.10+ | https://python.org |
| Chrome/Chromium | 120+ | 用于截图 |
| Whisper 模型 | small 或 turbo | `pip install openai-whisper` 或 `pip install faster-whisper` |

预检输出每个工具的状态（✓/✗），缺失时给出安装命令。

## 执行阶段

### Phase 1: 下载（可并行）

```bash
python scripts/download.py "<bilibili_url>" --workdir <output_dir>
```

逻辑：
1. `yt-dlp --print-json --no-download` → 保存 `metadata.json`
2. 并行下载：最佳音频流 + 封面缩略图 + CC字幕（如有）
3. ffmpeg 转为 192kbps mp3
4. ffprobe 验证时长，与 metadata 对比差异 > 5% 则告警
5. 写入 `state.json` 供下游阶段引用

**关键参数**：`--no-playlist` 避免多P混流

**遇到 412 错误时**（HTTP Error 412: Precondition Failed）：
1. **优先尝试短链**：将 `bilibili.com/video/BV...` 替换为 `b23.tv/...` 格式的短链重新下载
2. **或手动传 cookies**：`--cookies /path/to/cookies.txt`（用 `yt-dlp --cookies-from-browser edge --cookies /tmp/cookies.txt URL` 导出）
3. **或显式指定浏览器 cookies**：在命令中加 `--cookies-from-browser edge`

### Phase 2: 转写

```bash
python scripts/transcribe.py <workdir/state.json>
```

优先级：
1. **有 CC 字幕 (.srt)** → 直接解析为 segments，跳过 Whisper（省 80% 时间）
2. **faster-whisper** small 模型 (CTranslate2, 快 4x)
3. **openai-whisper** small 模型 — 最终回退
4. 语言检测：中文视频用 `zh`，英文用 `en`

导出文件：
- `transcript_full.json` — 完整 Whisper 输出
- `transcript_segments.txt` — `[start-end] text` 格式
- `transcript.txt` — 纯文本

校验：末段 end 时间 vs ffprobe duration，差异 > 5% 则标记异常并重试 1 次。

### Phase 3: AI 分章 + HTML 生成

**分章由 AI 手动完成**（不靠脚本自动分，保证质量）：

读取 transcript，按视频自然结构分章。每章结构如下：

```json
{
  "id": "ch1",
  "title": "章节标题",
  "start": 0,
  "time_range": "00:00 - 05:23",
  "problem": "一句话描述本章要解决的问题",
  "steps": ["操作步骤1", "操作步骤2", "操作步骤3"],
  "pitfalls": ["陷阱1 + 解决方法", "陷阱2 + 解决方法"],
  "conclusion": "一句话结论",
  "key_quote": "视频原话（带时间戳）",
  "svg_type": "flow|timeline|matrix|decision_tree|causal",
  "svg_items": ["步骤节点1", "步骤节点2"],
  "svg_events": [{"label": "标签", "detail": "详情"}],
  "svg_cols": ["列1", "列2"],
  "svg_rows": ["行1", "行2"],
  "svg_data": [["值", "值"], ["值", "值"]],
  "svg_nodes": [{"label": "节点", "detail": "描述"}]
}
```

SVG 图表类型选择规则：
- 流程类内容 → `flow`（横向箭头 + 框）
- 概念关系 → `flow`（层次/关系图）
- 时间变化 → `timeline`（纵向时间线）
- 对比内容 → `matrix`（2D 矩阵）
- 风险/误区 → `decision_tree`（决策树）
- 因果链 → `causal`（因果链图）

生成完成后调用：

```bash
python scripts/build_page.py <workdir/state.json>
```

生成的 HTML 要求：
- **单文件离线可用**：CSS 内联 `<style>`，SVG 内联 HTML
- 每章为独立 `<section>`
- 包含元数据头部（UP主、时长、标签、简介、BV号）
- 每张 SVG 包含真实关键词、关系、箭头，禁止占位装饰图

### Phase 4: 章节截图

```bash
python scripts/screenshot.py <workdir/analysis.html>
```

1. 启动本地 HTTP 服务（临时端口，禁止写死 18923/18924），用独立 `--user-data-dir` 的 Chrome DevTools Protocol (CDP) 打开 `analysis.html`。并发截图时固定端口会劫持别人的 Chrome，导致章节图串到另一份 HTML。
2. 设置足够高的 viewport，把整个页面一次性放入视口，避免滚动造成的内容重复/截断
3. 对每个 `<section class="chapter">` 用 `Page.captureScreenshot` 的 `clip` 参数精确截取该章节区域
4. 生成 `section_1.png` ~ `section_N.png`，并合并为 `screenshot_full.png`
5. 写入 `sections_manifest.json` 记录每章高度和文件信息

> 相比旧版（调整 viewport + 滚动 + ffmpeg 切片），clip 方案能从根本上消除章节标题重复、底部截断等问题。

### Phase 5: Obsidian 导出（可选）

```bash
python scripts/export_obsidian.py <workdir> --vault /path/to/your/vault
```

指定 vault 后（`--vault` 参数或环境变量 `BILIBILI_ANALYZE_VAULT`）：
1. 复制 `analysis.html`、封面、整页截图、章节截图到 `{vault}/{--attachments-dir}/`
2. 生成 `.md` 笔记到 `{vault}/{--notes-dir}/`，每章嵌入对应的 `section_N.png`

未提供 vault 时脚本会打印提示并退出，不影响前四个阶段的产出。

## 产出目录结构

```
<workdir>/<slug>/
├── metadata.json              # 视频元数据
├── thumbnail.jpg              # 封面图
├── audio_best.mp3             # 最佳音频 (192kbps mp3)
├── subtitles.srt              # CC 字幕 (如有)
├── state.json                 # 阶段间状态传递
├── chapters.json              # AI 分章结果
├── transcript_full.json       # Whisper 完整输出
├── transcript_segments.txt    # 带时间戳分段
├── transcript.txt             # 纯文本
├── analysis.html              # 离线 HTML 页面 (单文件)
├── screenshot_full.png        # 整页截图（由章节截图合并）
├── section_1.png, ...         # 每章独立截图
└── sections_manifest.json     # 章节截图 manifest
```

执行 Phase 5 时，Obsidian 笔记（`.md`）与附件导出到 vault 指定目录，不落在本工作目录。

## 错误处理矩阵

| 失败环节 | 处理策略 |
|---------|---------|
| yt-dlp 下载超时 | 重试 2 次，间隔 5s；仍失败 → 让用户提供 cookies |
| Whisper 模型缺失/损坏 | 自动下载 → 下载失败则换小一级模型 |
| 转写差异 > 5% | 重试 1 次；仍失败 → 标记异常但继续 |
| Chrome 截图失败 | 尝试 Chromium → 尝试 Edge → 跳过截图 |
| ffmpeg crop 失败 | 保留整张截图，不切片 |
| 磁盘空间不足 | 报错并停止后续阶段 |

## 执行规则

1. **并行优先**：Phase 1 的 metadata/audio/thumbnail 必须并行执行
2. **先验后做**：每次先跑 preflight，报告环境状态
3. **字幕优先**：有 CC 字幕直接解析，跳过 Whisper
4. **模型只下一次**：下载前先检查 `~/.cache/whisper/`
5. **失败不阻塞**：某 phase 失败不影响已完成产出，继续后续 phase
6. **绝对路径**：所有脚本调用用绝对路径
7. **进度追踪**：每完成一个 phase 更新进度状态
8. **内容分章由 AI 做**：Phase 3 的分章不靠脚本自动分，是 AI 读 transcript 后手动分章

---

## Python 脚本

脚本以独立文件维护在本 skill 目录的 `scripts/` 子目录中，按 phase 调用；源码不内嵌在本文档，修改脚本文件即生效，版本历史见 `CHANGELOG.md`。

| 脚本 | 阶段 | 用途 |
|------|------|------|
| `scripts/preflight.py` | 预检 | 检测 yt-dlp / ffmpeg / whisper 模型 / chrome / pip 依赖 |
| `scripts/download.py` | Phase 1 | 并行下载元数据、音频、封面、字幕，ffmpeg 转 mp3 并验时长 |
| `scripts/transcribe.py` | Phase 2 | SRT 字幕解析优先，faster-whisper / openai-whisper 回退 |
| `scripts/build_page.py` | Phase 3 | 由 `chapters.json` 生成单文件离线 HTML（内联 CSS + 动态 SVG） |
| `scripts/screenshot.py` | Phase 4 | Chrome headless 整页截图 + 底部空白裁剪 |
| `scripts/screenshot_sections.py` | Phase 4 | CDP `Page.captureScreenshot` + clip 逐章节截图 |
| `scripts/export_obsidian.py` | Phase 5 | 导出附件并生成带 frontmatter 的 Obsidian 笔记 |

---

## 版本管理

- **当前版本**：`1.1.0`（见 [`VERSION`](VERSION)）
- **变更日志**：见 [`CHANGELOG.md`](CHANGELOG.md)
- **语义化版本**：`MAJOR.MINOR.PATCH`
  - `MAJOR`：不兼容的接口或输出格式变更
  - `MINOR`：新增功能、修复问题、输出格式扩展
  - `PATCH`：bug 修复、文档更新

### Git 回滚

本 skill 依托 Git 进行版本控制。每次发布版本请对应一次 git commit/tag：

```bash
# 查看版本历史
git log --oneline

# 回滚到某个历史版本（保留 HEAD，仅还原工作区文件）
git checkout <commit-hash> -- .

# 或创建 tag
git tag -a v1.1.0 -m "fix: CDP clip section screenshots"
```

---

## 安装步骤

1. 将整个 skill 目录（含 `SKILL.md`、`scripts/`、`VERSION`、`CHANGELOG.md`、`assets/`）复制到 agent 的 skills 目录：
   - Kimi Code / Claude Code：`~/.agents/skills/bilibili-analyze/`
   - Codex：`~/.codex/skills/bilibili-analyze/`
2. 安装 Python 依赖：
   ```bash
   pip install yt-dlp openai-whisper faster-whisper Pillow numpy
   ```
3. 安装系统工具（如未装）：
   - **ffmpeg**：`winget install ffmpeg` (Windows) 或 `apt install ffmpeg` (Linux)
   - **Chrome** 或 Chromium（用于截图）
4. 用 `python scripts/preflight.py` 验证环境全部就绪

## 使用示例

```
用户: 分析这个B站视频 https://b23.tv/f4C7g13

AI:
1. [preflight] 检测环境... 全部就绪
2. [Phase 1] 并行下载元数据 + 音频 + 封面... 完成
3. [Phase 2] 无 CC 字幕，启动 Whisper small 转写... 完成 (3min)
4. [Phase 3] AI 分章 + 生成 7 章 SVG + 构建 HTML... 完成
5. [Phase 4] Chrome 截图 → 切片... 完成
6. [Phase 5] 写入 Obsidian... 完成

全部产出在 output/BV1oH5s6NEgE/
```
