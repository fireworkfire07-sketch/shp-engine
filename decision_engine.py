from __future__ import annotations

import json
from pathlib import Path

ROOT = Path("projects")
INPUT = ROOT / "batch-ranking.json"
OUTPUT_JSON = ROOT / "decision-report.json"
OUTPUT_MD = ROOT / "decision-report.md"


def classify(score: int) -> str:
    if score >= 55:
        return "YAP"
    if score >= 25:
        return "BEKLET"
    return "YAPMA"


def reason(item: dict) -> list[str]:
    score = int(item.get("niche_score", 0) or 0)
    metrics = item.get("metrics", {}) or {}
    median_speed = int(metrics.get("median_views_per_day", 0) or 0)
    top_speed = int(metrics.get("top_views_per_day", 0) or 0)
    diversity = float(metrics.get("channel_diversity", 0) or 0)

    reasons: list[str] = []
    if score >= 55:
        reasons.append("Niş puanı test üretimi için yeterli.")
    elif score >= 25:
        reasons.append("Potansiyel var fakat veri güçlü karar için yetersiz.")
    else:
        reasons.append("Talep ve rekabet verisi şu an zayıf.")

    if median_speed >= 1000:
        reasons.append("Medyan günlük izlenme hızı güçlü.")
    elif median_speed >= 100:
        reasons.append("Medyan günlük izlenme hızı orta seviyede.")
    else:
        reasons.append("Medyan günlük izlenme hızı düşük.")

    if top_speed >= 10000:
        reasons.append("Patlama yapmış örnek video var.")
    if diversity >= 0.5:
        reasons.append("Başarı birden fazla kanala yayılmış.")
    elif diversity < 0.2:
        reasons.append("Başarı az sayıda kanalda toplanmış.")

    return reasons


def main() -> None:
    if not INPUT.exists():
        raise SystemExit("projects/batch-ranking.json bulunamadı. Önce niş karşılaştırmasını çalıştır.")

    ranked = json.loads(INPUT.read_text(encoding="utf-8"))
    decisions = []

    for item in ranked:
        if item.get("error"):
            decisions.append({
                "topic": item.get("topic", "Bilinmeyen"),
                "decision": "BEKLET",
                "score": 0,
                "reasons": [f"Analiz hatası: {item['error']}"],
            })
            continue

        score = int(item.get("niche_score", 0) or 0)
        decisions.append({
            "topic": item.get("topic", "Bilinmeyen"),
            "decision": classify(score),
            "score": score,
            "reasons": reason(item),
            "report": item.get("report", ""),
        })

    order = {"YAP": 0, "BEKLET": 1, "YAPMA": 2}
    decisions.sort(key=lambda x: (order[x["decision"]], -x["score"]))

    payload = {
        "ceo_role": "SHP karar verir; üretim yapmaz.",
        "decisions": decisions,
        "top_choice": next((d for d in decisions if d["decision"] == "YAP"), decisions[0] if decisions else None),
    }
    OUTPUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# SHP CEO Karar Raporu",
        "",
        "**SHP rolü:** Veriyi analiz eder, karar verir, üretim yapmaz.",
        "",
    ]

    for decision_name in ("YAP", "BEKLET", "YAPMA"):
        lines.extend([f"## {decision_name}", ""])
        group = [d for d in decisions if d["decision"] == decision_name]
        if not group:
            lines.extend(["Bu grupta konu yok.", ""])
            continue
        for item in group:
            lines.append(f"### {item['topic']} — {item['score']}/100")
            for text in item["reasons"]:
                lines.append(f"- {text}")
            lines.append("")

    top = payload["top_choice"]
    if top:
        lines.extend([
            "## Bugünün CEO kararı",
            "",
            f"**Öncelik:** {top['topic']}",
            f"**Karar:** {top['decision']}",
            "",
        ])

    OUTPUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"CEO_DECISION_REPORT={OUTPUT_MD}")


if __name__ == "__main__":
    main()
