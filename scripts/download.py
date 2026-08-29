#!/usr/bin/env python3
"""
download.py — Phase 1: Download B站 video metadata, audio, thumbnail in parallel.
Usage: python download.py <bilibili_url> --workdir <output_dir> [--cookies <path>]
"""
import argparse, json, os, shutil, subprocess, sys, concurrent.futures
from pathlib import Path


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


def find_yt_dlp() -> str:
    exe = shutil.which("yt-dlp") or bundled_script("yt-dlp")
    if not exe:
        raise RuntimeError(f"yt-dlp not found. Install with: {sys.executable} -m pip install yt-dlp")
    return exe


YT_DLP = find_yt_dlp()
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

def run_yt(cmd: list[str], timeout: int = 180) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)

def get_metadata(url: str, cookies: str | None, workdir: Path) -> dict:
    cmd = [YT_DLP, "--user-agent", USER_AGENT, "--print-json", "--no-download"]
    if cookies:
        cmd += ["--cookies", cookies]
    cmd.append(url)
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        print(f"[ERROR] yt-dlp metadata failed: {r.stderr[:200]}")
        sys.exit(1)
    data = json.loads(r.stdout.strip().split("\n")[-1])
    bvid = data.get("display_id", "").replace("_p1", "").replace("_p2", "").replace("_p3", "")
    if not bvid:
        bvid = data.get("id", "unknown")
    outdir = workdir / bvid
    outdir.mkdir(parents=True, exist_ok=True)
    with open(outdir / "metadata.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"[OK] metadata -> {outdir / 'metadata.json'}")
    print(f"     title: {data.get('title', '?')[:60]}")
    print(f"     duration: {data.get('duration_string', '?')} | UP: {data.get('uploader', '?')}")
    return data

def download_audio(url: str, cookies: str | None, workdir: Path, slug: str) -> Path | None:
    outdir = workdir / slug
    tmpl = str(outdir / "audio_best.%(ext)s")
    for fmt in ["bestaudio", "worst"]:
        cmd = [YT_DLP, "--user-agent", USER_AGENT, "-f", fmt, "-o", tmpl]
        if cookies:
            cmd += ["--cookies", cookies]
        cmd.append(url)
        r = run_yt(cmd, timeout=300)
        if r.returncode == 0:
            for ext in ["m4a", "webm", "opus", "aac", "mp3", "mp4", "flv"]:
                candidate = outdir / f"audio_best.{ext}"
                if candidate.exists():
                    print(f"[OK] audio (fmt={fmt}) -> {candidate} ({candidate.stat().st_size / 1e6:.1f}MB)")
                    return candidate
        else:
            print(f"[WARN] format '{fmt}' failed; trying next...")
    print("[ERROR] all format attempts failed")
    return None

def download_thumbnail(url: str, cookies: str | None, workdir: Path, slug: str) -> Path | None:
    outdir = workdir / slug
    tmpl = str(outdir / "thumbnail")
    cmd = [YT_DLP, "--user-agent", USER_AGENT, "--write-thumbnail", "--skip-download", "-o", tmpl, url]
    if cookies:
        cmd += ["--cookies", cookies]
    run_yt(cmd, timeout=60)
    for ext in ["jpg", "webp", "png", "jpeg"]:
        candidate = outdir / f"thumbnail.{ext}"
        if candidate.exists():
            print(f"[OK] thumbnail -> {candidate} ({candidate.stat().st_size / 1e3:.0f}KB)")
            return candidate
    print("[WARN] thumbnail not found")
    return None

def download_subs(url: str, cookies: str | None, workdir: Path, slug: str) -> Path | None:
    outdir = workdir / slug
    fmt = str(outdir / "%(id)s.%(ext)s")
    cmd = [YT_DLP, "--user-agent", USER_AGENT, "--write-subs", "--sub-langs", "zh-Hans,zh-CN,zh,ai-zh", "--convert-subs", "srt", "--skip-download", "-o", fmt, url]
    if cookies:
        cmd += ["--cookies", cookies]
    run_yt(cmd, timeout=60)
    srt_files = list(outdir.glob("*.srt"))
    if srt_files:
        target = outdir / "subtitles.srt"
        srt_files[0].rename(target)
        print(f"[OK] subtitles -> {target}")
        return target
    print("[INFO] no CC subtitles available - will use Whisper")
    return None

def convert_audio(audio_path: Path, workdir: Path, slug: str) -> Path | None:
    outdir = workdir / slug
    mp3_path = outdir / "audio_best.mp3"
    if audio_path.suffix.lower() == ".mp3":
        if audio_path != mp3_path:
            audio_path.rename(mp3_path)
        return mp3_path
    cmd = ["ffmpeg", "-y", "-i", str(audio_path), "-codec:a", "libmp3lame", "-b:a", "192k", str(mp3_path)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if r.returncode == 0:
        print(f"[OK] converted to mp3 -> {mp3_path} ({mp3_path.stat().st_size / 1e6:.1f}MB)")
        return mp3_path
    print(f"[ERROR] ffmpeg conversion failed: {r.stderr[:200]}")
    return None

def validate_duration(mp3_path: Path, meta_duration: float) -> bool:
    cmd = ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", str(mp3_path)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    if r.returncode != 0:
        print("[WARN] ffprobe duration check failed")
        return False
    dur = float(json.loads(r.stdout)["format"]["duration"])
    diff = abs(dur - meta_duration) / meta_duration * 100
    status = "OK" if diff <= 5 else f"WARNING ({diff:.1f}%)"
    print(f"[{status}] audio duration: {dur:.1f}s vs metadata {meta_duration:.1f}s (diff {diff:.2f}%)")
    return diff <= 5

def main():
    parser = argparse.ArgumentParser(description="Download B站 video assets")
    parser.add_argument("url", help="Bilibili video URL")
    parser.add_argument("--workdir", required=True, help="Output base directory")
    parser.add_argument("--cookies", default=None, help="Path to cookies.txt")
    args = parser.parse_args()
    workdir = Path(args.workdir).resolve()
    workdir.mkdir(parents=True, exist_ok=True)
    print("=" * 50)
    print("  Phase 1: Download & Audio Processing")
    print("=" * 50)
    meta = get_metadata(args.url, args.cookies, workdir)
    bvid = meta.get("display_id", "").replace("_p1", "").replace("_p2", "").replace("_p3", "")
    if not bvid:
        bvid = meta.get("id", "unknown")
    outdir = workdir / bvid
    print("\n--- Downloading assets ---")
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
        fut_audio = ex.submit(download_audio, args.url, args.cookies, workdir, bvid)
        fut_thumb = ex.submit(download_thumbnail, args.url, args.cookies, workdir, bvid)
        fut_subs = ex.submit(download_subs, args.url, args.cookies, workdir, bvid)
        audio_path = fut_audio.result()
        thumb_path = fut_thumb.result()
        subs_path = fut_subs.result()
    print("\n--- Audio processing ---")
    mp3_path = None
    if audio_path:
        mp3_path = convert_audio(audio_path, workdir, bvid)
        if mp3_path:
            validate_duration(mp3_path, float(meta.get("duration", 0)))
    state = {
        "slug": bvid, "workdir": str(outdir),
        "metadata_path": str(outdir / "metadata.json"),
        "audio_path": str(mp3_path) if mp3_path else None,
        "subtitles_path": str(subs_path) if subs_path else None,
        "thumbnail_path": str(thumb_path) if thumb_path else None,
        "has_subs": subs_path is not None,
        "duration_seconds": float(meta.get("duration", 0)),
        "title": meta.get("title", ""), "uploader": meta.get("uploader", ""),
    }
    state_path = outdir / "state.json"
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    print(f"\n[OK] Phase 1 complete. State -> {state_path}")
    print(f"     Workdir: {outdir}")

if __name__ == "__main__":
    main()