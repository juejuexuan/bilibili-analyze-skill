# Changelog

All notable changes to the `bilibili-analyze` skill are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- 面向公开发布的清理：移除所有个人环境配置（本机 Obsidian vault 路径与个人目录约定），Obsidian 导出改为完全参数化——`--vault` 参数或 `BILIBILI_ANALYZE_VAULT` 环境变量，未指定时友好报错退出。
- 新增 `README.md`、`LICENSE`（MIT）、`requirements.txt`、`.gitignore`。

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

[Unreleased]: https://github.com/juejuexuan/bilibili-analyze-skill/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/juejuexuan/bilibili-analyze-skill/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/juejuexuan/bilibili-analyze-skill/releases/tag/v1.0.0
