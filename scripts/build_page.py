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
    colors = ["#3B82F6", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6", "#EC4899", "#06B6D4"]
    # Pick font size: smaller when many items or long labels
    max_label_len = max(len(item.replace("\n", "")) for item in items) if items else 6
    font_size = 12 if n <= 5 and max_label_len <= 8 else 11 if n <= 6 else 10
    box_h = 68
    elems = [
        f'<rect width="{width}" height="{height}" fill="#FAFBFC" rx="12"/>',
        f'<text x="{width/2}" y="28" text-anchor="middle" font-family="sans-serif" font-size="16" font-weight="bold" fill="#111827">{title}</text>',
    ]
    for i, item in enumerate(items):
        x = x_start + i * (box_w + gap)
        y = 50
        c = colors[i % len(colors)]
        elems.append(f'<rect x="{x}" y="{y}" width="{box_w}" height="{box_h}" rx="8" fill="{c}" opacity="0.15" stroke="{c}" stroke-width="2"/>')
        lines = item.split("\n")
        line_spacing = font_size + 6
        text_block_h = len(lines) * line_spacing
        y_start = y + (box_h - text_block_h) / 2 + font_size
        for j, line in enumerate(lines):
            elems.append(f'<text x="{x + box_w/2}" y="{y_start + j * line_spacing}" text-anchor="middle" font-family="sans-serif" font-size="{font_size}" fill="#1f2937">{line}</text>')
        if i < n - 1:
            ax = x + box_w + 2
            mid_y = y + box_h / 2
            elems.append(f'<polygon points="{ax},{mid_y-5} {ax+8},{mid_y} {ax+8},{mid_y+10} {ax},{mid_y+5}" fill="#9CA3AF"/>')
    return '\n'.join(f'  {e}' for e in elems)

def svg_decision_tree(title: str, question: str, yes_text: str, no_text: str, width: int = 800, height: int = 280) -> str:
    cx, cy = width // 2, 60
    elems = [
        f'<rect width="{width}" height="{height}" fill="#FAFBFC" rx="12"/>',
        f'<text x="{width/2}" y="28" text-anchor="middle" font-family="sans-serif" font-size="16" font-weight="bold" fill="#111827">{title}</text>',
        f'<ellipse cx="{cx}" cy="{cy}" rx="105" ry="22" fill="#3B82F6" opacity="0.2" stroke="#3B82F6" stroke-width="2"/>',
        f'<text x="{cx}" y="{cy+5}" text-anchor="middle" font-family="sans-serif" font-size="14" font-weight="bold" fill="#1E40AF">{question}</text>',
    ]
    for bx, by, color, label in [(cx - 180, 160, "#10B981", yes_text), (cx + 180, 160, "#EF4444", no_text)]:
        elems.append(f'<line x1="{cx}" y1="{cy+22}" x2="{bx}" y2="{by-22}" stroke="#9CA3AF" stroke-width="1.5" stroke-dasharray="4,3"/>')
        elems.append(f'<rect x="{bx-95}" y="{by-22}" width="190" height="44" rx="8" fill="{color}" opacity="0.15" stroke="{color}" stroke-width="2"/>')
        elems.append(f'<text x="{bx}" y="{by+2}" text-anchor="middle" font-family="sans-serif" font-size="13" fill="#1f2937">{label}</text>')
    return '\n'.join(f'  {e}' for e in elems)

def svg_timeline(title: str, events: list[dict], width: int = 800, height: int = 300) -> str:
    elems = [
        f'<rect width="{width}" height="{height}" fill="#FAFBFC" rx="12"/>',
        f'<text x="{width/2}" y="28" text-anchor="middle" font-family="sans-serif" font-size="16" font-weight="bold" fill="#111827">{title}</text>',
        f'<line x1="70" y1="55" x2="70" y2="{height-25}" stroke="#3B82F6" stroke-width="3" stroke-linecap="round"/>',
    ]
    colors = ["#EF4444", "#F59E0B", "#10B981", "#8B5CF6", "#EC4899"]
    for i, ev in enumerate(events):
        y = 80 + i * 55
        c = colors[i % len(colors)]
        elems.append(f'<circle cx="70" cy="{y}" r="9" fill="{c}" stroke="white" stroke-width="2"/>')
        elems.append(f'<text x="90" y="{y-5}" font-family="sans-serif" font-size="13" font-weight="bold" fill="#111827">{ev["label"]}</text>')
        elems.append(f'<text x="90" y="{y+15}" font-family="sans-serif" font-size="12" fill="#6B7280">{ev["detail"]}</text>')
    return '\n'.join(f'  {e}' for e in elems)

def svg_matrix(title: str, col_headers: list[str], row_headers: list[str], data: list[list[str]], width: int = 800, height: int = 280) -> str:
    cell_w = (width - 160) // len(col_headers)
    cell_h = 50
    start_x, start_y = 150, 60
    elems = [
        f'<rect width="{width}" height="{height}" fill="#FAFBFC" rx="12"/>',
        f'<text x="{width/2}" y="30" text-anchor="middle" font-family="sans-serif" font-size="16" font-weight="bold" fill="#111827">{title}</text>',
    ]
    for j, hdr in enumerate(col_headers):
        x = start_x + j * cell_w
        elems.append(f'<rect x="{x}" y="{start_y}" width="{cell_w}" height="32" rx="4" fill="#3B82F6" opacity="0.2"/>')
        elems.append(f'<text x="{x+cell_w/2}" y="{start_y+21}" text-anchor="middle" font-family="sans-serif" font-size="13" font-weight="bold" fill="#1E40AF">{hdr}</text>')
    for i, rh in enumerate(row_headers):
        y = start_y + 36 + i * cell_h
        elems.append(f'<rect x="10" y="{y}" width="130" height="{cell_h}" rx="4" fill="#F3F4F6"/>')
        elems.append(f'<text x="75" y="{y+cell_h/2+4}" text-anchor="middle" font-family="sans-serif" font-size="12" font-weight="bold" fill="#374151">{rh}</text>')
        for j, val in enumerate(data[i] if i < len(data) else []):
            x = start_x + j * cell_w
            bg = ["#FEE2E2", "#D1FAE5", "#FEF3C7", "#DBEAFE"][(i + j) % 4]
            elems.append(f'<rect x="{x}" y="{y}" width="{cell_w}" height="{cell_h}" rx="4" fill="{bg}" stroke="#E5E7EB" stroke-width="1"/>')
            elems.append(f'<text x="{x+cell_w/2}" y="{y+cell_h/2+4}" text-anchor="middle" font-family="sans-serif" font-size="13" fill="#1f2937">{val}</text>')
    return '\n'.join(f'  {e}' for e in elems)

def svg_causal_chain(title: str, nodes: list[dict], width: int = 800, height: int = 200) -> str:
    elems = [
        f'<rect width="{width}" height="{height}" fill="#FAFBFC" rx="12"/>',
        f'<text x="{width/2}" y="28" text-anchor="middle" font-family="sans-serif" font-size="16" font-weight="bold" fill="#111827">{title}</text>',
        '<defs><marker id="arrowhead" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto"><polygon points="0 0, 10 3.5, 0 7" fill="#9CA3AF"/></marker></defs>',
    ]
    n = len(nodes)
    colors = ["#3B82F6", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6", "#EC4899"]
    spacing = (width - 100) // max(n, 1)
    for i, node in enumerate(nodes):
        x = 50 + i * spacing
        y, r = 75, 30
        c = colors[i % len(colors)]
        elems.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{c}" opacity="0.15" stroke="{c}" stroke-width="2.5"/>')
        elems.append(f'<text x="{x}" y="{y+5}" text-anchor="middle" font-family="sans-serif" font-size="13" font-weight="bold" fill="#1f2937">{node["label"]}</text>')
        if node.get("detail"):
            elems.append(f'<text x="{x}" y="{y+r+18}" text-anchor="middle" font-family="sans-serif" font-size="11" fill="#6B7280">{node["detail"]}</text>')
        if i < n - 1:
            nx = 50 + (i + 1) * spacing - r - 2
            elems.append(f'<line x1="{x+r+2}" y1="{y}" x2="{nx}" y2="{y}" stroke="#9CA3AF" stroke-width="2" marker-end="url(#arrowhead)"/>')
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
  :root { --bg: #F8FAFC; --surface: #FFFFFF; --text: #1E293B; --text2: #64748B;
    --accent: #3B82F6; --accent2: #10B981; --warn: #F59E0B; --danger: #EF4444;
    --border: #E2E8F0; --radius: 12px; --shadow: 0 1px 3px rgba(0,0,0,.06), 0 1px 5px rgba(0,0,0,.04); }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans SC", sans-serif;
    background: var(--bg); color: var(--text); line-height: 1.65; }
  .container { max-width: 860px; margin: 0 auto; padding: 20px 16px 60px; }
  .header { background: var(--surface); border-radius: var(--radius); padding: 28px 24px;
    margin-bottom: 20px; box-shadow: var(--shadow); border: 1px solid var(--border); }
  .header h1 { font-size: 1.35rem; line-height: 1.5; margin-bottom: 10px; color: #0F172A; }
  .header .meta { display: flex; flex-wrap: wrap; gap: 8px; font-size: .85rem; color: var(--text2); }
  .header .meta span { background: #F1F5F9; padding: 3px 10px; border-radius: 20px; }
  .header .tags { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; }
  .header .tag { background: #EFF6FF; color: #1D4ED8; font-size: .78rem; padding: 2px 10px; border-radius: 12px; }
  .header .desc { margin-top: 10px; font-size: .88rem; color: var(--text2); line-height: 1.55; }
  .chapter { background: var(--surface); border-radius: var(--radius); margin-bottom: 24px;
    box-shadow: var(--shadow); border: 1px solid var(--border); overflow: hidden;
    position: relative; }
  .chapter-header { padding: 20px 24px 14px; border-bottom: 1px solid var(--border); }
  .chapter-num { font-size: .75rem; font-weight: 700; color: var(--accent); text-transform: uppercase;
    letter-spacing: .5px; }
  .chapter-header h2 { font-size: 1.12rem; margin: 4px 0 6px; color: #0F172A; }
  .chapter-time a { color: var(--accent); text-decoration: none; font-weight: 600; }
  .chapter-time a:hover { text-decoration: underline; }
  .chapter-body { padding: 20px 24px; }
  .block { margin-bottom: 18px; }
  .block:last-child { margin-bottom: 0; }
  .block-label { font-size: .78rem; font-weight: 700; text-transform: uppercase; letter-spacing: .5px; margin-bottom: 6px; }
  .block-label.problem { color: var(--danger); }
  .block-label.steps { color: var(--accent); }
  .block-label.pitfalls { color: var(--warn); }
  .block-label.conclusion { color: var(--accent2); }
  .block-label.quote { color: #8B5CF6; }
  .block-content { font-size: .9rem; color: #334155; }
  .block-content ul { list-style: none; padding-left: 0; }
  .block-content li { position: relative; padding-left: 18px; margin-bottom: 5px; }
  .block.steps .block-content li::before { content: "\\25B8"; color: var(--accent); position: absolute; left: 0; font-weight: 700; }
  .block.pitfalls .block-content li::before { content: "\\26A0"; color: var(--warn); position: absolute; left: 0; }
  .callout { background: #F8FAFC; border-left: 3px solid var(--accent); padding: 10px 14px;
    border-radius: 0 8px 8px 0; font-size: .88rem; color: #475569; font-style: italic; margin: 10px 0; }
  .svg-wrap { margin: 16px 0; border-radius: var(--radius); overflow: hidden;
    border: 1px solid var(--border); background: #FAFBFC; }
  .svg-wrap svg { display: block; width: 100%; height: auto; }
  .footer { text-align: center; padding: 20px; font-size: .8rem; color: var(--text2); }
  .footer a { color: var(--accent); text-decoration: none; }
  table { width: 100%; border-collapse: collapse; margin: 10px 0; font-size: .85rem; }
  th, td { border: 1px solid var(--border); padding: 8px 12px; text-align: left; }
  th { background: #F1F5F9; font-weight: 600; }
  pre { background: #1E293B; color: #E2E8F0; padding: 14px 18px; border-radius: 8px;
    overflow-x: auto; font-size: .83rem; line-height: 1.5; margin: 10px 0; }
  code { font-family: "JetBrains Mono", "Fira Code", monospace; }
""").strip()

def format_time_link(bvid: str, seconds: int) -> str:
    return f'<a href="https://www.bilibili.com/video/{bvid}?t={seconds}" target="_blank" rel="noopener">'

def build_html(state: dict, chapters: list[dict], bvid: str, meta: dict) -> str:
    tags_html = "".join(f'<span class="tag">{t}</span>' for t in meta.get("tags", []))
    parts = []
    for i, ch in enumerate(chapters):
        start_sec = ch.get("start", 0)
        time_link_start = format_time_link(bvid, start_sec)
        svg = generate_svg(ch)
        steps_html = "".join(f"<li>{s}</li>" for s in ch.get("steps", []))
        pitfalls_html = "".join(f"<li>{p}</li>" for p in ch.get("pitfalls", []))
        parts.append(f"""
    <section class="chapter" id="{ch.get('id','ch'+str(i+1))}">
      <div class="chapter-header">
        <div class="chapter-num">Chapter {i+1}</div>
        <h2>{ch.get('title','')}</h2>
        <div class="chapter-time">{time_link_start}{ch.get('time_range','')}</a></div>
      </div>
      <div class="chapter-body">
        <div class="block problem">
          <div class="block-label problem">Core Problem</div>
          <div class="block-content"><p>{ch.get('problem','')}</p></div>
        </div>
        <div class="block steps">
          <div class="block-label steps">Steps</div>
          <div class="block-content"><ul>{steps_html}</ul></div>
        </div>
        <div class="block pitfalls">
          <div class="block-label pitfalls">Pitfalls</div>
          <div class="block-content"><ul>{pitfalls_html}</ul></div>
        </div>
        <div class="block conclusion">
          <div class="block-label conclusion">Conclusion</div>
          <div class="block-content"><p>{ch.get('conclusion','')}</p></div>
        </div>
        <div class="block quote">
          <div class="block-label quote">Key Quote</div>
          <div class="callout">{ch.get('key_quote','')}</div>
        </div>
        <div class="svg-wrap">{svg}</div>
      </div>
    </section>""")
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
    <h1>{meta.get('title','')}</h1>
    <div class="meta">
      <span>UP: {meta.get('uploader','')}</span>
      <span>Duration: {meta.get('duration_string','')}</span>
      <span>{bvid}</span>
    </div>
    <div class="tags">{tags_html}</div>
    <div class="desc">{meta.get('description','')}</div>
  </header>
  {''.join(parts)}
  <footer class="footer"><p>AI-generated analysis | <a href="https://www.bilibili.com/video/{bvid}" target="_blank" rel="noopener">Original B站 video</a></p></footer>
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