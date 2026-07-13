"""Stage 11: Cinematic Shadow Compositor.

Real implementation of the classical building blocks of "dodge and burn"
and local contrast, applied automatically:

  * local contrast -> CLAHE (Contrast Limited Adaptive Histogram
    Equalization) on the L channel in LAB space, which is the standard
    real-world technique for adding depth/dimensionality without a global
    contrast punch
  * natural dodge & burn -> a soft radial luminance mask centered on the
    subject point (brightens the subject, gently darkens the frame edges),
    mimicking what a photographer does by hand with the dodge/burn tools

This produces a genuine, controllable depth effect. What it is NOT is a
learned "magazine look" grading model - matching a specific film stock or
a named cinematic LUT needs a trained/curated color-grading model, which
is a documented gap. The two real techniques above are exactly the
mechanical primitives such a model would still be built on top of.
"""

from __future__ import annotations

import cv2
import numpy as np

DODGE_BURN_STRENGTH = 0.12
CLAHE_CLIP_LIMIT = 2.0
CLAHE_TILE_GRID = (8, 8)


def apply_cinematic_shadow(rgb: np.ndarray, subject_point: tuple) -> np.ndarray:
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB)
    l_channel, a_channel, b_channel = cv2.split(lab)

    clahe = cv2.createCLAHE(clipLimit=CLAHE_CLIP_LIMIT, tileGridSize=CLAHE_TILE_GRID)
    l_channel = clahe.apply(l_channel)

    l_channel = _dodge_and_burn(l_channel, subject_point)

    lab = cv2.merge([l_channel, a_channel, b_channel])
    return cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)


def _dodge_and_burn(l_channel: np.ndarray, subject_point: tuple) -> np.ndarray:
    h, w = l_channel.shape
    sx, sy = subject_point
    ys, xs = np.indices((h, w))
    dist = np.hypot(xs - sx, ys - sy)
    max_dist = np.hypot(w, h) / 2

    # 1.0 at the subject, fading toward -1.0 at the frame's far corners.
    falloff = 1.0 - 2.0 * np.clip(dist / max_dist, 0.0, 1.0)
    delta = (falloff * DODGE_BURN_STRENGTH * 255.0).astype(np.float32)

    out = l_channel.astype(np.float32) + delta
    return np.clip(out, 0, 255).astype(np.uint8)
