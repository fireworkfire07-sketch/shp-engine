from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("projects")
OUTPUT_DIR = ROOT / "ceo-decision"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

CHANNEL_THEME_KEYWORDS = {
    "bitki", "bitkiler", "botanik", "doğa", "dogal", "ağaç", "agac", "çiçek", "cicek",
    "baharat", "şifalı", "sifali", "zehir", "mantar", "tohum", "yaprak", "kök", "kok",
    "ipek", "böcek", "bocek", "tarçın", "tarcin", "antik", "kadim", "tarih", "gizem",
    "gizli", "efsane", "mitoloji", "anadolu", "roma", "çin", "cin", "mısır", "misir",
    "ticaret", "ipek yolu", "baharat yolu", "doğa tarihi", "doga tarihi",
}

BLOCKED_OFF_THEME_KEYWORDS = {
    "yapay zeka", "ai haber", "teknoloji haber", "finans", "borsa", "kripto", "psikoloji",
    "girişimcilik", "girisimcilik", "başarı hikayesi", "basari hikayesi", "minecraft", "roblox",
    "fortnite", "spor", "futbol", "magazin",
}


def load_json(path: Path) -> dict | list | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def normalize(text: str) -> str:
    lowered = text.casefold()
    normalized = unicodedata.normalize("NFKD", lowered)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def channel_identity(channel: dict) -> str:
    channel_info = channel.get("channel", {}) or {}
    parts = [
        str(channel_info.get("title", "")),
        str(channel_info.get("description", "")),
    ]
    for video in channel.get("top_videos", []) or []:
        parts.append(str(video.get("title", "")))
    return normalize(" ".join(parts))


def topic_fit_score(topic: str, identity_text: str) -> tuple[int, list[str]]:
    normalized_topic = normalize(topic)
    score = 0
    notes: list[str] = []

    theme_hits = [key for key in CHANNEL_THEME_KEYWORDS if normalize(key) in normalized_topic]
    identity_words = set(re.findall(r"[a-z0-9]+", identity_text))
    topic_words = set(re.findall(r"[a-z0-9]+", normalized_topic))
    overlap = identity_words.intersection(topic_words)
    blocked_hits = [key for key in BLOCKED_OFF_THEME_KEYWORDS if normalize(key) in normalized_topic]

    score += min(60, len(theme_hits) * 20)
    score += min(30, len(overlap) * 5)
    score -= len(blocked_hits) * 80

    if theme_hits:
        notes.append(f"Kanal temasıyla eşleşen kelimeler: {', '.join(sorted(theme_hits)[:5])}.")
    if overlap:
        notes.append(f"Kanal başlıklarıyla ortak kelimeler: {', '.join(sorted(overlap)[:5])}.")
    if blocked_hits:
        notes.append(f"Kanal dışı konu işareti: {', '.join(sorted(blocked_hits))}.")

    return score, notes


def choose_topic(batch: list[dict] | None, channel: dict) -> tuple[str, int, list[str], int]:
    if not batch:
        return "Yeni konu seçilemedi", 0, ["Niş karşılaştırma verisi bulunamadı."], 0

    valid = [item for item in batch if not item.get("error")]
    if not valid:
        return "Yeni konu seçilemedi", 0, ["Geçerli niş sonucu bulunamadı."], 0

    identity_text = channel_identity(channel)
    ranked: list[tuple[int, int, dict, list[str]]] = []
    for item in valid:
        topic = str(item.get("topic", "Bilinmeyen konu"))
        niche_score = int(item.get("niche_score", 0) or 0)
        fit_score, fit_notes = topic_fit_score(topic, identity_text)
        combined = niche_score + fit_score
        ranked.append((combined, fit_score, item, fit_notes))

    ranked.sort(key=lambda row: (row[0], row[1], int(row[2].get("niche_score", 0) or 0)), reverse=True)
    combined, fit_score, best, fit_notes = ranked[0]
    topic = str(best.get("topic", "Bilinmeyen konu"))
    score = int(best.get("niche_score", 0) or 0)
    metrics = best.get("metrics", {}) or {}

    reasons = [f"Niş puanı: {score}/100.", f"Kanal uyum puanı: {fit_score}."]
    reasons.extend(fit_notes)
    reasons.append(f"Medyan günlük izlenme hızı: {int(metrics.get('median_views_per_day', 0) or 0)}.")
    if int(metrics.get("top_views_per_day", 0) or 0) > 10000:
        reasons.append("Bu konuda patlama yapmış video örneği var.")
    if float(metrics.get("channel_diversity", 0) or 0) >= 0.5:
        reasons.append("Başarı birden fazla kanala yayılmış.")

    if fit_score <= 0:
        return "Kanal temasıyla uyumlu konu bulunamadı", 0, reasons + ["Mevcut adayların hiçbiri kanal kimliğiyle örtüşmüyor."], fit_score

    return topic, score, reasons, fit_score


