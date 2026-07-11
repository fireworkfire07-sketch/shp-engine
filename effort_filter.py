from __future__ import annotations

import json
from pathlib import Path

ROOT = Path("projects")
DECISION_JSON = ROOT / "ceo-decision" / "analysis.json"
DECISION_MD = ROOT / "ceo-decision" / "report.md"
CHANNEL_JSON = ROOT / "channel-health" / "analysis.json"
COMPETITOR_JSON = ROOT / "competitor-health" / "analysis.json"
BATCH_JSON = ROOT / "batch-ranking.json"


def load(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def clamp(value: float) -> int:
    return max(0, min(100, round(value)))


def main() -> None:
    decision = load(DECISION_JSON, {})
    channel = load(CHANNEL_JSON, {})
    competitor = load(COMPETITOR_JSON, {})
    batch = load(BATCH_JSON, [])

    topic = str(decision.get("topic", ""))
    niche_score = int(decision.get("niche_score", 0) or 0)
    fit_score = int(decision.get("channel_fit_score", 0) or 0)
    channel_score = int(decision.get("channel_health_score", 0) or 0)
    strongest = channel.get("strongest_video") or {}
    own_speed = float(strongest.get("views_per_day", 0) or 0)

    rivals = competitor.get("competitors", []) or []
    rival_proof = 0.0
    rival_best_title = "Veri yok"
    if rivals:
        strongest_rival = max(
            rivals,
            key=lambda item: float((item.get("strongest_video") or {}).get("views_per_day", 0) or 0),
        )
        rival_best = strongest_rival.get("strongest_video") or {}
        rival_proof = float(rival_best.get("views_per_day", 0) or 0)
        rival_best_title = str(rival_best.get("title", "Veri yok"))

    topic_metrics = {}
    for item in batch if isinstance(batch, list) else []:
        if str(item.get("topic", "")) == topic:
            topic_metrics = item.get("metrics", {}) or {}
            break

    median_market_speed = float(topic_metrics.get("median_views_per_day", 0) or 0)
    breakout_speed = float(topic_metrics.get("top_views_per_day", 0) or 0)

    market_proof_score = min(100, median_market_speed / 250)
    breakout_score = min(100, breakout_speed / 2500)
    own_proof_score = min(100, own_speed * 7)
    rival_proof_score = min(100, rival_proof / 500)

    value_score = clamp(
        niche_score * 0.30
        + fit_score * 0.30
        + market_proof_score * 0.15
        + breakout_score * 0.10
        + own_proof_score * 0.10
        + rival_proof_score * 0.05
    )

    reasons: list[str] = []
    if fit_score >= 80:
        reasons.append("Kanal temasına güçlü biçimde uyuyor.")
    elif fit_score < 60:
        reasons.append("Kanal temasına uyumu zayıf.")

    if niche_score >= 55:
        reasons.append("Pazar verisi test için yeterli.")
    elif niche_score < 25:
        reasons.append("Pazar talebi emeği karşılayacak kadar güçlü görünmüyor.")

    if median_market_speed >= 100:
        reasons.append("Benzer videolarda ölçülebilir günlük izlenme talebi var.")
    else:
        reasons.append("Benzer videolarda medyan günlük hız düşük.")

    if own_speed >= 5:
        reasons.append("Kanalın mevcut güçlü videolarıyla performans bağı var.")
    else:
        reasons.append("Kanal içi başarı kanıtı henüz zayıf.")

    if rival_proof > 0:
        reasons.append(f"Rakiplerde çalışan örnek bulundu: {rival_best_title}.")

    missing = decision.get("missing_inputs", []) or []
    if missing:
        verdict = "DUR — VERİ EKSİK"
        action = "BEKLET"
    elif value_score >= 60:
        verdict = "EMEĞİNE DEĞER"
        action = "ÇEK"
    elif value_score >= 40:
        verdict = "SADECE KÜÇÜK TESTE DEĞER"
        action = "TEST ET"
    else:
        verdict = "EMEĞİNE DEĞMEZ"
        action = "DUR"

    original_decision = str(decision.get("decision", "BEKLET"))
    if action == "DUR":
        decision["decision"] = "ÇEKME"
        decision["publish"] = "HAYIR"
    elif action == "TEST ET" and original_decision == "ÇEK":
        decision["decision"] = "TEST ET"
        decision["publish"] = "1 TEST VİDEOSU"

    decision["effort_filter"] = {
        "verdict": verdict,
        "value_score": value_score,
        "action": action,
        "reasons": reasons,
        "signals": {
            "market_median_views_per_day": median_market_speed,
            "market_top_views_per_day": breakout_speed,
            "own_best_views_per_day": own_speed,
            "rival_best_views_per_day": rival_proof,
        },
    }
    decision["effort_verdict"] = verdict
    decision["effort_value_score"] = value_score
    decision["effort_action"] = action

    DECISION_JSON.write_text(json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8")

    current_report = DECISION_MD.read_text(encoding="utf-8") if DECISION_MD.exists() else "# SHP CEO Kararı\n"
    section = f"""

## EMEK FİLTRESİ

# {verdict}

**Emek/Getiri puanı:** {value_score}/100  
**Net aksiyon:** {action}

{chr(10).join(f'- {item}' for item in reasons)}

**SHP emri:** {('Bu videoya odaklan; mevcut adaylar içinde emeğe en çok değen seçenek bu.' if action == 'ÇEK' else 'Enerjini tam üretime harcama; önce daha güçlü aday seç.' if action == 'DUR' else 'Tam üretim yapma; düşük maliyetli tek test hazırla.')}
"""
    marker = "\n## EMEK FİLTRESİ\n"
    if marker in current_report:
        current_report = current_report.split(marker, 1)[0].rstrip()
    DECISION_MD.write_text(current_report + section + "\n", encoding="utf-8")

    print(f"EFFORT_VERDICT={verdict}")
    print(f"EFFORT_VALUE_SCORE={value_score}")
    print(f"EFFORT_ACTION={action}")


if __name__ == "__main__":
    main()
