"""Stage 1: Image Quality Analysis.

Fully real, classical computer-vision implementation - no trained models
needed for any of this:

  * sharpness / blur           -> variance of the Laplacian
  * over/under exposure        -> luma histogram + clipping percentages
  * noise                      -> Immerkaer's fast single-image noise estimator
  * color cast                 -> gray-world channel deviation
  * dynamic range               -> 95th/5th luma percentile spread
  * duplicate / near-duplicate / burst detection -> perceptual hashing (phash)

Not implemented here (documented gaps, need learned models to do well):
  * lens softness vs. missed focus vs. motion blur discrimination
  * chromatic aberration / lens distortion (needs lens profile database)
  * horizon alignment (needs horizon-line detection)
  * dirty sensor spot detection (needs a reference frame / dust map)
These would slot in as additional QualityMetrics fields computed the same
way — pass an ImageRecord in, fill in a field, no pipeline changes needed.
"""

from __future__ import annotations

import cv2
import imagehash
import numpy as np
from PIL import Image

from ..models import ImageRecord, QualityMetrics

BLUR_THRESHOLD = 100.0          # Laplacian variance below this = flagged blurry
OVEREXPOSED_MEAN = 235.0
UNDEREXPOSED_MEAN = 20.0
CLIP_PCT_FLAG = 2.0             # % of pixels at 0 or 255 to flag clipping
COLOR_CAST_FLAG = 15.0          # mean channel deviation (0-255 scale)
PHASH_DUPLICATE_DISTANCE = 6    # hamming distance <= this => near-duplicate
PHASH_SIZE = 16


def analyze_quality(rgb: np.ndarray) -> QualityMetrics:
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)

    sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    is_blurry = sharpness < BLUR_THRESHOLD

    exposure_mean = float(gray.mean())
    is_overexposed = exposure_mean > OVEREXPOSED_MEAN
    is_underexposed = exposure_mean < UNDEREXPOSED_MEAN

    total_px = gray.size
    clipped_highlights_pct = float((gray >= 250).sum()) / total_px * 100
    clipped_shadows_pct = float((gray <= 5).sum()) / total_px * 100

    noise_estimate = _estimate_noise(gray)

    color_cast_rgb_delta = _color_cast(rgb)

    p95, p5 = np.percentile(gray, [95, 5])
    dynamic_range = float(p95 - p5)

    phash = str(imagehash.phash(Image.fromarray(rgb), hash_size=PHASH_SIZE))

    metrics = QualityMetrics(
        sharpness=sharpness,
        is_blurry=is_blurry,
        exposure_mean=exposure_mean,
        is_overexposed=is_overexposed,
        is_underexposed=is_underexposed,
        clipped_highlights_pct=clipped_highlights_pct,
        clipped_shadows_pct=clipped_shadows_pct,
        noise_estimate=noise_estimate,
        color_cast_rgb_delta=color_cast_rgb_delta,
        dynamic_range=dynamic_range,
        phash=phash,
    )
    metrics.quality_score = _aggregate_score(metrics)
    return metrics


def _estimate_noise(gray: np.ndarray) -> float:
    """Immerkaer (1996) fast single-image noise estimator.

    Convolves with a Laplacian-of-Gaussian-like kernel designed so its
    response on noise-free content is ~0, isolating the noise floor.
    """
    h, w = gray.shape
    kernel = np.array([[1, -2, 1], [-2, 4, -2], [1, -2, 1]], dtype=np.float64)
    conv = cv2.filter2D(gray.astype(np.float64), -1, kernel)
    sigma = np.sqrt(np.pi / 2) * np.mean(np.abs(conv)) / (6 * (w - 2) * (h - 2)) * (w * h)
    return float(sigma)


def _color_cast(rgb: np.ndarray) -> float:
    """Gray-world assumption: a neutral scene should average to gray.

    Large spread between channel means suggests a color cast (e.g. a
    heavy orange/blue tint from bad white balance).
    """
    means = rgb.reshape(-1, 3).mean(axis=0)
    return float(means.max() - means.min())


def _aggregate_score(m: QualityMetrics) -> float:
    """0-100 quality score. Sharpness dominates; exposure/noise/cast subtract."""
    sharpness_score = min(100.0, (m.sharpness / 500.0) * 100.0)
    score = sharpness_score

    if m.is_blurry:
        score -= 40
    if m.is_overexposed or m.is_underexposed:
        score -= 25
    if m.clipped_highlights_pct > CLIP_PCT_FLAG:
        score -= min(20.0, m.clipped_highlights_pct)
    if m.clipped_shadows_pct > CLIP_PCT_FLAG:
        score -= min(15.0, m.clipped_shadows_pct)
    if m.color_cast_rgb_delta > COLOR_CAST_FLAG:
        score -= 10
    if m.noise_estimate > 6.0:
        score -= min(15.0, m.noise_estimate)

    return float(max(0.0, min(100.0, score)))


def detect_duplicates_and_bursts(records: list[ImageRecord]) -> None:
    """Group near-duplicate / burst-sequence images by perceptual hash.

    Mutates `duplicate_of` and `burst_group` on each record's QualityMetrics.
    A record is marked `duplicate_of` the first (by filename order) image in
    its group with the highest quality_score kept as the representative.
    """
    hashes = []
    for r in records:
        if r.quality.phash:
            hashes.append((r, imagehash.hex_to_hash(r.quality.phash)))

    groups: list[list] = []
    used = set()
    for i, (rec_a, hash_a) in enumerate(hashes):
        if rec_a.filename in used:
            continue
        group = [rec_a]
        used.add(rec_a.filename)
        for rec_b, hash_b in hashes[i + 1:]:
            if rec_b.filename in used:
                continue
            if hash_a - hash_b <= PHASH_DUPLICATE_DISTANCE:
                group.append(rec_b)
                used.add(rec_b.filename)
        if len(group) > 1:
            groups.append(group)

    for group_idx, group in enumerate(groups):
        best = max(group, key=lambda r: r.quality.quality_score)
        for r in group:
            r.quality.burst_group = group_idx
            if r is not best:
                r.quality.duplicate_of = best.filename
