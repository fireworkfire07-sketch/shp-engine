"""SHP Video CEO Pro — the final gate on the complete production package.

Script Agent V2's own internal `ceo_reviewer.py` only judges the script
text (curiosity/retention/emotion/originality/fact/psychology). Video CEO
Pro judges everything Script Agent V2 does not: niche fit, channel fit,
thumbnail concept, SEO, monetization/policy risk, production effort,
expected return and series potential — on top of re-checking the script
dimensions at the finished-package level. It is the actual greenlight (or
stop) for production, not a second opinion on prose.

Decisions: ÇEK (produce it) / DÜZELT (one controlled rewrite cycle sent
back to Script Agent V2) / DUR (stop, do not produce) / BEKLET — VERİ EKSİK
(required upstream data missing).

Reuses Script Agent V2's own engines to run the DÜZELT rewrite — it does
not reimplement scriptwriting, it re-drives the real pipeline with the
concrete corrections attached as feedback.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from script_agent_v2 import context as context_module
from script_agent_v2 import outputs as sa_outputs
from script_agent_v2 import textutil
from script_agent_v2.engines import (
    audience_engine,
    ceo_reviewer as script_ceo_reviewer,
    curiosity_engine,
    doctor,
    emotion_engine,
    fact_engine,
    generator,
    memory_engine,
    originality_engine,
    psychology_engine,
    retention_engine,
    story_dna_engine,
    visual_engine,
)
from script_agent_v2.llm import LLM
from story_score import score_title

ROOT = Path("projects")
OUTPUT_DIR = ROOT / "video-ceo"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

APPROVE_SCORE = 80
REVISE_FLOOR = 55

# Real, narrow YouTube monetization/policy risk terms. Not exhaustive by
# design — a hard blocker list is meant to catch unambiguous cases, not
# replace human judgment.
POLICY_RISK_KEYWORDS = [
    "intihar", "kendine zarar verme", "silah yapımı", "bomba yapımı",
    "uyuşturucu üretimi", "nefret söylemi", "çocuk istismarı",
    "tehlikeli meydan okuma", "yasa dışı bahis",
]

WEIGHTS = {
    "niche_fit": 0.08,
    "channel_fit": 0.08,
    "title": 0.06,
    "thumbnail": 0.05,
    "hook_3s": 0.07,
    "hook_10s": 0.05,
    "hook_30s": 0.04,
    "story_structure": 0.05,
    "curiosity": 0.08,
    "retention": 0.08,
    "emotion": 0.05,
    "fact": 0.07,
    "originality": 0.07,
    "visual_potential": 0.04,
    "seo": 0.05,
    "production_effort": 0.03,
    "expected_return": 0.05,
    "series_potential": 0.05,
}


def load_json(path: Path, default=None):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


# ---------------------------------------------------------------------------
# Component scores
# ---------------------------------------------------------------------------

def _hook_checkpoint_score(evaluations: dict, seconds: int) -> tuple[int, str]:
    checkpoints = (evaluations.get("retention") or {}).get("checkpoints", [])
    for checkpoint in checkpoints:
        if checkpoint.get("checkpoint_seconds") == seconds:
            risk = checkpoint.get("drop_risk", "orta")
            return {"düşük": 90, "orta": 55, "yüksek": 20}.get(risk, 50), risk
    return 50, "bilinmiyor"


def _thumbnail_score(thumbnail: dict) -> int:
    concept = str(thumbnail.get("concept", "")).strip()
    if not concept:
        return 0
    if thumbnail.get("originality_risk"):
        return 40
    return 80


def _story_structure_score(script: dict, evaluations: dict) -> int:
    sections = script.get("sections", [])
    section_score = 100 if len(sections) >= 5 else max(0, len(sections) * 15)
    emotion_score = (evaluations.get("emotion") or {}).get("curve_match_score", 0)
    return round((section_score + emotion_score) / 2)


def _visual_potential_score(storyboard: list) -> int:
    if not storyboard:
        return 0
    complete = sum(
        1 for scene in storyboard
        if str(scene.get("visual_idea", "")).strip()
        and str(scene.get("camera_idea", "")).strip()
        and str(scene.get("scene_idea", "")).strip()
    )
    return round(100 * complete / len(storyboard))


def _seo_score(youtube_upload: dict, growth: dict) -> int:
    trending = [k.lower() for k in (growth.get("trending_keywords") or [])]
    if not trending:
        return 60  # no market signal to grade against — neutral, not a penalty
    haystack = " ".join([
        str(youtube_upload.get("title", "")),
        str(youtube_upload.get("description", "")),
        " ".join(youtube_upload.get("tags", []) or []),
    ]).lower()
    hits = sum(1 for keyword in trending if keyword in haystack)
    return round(100 * hits / len(trending))


def _production_effort_score(handoff: dict) -> int:
    minutes = handoff.get("target_duration_minutes") or 0
    if minutes <= 0:
        return 50
    if minutes <= 8:
        return 100
    if minutes <= 15:
        return 70
    return 40


def _series_potential_score(niche: dict) -> int:
    winner = niche.get("winner") or {}
    metrics = winner.get("metrics") or {}
    evergreen = metrics.get("evergreen_score")
    if evergreen is None:
        return 50  # not enough niche data to grade — neutral, not a penalty
    return round(max(0, min(100, evergreen)))


def scan_policy_risk(script: dict, youtube_upload: dict) -> list[str]:
    haystack = " ".join(
        [str(script.get("title", "")), str(script.get("hook", "")), str(youtube_upload.get("description", ""))]
        + [str(section.get("voiceover", "")) for section in script.get("sections", [])]
    )
    return textutil.contains_any(haystack, POLICY_RISK_KEYWORDS)


def evaluate_production_package(
    script_payload: dict, ceo_decision: dict, niche: dict, growth: dict,
    thumbnail: dict, storyboard: list, youtube_upload: dict, handoff: dict,
) -> dict:
    script = script_payload.get("script", {})
    evaluations = script_payload.get("evaluations", {})

    hook_3s_score, hook_3s_risk = _hook_checkpoint_score(evaluations, 3)
    hook_10s_score, hook_10s_risk = _hook_checkpoint_score(evaluations, 10)
    hook_30s_score, hook_30s_risk = _hook_checkpoint_score(evaluations, 30)

    scores = {
        "niche_fit": ceo_decision.get("niche_score", 0),
        "channel_fit": ceo_decision.get("channel_fit_score", 0),
        "title": score_title(script.get("title", ""))["score"],
        "thumbnail": _thumbnail_score(thumbnail),
        "hook_3s": hook_3s_score,
        "hook_10s": hook_10s_score,
        "hook_30s": hook_30s_score,
        "story_structure": _story_structure_score(script, evaluations),
        "curiosity": (evaluations.get("curiosity") or {}).get("overall_score", 0),
        "retention": (evaluations.get("retention") or {}).get("overall_score", 0),
        "emotion": (evaluations.get("emotion") or {}).get("curve_match_score", 0),
        "fact": (evaluations.get("fact") or {}).get("overall_score", 0),
        "originality": (evaluations.get("originality") or {}).get("overall_score", 0),
        "visual_potential": _visual_potential_score(storyboard),
        "seo": _seo_score(youtube_upload, growth),
        "production_effort": _production_effort_score(handoff),
        "expected_return": ceo_decision.get("effort_value_score", 0),
        "series_potential": _series_potential_score(niche),
    }

    total_weight = sum(WEIGHTS.values())
    video_ceo_score = round(sum(scores[dim] * weight for dim, weight in WEIGHTS.items()) / total_weight)

    policy_hits = scan_policy_risk(script, youtube_upload)

    weak_dims = {dim: value for dim, value in scores.items() if value < REVISE_FLOOR}

    return {
        "component_scores": scores,
        "video_ceo_score": video_ceo_score,
        "policy_risk_hits": policy_hits,
        "weak_dimensions": weak_dims,
        "hook_risk": {"3s": hook_3s_risk, "10s": hook_10s_risk, "30s": hook_30s_risk},
        "script_agent_status": script_payload.get("status", "UNKNOWN"),
        "script_agent_ceo_score": (script_payload.get("ceo_review") or {}).get("ceo_score", 0),
        "source_mode": script.get("source_mode", "unknown"),
    }


def build_corrections(evaluation: dict) -> list[str]:
    corrections = []
    scores = evaluation["component_scores"]
    if scores["hook_3s"] < 60:
        corrections.append("İlk 3 saniye izleyiciyi yeterince tutmuyor; daha güçlü, doğrudan bir açılış gerekli.")
    if scores["hook_10s"] < 60:
        corrections.append("İlk 10 saniyede izleyiciye kalmak için somut bir sebep verilmiyor.")
    if scores["hook_30s"] < 60:
        corrections.append("30. saniyeye kadar konu netleşmiyor veya ilk merak açılmıyor.")
    if scores["thumbnail"] < 60:
        corrections.append("Thumbnail konsepti zayıf, boş veya özgünlük riski taşıyor; tek net gizem işareti olan bir konsept üret.")
    if scores["seo"] < 50:
        corrections.append("Başlık/açıklama/etiketler trend anahtar kelimeleri yeterince kullanmıyor.")
    if scores["fact"] < 70:
        corrections.append("Doğrulanmamış iddialar var; kanıt defterindeki bilgilerle netleştir veya temkinli ifade et.")
    if scores["originality"] < 70:
        corrections.append("Özgünlük riski taşıyan, rakip/referans metne çok yakın ifadeler var.")
    if scores["curiosity"] < 60:
        corrections.append("Merak boşlukları yetersiz; her bölümde yeni bir bilgi boşluğu açılmalı.")
    if scores["retention"] < 60:
        corrections.append("İzlenme süresi kritik noktalarında (3sn/10sn/30sn/1dk/3dk) düşüş riski yüksek.")
    if scores["story_structure"] < 60:
        corrections.append("Bölüm sayısı veya duygu eğrisi (merak->şaşkınlık->gerilim->keşif->tatmin) hedefi tutmuyor.")
    if not corrections:
        corrections.append("Genel kalite eşiği (80/100) altında; en zayıf boyutları güçlendir.")
    return corrections


# ---------------------------------------------------------------------------
# DÜZELT rewrite cycle — re-drives the real Script Agent V2 engines with
# Video CEO Pro's corrections as feedback. Exactly one cycle: this function
# is only ever called once per run (see main()).
# ---------------------------------------------------------------------------

def run_rewrite_cycle(script_payload: dict, corrections: list[str]) -> dict:
    context_dict = script_payload["context"]
    knowledge = script_payload["knowledge"]
    story_dna_plan = script_payload["story_dna_plan"]
    memory = load_json(context_module.MEMORY_PATH, {"runs": [], "best_hooks": [], "best_endings": [], "best_thumbnails": []})

    llm = LLM()
    psychology_plan = psychology_engine.plan(context_dict)
    audience_profile = audience_engine.run(context_dict)
    curiosity_plan = curiosity_engine.plan(story_dna_plan)
    retention_plan = retention_engine.plan(context_dict)
    emotion_plan = emotion_engine.plan(story_dna_plan)
    originality_plan = originality_engine.plan(context_dict)
    visual_plan = visual_engine.plan(context_dict)
    fact_ledger = fact_engine.build_ledger(knowledge)
    memory_hints = memory_engine.hints_for_generation(memory)

    script = generator.generate(
        context_dict, llm, knowledge, story_dna_plan, psychology_plan, audience_profile,
        curiosity_plan, retention_plan, emotion_plan, originality_plan,
        fact_ledger, memory_hints, feedback=corrections,
    )
    script = doctor.review_and_fix(
        script, llm, curiosity_plan, retention_plan, emotion_plan, originality_plan, fact_ledger,
    )

    sections = script.get("sections", [])
    evaluations = {
        "curiosity": curiosity_engine.evaluate(sections, curiosity_plan),
        "retention": retention_engine.evaluate(sections, retention_plan),
        "emotion": emotion_engine.evaluate(sections, emotion_plan),
        "originality": originality_engine.evaluate(sections, originality_plan, llm),
        "fact": fact_engine.evaluate(sections, fact_ledger),
    }
    ceo_review = script_ceo_reviewer.review(script, evaluations)
    visuals = visual_engine.generate(sections, knowledge, visual_plan, llm)

    updated_memory = memory_engine.record(memory, script, ceo_review, evaluations, story_dna_plan)
    memory_engine.save(updated_memory, context_module.MEMORY_PATH)

    attempts = script_payload.get("attempts", 1) + 1
    rejected_history = list(script_payload.get("rejected_history", []))
    rejected_history.append({
        "attempt": attempts,
        "ceo_score": ceo_review["ceo_score"],
        "reasons": ["Video CEO Pro DÜZELT kararı sonrası tek kontrollü yeniden yazım."] + corrections,
    })

    sa_outputs.write_all(
        script, context_dict, knowledge, story_dna_plan, evaluations, ceo_review,
        visuals, attempts, rejected_history,
    )

    return {
        "agent": "SHP Script Agent V2",
        "status": ceo_review["decision"],
        "attempts": attempts,
        "context": context_dict,
        "knowledge": knowledge,
        "story_dna_plan": story_dna_plan,
        "script": script,
        "evaluations": evaluations,
        "ceo_review": ceo_review,
        "rejected_history": rejected_history,
    }


# ---------------------------------------------------------------------------

def main() -> None:
    script_payload = load_json(ROOT / "script-agent" / "script.json")
    ceo_decision = load_json(ROOT / "ceo-decision" / "analysis.json")

    if not script_payload or not ceo_decision:
        missing = [name for name, value in {"script-agent/script.json": script_payload, "ceo-decision/analysis.json": ceo_decision}.items() if not value]
        decision = "BEKLET — VERİ EKSİK"
        payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "decision": decision,
            "missing_inputs": missing,
            "reasons": [f"Gerekli girdi eksik: {', '.join(missing)}."],
        }
        _write(payload, rewrite_happened=False)
        print(f"VIDEO_CEO_DECISION={decision}")
        return

    niche = load_json(ROOT / "niche-intelligence" / "analysis.json", {})
    growth = load_json(ROOT / "growth-advisor" / "analysis.json", {})
    thumbnail = load_json(ROOT / "script-agent" / "thumbnail.json", {})
    storyboard = load_json(ROOT / "script-agent" / "storyboard.json", [])
    youtube_upload = load_json(ROOT / "script-agent" / "youtube_upload.json", {})
    handoff = load_json(ROOT / "script-agent" / "video_engine_handoff.json", {})

    evaluation = evaluate_production_package(
        script_payload, ceo_decision, niche, growth, thumbnail, storyboard, youtube_upload, handoff,
    )

    rewrite_happened = False
    rewrite_blocked_reason = ""

    if evaluation["policy_risk_hits"]:
        decision = "DUR"
        reasons = [f"Politika/marka güvenliği riski tespit edildi: {', '.join(evaluation['policy_risk_hits'])}."]
    elif evaluation["video_ceo_score"] >= APPROVE_SCORE and evaluation["script_agent_status"] == "APPROVE":
        decision = "ÇEK"
        reasons = ["Üretim paketi tüm eşikleri karşılıyor."]
    elif evaluation["video_ceo_score"] >= REVISE_FLOOR:
        corrections = build_corrections(evaluation)
        if evaluation["source_mode"] == "rule_based_fallback":
            decision = "DUR"
            rewrite_blocked_reason = "GROQ_API_KEY yok; kural tabanlı taslak yeniden yazılarak iyileştirilemez, üretim durduruldu."
            reasons = corrections + [rewrite_blocked_reason]
        else:
            rewritten_payload = run_rewrite_cycle(script_payload, corrections)
            rewrite_happened = True
            youtube_upload = load_json(ROOT / "script-agent" / "youtube_upload.json", {})
            thumbnail = load_json(ROOT / "script-agent" / "thumbnail.json", {})
            storyboard = load_json(ROOT / "script-agent" / "storyboard.json", [])
            handoff = load_json(ROOT / "script-agent" / "video_engine_handoff.json", {})
            evaluation = evaluate_production_package(
                rewritten_payload, ceo_decision, niche, growth, thumbnail, storyboard, youtube_upload, handoff,
            )
            script_payload = rewritten_payload
            if evaluation["policy_risk_hits"]:
                decision = "DUR"
                reasons = [f"Yeniden yazımdan sonra politika riski hâlâ mevcut: {', '.join(evaluation['policy_risk_hits'])}."]
            elif evaluation["video_ceo_score"] >= APPROVE_SCORE and evaluation["script_agent_status"] == "APPROVE":
                decision = "ÇEK"
                reasons = ["Tek kontrollü yeniden yazım sonrası paket eşikleri karşılıyor."]
            else:
                decision = "DUR"
                reasons = ["Tek kontrollü yeniden yazım hakkı kullanıldı; paket hâlâ eşiklerin altında.", *build_corrections(evaluation)]
    else:
        decision = "DUR"
        reasons = ["Üretim paketi genel kalite eşiğinin (55/100) belirgin biçimde altında.", *build_corrections(evaluation)]

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "decision": decision,
        "video_ceo_score": evaluation["video_ceo_score"],
        "approve_threshold": APPROVE_SCORE,
        "revise_floor": REVISE_FLOOR,
        "component_scores": evaluation["component_scores"],
        "policy_risk_hits": evaluation["policy_risk_hits"],
        "hook_risk": evaluation["hook_risk"],
        "script_agent_status": evaluation["script_agent_status"],
        "script_agent_ceo_score": evaluation["script_agent_ceo_score"],
        "rewrite_cycle_used": rewrite_happened,
        "title": script_payload.get("script", {}).get("title", ""),
        "reasons": reasons,
        "missing_inputs": [],
    }
    _write(payload, rewrite_happened)
    print(f"VIDEO_CEO_DECISION={decision}")
    print(f"VIDEO_CEO_SCORE={evaluation['video_ceo_score']}")
    print(f"VIDEO_CEO_REWRITE_USED={rewrite_happened}")


def _write(payload: dict, rewrite_happened: bool) -> None:
    (OUTPUT_DIR / "analysis.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# SHP Video CEO Pro Kararı",
        "",
        f"# {payload['decision']}",
        "",
        f"**Başlık:** {payload.get('title', '-')}",
        f"**Video CEO puanı:** {payload.get('video_ceo_score', '-')}/100 (ÇEK eşiği: {payload.get('approve_threshold', '-')}, DÜZELT tabanı: {payload.get('revise_floor', '-')})",
        f"**Script Agent V2 durumu:** {payload.get('script_agent_status', '-')} ({payload.get('script_agent_ceo_score', '-')}/100)",
        f"**Yeniden yazım döngüsü kullanıldı mı:** {'Evet' if rewrite_happened else 'Hayır'}",
        "",
        "## Gerekçe",
        "",
        *[f"- {reason}" for reason in payload.get("reasons", [])],
        "",
    ]
    if payload.get("component_scores"):
        lines += ["## Boyut puanları", "", "| Boyut | Puan |", "|---|---:|"]
        lines += [f"| {dim} | {score} |" for dim, score in payload["component_scores"].items()]
        lines.append("")
    if payload.get("policy_risk_hits"):
        lines += ["## Politika riski", "", *[f"- {hit}" for hit in payload["policy_risk_hits"]], ""]
    lines += [
        "## Gerçek sınırlar",
        "",
        "- Bu karar Script Agent V2'nin ürettiği gerçek metin ve gerçek YouTube/niş verisine dayanır; hiçbir puan uydurulmaz.",
        "- DÜZELT en fazla tek kontrollü yeniden yazım döngüsü tetikler; ikinci tur otomatik denenmez.",
        "- GROQ_API_KEY yoksa kural tabanlı taslak yeniden yazılarak iyileştirilemez; bu durumda DÜZELT yerine dürüstçe DUR verilir.",
    ]
    (OUTPUT_DIR / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
