#!/usr/bin/env python3
"""
build_page.py — Phase 3: Build offline HTML with dynamic SVG charts.
Usage: python build_page.py <state.json_or_workdir> [--chapters chapters.json]
The AI writes chapters.json first, then this script generates analysis.html.
"""
import argparse, json, os, sys
from pathlib import Path
from textwrap import dedent

# ── SVG generators ──────────────────────────────────────────

PALETTE = ["#6366F1", "#0EA5E9", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6", "#EC4899"]

def svg_flow(title: str, items: list[str], width: int = 800, height: int = 0) -> str:
    n = len(items)
    # Scale box width: generous minimum for CJK text, cap to avoid overly wide boxes
    gap = 14
    side_margin = 60
    box_w = max(min((width - side_margin) // n - gap, 145), 100)
    x_start = (width - (n * box_w + (n - 1) * gap)) // 2
    # Auto-calc height: title(40) + box(68) + padding(20)
    if height <= 0:
        height = 40 + 68 + 20
    colors = PALETTE
    # Pick font size: smaller when many items or long labels
    max_label_len = max(len(item.replace("\n", "")) for item in items) if items else 6
    font_size = 12 if n <= 5 and max_label_len <= 8 else 11 if n <= 6 else 10
    box_h = 68
    elems = [
        f'<rect width="{width}" height="{height}" fill="#FFFFFF" rx="12"/>',
        f'<text x="{width/2}" y="28" text-anchor="middle" font-family="sans-serif" font-size="16" font-weight="bold" fill="#111827">{title}</text>',
    ]
    for i, item in enumerate(items):
        x = x_start + i * (box_w + gap)
        y = 50
        c = colors[i % len(colors)]
        elems.append(f'<rect x="{x}" y="{y}" width="{box_w}" height="{box_h}" rx="10" fill="{c}" opacity="0.10" stroke="{c}" stroke-width="1.5"/>')
        lines = item.split("\n")
        line_spacing = font_size + 6
        text_block_h = len(lines) * line_spacing
        y_start = y + (box_h - text_block_h) / 2 + font_size
        for j, line in enumerate(lines):
            elems.append(f'<text x="{x + box_w/2}" y="{y_start + j * line_spacing}" text-anchor="middle" font-family="sans-serif" font-size="{font_size}" fill="#1f2937">{line}</text>')
        if i < n - 1:
            ax = x + box_w + 2
            mid_y = y + box_h / 2
            elems.append(f'<polygon points="{ax},{mid_y-5} {ax+8},{mid_y} {ax+8},{mid_y+10} {ax},{mid_y+5}" fill="#A3A3A3"/>')
    return '\n'.join(f'  {e}' for e in elems)

def svg_decision_tree(title: str, question: str, yes_text: str, no_text: str, width: int = 800, height: int = 280) -> str:
    cx, cy = width // 2, 60
    elems = [
        f'<rect width="{width}" height="{height}" fill="#FFFFFF" rx="12"/>',
        f'<text x="{width/2}" y="28" text-anchor="middle" font-family="sans-serif" font-size="16" font-weight="bold" fill="#111827">{title}</text>',
        f'<ellipse cx="{cx}" cy="{cy}" rx="105" ry="22" fill="#6366F1" opacity="0.12" stroke="#6366F1" stroke-width="1.5"/>',
        f'<text x="{cx}" y="{cy+5}" text-anchor="middle" font-family="sans-serif" font-size="14" font-weight="bold" fill="#4338CA">{question}</text>',
    ]
    for bx, by, color, label in [(cx - 180, 160, "#10B981", yes_text), (cx + 180, 160, "#EF4444", no_text)]:
        elems.append(f'<line x1="{cx}" y1="{cy+22}" x2="{bx}" y2="{by-22}" stroke="#A3A3A3" stroke-width="1.5" stroke-dasharray="4,3"/>')
        elems.append(f'<rect x="{bx-95}" y="{by-22}" width="190" height="44" rx="10" fill="{color}" opacity="0.10" stroke="{color}" stroke-width="1.5"/>')
        elems.append(f'<text x="{bx}" y="{by+2}" text-anchor="middle" font-family="sans-serif" font-size="13" fill="#1f2937">{label}</text>')
    return '\n'.join(f'  {e}' for e in elems)

def svg_timeline(title: str, events: list[dict], width: int = 800, height: int = 300) -> str:
    elems = [
        f'<rect width="{width}" height="{height}" fill="#FFFFFF" rx="12"/>',
        f'<text x="{width/2}" y="28" text-anchor="middle" font-family="sans-serif" font-size="16" font-weight="bold" fill="#111827">{title}</text>',
        f'<line x1="70" y1="55" x2="70" y2="{height-25}" stroke="#6366F1" stroke-width="2" stroke-linecap="round"/>',
    ]
    colors = PALETTE
    for i, ev in enumerate(events):
        y = 80 + i * 55
        c = colors[i % len(colors)]
        elems.append(f'<circle cx="70" cy="{y}" r="7" fill="{c}" stroke="white" stroke-width="2"/>')
        elems.append(f'<text x="90" y="{y-5}" font-family="sans-serif" font-size="13" font-weight="bold" fill="#111827">{ev["label"]}</text>')
        elems.append(f'<text x="90" y="{y+15}" font-family="sans-serif" font-size="12" fill="#737373">{ev["detail"]}</text>')
    return '\n'.join(f'  {e}' for e in elems)

def svg_matrix(title: str, col_headers: list[str], row_headers: list[str], data: list[list[str]], width: int = 800, height: int = 280) -> str:
    cell_w = (width - 160) // len(col_headers)
    cell_h = 50
    start_x, start_y = 150, 60
    elems = [
        f'<rect width="{width}" height="{height}" fill="#FFFFFF" rx="12"/>',
        f'<text x="{width/2}" y="30" text-anchor="middle" font-family="sans-serif" font-size="16" font-weight="bold" fill="#111827">{title}</text>',
    ]
    for j, hdr in enumerate(col_headers):
        x = start_x + j * cell_w
        elems.append(f'<rect x="{x}" y="{start_y}" width="{cell_w}" height="32" rx="6" fill="#6366F1" opacity="0.12"/>')
        elems.append(f'<text x="{x+cell_w/2}" y="{start_y+21}" text-anchor="middle" font-family="sans-serif" font-size="13" font-weight="bold" fill="#4338CA">{hdr}</text>')
    for i, rh in enumerate(row_headers):
        y = start_y + 36 + i * cell_h
        elems.append(f'<rect x="10" y="{y}" width="130" height="{cell_h}" rx="6" fill="#F5F5F5"/>')
        elems.append(f'<text x="75" y="{y+cell_h/2+4}" text-anchor="middle" font-family="sans-serif" font-size="12" font-weight="bold" fill="#404040">{rh}</text>')
        for j, val in enumerate(data[i] if i < len(data) else []):
            x = start_x + j * cell_w
            bg = ["#FEF2F2", "#ECFDF5", "#FFFBEB", "#EFF6FF"][(i + j) % 4]
            elems.append(f'<rect x="{x}" y="{y}" width="{cell_w}" height="{cell_h}" rx="6" fill="{bg}" stroke="#E5E5E5" stroke-width="1"/>')
            elems.append(f'<text x="{x+cell_w/2}" y="{y+cell_h/2+4}" text-anchor="middle" font-family="sans-serif" font-size="13" fill="#1f2937">{val}</text>')
    return '\n'.join(f'  {e}' for e in elems)

def svg_causal_chain(title: str, nodes: list[dict], width: int = 800, height: int = 200) -> str:
    elems = [
        f'<rect width="{width}" height="{height}" fill="#FFFFFF" rx="12"/>',
        f'<text x="{width/2}" y="28" text-anchor="middle" font-family="sans-serif" font-size="16" font-weight="bold" fill="#111827">{title}</text>',
        '<defs><marker id="arrowhead" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto"><polygon points="0 0, 10 3.5, 0 7" fill="#A3A3A3"/></marker></defs>',
    ]
    n = len(nodes)
    colors = PALETTE
    spacing = (width - 100) // max(n, 1)
    for i, node in enumerate(nodes):
        x = 50 + i * spacing
        y, r = 75, 30
        c = colors[i % len(colors)]
        elems.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{c}" opacity="0.10" stroke="{c}" stroke-width="2"/>')
        elems.append(f'<text x="{x}" y="{y+5}" text-anchor="middle" font-family="sans-serif" font-size="13" font-weight="bold" fill="#1f2937">{node["label"]}</text>')
        if node.get("detail"):
            elems.append(f'<text x="{x}" y="{y+r+18}" text-anchor="middle" font-family="sans-serif" font-size="11" fill="#737373">{node["detail"]}</text>')
        if i < n - 1:
            nx = 50 + (i + 1) * spacing - r - 2
            elems.append(f'<line x1="{x+r+2}" y1="{y}" x2="{nx}" y2="{y}" stroke="#A3A3A3" stroke-width="1.5" marker-end="url(#arrowhead)"/>')
    return '\n'.join(f'  {e}' for e in elems)

# ── SVG factory ─────────────────────────────────────────────

def generate_svg(chapter: dict) -> str:
    svg_type = chapter.get("svg_type", "flow")
    ch_title = chapter.get("title", "")
    # Common SVG wrapper — no inline style (CSS handles sizing via .svg-wrap svg)
    def wrap(w, h, body):
        return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}">\n{body}\n</svg>'
    if svg_type == "flow":
        items = chapter.get("svg_items", ["Step 1", "Step 2", "Step 3", "Step 4"])
        w = 800
        h = max(128, 40 + 68 + 20)
        return wrap(w, h, svg_flow(ch_title, items, width=w, height=h))
    elif svg_type == "decision_tree":
        q = chapter.get("svg_question", "Condition?")
        return wrap(800, 280, svg_decision_tree(ch_title, q, chapter.get("svg_yes", "YES"), chapter.get("svg_no", "NO"), width=800))
    elif svg_type == "timeline":
        events = chapter.get("svg_events", [{"label": "Start", "detail": "begin"}, {"label": "Mid", "detail": "progress"}, {"label": "End", "detail": "done"}])
        h = max(220, 60 + len(events) * 55 + 30)
        return wrap(800, h, svg_timeline(ch_title, events, width=800, height=h))
    elif svg_type == "matrix":
        cols = chapter.get("svg_cols", ["Col1", "Col2"])
        rows = chapter.get("svg_rows", ["Row1", "Row2"])
        data = chapter.get("svg_data", [["", ""], ["", ""]])
        h = 80 + len(rows) * 50 + 30
        return wrap(800, h, svg_matrix(ch_title, cols, rows, data, width=800, height=h))
    elif svg_type == "causal":
        nodes = chapter.get("svg_nodes", [{"label": "A", "detail": "cause"}, {"label": "B", "detail": "effect"}])
        return wrap(800, 200, svg_causal_chain(ch_title, nodes, width=800))
    else:
        items = chapter.get("svg_items", ["Step 1", "Step 2", "Step 3"])
        return wrap(800, 128, svg_flow(ch_title, items, width=800, height=128))

# ── HTML builder ────────────────────────────────────────────

CSS = dedent("""
  :root {
    --bg: #FAFAFA; --surface: #FFFFFF; --text: #171717; --text2: #525252; --text3: #8F8F8F;
    --accent: #FB7299; --blue: #3B82F6; --green: #10B981; --amber: #D97706; --red: #DC2626; --violet: #7C3AED;
    --border: #E5E5E5; --border-strong: #D4D4D4; --radius: 14px;
    --shadow: 0 1px 2px rgba(0,0,0,.04);
    --tint-problem: #FDF6F7; --tint-steps: #F6F9FE; --tint-pitfalls: #FDFAF3;
    --tint-conclusion: #F4FBF7; --tint-quote: #F8F6FD;
    --mono: ui-monospace, "SF Mono", "JetBrains Mono", Consolas, monospace;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --bg: #0A0A0A; --surface: #121212; --text: #EDEDED; --text2: #A1A1A1; --text3: #6B6B6B;
      --border: #262626; --border-strong: #383838;
      --shadow: 0 1px 2px rgba(0,0,0,.5);
      --tint-problem: #1C1315; --tint-steps: #121A29; --tint-pitfalls: #1C1710;
      --tint-conclusion: #101C15; --tint-quote: #17131F;
    }
  }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  html { scroll-behavior: smooth; }
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", "Noto Sans SC", sans-serif;
    background: var(--bg); color: var(--text); line-height: 1.75;
    -webkit-font-smoothing: antialiased; text-rendering: optimizeLegibility; }
  .container { max-width: 820px; margin: 0 auto; padding: 28px 20px 64px; }

  /* ── Hero header ── */
  .header { position: relative; overflow: hidden; border-radius: var(--radius);
    background: #0A0A0A; padding: 38px 34px 30px; margin-bottom: 18px; color: #EDEDED;
    border: 1px solid #262626; }
  .header::before { content: ""; position: absolute; inset: 0; pointer-events: none;
    background-image: radial-gradient(rgba(255,255,255,.13) 1px, transparent 1.2px);
    background-size: 22px 22px;
    mask-image: linear-gradient(115deg, rgba(0,0,0,.9) 0%, rgba(0,0,0,.35) 55%, transparent 85%);
    -webkit-mask-image: linear-gradient(115deg, rgba(0,0,0,.9) 0%, rgba(0,0,0,.35) 55%, transparent 85%); }
  .header::after { content: ""; position: absolute; right: -90px; top: -110px; width: 320px; height: 320px;
    border-radius: 50%; background: radial-gradient(circle, rgba(251,114,153,.28) 0%, transparent 65%);
    pointer-events: none; }
  .header > * { position: relative; z-index: 1; }
  .header .kicker { font-family: var(--mono); font-size: .72rem; font-weight: 500; letter-spacing: .22em;
    text-transform: uppercase; color: #FB7299; margin-bottom: 12px; }
  .header h1 { font-size: 1.55rem; line-height: 1.4; letter-spacing: -0.02em; font-weight: 700;
    margin-bottom: 16px; color: #FAFAFA; }
  .header .meta { display: flex; flex-wrap: wrap; gap: 8px; font-size: .83rem; color: #A1A1A1; }
  .header .meta span { background: rgba(255,255,255,.06); padding: 3px 12px; border-radius: 20px;
    border: 1px solid rgba(255,255,255,.12); }
  .header .meta .num { font-family: var(--mono); font-size: .8rem; }
  .header .meta a { color: #EDEDED; text-decoration: none; font-weight: 600; font-family: var(--mono); }
  .header .meta a:hover { color: #FB7299; }
  .header .tags { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 14px; }
  .header .tag { background: transparent; color: #C9A3B4; font-size: .75rem;
    padding: 2px 11px; border-radius: 6px; border: 1px solid rgba(251,114,153,.3); }
  .header .desc { margin-top: 14px; font-size: .85rem; color: #8F8F8F; line-height: 1.7;
    display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }

  /* ── TOC ── */
  .toc { background: var(--surface); border-radius: var(--radius); padding: 18px 22px 20px;
    margin-bottom: 26px; border: 1px solid var(--border); box-shadow: var(--shadow); }
  .toc-title { font-family: var(--mono); font-size: .72rem; font-weight: 500; letter-spacing: .18em;
    text-transform: uppercase; color: var(--text3); margin-bottom: 12px; }
  .toc-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 2px 20px; }
  .toc a { display: flex; align-items: baseline; gap: 10px; color: var(--text2); text-decoration: none;
    font-size: .88rem; padding: 6px 8px; border-radius: 8px;
    transition: transform .2s ease-out, background-color .2s ease-out, color .2s ease-out; }
  .toc a:hover { background: var(--tint-steps); color: var(--text); transform: translateX(3px); }
  .toc .n { font-family: var(--mono); font-size: .74rem; font-weight: 600; color: var(--accent); min-width: 22px; }
  .toc .t { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

  /* ── Chapters ── */
  .chapter { background: var(--surface); border-radius: var(--radius); margin-bottom: 28px;
    box-shadow: var(--shadow); border: 1px solid var(--border); overflow: hidden;
    opacity: 0; animation: fadeUp .5s ease-out forwards; }
  @keyframes fadeUp { from { opacity: 0; transform: translateY(14px); } to { opacity: 1; transform: none; } }
  @media (prefers-reduced-motion: reduce) {
    .chapter { animation: none; opacity: 1; }
    html { scroll-behavior: auto; }
  }
  .chapter-header { display: flex; align-items: center; gap: 16px; padding: 18px 24px;
    border-bottom: 1px solid var(--border); }
  .chapter-num { flex: none; width: 38px; height: 38px; border-radius: 10px; display: flex;
    align-items: center; justify-content: center; font-family: var(--mono);
    font-size: .95rem; font-weight: 700; font-variant-numeric: tabular-nums;
    color: #FAFAFA; background: #171717; }
  @media (prefers-color-scheme: dark) {
    .chapter-num { background: #EDEDED; color: #171717; }
  }
  .chapter-heading { flex: 1; min-width: 0; }
  .chapter-heading .kicker { font-family: var(--mono); font-size: .68rem; font-weight: 500;
    letter-spacing: .18em; color: var(--text3); text-transform: uppercase; }
  .chapter-header h2 { font-size: 1.14rem; font-weight: 650; letter-spacing: -0.01em;
    margin-top: 2px; color: var(--text); line-height: 1.45; }
  .chapter-time { flex: none; }
  .chapter-time a { color: var(--text2); text-decoration: none; font-weight: 500;
    font-family: var(--mono); font-size: .78rem; font-variant-numeric: tabular-nums;
    padding: 5px 12px; border-radius: 8px; border: 1px solid var(--border);
    transition: color .2s ease-out, border-color .2s ease-out; }
  .chapter-time a:hover { color: var(--accent); border-color: var(--accent); }
  .chapter-body { padding: 22px 24px 24px; }
  .block { border-radius: 10px; padding: 13px 16px; margin-bottom: 12px;
    border: 1px solid var(--border); border-left: 2px solid var(--border-strong); }
  .block:last-of-type { margin-bottom: 0; }
  .block-label { font-family: var(--mono); font-size: .72rem; font-weight: 600;
    letter-spacing: .14em; text-transform: uppercase; margin-bottom: 5px; }
  .block-content { font-size: .92rem; color: var(--text); }
  .block-content ul { list-style: none; padding-left: 0; }
  .block-content li { position: relative; padding-left: 18px; margin-bottom: 4px; }
  .block.steps .block-content li::before { content: "\\25B8"; color: var(--blue); position: absolute; left: 0; font-weight: 700; }
  .block.pitfalls .block-content li::before { content: "\\26A0"; color: var(--amber); position: absolute; left: 0; }
  .block.problem { background: var(--tint-problem); border-left-color: var(--red); }
  .block.problem .block-label { color: var(--red); }
  .block.steps { background: var(--tint-steps); border-left-color: var(--blue); }
  .block.steps .block-label { color: var(--blue); }
  .block.pitfalls { background: var(--tint-pitfalls); border-left-color: var(--amber); }
  .block.pitfalls .block-label { color: var(--amber); }
  .block.conclusion { background: var(--tint-conclusion); border-left-color: var(--green); }
  .block.conclusion .block-label { color: var(--green); }
  .block.quote { background: var(--tint-quote); border-left-color: var(--violet); }
  .block.quote .block-label { color: var(--violet); }
  .block.quote .block-content { font-style: italic; color: var(--text2); }
  .callout { font-size: .88rem; }
  .svg-wrap { margin: 20px 0 2px; border-radius: 12px; overflow: hidden;
    border: 1px solid var(--border); background: #FFFFFF; }
  .svg-wrap svg { display: block; width: 100%; height: auto; }

  .footer { text-align: center; padding: 28px 20px 12px; font-size: .78rem; color: var(--text3);
    font-family: var(--mono); letter-spacing: .04em; }
  .footer a { color: var(--accent); text-decoration: none; font-weight: 600; }
  .footer a:hover { text-decoration: underline; }

  table { width: 100%; border-collapse: collapse; margin: 10px 0; font-size: .85rem; }
  th, td { border: 1px solid var(--border); padding: 8px 12px; text-align: left; }
  th { background: var(--tint-steps); font-weight: 600; }
  pre { background: #171717; color: #EDEDED; padding: 14px 18px; border-radius: 10px;
    overflow-x: auto; font-size: .83rem; line-height: 1.6; margin: 10px 0; }
  code { font-family: var(--mono); }

  @media (max-width: 640px) {
    .container { padding: 16px 12px 48px; }
    .header { padding: 28px 22px 24px; }
    .header h1 { font-size: 1.3rem; }
    .chapter-header { gap: 12px; padding: 16px 18px; }
    .chapter-body { padding: 18px 18px 20px; }
    .chapter-time a { font-size: .72rem; padding: 4px 9px; }
  }
  @media print {
    .chapter { animation: none; opacity: 1; break-inside: avoid; box-shadow: none; }
    .toc, .footer { display: none; }
  }
""").strip()

def format_time_link(bvid: str, seconds: int) -> str:
    return f'<a href="https://www.bilibili.com/video/{bvid}?t={seconds}" target="_blank" rel="noopener">'

def build_chapter_section(i: int, ch: dict, bvid: str) -> str:
    start_sec = ch.get("start", 0)
    time_link_start = format_time_link(bvid, start_sec)
    svg = generate_svg(ch)
    blocks = []
    if ch.get("problem"):
        blocks.append(f'''
        <div class="block problem">
          <div class="block-label">核心问题</div>
          <div class="block-content"><p>{ch['problem']}</p></div>
        </div>''')
    if ch.get("steps"):
        steps_html = "".join(f"<li>{s}</li>" for s in ch["steps"])
        blocks.append(f'''
        <div class="block steps">
          <div class="block-label">操作步骤</div>
          <div class="block-content"><ul>{steps_html}</ul></div>
        </div>''')
    if ch.get("pitfalls"):
        pitfalls_html = "".join(f"<li>{p}</li>" for p in ch["pitfalls"])
        blocks.append(f'''
        <div class="block pitfalls">
          <div class="block-label">注意陷阱</div>
          <div class="block-content"><ul>{pitfalls_html}</ul></div>
        </div>''')
    if ch.get("conclusion"):
        blocks.append(f'''
        <div class="block conclusion">
          <div class="block-label">一句话结论</div>
          <div class="block-content"><p>{ch['conclusion']}</p></div>
        </div>''')
    if ch.get("key_quote"):
        blocks.append(f'''
        <div class="block quote">
          <div class="block-label">关键原话</div>
          <div class="callout">{ch['key_quote']}</div>
        </div>''')
    return f'''
    <section class="chapter" id="{ch.get('id','ch'+str(i+1))}" style="animation-delay:{i*70}ms">
      <div class="chapter-header">
        <div class="chapter-num">{i+1:02d}</div>
        <div class="chapter-heading">
          <div class="kicker">Chapter {i+1:02d}</div>
          <h2>{ch.get('title','')}</h2>
        </div>
        <div class="chapter-time">{time_link_start}{ch.get('time_range','')}</a></div>
      </div>
      <div class="chapter-body">{''.join(blocks)}
        <div class="svg-wrap">{svg}</div>
      </div>
    </section>'''

def build_toc(chapters: list[dict]) -> str:
    if len(chapters) < 2:
        return ""
    items = "".join(
        f'<a href="#{ch.get("id", "ch"+str(i+1))}"><span class="n">{i+1:02d}</span><span class="t">{ch.get("title","")}</span></a>'
        for i, ch in enumerate(chapters)
    )
    return f'''
  <nav class="toc">
    <div class="toc-title">目录 · Contents</div>
    <div class="toc-grid">{items}</div>
  </nav>'''

def build_html(state: dict, chapters: list[dict], bvid: str, meta: dict) -> str:
    tags_html = "".join(f'<span class="tag">{t}</span>' for t in meta.get("tags", []))
    toc_html = build_toc(chapters)
    chapter_sections = "".join(build_chapter_section(i, ch, bvid) for i, ch in enumerate(chapters))
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{meta.get('title','')}</title>
<style>{CSS}</style>
</head>
<body>
<div class="container">
  <header class="header">
    <div class="kicker">Bilibili Video Analysis</div>
    <h1>{meta.get('title','')}</h1>
    <div class="meta">
      <span>UP · {meta.get('uploader','')}</span>
      <span class="num">{meta.get('duration_string','')}</span>
      <span><a href="https://www.bilibili.com/video/{bvid}" target="_blank" rel="noopener">{bvid}</a></span>
    </div>
    <div class="tags">{tags_html}</div>
    <div class="desc">{meta.get('description','')}</div>
  </header>
  {toc_html}
  {chapter_sections}
  <footer class="footer"><p>AI-GENERATED NOTES · <a href="https://www.bilibili.com/video/{bvid}" target="_blank" rel="noopener">SOURCE VIDEO</a></p></footer>
</div>
</body>
</html>"""


VALID_SVG_TYPES = {"flow", "timeline", "matrix", "decision_tree", "causal"}
REQUIRED_FIELDS = ["id", "title", "start", "time_range", "problem", "steps", "pitfalls", "conclusion", "key_quote", "svg_type"]

def validate_chapters(chapters):
    fixed = []
    for i, ch in enumerate(chapters):
        idx = i + 1
        for field in REQUIRED_FIELDS:
            if field not in ch:
                print(f"[WARN] ch{idx}: missing required field '{field}'")
                ch[field] = "" if field != "start" else 0
        st = ch.get("svg_type", "flow")
        if st not in VALID_SVG_TYPES:
            print(f"[WARN] ch{idx}: unknown svg_type '{st}', falling back to 'flow'")
            ch["svg_type"] = "flow"
        if ch["svg_type"] == "decision_tree" and "svg_question" not in ch:
            ch["svg_question"] = ch.get("problem", "Decision?")
        fixed.append(ch)
    return fixed


def main():
    parser = argparse.ArgumentParser(description="Build single-page HTML with dynamic SVGs")
    parser.add_argument("input", help="Path to state.json or workdir")
    parser.add_argument("--chapters", default=None, help="Path to chapters.json")
    args = parser.parse_args()
    inp = Path(args.input)
    if inp.is_dir():
        state_path = inp / "state.json"
        workdir = inp
    else:
        state_path = inp
        workdir = state_path.parent
    with open(state_path, encoding="utf-8") as f:
        state = json.load(f)
    chapters_path = Path(args.chapters) if args.chapters else workdir / "chapters.json"
    if not chapters_path.exists():
        print(f"[ERROR] chapters.json not found at {chapters_path}")
        sys.exit(1)
    with open(chapters_path, encoding="utf-8-sig") as f:
        chapters_raw = json.load(f)
    if isinstance(chapters_raw, dict) and "chapters" in chapters_raw:
        chapters = chapters_raw["chapters"]
    else:
        chapters = chapters_raw
    meta_path = state.get("metadata_path")
    meta = json.load(open(meta_path, encoding="utf-8")) if meta_path else {}
    bvid = state.get("bv_id") or state.get("slug", "unknown")
    chapters = validate_chapters(chapters)
    print("=" * 50)
    print(f"  Phase 3: Build HTML + {len(chapters)} SVG Charts")
    print("=" * 50)
    html = build_html(state, chapters, bvid, meta)
    out_path = workdir / "analysis.html"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[OK] HTML -> {out_path} ({len(html)//1024}KB)")

if __name__ == "__main__":
    main()
