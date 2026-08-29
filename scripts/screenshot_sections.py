#!/usr/bin/env python3
"""
screenshot_sections.py — Per-section screenshot via Chrome DevTools Protocol.
Uses Page.captureScreenshot with a clip rectangle to capture each <h2> section
exactly once, avoiding duplicate headers caused by viewport resizing or scroll timing.

Usage: python screenshot_sections.py <html_path> --workdir <dir>
"""
import argparse, base64, json, os, socket, subprocess, sys, shutil, tempfile, time
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
import threading

CHROME_CANDIDATES = [
    "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
    "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
]


def find_chrome():
    for p in CHROME_CANDIDATES:
        if os.path.exists(p):
            return p
    return shutil.which("chrome")


def pick_free_port() -> int:
    """Bind port 0 so concurrent screenshot jobs do not share 18923/18924."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]


def ws_connect(url):
    from urllib.parse import urlparse
    import socket, hashlib
    parsed = urlparse(url)
    sock = socket.create_connection((parsed.hostname, parsed.port))
    key = base64.b64encode(os.urandom(16)).decode()
    req = (f"GET {parsed.path} HTTP/1.1\r\n"
           f"Host: {parsed.hostname}:{parsed.port}\r\n"
           f"Upgrade: websocket\r\n"
           f"Connection: Upgrade\r\n"
           f"Sec-WebSocket-Key: {key}\r\n"
           f"Sec-WebSocket-Version: 13\r\n\r\n")
    sock.send(req.encode())
    sock.recv(4096)
    return sock


def ws_send(sock, msg):
    import struct
    data = json.dumps(msg).encode()
    frame = bytearray()
    frame.append(0x81)
    mask_key = os.urandom(4)
    if len(data) < 126:
        frame.append(0x80 | len(data))
    elif len(data) < 65536:
        frame.append(0x80 | 126)
        frame.extend(struct.pack(">H", len(data)))
    else:
        frame.append(0x80 | 127)
        frame.extend(struct.pack(">Q", len(data)))
    frame.extend(mask_key)
    for i, b in enumerate(data):
        frame.append(b ^ mask_key[i % 4])
    sock.send(frame)


def ws_recv(sock):
    data = b""
    while True:
        chunk = sock.recv(65536)
        if not chunk:
            break
        data += chunk
        if len(chunk) < 65536:
            break
    if len(data) < 2:
        return ""
    payload_len = data[1] & 0x7F
    offset = 2
    if payload_len == 126:
        offset = 4
    elif payload_len == 127:
        offset = 10
    return data[offset:].decode("utf-8", errors="replace")


def main():
    parser = argparse.ArgumentParser(description="Per-section screenshot via Chrome CDP (clip-based)")
    parser.add_argument("html_path", help="Path to analysis.html")
    parser.add_argument("--workdir", default=None, help="Output directory")
    parser.add_argument("--width", type=int, default=820, help="Capture width in CSS pixels")
    parser.add_argument("--scale", type=int, default=2, help="Device scale factor (PNG resolution)")
    args = parser.parse_args()

    html = Path(args.html_path).resolve()
    if not html.exists():
        print(f"[ERROR] HTML not found: {html}")
        sys.exit(1)
    workdir = Path(args.workdir).resolve() if args.workdir else html.parent
    workdir.mkdir(parents=True, exist_ok=True)

    print("=" * 50)
    print("  Phase 4: Per-Section Screenshot (CDP clip)")
    print("=" * 50)

    chrome = find_chrome()
    if not chrome:
        print("[ERROR] Chrome not found")
        sys.exit(1)

    # Start local HTTP server on an ephemeral port (fixed 18923 collides
    # when another agent screenshots at the same time).
    html_dir = str(html.parent)
    port = pick_free_port()

    class QuietHandler(SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=html_dir, **kw)
        def log_message(self, format, *args):
            pass

    server = HTTPServer(("127.0.0.1", port), QuietHandler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    print(f"[INFO] local server on port {port}")

    # Isolated Chrome: unique debug port + user-data-dir so a concurrent
    # job cannot attach to / navigate this instance.
    debug_port = pick_free_port()
    user_data = tempfile.mkdtemp(prefix="bili-chrome-")
    cmd = [
        chrome, "--headless=new", "--disable-gpu", "--no-sandbox",
        "--disable-scrollbars", "--hide-scrollbars",
        f"--remote-debugging-port={debug_port}",
        f"--user-data-dir={user_data}",
        f"--window-size={args.width},600",
        f"http://127.0.0.1:{port}/{html.name}"
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    time.sleep(3)

    # Connect CDP
    import urllib.request
    try:
        resp = urllib.request.urlopen(f"http://127.0.0.1:{debug_port}/json")
        targets = json.loads(resp.read())
        ws_url = None
        for t in targets:
            if t.get("type") == "page":
                ws_url = t["webSocketDebuggerUrl"]
                break
        if not ws_url:
            raise RuntimeError("no page target")
    except Exception as e:
        print(f"[ERROR] CDP connection failed: {e}")
        proc.kill()
        server.shutdown()
        shutil.rmtree(user_data, ignore_errors=True)
        sys.exit(1)

    print(f"[INFO] CDP connected")
    ws = ws_connect(ws_url)
    msg_id = 1

    def cdp_send(method, params=None, wait=0.4):
        nonlocal msg_id
        msg = {"id": msg_id, "method": method}
        if params:
            msg["params"] = params
        ws_send(ws, msg)
        msg_id += 1
        time.sleep(wait)
        return ws_recv(ws)

    try:
        cdp_send("Page.enable")
        cdp_send("Runtime.enable")

        # Fail fast if another job hijacked this Chrome and opened a different HTML.
        page_url = json.loads(cdp_send("Runtime.evaluate", {
            "expression": "location.href"
        })).get("result", {}).get("result", {}).get("value", "")
        page_title = json.loads(cdp_send("Runtime.evaluate", {
            "expression": "document.title"
        })).get("result", {}).get("result", {}).get("value", "")
        print(f"[INFO] page url={page_url}")
        print(f"[INFO] page title={page_title}")
        if html.name not in str(page_url):
            raise RuntimeError(f"Chrome opened unexpected URL: {page_url} (wanted {html.name})")

        # Inject CSS to hide scrollbars and ensure stable layout
        cdp_send("Runtime.evaluate", {
            "expression": """
            (function() {
                var s = document.createElement('style');
                s.textContent = '::-webkit-scrollbar{display:none!important} html,body{overflow-x:hidden!important}';
                document.head.appendChild(s);
            })()
            """
        })

        # Measure document height and set viewport tall enough to show everything
        total_height = json.loads(cdp_send("Runtime.evaluate", {
            "expression": "document.documentElement.scrollHeight"
        })).get("result", {}).get("result", {}).get("value", 3000)
        viewport_height = int(total_height) + 200
        cdp_send("Emulation.setDeviceMetricsOverride", {
            "width": args.width,
            "height": viewport_height,
            "deviceScaleFactor": 1,
            "mobile": False
        })
        time.sleep(1)  # allow reflow

        # Get all h2 sections with their bounding rectangles
        result = cdp_send("Runtime.evaluate", {
            "expression": """
            JSON.stringify(Array.from(document.querySelectorAll('h2')).map(function(h, i) {
                var rect = h.getBoundingClientRect();
                var parent = h.closest('.chapter');
                var parentRect = parent ? parent.getBoundingClientRect() : rect;
                return {
                    index: i,
                    top: rect.top,
                    left: rect.left,
                    headerHeight: rect.height,
                    parentTop: parentRect.top,
                    parentHeight: parentRect.height,
                    text: h.textContent.substring(0, 40)
                };
            }))
            """
        })

        result_str = json.loads(result).get("result", {}).get("result", {}).get("value", "[]")
        headers = json.loads(result_str)
        print(f"[INFO] found {len(headers)} h2 sections")

        if not headers:
            raise RuntimeError("no h2 sections found")

        # Determine section boundaries from parent <section> heights
        screenshots = []
        for i, h in enumerate(headers):
            sec_top = max(0, int(h["parentTop"]) - 20)
            sec_height = int(h["parentHeight"]) + 40
            sec_bottom = sec_top + sec_height

            # Sanity: clip must be inside viewport
            if sec_bottom > viewport_height:
                sec_height = viewport_height - sec_top

            clip = {
                "x": 0,
                "y": sec_top,
                "width": args.width,
                "height": sec_height,
                "scale": args.scale
            }

            r = cdp_send("Page.captureScreenshot", {
                "format": "png",
                "clip": clip
            }, wait=0.8)
            resp = json.loads(r)
            if "result" not in resp:
                print(f"[WARN] CDP response for section {i+1}: {r[:300]}")
                continue
            img_data = base64.b64decode(resp["result"]["data"])
            fname = f"section_{i + 1}.png"
            fpath = workdir / fname
            fpath.write_bytes(img_data)
            fsize = fpath.stat().st_size / 1024
            screenshots.append({"file": fname, "section": i + 1, "height": sec_height, "size_kb": round(fsize)})
            print(f"[OK] {fname}: \"{h['text']}\", {sec_height}px, {fsize:.0f}KB")

        # Merge into full screenshot
        from PIL import Image
        images = [Image.open(str(workdir / s["file"])) for s in screenshots]
        total_h = sum(img.height for img in images)
        max_w = max(img.width for img in images)
        full = Image.new("RGB", (max_w, total_h), "white")
        y = 0
        for img in images:
            full.paste(img, (0, y))
            y += img.height
        full_path = str(workdir / "screenshot_full.png")
        full.save(full_path)
        print(f"[OK] merged full -> {full_path} ({os.path.getsize(full_path)/1024:.0f}KB)")

        # Manifest
        manifest = {"total_sections": len(screenshots), "screenshots": screenshots}
        with open(workdir / "sections_manifest.json", "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)

        print(f"\n[OK] {len(screenshots)} section screenshots -> {workdir}")
        print("[OK] Phase 4 complete.")

    finally:
        try:
            cdp_send("Browser.close", wait=0.2)
        except Exception:
            pass
        ws.close()
        proc.wait(timeout=5)
        server.shutdown()
        shutil.rmtree(user_data, ignore_errors=True)


if __name__ == "__main__":
    main()
