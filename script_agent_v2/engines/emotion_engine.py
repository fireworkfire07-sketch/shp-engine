"""7. EMOTION ENGINE

Controls the emotional flow of the whole script: curiosity -> surprise ->
tension -> discovery -> satisfaction. Plans the target curve before
generation, then detects the actual emotion carried by each generated
section and scores how closely the real curve follows the target shape.
"""

from __future__ import annotations

from script_agent_v2 import textutil

TARGET_CURVE = ["merak", "şaşkınlık", "gerilim", "keşif", "tatmin"]

LEXICON = {
    "merak": textutil.CURIOSITY_WORDS,
    "şaşkınlık": textutil.SURPRISE_WORDS,
    "gerilim": textutil.TENSION_WORDS,
    "keşif": textutil.DISCOVERY_WORDS,
    "tatmin": textutil.SATISFACTION_WORDS,
}


def plan(story_dna_plan: dict) -> dict:
    chapter_count = story_dna_plan.get("recommended_chapter_count", 7)
    curve = []
    for i in range(chapter_count):
        position = i / max(1, chapter_count - 1)
        index = min(len(TARGET_CURVE) - 1, round(position * (len(TARGET_CURVE) - 1)))
        curve.append(TARGET_CURVE[index])
    return {"target_curve": curve, "emotion_labels": TARGET_CURVE}


def detect_emotion(text: str) -> str:
    scores = {label: len(textutil.contains_any(text, words)) for label, words in LEXICON.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "merak"


def evaluate(sections: list[dict], emotion_plan: dict) -> dict:
    target_curve = emotion_plan.get("target_curve", [])
    detected = [detect_emotion(str(s.get("voiceover", ""))) for s in sections]

    matches = 0
    mismatches = []
    for i, (expected, actual) in enumerate(zip(target_curve, detected)):
        if expected == actual:
            matches += 1
        else:
            mismatches.append({
                "section": sections[i].get("name", "") if i < len(sections) else f"#{i}",
                "expected": expected,
                "detected": actual,
            })

    total = max(1, len(target_curve))
    curve_score = round(100 * matches / total)
    return {
        "detected_curve": detected,
        "target_curve": target_curve,
        "mismatches": mismatches,
        "curve_match_score": curve_score,
        "overall_pass": curve_score >= 40,
    }
