# Changelog

All notable changes to the `bilibili-analyze` skill are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.2.0] - 2026-09-08

### Added
- 界面全面美化：渐变 Hero 头部、目录导航（TOC）、章节编号徽章、分区着色卡片（核心问题 / 操作步骤 / 注意陷阱 / 结论 / 关键原话）、悬停动效、`prefers-color-scheme` 暗色模式适配；SVG 配色同步更新，空内容分区不再渲染。
- 新增 `examples/`：两个脱敏的真实运行结果（6 章 + 5 章，选自中科院官方账号「中国科普博览」的公开科普视频，覆盖全部五种 SVG 图表类型），含章节截图与整页长图；已移除音频、字幕、转写文本，`metadata.json` 精简、`state.json` 最小化，不含任何本机路径与推广信息。
- 新增 `requirements.txt`、`.gitignore`（并加强：仓库内直接运行产生的流水线产物一律忽略，`examples/` 显式放行）。

### Changed
- 面向公开发布的清理：移除所有个人环境配置（本机 Obsidian vault 路径与个人目录约定），Obsidian 导出改为完全参数化——`--vault` 参数或 `BILIBILI_ANALYZE_VAULT` 环境变量，未指定时友好报错退出。

### Fixed
- `screenshot.py` / `screenshot_sections.py`: HTTP 服务和 Chrome CDP 不再写死 `18923/18924`。并发任务共用固定端口时，后启动的任务会劫持先启动的 headless Chrome，导致章节截图从中途开始变成另一份 `analysis.html`。现改为临时端口 + 独立 `--user-data-dir`，并校验 `location.href` 是否指向本任务的 HTML。

### Changed (1.1.x 期间)
- `export_obsidian.py` frontmatter：`tags` 改为 YAML 多行列表，并写入 `bv`。B 站带 `#` 的标签不再截断后续属性（Obsidian 属性面板会显示成「只剩半截 tags」）。
- `SKILL.md` 不再内嵌 Python 脚本源码（1296 行 → ~280 行），改为引用 `scripts/` 外部文件，显著降低 skill 加载时的上下文占用。

## [1.1.0] - 2026-07-31

### Fixed
- `screenshot.py` / `screenshot_sections.py`: replaced viewport-scroll slicing with CDP `Page.captureScreenshot` + `clip` to capture each `<section class="chapter">` precisely. Eliminates duplicate chapter headers (e.g. Chapter 7 appearing twice) and content truncation caused by scroll position drift.
- `export_obsidian.py`: now copies `section_*.png` assets and embeds one per chapter.

### Changed
- Phase 4 output format changed from `slice_*.png` + `slices.json` to `section_*.png` + `sections_manifest.json`.
- `SKILL.md` Phase 4 documentation updated to reflect the new CDP clip-based workflow.

### Removed
- Deleted stale `scripts/download.py.bak`.

## [1.0.0] - 2026-07-31

### Added
- Initial release of the bilibili-analyze skill:
  - Download metadata, audio, thumbnail and CC subtitles from Bilibili.
  - Transcribe with faster-whisper / openai-whisper, with CC subtitle priority.
  - AI-assisted chapter splitting with structured JSON output.
  - Build single-file offline HTML notes with inline CSS/SVG.
  - Full-page screenshot and section slicing.
  - Export to Obsidian vault with embedded screenshots.

[Unreleased]: https://github.com/juejuexuan/bilibili-analyze-skill/compare/v1.2.0...HEAD
[1.2.0]: https://github.com/juejuexuan/bilibili-analyze-skill/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/juejuexuan/bilibili-analyze-skill/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/juejuexuan/bilibili-analyze-skill/releases/tag/v1.0.0
