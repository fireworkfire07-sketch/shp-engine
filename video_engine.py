"""SHP Video Engine — the safest immediately usable video renderer.

Two modes:
  LIGHTWEIGHT_MODE      Pillow-generated (or user-supplied) still frames,
                        Ken Burns pan/zoom via FFmpeg, burned-in subtitles,
                        real TTS voiceover audio when voiceover_engine.py
                        produced one (silence, honestly, if not), optional
                        user-supplied background music, FFmpeg concat to a
                        1080p MP4. Works without any paid API.
  GENERATIVE_VIDEO_MODE  Clean adapter interface only (ComfyUI/Wan/LTX/
                        another provider). Not required for a first
                        working version — see GenerativeVideoAdapter below.

Gated on Video CEO Pro's decision: only ÇEK renders. DÜZELT/DUR/BEKLET stop
production safely, matching the same rule video_ceo.py itself applies to
Script Agent V2's output.

If FFmpeg is unavailable, the full render manifest and every frame/audio
asset are still built and packaged, and the report states the exact
external runtime requirement — a video is never reported as rendered when
it was not.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("projects")
SCRIPT_DIR = ROOT / "script-agent"
VOICEOVER_DIR = ROOT / "voiceover"
OUTPUT_DIR = ROOT / "video-engine"
ASSETS_DIR = OUTPUT_DIR / "assets"
FRAMES_DIR = ASSETS_DIR / "frames"
CLIPS_DIR = ASSETS_DIR / "clips"
FINAL_VIDEO_PATH = OUTPUT_DIR / "final_video.mp4"

SUPPLIED_IMAGES_DIR = Path("assets/images")
SUPPLIED_MUSIC_CANDIDATES = [Path("assets/audio/background_music.mp3"), Path("assets/audio/background_music.wav")]

RESOLUTION = (1920, 1080)
FPS = 25
MIN_CLIP_SECONDS = 2.0

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
]

PALETTE_BY_ROLE = {
    "hook": (14, 14, 20),
    "origin": (24, 26, 38),
    "conflict": (40, 18, 20),
    "mystery": (18, 20, 30),
    "reveal": (30, 26, 14),
    "final": (32, 24, 14),
}


def load_json(path: Path, default=None):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def _find_font() -> str | None:
    for candidate in FONT_CANDIDATES:
        if Path(candidate).exists():
            return candidate
    return None


# ---------------------------------------------------------------------------
# Frames
# ---------------------------------------------------------------------------

def resolve_scene_image(scene_number: int, role: str, caption: str) -> tuple[Path, bool]:
    """Returns (image_path, is_supplied). Prefers a user-supplied image at
    assets/images/scene_<N>.(png|jpg|jpeg) over the generated placeholder —
    this is the "supplied images" half of LIGHTWEIGHT_MODE's image input."""
    for ext in ("png", "jpg", "jpeg"):
        candidate = SUPPLIED_IMAGES_DIR / f"scene_{scene_number:02d}.{ext}"
        if candidate.exists():
            return candidate, True
    return generate_placeholder_frame(scene_number, role, caption), False


def generate_placeholder_frame(scene_number: int, role: str, caption: str) -> Path:
    """No AI image-generation API is configured in this repo, so the honest
    fallback is a real, rendered typographic frame — not a claim of
    AI-generated stock footage. Gradient background keyed to the scene's
    narrative role, wrapped caption text from the scene's own visual idea."""
    from PIL import Image, ImageDraw, ImageFont

    FRAMES_DIR.mkdir(parents=True, exist_ok=True)
    width, height = RESOLUTION
    base = PALETTE_BY_ROLE.get(role, (20, 20, 26))
    img = Image.new("RGB", (width, height), base)
    draw = ImageDraw.Draw(img)
    for y in range(height):
        t = y / height
        color = tuple(min(255, int(c + t * 35)) for c in base)
        draw.line([(0, y), (width, y)], fill=color)

    font_path = _find_font()
    font = ImageFont.truetype(font_path, 60) if font_path else ImageFont.load_default()

    import textwrap
    text = caption.strip() or f"Sahne {scene_number}"
    lines = textwrap.wrap(text, width=30) or [text]
    line_height = 84 if font_path else 20
    total_h = len(lines) * line_height
    y = (height - total_h) // 2
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        w = bbox[2] - bbox[0]
        draw.text(((width - w) / 2, y), line, font=font, fill=(240, 240, 245))
        y += line_height

    out_path = FRAMES_DIR / f"scene_{scene_number:02d}.png"
    img.save(out_path)
    return out_path


