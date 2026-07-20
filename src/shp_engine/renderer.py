from __future__ import annotations

from pathlib import Path
import textwrap

from moviepy.editor import ImageClip, concatenate_videoclips
from PIL import Image, ImageDraw, ImageFont

from .content import Scene

WIDTH = 1080
HEIGHT = 1920


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
    ):
        if Path(path).exists():
            return ImageFont.truetype(path, size=size)
    return ImageFont.load_default()


def _draw_centered(draw: ImageDraw.ImageDraw, text: str, y: int, font, width: int = 900) -> int:
    lines = textwrap.wrap(text, width=24 if font.size >= 70 else 34)
    current_y = y
    for line in lines:
        box = draw.textbbox((0, 0), line, font=font)
        line_width = box[2] - box[0]
        draw.text(((WIDTH - line_width) / 2, current_y), line, font=font, fill="white")
        current_y += (box[3] - box[1]) + 28
    return current_y


def render_video(scenes: list[Scene], output_path: Path, fps: int = 24) -> Path:
    """Render a real vertical MP4 using only Pillow and MoviePy."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    frame_dir = output_path.parent / "frames"
    frame_dir.mkdir(parents=True, exist_ok=True)

    clips = []
    for index, scene in enumerate(scenes, start=1):
        image = Image.new("RGB", (WIDTH, HEIGHT), (14, 18, 28))
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((70, 100, WIDTH - 70, HEIGHT - 100), radius=45, outline=(185, 150, 80), width=5)
        draw.text((90, 125), f"SHP ENGINE • {index:02d}", font=_font(34), fill=(210, 180, 110))
        y = _draw_centered(draw, scene.heading, 510, _font(86))
        _draw_centered(draw, scene.body, y + 110, _font(52))
        draw.text((90, HEIGHT - 185), "Otomatik video üretim sistemi", font=_font(30), fill=(180, 180, 180))

        frame_path = frame_dir / f"scene_{index:02d}.png"
        image.save(frame_path)
        clips.append(ImageClip(str(frame_path)).set_duration(scene.duration))

    final = concatenate_videoclips(clips, method="compose")
    final.write_videofile(str(output_path), fps=fps, codec="libx264", audio=False, logger=None)
    final.close()
    for clip in clips:
        clip.close()
    return output_path
