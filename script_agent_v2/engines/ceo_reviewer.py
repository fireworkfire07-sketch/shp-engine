"""14. CEO REVIEWER

Final gate. Combines every engine's evaluation into one composite score and
asks the only question that matters: "If I were the CEO, would I invest six
hours producing this video?" If the answer is no, the script is REJECTED
and sent back through Script Generator + Script Doctor for another attempt.
"""

from __future__ import annotations

from datetime import datetime, timezone

from script_agent_v2.engines import psychology_engine
from story_score import score_title

APPROVAL_THRESHOLD = 85
HARD_FLOORS = {
    "curiosity": 30,
    "retention": 25,
    "originality": 40,
}

WEIGHTS = {
    "curiosity": 0.22,
    "retention": 0.22,
    "emotion": 0.14,
    "originality": 0.14,
    "fact": 0.14,
    "psychology": 0.14,
}


def review(script: dict, evaluations: dict) -> dict:
    curiosity_score = evaluations["curiosity"]["overall_score"]
    retention_score = evaluations["retention"]["overall_score"]
    emotion_score = evaluations["emotion"]["curve_match_score"]
    originality_score = evaluations["originality"]["overall_score"]
    fact_score = evaluations["fact"]["overall_score"]

    hook_psych = psychology_engine.score(str(script.get("hook", "")))
    title_score = score_title(str(script.get("title", "")))["score"]
    psychology_score = round((hook_psych["average"] + title_score) / 2)

    ceo_score = round(
        curiosity_score * WEIGHTS["curiosity"]
        + retention_score * WEIGHTS["retention"]
        + emotion_score * WEIGHTS["emotion"]
        + originality_score * WEIGHTS["originality"]
        + fact_score * WEIGHTS["fact"]
        + psychology_score * WEIGHTS["psychology"]
    )

    floor_violations = []
    if curiosity_score < HARD_FLOORS["curiosity"]:
        floor_violations.append(f"Merak puanı taban çizgisinin altında ({curiosity_score}/{HARD_FLOORS['curiosity']}).")
    if retention_score < HARD_FLOORS["retention"]:
        floor_violations.append(f"İzlenme süresi puanı taban çizgisinin altında ({retention_score}/{HARD_FLOORS['retention']}).")
    if originality_score < HARD_FLOORS["originality"]:
        floor_violations.append(f"Özgünlük riski çok yüksek ({originality_score}/{HARD_FLOORS['originality']}).")
    if evaluations["retention"]["checkpoints"] and evaluations["retention"]["checkpoints"][0]["drop_risk"] == "yüksek":
        floor_violations.append("İlk 3 saniye izleyiciyi tutmuyor.")

    reasons = []
    if evaluations["curiosity"]["weak_sections"]:
        reasons.append(f"Zayıf merak bölümleri: {', '.join(evaluations['curiosity']['weak_sections'])}.")
    if evaluations["retention"]["weak_checkpoints"]:
        reasons.append(f"Riskli izlenme noktaları: {', '.join(evaluations['retention']['weak_checkpoints'])}.")
    if evaluations["emotion"]["mismatches"]:
        reasons.append(f"Duygu eğrisi hedefi tutmuyor ({len(evaluations['emotion']['mismatches'])} bölümde).")
    if evaluations["originality"]["flagged_sentences"]:
        reasons.append(f"{len(evaluations['originality']['flagged_sentences'])} cümlede özgünlük riski tespit edildi.")
    if evaluations["fact"]["unverified_claim_count"]:
        reasons.append(f"{evaluations['fact']['unverified_claim_count']} doğrulanmamış iddia var.")

    decision = "REJECT" if (floor_violations or ceo_score < APPROVAL_THRESHOLD) else "APPROVE"

    if decision == "APPROVE":
        verdict_text = (
            "CEO olsam bu videoyu üretmek için altı saat harcardım. "
            "İlk saniyeden finale kadar merak, duygu ve kanıt dengesi tutuyor."
        )
    else:
        verdict_text = (
            "CEO olsam bu haliyle altı saat üretim süresi harcamazdım. "
            "Önce aşağıdaki sorunlar çözülmeli."
        )

    return {
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "decision": decision,
        "ceo_score": ceo_score,
        "approval_threshold": APPROVAL_THRESHOLD,
        "component_scores": {
            "curiosity": curiosity_score,
            "retention": retention_score,
            "emotion": emotion_score,
            "originality": originality_score,
            "fact": fact_score,
            "psychology": psychology_score,
        },
        "floor_violations": floor_violations,
        "reasons": reasons,
        "verdict_text": verdict_text,
        "question": "CEO olsaydım bu videoyu üretmek için altı saat harcar mıydım?",
    }
