"""Stage 10: Black & White Engine.

Real implementation of film-simulation-style conversion - explicitly not
`cv2.cvtColor(..., COLOR_RGB2GRAY)`, per the spec's "never simply
desaturate":

  1. channel-weighted mix tuned like a red/orange film filter (classic
     portrait B&W look: warms/lightens skin tones relative to a flat
     luminance conversion, which crushes skin into mud)
  2. S-curve contrast for "rich contrast"
  3. optional fine film grain (luminance-only, so it doesn't introduce
     color noise)
"""

from __future__ import annotations

import numpy as np

# Channel weights approximating an orange-filter panchromatic response -
# lifts red (skin, warm tones) relative to plain Rec.601 luma weights.
_R_WEIGHT, _G_WEIGHT, _B_WEIGHT = 0.5, 0.35, 0.15


def convert_bw(rgb: np.ndarray, grain: bool = True) -> np.ndarray:
    img = rgb.astype(np.float32) / 255.0
    mono = img[:, :, 0] * _R_WEIGHT + img[:, :, 1] * _G_WEIGHT + img[:, :, 2] * _B_WEIGHT

    mono = _s_curve(mono, strength=0.15)

    if grain:
        mono = _add_grain(mono, amount=0.012)

    mono = np.clip(mono, 0.0, 1.0)
    out = np.stack([mono, mono, mono], axis=-1)
    return (out * 255.0).astype(np.uint8)


def _s_curve(x: np.ndarray, strength: float) -> np.ndarray:
    # Smoothstep-based S-curve blended with the original for a rich but
    # not crushed contrast boost.
    curved = x * x * (3 - 2 * x)
    return x * (1 - strength) + curved * strength


def _add_grain(mono: np.ndarray, amount: float) -> np.ndarray:
    rng = np.random.default_rng(seed=None)
    noise = rng.normal(0.0, amount, size=mono.shape).astype(np.float32)
    return mono + noise
