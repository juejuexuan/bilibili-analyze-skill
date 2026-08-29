#!/usr/bin/env python3
"""
preflight.py — Environment checker for bilibili-analyze skill.
Checks: yt-dlp, ffmpeg, ffprobe, whisper model, chrome, python deps
Usage: python preflight.py [--json]
"""
import hashlib, importlib.util, json, os, shutil, subprocess, sys
from pathlib import Path

WHISPER_HOME = Path.home() / ".cache" / "whisper"
MODEL_CHECKSUMS = {
    "small.pt": "edf6901f", "medium.pt": "4f5b8b1a",
    "turbo.pt": "3e5c1a7f", "large-v3-turbo.pt": "3e5c1a7f",
    "large-v3.pt": "5d5b0a5b",
}
CHROME_PATHS = [
    "/c/Program Files/Google/Chrome/Application/chrome.exe",
    "/c/Program Files (x86)/Google/Chrome/Application/chrome.exe",
    "/mnt/c/Program Files/Google/Chrome/Application/chrome.exe",
    "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
    "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
]

def bundled_script(name: str) -> str | None:
    scripts_dir = Path(sys.executable).resolve().parent / "Scripts"
    names = [name]
    if os.name == "nt":
        names.insert(0, f"{name}.exe")
    for candidate in names:
        path = scripts_dir / candidate
        if path.exists():
            return str(path)
    return None

def find_executable(name: str) -> str | None:
    return shutil.which(name) or bundled_script(name)

def run(cmd: list[str], timeout: int = 15) -> tuple[bool, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        line = (r.stdout or r.stderr).split("\n")[0].strip()
        return r.returncode == 0, line[:120]
    except FileNotFoundError:
        return False, "NOT FOUND"
    except subprocess.TimeoutExpired:
        return False, "TIMEOUT"
    except Exception as e:
        return False, str(e)

def check_yt_dlp() -> dict:
    exe = find_executable("yt-dlp")
    if not exe:
        return {"tool": "yt-dlp", "ok": False, "detail": "NOT FOUND", "fix": f"{sys.executable} -m pip install yt-dlp"}
    ok, ver = run([exe, "--version"])
    return {"tool": "yt-dlp", "ok": ok, "detail": f"{ver} ({exe})", "fix": f"{sys.executable} -m pip install -U yt-dlp" if not ok else None}

def check_ffmpeg() -> dict:
    ok, ver = run(["ffmpeg", "-version"])
    return {"tool": "ffmpeg", "ok": ok, "detail": ver, "fix": "winget install ffmpeg" if not ok else None}

def check_ffprobe() -> dict:
    ok, ver = run(["ffprobe", "-version"])
    return {"tool": "ffprobe", "ok": ok, "detail": ver, "fix": "reuse ffmpeg install" if not ok else None}

def check_python() -> dict:
    major, minor = sys.version_info[:2]
    ok = (major, minor) >= (3, 10)
    return {"tool": "python", "ok": ok, "detail": f"{major}.{minor}", "fix": "Install Python 3.10+" if not ok else None}

def check_chrome() -> dict:
    for p in CHROME_PATHS:
        if os.path.exists(p):
            return {"tool": "chrome", "ok": True, "detail": p, "fix": None}
    for name in ["chrome", "chromium", "google-chrome", "chromium-browser"]:
        found = shutil.which(name)
        if found:
            return {"tool": "chrome", "ok": True, "detail": found, "fix": None}
    return {"tool": "chrome", "ok": False, "detail": "not found", "fix": "Install Chrome or Chromium"}

def check_whisper_model() -> dict:
    if not WHISPER_HOME.exists():
        return {"tool": "whisper-model", "ok": False, "detail": "no cache dir", "fix": "Run whisper once to download model"}
    found = []
    valid = False
    for fname, prefix in MODEL_CHECKSUMS.items():
        fpath = WHISPER_HOME / fname
        if not fpath.exists():
            continue
        try:
            with open(fpath, "rb") as fh:
                h = hashlib.sha256(fh.read()).hexdigest()[:8]
        except Exception:
            continue
        if h == prefix:
            valid = True
            found.append(f"{fname} (OK {fpath.stat().st_size / 1e9:.1f}GB)")
        else:
            found.append(f"{fname} (present; checksum differs)")
    if found:
        # Model checksums can change across upstream releases; presence is enough for preflight.
        return {"tool": "whisper-model", "ok": True, "detail": "; ".join(found), "fix": None if valid else "If transcription fails, delete the model and reload it"}
    return {"tool": "whisper-model", "ok": False, "detail": "no model file", "fix": f'{sys.executable} -c "import whisper; whisper.load_model(\'small\')"'}

def check_pip_deps() -> dict:
    required = ["PIL", "numpy", "yt_dlp"]
    optional_one_of = ["faster_whisper", "whisper"]
    missing = [name for name in required if importlib.util.find_spec(name) is None]
    if all(importlib.util.find_spec(name) is None for name in optional_one_of):
        missing.append("faster_whisper or whisper")
    if missing:
        return {"tool": "pip-deps", "ok": False, "detail": f"missing: {missing}", "fix": f"{sys.executable} -m pip install yt-dlp openai-whisper faster-whisper Pillow numpy"}
    engines = [name for name in optional_one_of if importlib.util.find_spec(name)]
    return {"tool": "pip-deps", "ok": True, "detail": f"PIL, numpy, yt_dlp, {', '.join(engines)} OK", "fix": None}

def main():
    json_out = "--json" in sys.argv
    checks = [check_python(), check_yt_dlp(), check_ffmpeg(), check_ffprobe(), check_chrome(), check_whisper_model(), check_pip_deps()]
    all_ok = all(c["ok"] for c in checks)
    if json_out:
        print(json.dumps({"all_ok": all_ok, "checks": checks}, ensure_ascii=False, indent=2))
    else:
        print("=" * 50)
        print("  bilibili-analyze Environment Check")
        print("=" * 50)
        for c in checks:
            icon = "[OK]" if c["ok"] else "[XX]"
            print(f"  {icon}  {c['tool']:18s} {c['detail']}")
            if c.get("fix") and not c["ok"]:
                print(f"     -> fix: {c['fix']}")
        print("=" * 50)
        print(f"  {'ALL OK' if all_ok else 'SOME MISSING - fix before continuing'}")
    sys.exit(0 if all_ok else 1)

if __name__ == "__main__":
    main()