# ---------------------------------------------------------------------------
# FFmpeg rendering
# ---------------------------------------------------------------------------

def render_scene_clip(image_path: Path, duration_seconds: float, subtitle_text: str, out_path: Path) -> bool:
    width, height = RESOLUTION
    frames = max(1, round(duration_seconds * FPS))
    zoompan = (
        f"scale=3840:-2,zoompan=z='min(zoom+0.0015,1.2)':"
        f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={width}x{height}:fps={FPS},format=yuv420p"
    )
    font_path = _find_font()
    vf = zoompan
    subtitle_file = None
    if subtitle_text.strip() and font_path:
        subtitle_file = out_path.parent / f"{out_path.stem}_subtitle.txt"
        subtitle_file.write_text(subtitle_text.strip(), encoding="utf-8")
        escaped = str(subtitle_file).replace("\\", "\\\\").replace(":", "\\:")
        vf += (
            f",drawtext=fontfile={font_path}:textfile={escaped}:fontcolor=white:fontsize=42:"
            f"box=1:boxcolor=black@0.6:boxborderw=14:x=(w-text_w)/2:y=h-130:line_spacing=6"
        )
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-loop", "1", "-i", str(image_path), "-vf", vf,
             "-t", f"{duration_seconds:.3f}", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(out_path)],
            check=True, capture_output=True, timeout=180,
        )
        return out_path.exists()
    except (subprocess.SubprocessError, OSError):
        return False
    finally:
        if subtitle_file:
            subtitle_file.unlink(missing_ok=True)


def mux_scene_audio(video_path: Path, audio_path: Path | None, duration_seconds: float, out_path: Path) -> bool:
    if not audio_path or not audio_path.exists():
        # No voiceover for this scene — ship the silent clip as-is rather
        # than fabricating audio.
        shutil.copy(video_path, out_path)
        return out_path.exists()
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(video_path), "-i", str(audio_path),
             "-filter_complex", "[1:a]apad[a]", "-map", "0:v", "-map", "[a]",
             "-c:v", "copy", "-c:a", "aac", "-t", f"{duration_seconds:.3f}", str(out_path)],
            check=True, capture_output=True, timeout=180,
        )
        return out_path.exists()
    except (subprocess.SubprocessError, OSError):
        return False


def concat_scenes(clip_paths: list[Path], out_path: Path) -> bool:
    if not clip_paths:
        return False
    list_path = out_path.parent / "_concat_list.txt"
    list_path.write_text("\n".join(f"file '{p.resolve()}'" for p in clip_paths), encoding="utf-8")
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


def find_supplied_music() -> Path | None:
    for candidate in SUPPLIED_MUSIC_CANDIDATES:
        if candidate.exists():
            return candidate
    return None


def mix_background_music(video_path: Path, music_path: Path, out_path: Path) -> bool:
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(video_path), "-i", str(music_path),
             "-filter_complex",
             "[1:a]volume=0.12,aloop=loop=-1:size=2e9[bg];[0:a][bg]amix=inputs=2:duration=first:dropout_transition=0[a]",
             "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", str(out_path)],
            check=True, capture_output=True, timeout=300,
        )
        return out_path.exists()
    except (subprocess.SubprocessError, OSError):
        return False


# ---------------------------------------------------------------------------
# GENERATIVE_VIDEO_MODE — adapter interface only, not required to work.
# ---------------------------------------------------------------------------

class GenerativeVideoAdapter:
    """Clean seam for a real generative video backend (ComfyUI, Wan, LTX,
    or another provider). No default implementation ships — wiring one in
    means overriding `generate_clip` with real API/local-inference calls.
    LIGHTWEIGHT_MODE must work without this ever being implemented."""

    name = "unconfigured"

    def available(self) -> bool:
        return False

    def generate_clip(self, video_prompt: str, duration_seconds: float, out_path: Path) -> bool:
        raise NotImplementedError("No generative video provider is configured in this repository.")


# ---------------------------------------------------------------------------