def main() -> None:
    channel = load_json(ROOT / "channel-health" / "analysis.json") or {}
    competitor = load_json(ROOT / "competitor-health" / "analysis.json") or {}
    batch = load_json(ROOT / "batch-ranking.json")

    topic, niche_score, reasons, fit_score = choose_topic(batch if isinstance(batch, list) else None, channel)

    channel_score = int(channel.get("health_score", 0) or 0)
    strongest = channel.get("strongest_video") or {}
    own_speed = float(strongest.get("views_per_day", 0) or 0)

    competitors = competitor.get("competitors", []) or []
    rival = competitors[0] if competitors else {}
    rival_title = (rival.get("channel") or {}).get("title", "Rakip verisi yok")
    rival_speed = float(rival.get("median_views_per_day", 0) or 0)
    rival_best = (rival.get("strongest_video") or {}).get("title", "Veri yok")

    confidence = min(
        100,
        round(niche_score * 0.45 + max(fit_score, 0) * 0.25 + max(channel_score, 1) * 0.10 + (20 if competitors else 5)),
    )

    if fit_score <= 0:
        decision = "ÇEKME"
        publish = "HAYIR"
    elif niche_score >= 55:
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
        reasons.append(f"En güçlü karşılaştırılan rakip: {rival_title}; medyan günlük hız {rival_speed:.1f}.")

    title_direction = f"{topic}: güçlü merak + gizem + tarih çatışması"
    hook_direction = "İlk 10 saniyede büyük soru, risk veya kayıp göster; cevabı hemen verme."
    thumbnail_direction = "Tek ana nesne, yüksek kontrast, en fazla 3-4 kelime ve net bir gizem işareti kullan."

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "role": "SHP analizleri birleştirir ve kanal kimliğine uygun tek CEO kararı verir; video üretmez.",
        "decision": decision,
        "publish": publish,
        "topic": topic,
        "confidence": confidence,
        "niche_score": niche_score,
        "channel_fit_score": fit_score,
        "channel_health_score": channel_score,
        "reasons": reasons,
        "title_direction": title_direction,
        "hook_direction": hook_direction,
        "thumbnail_direction": thumbnail_direction,
        "competitor_reference": {
            "channel": rival_title,
            "strongest_video": rival_best,
            "instruction": "Başlığı kopyalama; aynı izleyici ihtiyacına kanal temasına uygun özgün açı üret.",
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

    (OUTPUT_DIR / "analysis.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    report = f"""# SHP CEO Kararı v2

## Bugünün kararı

**{decision}**

**Konu:** {topic}  
**Yayın kararı:** {publish}  
**Karar güveni:** {confidence}/100  
**Kanal uyumu:** {fit_score}

## Neden

{chr(10).join(f'- {item}' for item in reasons)}

## Uygulama yönü

- **Başlık yönü:** {title_direction}
- **İlk 30 saniye:** {hook_direction}
- **Thumbnail yönü:** {thumbnail_direction}

## Rakip referansı

- **Kanal:** {rival_title}
- **En güçlü video:** {rival_best}
- **Kural:** Başlığı kopyalama; aynı izleyici ihtiyacına kanal temasına uygun özgün açı üret.

## Sistem durumu

- Kanal sağlık skoru: {channel_score}/100
- Niş puanı: {niche_score}/100
- Kanal uyum puanı: {fit_score}
- Eksik girdiler: {', '.join(payload['missing_inputs']) if payload['missing_inputs'] else 'Yok'}

## Gerçek sınırlar

- Public YouTube API CTR, retention ve gelir vermez.
- Bu rapor mevcut repo verilerini birleştirir; veri eksikse karar güveni düşer.
- SHP karar verir; video üretmez veya yayınlamaz.
"""
    (OUTPUT_DIR / "report.md").write_text(report, encoding="utf-8")

    print(f"CEO_DECISION={decision}")
    print(f"CEO_TOPIC={topic}")
    print(f"CEO_CHANNEL_FIT={fit_score}")
    print(f"CEO_CONFIDENCE={confidence}")
    print(f"REPORT={OUTPUT_DIR / 'report.md'}")


if __name__ == "__main__":
    main()
