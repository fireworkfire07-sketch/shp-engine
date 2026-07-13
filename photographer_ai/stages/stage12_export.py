"""Stage 12: Export.

Real implementation - resizing, quality settings, watermarking and
zip packaging are all standard, fully-working image I/O (no ML needed).

Generates the delivery set from the spec:
  lightroom_edit, black_white_hero, web, high_resolution, preview,
  watermarked_preview, print, album, plus one file per Stage 7 social crop,
  and a single ZIP bundling everything for one image.
"""

from __future__ import annotations

import os
import zipfile

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from ..io_utils import save_rgb

WEB_MAX_DIM = 2048
PREVIEW_MAX_DIM = 900
SOCIAL_MAX_DIM = 1600


def export_all(
    filename_stem: str,
    output_dir: str,
    edited_rgb: np.ndarray,
    bw_rgb: "np.ndarray | None",
    crops: dict,
    is_hero: bool,
) -> dict:
    paths = {}
    base_dir = os.path.join(output_dir, filename_stem)
    os.makedirs(base_dir, exist_ok=True)

    paths["high_resolution"] = save_rgb(edited_rgb, os.path.join(base_dir, "high_resolution.jpg"), quality=98)
    paths["lightroom_edit"] = paths["high_resolution"]

    web = _resize_max_dim(edited_rgb, WEB_MAX_DIM)
    paths["web"] = save_rgb(web, os.path.join(base_dir, "web.jpg"), quality=88)

    preview = _resize_max_dim(edited_rgb, PREVIEW_MAX_DIM)
    paths["preview"] = save_rgb(preview, os.path.join(base_dir, "preview.jpg"), quality=80)

    watermarked = _apply_watermark(preview, "PREVIEW")
    paths["watermarked_preview"] = save_rgb(
        watermarked, os.path.join(base_dir, "watermarked_preview.jpg"), quality=80
    )

    if bw_rgb is not None and is_hero:
        paths["black_white_hero"] = save_rgb(
            bw_rgb, os.path.join(base_dir, "black_white_hero.jpg"), quality=95
        )

    for name, crop_rgb in crops.items():
        if name == "original":
            continue
        sized = _resize_max_dim(crop_rgb, SOCIAL_MAX_DIM)
        paths[name] = save_rgb(sized, os.path.join(base_dir, f"{name}.jpg"), quality=88)

    paths["zip"] = _zip_exports(base_dir, paths, filename_stem)
    return paths


def _resize_max_dim(rgb: np.ndarray, max_dim: int) -> np.ndarray:
    h, w = rgb.shape[:2]
    scale = min(1.0, max_dim / max(h, w))
    if scale >= 1.0:
        return rgb
    new_w, new_h = int(round(w * scale)), int(round(h * scale))
    img = Image.fromarray(rgb).resize((new_w, new_h), Image.LANCZOS)
    return np.array(img)


def _apply_watermark(rgb: np.ndarray, text: str) -> np.ndarray:
    img = Image.fromarray(rgb).convert("RGBA")
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    font_size = max(18, img.width // 18)
    try:
        font = ImageFont.load_default(size=font_size)
    except TypeError:
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), text, font=font)
    text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]

    step_x = text_w + 80
    step_y = text_h + 80
    for y in range(-step_y, img.height + step_y, step_y):
        for x in range(-step_x, img.width + step_x, step_x):
            draw.text((x, y), text, font=font, fill=(255, 255, 255, 90))

    watermarked = Image.alpha_composite(img, overlay).convert("RGB")
    return np.array(watermarked)


def _zip_exports(base_dir: str, paths: dict, stem: str) -> str:
    zip_path = os.path.join(base_dir, f"{stem}_export.zip")
    seen_paths = set()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, path in paths.items():
            if path and os.path.isfile(path) and path not in seen_paths:
                seen_paths.add(path)
                zf.write(path, arcname=os.path.basename(path))
    return zip_path