def build_scene_plan(storyboard: list[dict], audio_manifest: dict | None) -> list[dict]:
    audio_by_scene = {}
    if audio_manifest:
        for entry in audio_manifest.get("scenes", []):
            audio_by_scene[entry.get("scene_number")] = entry

    plan = []
    for scene in storyboard:
        scene_number = scene.get("scene_number")
        audio_entry = audio_by_scene.get(scene_number, {})
        estimated = max(
            0.0, scene.get("subtitle_end_seconds", 0) - scene.get("subtitle_start_seconds", 0)
        )
        actual_audio = audio_entry.get("actual_seconds")
        duration = max(MIN_CLIP_SECONDS, actual_audio or estimated or MIN_CLIP_SECONDS)
        plan.append({
            "scene_number": scene_number,
            "section": scene.get("section", ""),
            "role": scene.get("role", ""),
            "narration": scene.get("narration", ""),
            "visual_idea": scene.get("visual_idea", ""),
            "scene_idea": scene.get("scene_idea", ""),
            "transition": scene.get("transition", ""),
            "audio_file": str(ROOT / audio_entry["audio_file"]) if audio_entry.get("audio_file") else None,
            "clip_duration_seconds": round(duration, 2),
        })
    return plan


def render(scene_plan: list[dict]) -> tuple[bool, list[str]]:
    CLIPS_DIR.mkdir(parents=True, exist_ok=True)
    clip_paths = []
    for scene in scene_plan:
        image_path, is_supplied = resolve_scene_image(scene["scene_number"], scene["role"], scene["visual_idea"] or scene["scene_idea"])
        scene["image_source"] = str(image_path)
        scene["image_supplied"] = is_supplied

        silent_path = CLIPS_DIR / f"scene_{scene['scene_number']:02d}_silent.mp4"
        if not render_scene_clip(image_path, scene["clip_duration_seconds"], scene["narration"], silent_path):
            return False, [f"Sahne {scene['scene_number']} render edilemedi (FFmpeg hatası)."]

        final_scene_path = CLIPS_DIR / f"scene_{scene['scene_number']:02d}_final.mp4"
        audio_path = Path(scene["audio_file"]) if scene["audio_file"] else None
        if not mux_scene_audio(silent_path, audio_path, scene["clip_duration_seconds"], final_scene_path):
            return False, [f"Sahne {scene['scene_number']} ses ile birleştirilemedi."]
        clip_paths.append(final_scene_path)

    if not concat_scenes(clip_paths, FINAL_VIDEO_PATH):
        return False, ["Sahneler tek videoda birleştirilemedi (FFmpeg concat hatası)."]

    music_path = find_supplied_music()
    if music_path:
        with_music = OUTPUT_DIR / "_with_music.mp4"
        if mix_background_music(FINAL_VIDEO_PATH, music_path, with_music):
            with_music.replace(FINAL_VIDEO_PATH)

    return True, []


