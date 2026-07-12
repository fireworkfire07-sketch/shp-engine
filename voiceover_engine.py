"""SHP Voiceover Engine — adapter-based voiceover system.

Modes, in preference order:
  OPTIONAL_PROVIDER  — a paid TTS API, only attempted if a provider key is
                        actually configured (ELEVENLABS_API_KEY today).
  LOCAL_TTS          — espeak-ng, if installed. Real, dinlenebilir (audible)
                        synthesized speech, not studio quality, but genuine
                        audio, no paid account required.
  TEXT_ONLY          — no TTS available anywhere: confirms text + estimated
                        timing only, produces no audio file. Never fabricated.

The pipeline must complete in every mode — a paid provider is never
required. Reads projects/script-agent/storyboard.json (already has
per-scene narration text) so it does not re-derive narration itself.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from script_agent_v2 import textutil

ROOT = Path("projects")
SCRIPT_DIR = ROOT / "script-agent"
OUTPUT_DIR = ROOT / "voiceover"
AUDIO_DIR = OUTPUT_DIR / "scenes"
FULL_AUDIO_PATH = OUTPUT_DIR / "voiceover.wav"


def load_json(path: Path, default=None):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def provider_configured() -> str | None:
    if os.getenv("ELEVENLABS_API_KEY", "").strip():
        return "elevenlabs"
    return None


def _synthesize_with_provider(provider: str, text: str, out_path: Path) -> bool:
    # No provider implementation ships in this repo — wiring a real paid
    # account in would need real credentials to test honestly, and the
    # pipeline must never depend on one. This is the adapter seam Phase 6's
    # uploader uses the same pattern for: interface present, not required.
    return False


def local_tts_available() -> bool:
    return shutil.which("espeak-ng") is not None


def synthesize_local_tts(text: str, out_path: Path, language: str = "tr") -> bool:
    if not text.strip() or not local_tts_available():
        return False
    try:
        subprocess.run(
            ["espeak-ng", "-v", language, "-s", "150", "-w", str(out_path), text],
            check=True, capture_output=True, timeout=60,
        )
        return out_path.exists() and out_path.stat().st_size > 0
    except (subprocess.SubprocessError, OSError):
        return False


def probe_duration_seconds(path: Path) -> float:
    if not shutil.which("ffprobe") or not path.exists():
        return 0.0
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
            capture_output=True, text=True, timeout=30, check=True,
        )
        return round(float(result.stdout.strip()), 2)
    except (subprocess.SubprocessError, OSError, ValueError):
        return 0.0


def synthesize_storyboard(storyboard: list[dict], language: str = "tr") -> tuple[str, list[dict]]:
    provider = provider_configured()
    local_available = local_tts_available()
    mode = "OPTIONAL_PROVIDER" if provider else ("LOCAL_TTS" if local_available else "TEXT_ONLY")

    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    scenes = []
    for scene in storyboard:
        text = str(scene.get("narration", ""))
        scene_number = scene.get("scene_number", len(scenes) + 1)
        entry = {
            "scene_number": scene_number,
            "section": scene.get("section", ""),
            "text": text,
            "estimated_seconds": textutil.estimate_seconds(text),
            "audio_file": None,
            "actual_seconds": None,
        }
        audio_path = AUDIO_DIR / f"scene_{scene_number:02d}.wav"
        synthesized = False
        if mode == "OPTIONAL_PROVIDER":
            synthesized = _synthesize_with_provider(provider, text, audio_path)
        if not synthesized and local_available:
            synthesized = synthesize_local_tts(text, audio_path, language)
        if synthesized:
            entry["audio_file"] = str(audio_path.relative_to(ROOT))
            entry["actual_seconds"] = probe_duration_seconds(audio_path)
        scenes.append(entry)
    return mode, scenes


def concatenate_audio(scenes: list[dict], out_path: Path) -> bool:
    """Concatenate every scene's audio into one full voiceover track via
    ffmpeg's concat demuxer. Returns False (never raises) if ffmpeg is
    missing or any scene has no audio."""
    if not shutil.which("ffmpeg"):
        return False
    files = [s["audio_file"] for s in scenes if s.get("audio_file")]
    if len(files) != len(scenes) or not files:
        return False

    list_path = out_path.parent / "_concat_list.txt"
    list_path.write_text(
        "\n".join(f"file '{(ROOT / f).resolve()}'" for f in files), encoding="utf-8"
    )
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_path), "-c", "copy", str(out_path)],
            check=True, capture_output=True, timeout=300,
        )
        return out_path.exists()
    except (subprocess.SubprocessError, OSError):
        return False
    finally:
        list_path.unlink(missing_ok=True)


def _write(payload: dict) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "audio_manifest.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    lines = [
        "# SHP Voiceover Raporu", "",
        f"**Mod:** {payload['mode']}",
        f"**Dil:** {payload.get('language', '-')}",
        f"**Tam ses dosyası:** {payload.get('full_audio_file') or 'yok (ses üretilemedi)'}",
        f"**Tahmini toplam süre:** {payload.get('total_estimated_seconds', 0)} sn",
        f"**Gerçek toplam süre:** {payload.get('total_actual_seconds') if payload.get('total_actual_seconds') is not None else 'ölçülemedi'}",
        "",
        "## Sahne başına ses", "",
        "| Sahne | Tahmini sn | Gerçek sn | Ses dosyası |",
        "|---:|---:|---:|---|",
    ]
    for scene in payload.get("scenes", []):
        lines.append(
            f"| {scene['scene_number']} | {scene['estimated_seconds']} | "
            f"{scene.get('actual_seconds') if scene.get('actual_seconds') is not None else '-'} | "
            f"{scene.get('audio_file') or '-'} |"
        )
    lines += ["", "## Gerçek sınırlar", ""] + [f"- {item}" for item in payload.get("limitations", [])]
    (OUTPUT_DIR / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    script_payload = load_json(SCRIPT_DIR / "script.json", {})
    storyboard = load_json(SCRIPT_DIR / "storyboard.json", [])
    language = ((script_payload or {}).get("script", {}) or {}).get("language", "tr")

    if not storyboard:
        payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "mode": "TEXT_ONLY",
            "language": language,
            "scenes": [],
            "full_audio_file": None,
            "total_estimated_seconds": 0,
            "total_actual_seconds": None,
            "limitations": ["projects/script-agent/storyboard.json bulunamadı veya boş; seslendirme üretilemedi."],
        }
        _write(payload)
        print("VOICEOVER_MODE=TEXT_ONLY")
        return

    mode, scenes = synthesize_storyboard(storyboard, language)
    concatenated = concatenate_audio(scenes, FULL_AUDIO_PATH) if mode != "TEXT_ONLY" else False

    total_actual = None
    if scenes and all(s.get("actual_seconds") is not None for s in scenes):
        total_actual = round(sum(s["actual_seconds"] for s in scenes), 1)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "language": language,
        "local_tts_available": local_tts_available(),
        "provider_configured": provider_configured(),
        "scenes": scenes,
        "full_audio_file": str(FULL_AUDIO_PATH.relative_to(ROOT)) if concatenated else None,
        "total_estimated_seconds": round(sum(s["estimated_seconds"] for s in scenes), 1),
        "total_actual_seconds": total_actual,
        "limitations": [
            "OPTIONAL_PROVIDER modu yalnızca bir sağlayıcı anahtarı tanımlıysa denenir; bu depoda varsayılan olarak hiçbir ücretli sağlayıcı bağlı değildir.",
            "LOCAL_TTS espeak-ng ile üretilir; stüdyo kalitesinde değildir ama gerçek, dinlenebilir bir seslendirmedir.",
            "Ses üretilemezse (TEXT_ONLY) Video Engine sessiz video üretir; hiçbir zaman sahte ses dosyası oluşturulmaz.",
        ],
    }
    _write(payload)
    print(f"VOICEOVER_MODE={mode}")
    print(f"VOICEOVER_FULL_AUDIO={payload['full_audio_file']}")
    print(f"REPORT={OUTPUT_DIR / 'report.md'}")


if __name__ == "__main__":
    main()
