"""Image loading for every format in the spec's INPUT list.

RAW  (CR2/CR3/NEF/ARW/RAF/DNG) -> rawpy (bundled libraw), real decoding.
HEIC/HEIF                       -> pillow-heif, real decoding.
JPEG/PNG                        -> Pillow, real decoding.

Everything returns a numpy uint8 RGB array (H, W, 3) plus a PIL.Image for
stages that want to keep working in Pillow-land.
"""

from __future__ import annotations

import os

import numpy as np
from PIL import Image

import pillow_heif

pillow_heif.register_heif_opener()

RAW_EXTENSIONS = {".cr2", ".cr3", ".nef", ".arw", ".raf", ".dng"}
STANDARD_EXTENSIONS = {".jpg", ".jpeg", ".png", ".heic", ".heif"}
SUPPORTED_EXTENSIONS = RAW_EXTENSIONS | STANDARD_EXTENSIONS


def is_supported(path: str) -> bool:
    return os.path.splitext(path)[1].lower() in SUPPORTED_EXTENSIONS


def list_images(directory: str) -> list:
    out = []
    for root, _dirs, files in os.walk(directory):
        for f in sorted(files):
            if is_supported(f):
                out.append(os.path.join(root, f))
    return out


def load_rgb(path: str) -> np.ndarray:
    """Decode any supported format to an (H, W, 3) uint8 RGB numpy array."""
    ext = os.path.splitext(path)[1].lower()
    if ext in RAW_EXTENSIONS:
        return _load_raw(path)
    return _load_standard(path)


def _load_raw(path: str) -> np.ndarray:
    import rawpy

    with rawpy.imread(path) as raw:
        # use_camera_wb: trust the camera's white balance rather than
        # guessing one, matching how a photographer expects the initial
        # RAW preview to look.
        rgb = raw.postprocess(
            use_camera_wb=True,
            no_auto_bright=False,
            output_bps=8,
        )
    return rgb


def _load_standard(path: str) -> np.ndarray:
    img = Image.open(path)
    img = _apply_exif_orientation(img)
    img = img.convert("RGB")
    return np.array(img)


def _apply_exif_orientation(img: Image.Image) -> Image.Image:
    from PIL import ImageOps

    return ImageOps.exif_transpose(img)


def rgb_to_pil(rgb: np.ndarray) -> Image.Image:
    return Image.fromarray(rgb.astype(np.uint8), mode="RGB")


def save_rgb(rgb: np.ndarray, path: str, quality: int = 95) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img = rgb_to_pil(rgb)
    save_kwargs = {}
    if path.lower().endswith((".jpg", ".jpeg")):
        save_kwargs = {"quality": quality, "optimize": True}
    img.save(path, **save_kwargs)
    return path
