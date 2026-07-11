from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("projects")
OUTPUT_DIR = ROOT / "ceo-decision"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def load_json(path: Path) -> dict | list | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def choose_topic(batch: list[dict] | None) -> tuple[str, int, list[str]]:
    if not batch:
        return "Yeni konu seçilemedi", 0, ["Niş karşılaştırma verisi bulunamadı."]

    valid = [item for item in batch if not item.get("error")]
    if not valid:
        return "Yeni konu seçilemedi", 0, ["Geçerli niş sonucu bulunamadı."]

    best = max(valid, key=lambda item: int(item.get("niche_score", 0) or 0))
    topic = str(best.get("topic", "Bilinmeyen konu"))
    score = int(best.get("niche_score", 0) or 0)
    metrics = best.get("metrics", {}) or {}

    reasons = [f"Niş puanı: {score}/100."]
    reasons.append(
        f"Medyan günlük izlenme hızı: {int(metrics.get('median_views_per_day', 0) or 0)}."
    )
    if int(metrics.get("top_views_per_day", 0) or 0) > 10000:
        reasons.append("Bu konuda patlama yapmış video örneği var.")
    if float(metrics.get("channel_diversity", 0) or 0) >= 0.5:
        reasons.append("Başarı birden fazla kanala yayılmış.")
    return topic, score, reasons


def main() -> None:
    channel = load_json(ROOT / "channel-health" / "analysis.json") or {}
    competitor = load_json(ROOT / "competitor-health" / "analysis.json") or {}
    batch = load_json(ROOT / "batch-ranking.json")

    topic, niche_score, reasons = choose_topic(batch if isinstance(batch, list) else None)

    channel_score = int(channel.get("health_score", 0) or 0)
    strongest = channel.get("strongest_video") or {}
    own_speed = float(strongest.get("views_per_day", 0) or 0)

    competitors = competitor.get("competitors", []) or []
    rival = competitors[0] if competitors else {}
    rival_title = (rival.get("channel") or {}).get("title", "Rakip verisi yok")
    rival_speed = float(rival.get("median_views_per_day", 0) or 0)
    rival_best = (rival.get("strongest_video") or {}).get("title", "Veri yok")

    confidence = min(100, round(niche_score * 0.55 + max(channel_score, 1) * 0.15 + (30 if competitors else 10)))

    if niche_score >= 55:
        decision = "ÇEK"
        publish = "EVET"
    elif niche_score >= 25:
        decision = "BEKLET"
        publish = "TEST VİDEOSU HAZIRLA"
    else:
        decision = "ÇEKME"
        publish = "HAYIR"

    if channel_score <= 10:
        reasons.append("Kanal sağlık skoru düşük; tek güçlü test videosuna odaklan.")
    if strongest:
        reasons.append(
            f"Kanalın mevcut en hızlı videosu: {strongest.get('title', 'Veri yok')} "
            f"({own_speed:.1f} günlük izlenme)."
        )
    if competitors:
        reasons.append(
            f"En güçlü karşılaştırılan rakip: {rival_title}; medyan günlük hız {rival_speed:.1f}."
        )

    title_direction = f"{topic}: güçlü merak + gizem + tarih çatışması"
    hook_direction = (
        "İlk 10 saniyede büyük soru, risk veya kayıp göster; cevabı hemen verme."
    )
    thumbnail_direction = (
        "Tek ana nesne, yüksek kontrast, en fazla 3-4 kelime ve net bir gizem işareti kullan."
    )

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "role": "SHP analizleri birleştirir ve tek CEO kararı verir; video üretmez.",
        "decision": decision,
        "publish": publish,
        "topic": topic,
        "confidence": confidence,
        "niche_score": niche_score,
        "channel_health_score": channel_score,
        "reasons": reasons,
        "title_direction": title_direction,
        "hook_direction": hook_direction,
        "thumbnail_direction": thumbnail_direction,
        "competitor_reference": {
            "channel": rival_title,
            "strongest_video": rival_best,
            "instruction": "Başlığı kopyalama; aynı izleyici ihtiyacına özgün açı üret.",
        },
        "missing_inputs": [
            name
            for name, value in {
                "channel-health": channel,
                "competitor-health": competitor,
                "batch-ranking": batch,
            }.items()
            if not value
        ],
    }

    (OUTPUT_DIR / "analysis.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    report = f"""# SHP CEO Kararı v2

## Bugünün kararı

**{decision}**

**Konu:** {topic}  
**Yayın kararı:** {publish}  
**Karar güveni:** {confidence}/100

## Neden

{chr(10).join(f'- {item}' for item in reasons)}

## Uygulama yönü

- **Başlık yönü:** {title_direction}
- **İlk 30 saniye:** {hook_direction}
- **Thumbnail yönü:** {thumbnail_direction}

## Rakip referansı

- **Kanal:** {rival_title}
- **En güçlü video:** {rival_best}
- **Kural:** Başlığı kopyalama; aynı izleyici ihtiyacına özgün açı üret.

## Sistem durumu

- Kanal sağlık skoru: {channel_score}/100
- Niş puanı: {niche_score}/100
- Eksik girdiler: {', '.join(payload['missing_inputs']) if payload['missing_inputs'] else 'Yok'}

## Gerçek sınırlar

- Public YouTube API CTR, retention ve gelir vermez.
- Bu rapor mevcut repo verilerini birleştirir; veri eksikse karar güveni düşer.
- SHP karar verir; video üretmez veya yayınlamaz.
"""
    (OUTPUT_DIR / "report.md").write_text(report, encoding="utf-8")

    print(f"CEO_DECISION={decision}")
    print(f"CEO_TOPIC={topic}")
    print(f"CEO_CONFIDENCE={confidence}")
    print(f"REPORT={OUTPUT_DIR / 'report.md'}")


if __name__ == "__main__":
    main()
