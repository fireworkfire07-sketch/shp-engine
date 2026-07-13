"""Stage 6: Lightroom AI - automatic tonal/color edit engine.

Real, working implementation of the classic "auto develop" moves a
Lightroom editor reaches for first, each one driven by the Stage 1 quality
measurements rather than applied blindly:

  * white balance   -> gray-world correction, strength scaled by the
                        measured color_cast_rgb_delta (skipped if the image
                        is already neutral)
  * exposure         -> shifts the luma median toward a healthy midtone,
                        scaled by how far off exposure_mean already is
  * highlight/shadow recovery -> smooth S-curve compression, strength
                        driven by measured clipping percentages
  * contrast          -> gentle percentile-based tone stretch
  * saturation/vibrance -> HSV vibrance boost that favors already-muted
                        colors over already-saturated ones (skin tones stay
                        natural instead of blowing out)
  * noise reduction   -> bilateral filter, only applied when noise_estimate
                        exceeds a threshold, and only as strong as the
                        measured noise warrants
  * sharpening        -> unsharp mask, skipped/reduced on images already
                        flagged blurry (sharpening a blur just adds halos)

Every adjustment is intentionally capped to stay subtle, per the spec's
"never over-edit" principle. Advanced curve/profile-matching (lens
correction profiles, camera color-science profiles) is a documented gap -
lens correction needs a per-lens distortion database we don't have here.
"""

from __future__ import annotations

import cv2
import numpy as np

from ..models import QualityMetrics


def auto_edit(rgb: np.ndarray, quality: QualityMetrics) -> np.ndarray:
    img = rgb.astype(np.float32) / 255.0

    img = _white_balance(img, quality)
    img = _exposure(img, quality)
    img = _tone_curve(img, quality)
    img = _contrast(img)
    img = _vibrance(img)

    out = np.clip(img * 255.0, 0, 255).astype(np.uint8)

    if quality.noise_estimate > 6.0:
        out = _denoise(out, quality)
    if not quality.is_blurry:
        out = _sharpen(out)

    return out


def _white_balance(img: np.ndarray, quality: QualityMetrics) -> np.ndarray:
    if quality.color_cast_rgb_delta < 8.0:
        return img
    means = img.reshape(-1, 3).mean(axis=0)
    gray_target = means.mean()
    gains = gray_target / np.clip(means, 1e-4, None)
    # Only correct part-way: a full gray-world correction over-neutralizes
    # intentionally warm/cool scenes (sunsets, golden hour portraits).
    strength = min(1.0, quality.color_cast_rgb_delta / 60.0)
    gains = 1.0 + (gains - 1.0) * strength
    return np.clip(img * gains, 0.0, 1.0)


def _exposure(img: np.ndarray, quality: QualityMetrics) -> np.ndarray:
    target_mean = 118.0  # ~0.46 in 0-1, a healthy midtone
    current = quality.exposure_mean
    if abs(current - target_mean) < 10:
        return img
    # Move at most a third of the way to target in one pass - subtle nudge,
    # not a full auto-exposure reset.
    delta = (target_mean - current) / 255.0 / 3.0
    return np.clip(img + delta, 0.0, 1.0)


def _tone_curve(img: np.ndarray, quality: QualityMetrics) -> np.ndarray:
    """Highlight/shadow recovery via a smooth compression curve."""
    highlight_strength = min(0.3, quality.clipped_highlights_pct / 20.0)
    shadow_strength = min(0.3, quality.clipped_shadows_pct / 20.0)
    if highlight_strength <= 0 and shadow_strength <= 0:
        return img

    x = img
    if highlight_strength > 0:
        # Compress the top of the range so near-clipped highlights recover
        # detail instead of clipping flat white.
        x = np.where(x > 0.7, 0.7 + (x - 0.7) * (1 - highlight_strength), x)
    if shadow_strength > 0:
        x = np.where(x < 0.15, x * (1 - shadow_strength) + 0.15 * shadow_strength * (x / 0.15), x)
    return np.clip(x, 0.0, 1.0)


def _contrast(img: np.ndarray) -> np.ndarray:
    lo, hi = np.percentile(img, [1, 99]).astype(np.float32)
    if hi - lo < 1e-3:
        return img
    stretched = (img - lo) / (hi - lo)
    # Blend with the original so contrast is enhanced, not fully reset -
    # keeps the look realistic instead of a harsh auto-levels punch.
    result = np.clip(0.6 * stretched + 0.4 * img, 0.0, 1.0)
    return result.astype(np.float32)


def _vibrance(img: np.ndarray) -> np.ndarray:
    hsv = cv2.cvtColor(img, cv2.COLOR_RGB2HSV)
    s = hsv[:, :, 1]
    # Boost low-saturation pixels more than already-saturated ones so skin
    # tones (naturally lower saturation) don't get oversaturated along with
    # genuinely vivid colors.
    boost = 1.0 + 0.25 * (1.0 - s)
    hsv[:, :, 1] = np.clip(s * boost, 0.0, 1.0)
    return cv2.cvtColor(hsv, cv2.COLOR_HSV2RGB)


def _denoise(rgb_u8: np.ndarray, quality: QualityMetrics) -> np.ndarray:
    strength = int(min(9, max(3, quality.noise_estimate)))
    return cv2.bilateralFilter(rgb_u8, d=strength, sigmaColor=40, sigmaSpace=40)


def _sharpen(rgb_u8: np.ndarray) -> np.ndarray:
    blurred = cv2.GaussianBlur(rgb_u8, (0, 0), sigmaX=2.0)
    sharpened = cv2.addWeighted(rgb_u8, 1.3, blurred, -0.3, 0)
    return np.clip(sharpened, 0, 255).astype(np.uint8)