def _write(payload: dict, manifest: dict) -> None:
    # Single source of truth: every caller's manifest dict gets the same
    # status/reasons stamped on it, regardless of which branch built it.
    manifest["status"] = payload["status"]
    manifest["reasons"] = payload.get("reasons", [])
    manifest["final_video"] = payload.get("final_video")
    if payload.get("external_requirement"):
        manifest["external_requirement"] = payload["external_requirement"]

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "render_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    lines = [
        "# SHP Video Engine Raporu", "",
        f"**Durum:** {payload['status']}",
        f"**Mod:** LIGHTWEIGHT_MODE",
        f"**Çözünürlük:** {RESOLUTION[0]}x{RESOLUTION[1]} @ {FPS}fps",
        f"**Toplam süre:** {payload.get('total_duration_seconds', '-')} sn",
        f"**Final video:** {payload.get('final_video') or 'üretilmedi'}",
        f"**Arka plan müziği:** {payload.get('music_used') or 'yok (assets/audio/background_music.mp3|wav sağlanmadı)'}",
        "",
        "## Gerekçe / durum notları", "",
        *[f"- {r}" for r in payload.get("reasons", [])],
        "",
    ]
    if payload.get("external_requirement"):
        lines += ["## Gerekli dış çalışma zamanı", "", f"- {payload['external_requirement']}", ""]
    lines += [
        "## Gerçek sınırlar", "",
        "- Görsel API anahtarı yoksa sahne görselleri gerçek AI görseli değil, tipografik yerleşim kartıdır (assets/images/scene_NN.png|jpg sağlanırsa onun yerine kullanılır).",
        "- Sahne süresi, gerçek TTS ses süresi varsa ondan; yoksa tahmini konuşma süresinden alınır — konuşma asla kesilmez.",
        "- GENERATIVE_VIDEO_MODE bu depoda bağlı değildir; sadece arayüz mevcuttur (GenerativeVideoAdapter).",
        "- Bu rapor sahte bir video üretimini asla bildirmez: final_video.mp4 yalnızca gerçekten render edildiyse mevcuttur.",
    ]
    (OUTPUT_DIR / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    video_ceo = load_json(ROOT / "video-ceo" / "analysis.json")
    storyboard = load_json(SCRIPT_DIR / "storyboard.json", [])
    audio_manifest = load_json(VOICEOVER_DIR / "audio_manifest.json")

    if not video_ceo or video_ceo.get("decision") != "ÇEK":
        decision = (video_ceo or {}).get("decision", "BİLİNMİYOR (video-ceo/analysis.json bulunamadı)")
        payload = {
            "status": "STOPPED_BY_VIDEO_CEO",
            "reasons": [f"Video CEO Pro kararı '{decision}'; üretim güvenli şekilde durduruldu, render denenmedi."],
            "final_video": None,
            "total_duration_seconds": 0,
        }
        _write(payload, {"generated_at": datetime.now(timezone.utc).isoformat(), "status": payload["status"], "video_ceo_decision": decision, "scenes": []})
        print(f"VIDEO_ENGINE_STATUS={payload['status']}")
        return

    if not storyboard:
        payload = {"status": "BLOCKED_MISSING_DATA", "reasons": ["projects/script-agent/storyboard.json bulunamadı veya boş."], "final_video": None, "total_duration_seconds": 0}
        _write(payload, {"generated_at": datetime.now(timezone.utc).isoformat(), "status": payload["status"], "scenes": []})
        print(f"VIDEO_ENGINE_STATUS={payload['status']}")
        return

    scene_plan = build_scene_plan(storyboard, audio_manifest)
    total_duration = round(sum(s["clip_duration_seconds"] for s in scene_plan), 2)

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "resolution": f"{RESOLUTION[0]}x{RESOLUTION[1]}",
        "fps": FPS,
        "total_duration_seconds": total_duration,
        "scenes": scene_plan,
        "music_candidate": str(find_supplied_music()) if find_supplied_music() else None,
    }

    if not ffmpeg_available():
        # Still resolve/generate every frame asset so the package is
        # complete — only the actual encode step is skipped.
        for scene in scene_plan:
            image_path, is_supplied = resolve_scene_image(scene["scene_number"], scene["role"], scene["visual_idea"] or scene["scene_idea"])
            scene["image_source"] = str(image_path)
            scene["image_supplied"] = is_supplied
        payload = {
            "status": "RENDER_SKIPPED_NO_FFMPEG",
            "reasons": ["FFmpeg bu ortamda kurulu değil; render denenmedi, ancak tüm sahne görselleri ve manifest hazırlandı."],
            "external_requirement": "FFmpeg kurulu bir ortamda çalıştır: `sudo apt-get install -y ffmpeg` sonrasında `python video_engine.py`. GitHub Actions ubuntu-latest runner'larında FFmpeg varsayılan olarak kuruludur.",
            "final_video": None,
            "total_duration_seconds": total_duration,
        }
        _write(payload, manifest)
        print(f"VIDEO_ENGINE_STATUS={payload['status']}")
        return

    ok, reasons = render(scene_plan)
    manifest["scenes"] = scene_plan  # now includes image_source/image_supplied
    music_used = find_supplied_music()
    payload = {
        "status": "RENDERED" if ok else "TECHNICAL_FAILURE",
        "reasons": reasons or ["Render tamamlandı."],
        "final_video": str(FINAL_VIDEO_PATH) if ok else None,
        "total_duration_seconds": total_duration,
        "music_used": str(music_used) if (ok and music_used) else None,
    }
    _write(payload, manifest)
    print(f"VIDEO_ENGINE_STATUS={payload['status']}")
    print(f"VIDEO_ENGINE_OUTPUT={payload['final_video']}")
    print(f"VIDEO_ENGINE_DURATION={total_duration}")


if __name__ == "__main__":
    main()
