"""5. CURIOSITY ENGINE

Every 20-30 seconds of narration must open a new curiosity gap. Plans the
required gap cadence before generation, then evaluates the actual generated
sections and flags any stretch of narration that lets curiosity drop —
Script Doctor rewrites whatever this engine flags.
"""

from __future__ import annotations

from script_agent_v2 import textutil
from script_agent_v2.engines import psychology_engine

GAP_INTERVAL_SECONDS = 27
MIN_SECTION_CURIOSITY_SCORE = 45


def plan(story_dna_plan: dict) -> dict:
    target_seconds = story_dna_plan.get("target_duration_seconds", 420)
    required_gaps = max(6, round(target_seconds / GAP_INTERVAL_SECONDS))
    return {
        "gap_interval_seconds": GAP_INTERVAL_SECONDS,
        "required_gap_count": required_gaps,
        "minimum_section_score": MIN_SECTION_CURIOSITY_SCORE,
        "techniques": [
            "Cevabı hemen verme; bir sonraki bölüme sakla.",
            "Yarım bırakılmış bir detay ile bölümü kapat.",
            "Beklenmedik bir karşılaştırma veya sayı düş.",
            "Açık bir soru sor ve videoya kadar cevaplama.",
        ],
    }


def evaluate(sections: list[dict], curiosity_plan: dict) -> dict:
    threshold = curiosity_plan.get("minimum_section_score", MIN_SECTION_CURIOSITY_SCORE)
    per_section = []
    elapsed = 0.0
    last_gap_at = 0.0
    weak_sections = []
    gap_count = 0

    for section in sections:
        text = str(section.get("voiceover", ""))
        duration = textutil.estimate_seconds(text)
        elapsed += duration
        result = psychology_engine.score(text)
        curiosity_score = result["curiosity"] + result["information_gap"]
        has_gap = result["information_gap"] > 0 or "?" in text
        if has_gap:
            gap_count += 1
            last_gap_at = elapsed

        stall_seconds = elapsed - last_gap_at
        passes = curiosity_score >= threshold or has_gap
        per_section.append({
            "name": section.get("name", ""),
            "estimated_seconds": duration,
            "cumulative_seconds": round(elapsed, 1),
            "curiosity_score": min(100, curiosity_score),
            "has_curiosity_gap": has_gap,
            "seconds_since_last_gap": round(stall_seconds, 1),
            "pass": passes,
        })
        if not passes:
            weak_sections.append(section.get("name", ""))

    overall_pass = not weak_sections and gap_count >= curiosity_plan.get("required_gap_count", 6) * 0.6
    return {
        "per_section": per_section,
        "weak_sections": weak_sections,
        "gap_count": gap_count,
        "required_gap_count": curiosity_plan.get("required_gap_count", 6),
        "overall_pass": overall_pass,
        "overall_score": round(sum(s["curiosity_score"] for s in per_section) / max(1, len(per_section))),
    }
