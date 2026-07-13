"""Stage 9: Hero Shot Detector + Stage 13: Photo Ranking.

Real implementation, combined into one module since ranking is a direct
function of the hero score: weighted combination of the Stage 1
(quality), Stage 2 (face/eye state) and Stage 4 (composition) scores that
were already computed for real.

Explicitly NOT a learned aesthetic model - "storytelling" and "impact" in
the spec require understanding scene semantics that classical CV can't
give us. What's implemented is the measurable half of the spec's Hero
criteria (sharpness, composition, lighting-via-exposure, subject
isolation, eyes-open); emotion/storytelling stay at their Stage 2
documented-gap default and simply don't contribute a term here, rather
than being faked with a random or constant value.
"""

from __future__ import annotations

from ..models import CompositionScore, FaceReport, HeroScore, QualityMetrics, Rating

STAR_THRESHOLDS = (
    (85, Rating.HERO, 5),
    (70, Rating.EXCELLENT, 4),
    (55, Rating.GOOD, 3),
    (35, Rating.NEEDS_REVIEW, 2),
    (0, Rating.REJECT, 1),
)


def score_hero(quality: QualityMetrics, faces: FaceReport, composition: CompositionScore) -> HeroScore:
    score = 0.5 * quality.quality_score + 0.35 * composition.composition_score

    face_term = _face_term(faces)
    score += 0.15 * face_term

    if quality.duplicate_of is not None:
        score -= 30  # never crown a near-duplicate the hero over its best sibling
    if quality.is_blurry:
        score -= 20
    if faces.any_face_needs_review:
        score -= 10

    score = max(0.0, min(100.0, score))

    rating, stars = _rank(score, quality)

    return HeroScore(hero_score=float(score), rating=rating, stars=stars)


def _face_term(faces: FaceReport) -> float:
    if not faces.faces:
        # No people in frame (landscape/detail shot) - neutral, not penalized.
        return 70.0
    open_eyes = sum(1 for f in faces.faces if f.both_eyes_open)
    ratio = open_eyes / len(faces.faces)
    return 100.0 * ratio


def _rank(score: float, quality: QualityMetrics) -> tuple:
    if quality.is_blurry and score < 40:
        return Rating.REJECT, 1
    for threshold, rating, stars in STAR_THRESHOLDS:
        if score >= threshold:
            return rating, stars
    return Rating.REJECT, 1


def rank_batch(records: list) -> dict:
    """Group ImageRecords by star rating for the culling UI's filter view."""
    buckets = {stars: [] for _, _, stars in STAR_THRESHOLDS}
    for r in records:
        buckets[r.hero.stars].append(r)
    for bucket in buckets.values():
        bucket.sort(key=lambda r: r.hero.hero_score, reverse=True)
    return buckets
