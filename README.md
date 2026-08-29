# bilibili-analyze

从 B 站视频链接到离线 HTML 笔记的全自动分析流水线，配合 AI Agent（Kimi Code / Claude Code 等）使用效果最佳。

## 功能特性

- **并行下载**：元数据 + 最佳音频 + 封面 + CC 字幕一次抓齐（基于 yt-dlp）
- **智能转写**：有 CC 字幕直接解析（省 80% 时间）；无字幕时 Whisper 转写，faster-whisper 优先、openai-whisper 回退
- **AI 分章**：Agent 阅读转写稿按视频自然结构分章，逐章提炼「核心问题 / 步骤 / 陷阱 / 结论 / 金句」
- **动态 SVG**：每章按内容类型生成 flow / timeline / matrix / decision_tree / causal 五类图表
- **离线 HTML**：单文件笔记，CSS 与 SVG 全部内联，无网络也能看
- **章节截图**：Chrome headless + CDP `clip` 精确截取每章，自动合并整页长图
- **Obsidian 导出（可选）**：生成带 YAML frontmatter 的 Markdown 笔记，逐章嵌入截图

## 流水线

```
B站链接 → [并行] 元数据+音频+封面
       → ffmpeg 转 mp3 → ffprobe 验时长
       → 字幕优先（有CC则跳过Whisper）
       → Whisper 转写 (优先 faster-whisper，回退 openai-whisper)
       → AI 按内容分章 → 动态生成 SVG 图表
       → 构建单页离线 HTML (内联 CSS+SVG)
       → Chrome headless 整页截图 → CDP clip 切片
       → 写入 Obsidian vault (可选，需指定 --vault)
```

交互式流程图见 [`assets/workflow.html`](assets/workflow.html)（浏览器直接打开）。

## 环境依赖

| 工具 | 最低版本 | 安装命令 |
|------|---------|---------|
| Python | 3.10+ | https://python.org |
| yt-dlp | 2024+ | `pip install yt-dlp` |
| ffmpeg / ffprobe | 6.0+ | `winget install ffmpeg` (Windows) / `apt install ffmpeg` (Linux) |
| Chrome / Chromium | 120+ | 用于 headless 截图 |
| Whisper 模型 | small 或 turbo | `pip install openai-whisper` 或 `pip install faster-whisper`（首次运行自动下载模型到 `~/.cache/whisper/`） |

安装后先跑预检：

```bash
python scripts/preflight.py
```

全部 `[OK]` 即可开始。

## 安装

```bash
git clone https://github.com/juejuexuan/bilibili-analyze-skill.git
cd bilibili-analyze-skill
pip install -r requirements.txt
```

作为 Agent skill 使用时，将整个目录复制（或符号链接）到 skills 目录：

- Kimi Code / Claude Code：`~/.agents/skills/bilibili-analyze/`
- Codex：`~/.codex/skills/bilibili-analyze/`

## 快速开始

```bash
# Phase 1: 下载（元数据/音频/封面并行）
python scripts/download.py "https://www.bilibili.com/video/BVxxxx" --workdir output

# Phase 2: 转写（CC 字幕优先，否则 Whisper）
python scripts/transcribe.py output/BVxxxx/state.json

# Phase 3: 分章后构建 HTML（chapters.json 由 AI 按 assets/chapters.template.json 生成）
python scripts/build_page.py output/BVxxxx/state.json

# Phase 4: 章节截图
python scripts/screenshot_sections.py output/BVxxxx/analysis.html
```

完整的分章 JSON 结构、SVG 类型选择规则与 Agent 执行规则见 [`SKILL.md`](SKILL.md)。

## Obsidian 导出（可选）

```bash
python scripts/export_obsidian.py output/BVxxxx --vault /path/to/your/vault
```

| 参数 | 环境变量 | 默认值 | 说明 |
|------|---------|--------|------|
| `--vault` | `BILIBILI_ANALYZE_VAULT` | 无（二者至少提供一个） | Obsidian vault 根目录 |
| `--notes-dir` | — | `bilibili-notes` | vault 内笔记相对目录 |
| `--attachments-dir` | — | `bilibili-attachments` | vault 内附件相对目录 |

笔记 frontmatter 含 `title` / `source` / `up` / `date` / `duration` / `bv`；带 `#` 的 B 站标签会被自动清理，避免 YAML 注入。

## 产出目录结构

```
<workdir>/<BV号>/
├── metadata.json              # 视频元数据
├── thumbnail.jpg              # 封面图
├── audio_best.mp3             # 最佳音频 (192kbps mp3)
├── subtitles.srt              # CC 字幕 (如有)
├── state.json                 # 阶段间状态传递
├── chapters.json              # AI 分章结果
├── transcript_full.json       # 转写完整输出
├── transcript_segments.txt    # 带时间戳分段
├── transcript.txt             # 纯文本
├── analysis.html              # 离线 HTML 页面 (单文件)
├── screenshot_full.png        # 整页截图（由章节截图合并）
├── section_1.png, ...         # 每章独立截图
└── sections_manifest.json     # 章节截图 manifest
```

## 常见问题

**下载报 HTTP 412？**
换 `b23.tv` 短链重试；仍失败则导出浏览器 cookies 传入：`python scripts/download.py <url> --workdir output --cookies cookies.txt`。

**Whisper 模型下载慢 / 失败？**
模型缓存在 `~/.cache/whisper/`，可手动下载 `small.pt` 放入；或改用更小的模型。

**转写末段时长与音频差 5% 以上？**
脚本会自动重试一次；仍异常会标记告警但继续后续阶段，多为视频尾部无声片段所致。

**并发截图会不会互相干扰？**
不会。HTTP 服务使用临时端口，Chrome 使用独立 `--user-data-dir`，并校验页面 URL，多任务并行安全。

## 版本

当前版本见 [`VERSION`](VERSION)，变更历史见 [`CHANGELOG.md`](CHANGELOG.md)。

## License

[MIT](LICENSE)
