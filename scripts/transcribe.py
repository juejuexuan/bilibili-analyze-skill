#!/usr/bin/env python3
"""
transcribe.py — Phase 2: Whisper transcription with model fallback.
Priority: 1. SRT subtitles  2. faster-whisper  3. openai-whisper
Usage: python transcribe.py <state.json_or_workdir> [--force-whisper] [--language zh]
"""
import argparse, json, os, re, subprocess, sys
from pathlib import Path

def parse_srt(srt_path: Path) -> list[dict]:
    segments = []
    with open(srt_path, encoding="utf-8") as f:
        content = f.read()
    blocks = re.split(r'\n\n+', content.strip())
    for block in blocks:
        lines = block.strip().split('\n')
        if len(lines) < 3:
            continue
        m = re.match(r'(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)', lines[1])
        if not m:
            continue
        start = int(m.group(1))*3600 + int(m.group(2))*60 + int(m.group(3)) + int(m.group(4))/1000
        end = int(m.group(5))*3600 + int(m.group(6))*60 + int(m.group(7)) + int(m.group(8))/1000
        text = ' '.join(lines[2:]).strip()
        segments.append({"start": start, "end": end, "text": text})
    print(f"[OK] parsed {len(segments)} segments from SRT subtitles")
    return segments

def transcribe_faster_whisper(audio_path: str, model_name: str = "small", language: str = "zh") -> dict | None:
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        print("[INFO] faster-whisper not installed, trying openai-whisper...")
        return None
    try:
        model = WhisperModel(model_name, device="cpu", compute_type="int8")
        segments_raw, info = model.transcribe(audio_path, language=language, beam_size=5, vad_filter=True)
        segments = []
        text_parts = []
        for seg in segments_raw:
            segments.append({"start": seg.start, "end": seg.end, "text": seg.text.strip()})
            text_parts.append(seg.text.strip())
        print(f"[OK] faster-whisper {model_name}: {len(segments)} segments")
        return {"segments": segments, "text": " ".join(text_parts), "language": info.language}
    except Exception as e:
        print(f"[WARN] faster-whisper failed: {e}")
        return None

def transcribe_openai_whisper(audio_path: str, model_name: str = "small", language: str = "zh") -> dict:
    import whisper
    print(f"[INFO] loading openai-whisper '{model_name}'...")
    model = whisper.load_model(model_name)
    print(f"[INFO] transcribing...")
    result = model.transcribe(audio_path, language=language, task="transcribe", verbose=False)
    print(f"[OK] openai-whisper {model_name}: {len(result['segments'])} segments")
    return result

def save_outputs(result: dict, workdir: Path):
    with open(workdir / "transcript_full.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    full_text = result.get("text", "")
    if not full_text:
        full_text = "\n".join(s["text"] for s in result.get("segments", []))
    with open(workdir / "transcript.txt", "w", encoding="utf-8") as f:
        f.write(full_text)
    with open(workdir / "transcript_segments.txt", "w", encoding="utf-8") as f:
        for seg in result.get("segments", []):
            f.write(f'[{seg["start"]:.1f}s - {seg["end"]:.1f}s] {seg["text"].strip()}\n')
    print(f"[OK] transcripts saved to {workdir}")

def validate_end_time(result: dict, audio_duration: float) -> bool:
    segs = result.get("segments", [])
    if not segs:
        print("[WARN] no segments to validate")
        return True
    last_end = segs[-1]["end"]
    diff = abs(last_end - audio_duration) / audio_duration * 100
    if diff > 5:
        print(f"[WARN] last segment ends at {last_end:.1f}s vs audio {audio_duration:.1f}s ({diff:.1f}% > 5%)")
        return False
    print(f"[OK] last segment ends at {last_end:.1f}s vs audio {audio_duration:.1f}s ({diff:.2f}%)")
    return True

def main():
    parser = argparse.ArgumentParser(description="Transcribe audio with Whisper fallback")
    parser.add_argument("input", help="Path to state.json or workdir")
    parser.add_argument("--force-whisper", action="store_true", help="Skip SRT parsing")
    parser.add_argument("--language", default=None, help="Force language (zh/en)")
    args = parser.parse_args()
    inp = Path(args.input)
    state_path = inp / "state.json" if inp.is_dir() else inp
    with open(state_path, encoding="utf-8") as f:
        state = json.load(f)
    workdir = Path(state["workdir"])
    audio_path = state.get("audio_path")
    subs_path = state.get("subtitles_path")
    duration = state.get("duration_seconds", 0)
    print("=" * 50)
    print("  Phase 2: Transcription")
    print("=" * 50)
    # Priority 1: SRT subtitles
    if subs_path and not args.force_whisper:
        srt_path = Path(subs_path)
        if srt_path.exists():
            segments = parse_srt(srt_path)
            result = {"segments": segments, "text": " ".join(s["text"] for s in segments)}
            save_outputs(result, workdir)
            validate_end_time(result, duration)
            return
    # Priority 2 & 3: Whisper
    if audio_path and Path(audio_path).exists():
        lang = args.language or "zh"
        result = transcribe_faster_whisper(audio_path, model_name="small", language=lang)
        if result is None:
            result = transcribe_openai_whisper(audio_path, model_name="small", language=lang)
        if result:
            save_outputs(result, workdir)
            validate_end_time(result, duration)
            return
    print("[ERROR] no audio or subtitles to transcribe")
    sys.exit(1)

if __name__ == "__main__":
    main()