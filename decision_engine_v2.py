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
    parts = [str(channel_info.get("title", "")), str(channel_info.get("description", ""))]
    strongest = channel.get("strongest_video", {}) or {}
    parts.append(str(strongest.get("title", "")))
    for video in channel.get("top_videos", []) or []:
        parts.append(str(video.get("title", "")))
    return normalize(" ".join(parts))


def topic_fit_score(topic: str, identity_text: str) -> tuple[int, list[str]]:
    normalized_topic = normalize(topic)
    blocked_hits = [key for key in BLOCKED_OFF_THEME_KEYWORDS if normalize(key) in normalized_topic]
    if blocked_hits:
        return 0, [f"Kanal dışı konu engellendi: {', '.join(sorted(blocked_hits))}."]

    theme_hits = [key for key in CHANNEL_THEME_KEYWORDS if normalize(key) in normalized_topic]
    identity_words = set(re.findall(r"[a-z0-9]+", identity_text))
    topic_words = set(re.findall(r"[a-z0-9]+", normalized_topic))
    overlap = identity_words.intersection(topic_words)

    score = 25 + min(55, len(theme_hits) * 20) + min(20, len(overlap) * 5)
    score = min(100, score)

    notes: list[str] = [f"Kanal uyum puanı: {score}/100."]
    if theme_hits:
        notes.append(f"Kanal temasıyla eşleşen kelimeler: {', '.join(sorted(theme_hits)[:5])}.")
    if overlap:
        notes.append(f"Kanal başlıklarıyla ortak kelimeler: {', '.join(sorted(overlap)[:5])}.")
    return score, notes


def choose_topic(batch: list[dict] | None, channel: dict) -> tuple[str, int, list[str], int]:
    fallback_topic = "Bitkilerin Gizli Tarihi"
    if not batch:
        return fallback_topic, 0, ["Niş verisi yok; kanalın sabit teması kullanıldı."], 100

    identity_text = channel_identity(channel)
    ranked: list[tuple[float, int, dict, list[str]]] = []
    for item in batch:
        if item.get("error"):
            continue
        topic = str(item.get("topic", ""))
        niche_score = int(item.get("niche_score", 0) or 0)
        fit_score, fit_notes = topic_fit_score(topic, identity_text)
        if fit_score <= 0:
            continue
        combined = niche_score * 0.65 + fit_score * 0.35
        ranked.append((combined, fit_score, item, fit_notes))

    if not ranked:
        return fallback_topic, 0, [
            "Kanal dışı adayların tamamı elendi.",
            "Güvenli geri dönüş olarak kanalın sabit teması seçildi.",
        ], 100

    ranked.sort(key=lambda row: row[0], reverse=True)
    _, fit_score, best, fit_notes = ranked[0]
    topic = str(best.get("topic", fallback_topic))
    score = int(best.get("niche_score", 0) or 0)
    metrics = best.get("metrics", {}) or {}

    reasons = [f"Niş puanı: {score}/100.", *fit_notes]
    reasons.append(f"Medyan günlük izlenme hızı: {int(metrics.get('median_views_per_day', 0) or 0)}.")
    if int(metrics.get("top_views_per_day", 0) or 0) > 10000:
        reasons.append("Bu konuda patlama yapmış video örneği var.")
    if float(metrics.get("channel_diversity", 0) or 0) >= 0.5:
        reasons.append("Başarı birden fazla kanala yayılmış.")
    return topic, score, reasons, fit_score


def build_video_idea(topic: str, strongest_title: str) -> str:
    normalized = normalize(topic)
    if "baharat" in normalized:
        return "Bir Baharat Uğruna İmparatorluklar Neden Savaştı?"
    if "zehir" in normalized:
        return "Tarihin En Tehlikeli Bitkisi Nasıl Bir Silaha Dönüştü?"
    if "sifali" in normalized:
        return "İnsanlar Bu Bitkinin Gücünü Yüzyıllarca Neden Sakladı?"
    if "antik" in normalized or "kadim" in normalized or "tarih" in normalized:
        return "Bu Bitki Bir İmparatorluğun Kaderini Nasıl Değiştirdi?"
    if "mantar" in normalized:
        return "Bu Mantar Neden Yüzyıllarca Yasaklandı?"
    if strongest_title:
        clean = re.sub(r"\s+", " ", strongest_title).strip()
        return f"{clean} Formatının Devamı: Daha Güçlü Bir Gizem Hikâyesi"
    return "İnsanlık Tarihini Değiştiren En Gizemli Bitki"


def main() -> None:
    channel = load_json(ROOT / "channel-health" / "analysis.json") or {}
    competitor = load_json(ROOT / "competitor-health" / "analysis.json") or {}
    batch = load_json(ROOT / "batch-ranking.json")

    topic, niche_score, reasons, fit_score = choose_topic(batch if isinstance(batch, list) else None, channel)

    channel_score = int(channel.get("health_score", 0) or 0)
    strongest = channel.get("strongest_video") or {}
    strongest_title = str(strongest.get("title", ""))
    own_speed = float(strongest.get("views_per_day", 0) or 0)

    competitors = competitor.get("competitors", []) or []
    rival = competitors[0] if competitors else {}
    rival_title = (rival.get("channel") or {}).get("title", "Rakip verisi yok")
    rival_speed = float(rival.get("median_views_per_day", 0) or 0)
    rival_best = (rival.get("strongest_video") or {}).get("title", "Veri yok")

    missing_inputs = [
        name
        for name, value in {
            "channel-health": channel,
            "competitor-health": competitor,
            "batch-ranking": batch,
        }.items()
        if not value
    ]

    if missing_inputs:
        decision = "BEKLET"
        publish = "HAYIR"
        reasons.append(f"Eksik veri var: {', '.join(missing_inputs)}.")
    elif fit_score < 60:
        decision = "BEKLET"
        publish = "HAYIR"
        reasons.append("Kanal uyumu yeterince güçlü değil.")
    elif niche_score >= 55:
        decision = "ÇEK"
        publish = "EVET"
    elif niche_score >= 25:
        decision = "TEST ET"
        publish = "1 TEST VİDEOSU"
    else:
        decision = "BEKLET"
        publish = "HAYIR"

    if channel_score <= 10:
        reasons.append("Kanal sağlık skoru düşük; aynı anda tek güçlü test videosuna odaklan.")
    if strongest:
        reasons.append(f"Kanalın en hızlı videosu: {strongest_title} ({own_speed:.1f} günlük izlenme).")
    if competitors:
        reasons.append(f"En güçlü karşılaştırılan rakip: {rival_title}; medyan günlük hız {rival_speed:.1f}.")

    confidence = min(
        100,
        round(
            niche_score * 0.40
            + fit_score * 0.35
            + max(channel_score, 1) * 0.10
            + (15 if competitors else 5)
            - len(missing_inputs) * 20
        ),
    )

    video_idea = build_video_idea(topic, strongest_title)
    hook_direction = "İlk 10 saniyede büyük soru, gizli çıkar veya tarihsel tehlike göster; cevabı hemen verme."
    thumbnail_direction = "Tek ana nesne, yüksek kontrast, en fazla 3-4 kelime ve tek güçlü gizem işareti kullan."

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "role": "SHP analizleri birleştirir ve kanal kimliğine uygun tek CEO kararı verir; video üretmez.",
        "decision": decision,
        "publish": publish,
        "topic": topic,
        "video_idea": video_idea,
        "confidence": max(0, confidence),
        "niche_score": niche_score,
        "channel_fit_score": fit_score,
        "channel_health_score": channel_score,
        "reasons": reasons,
        "title_direction": video_idea,
        "hook_direction": hook_direction,
        "thumbnail_direction": thumbnail_direction,
        "competitor_reference": {
            "channel": rival_title,
            "strongest_video": rival_best,
            "instruction": "Başlığı kopyalama; aynı izleyici ihtiyacına kanal temasına uygun özgün açı üret.",
        },
        "missing_inputs": missing_inputs,
    }

    (OUTPUT_DIR / "analysis.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    report = f"""# SHP CEO Kararı v2

## BUGÜNÜN EMRİ

# {decision}

**Video fikri:** {video_idea}  
**Ana tema:** {topic}  
**Yayın kararı:** {publish}  
**Karar güveni:** {max(0, confidence)}/100  
**Kanal uyumu:** {fit_score}/100

## Neden

{chr(10).join(f'- {item}' for item in reasons)}

## Uygulama yönü

- **Başlık:** {video_idea}
- **İlk 30 saniye:** {hook_direction}
- **Thumbnail:** {thumbnail_direction}

## Rakip referansı

- **Kanal:** {rival_title}
- **En güçlü video:** {rival_best}
- **Kural:** Başlığı kopyalama; aynı izleyici ihtiyacına kanal temasına uygun özgün açı üret.

## Sistem durumu

- Kanal sağlık skoru: {channel_score}/100
- Niş puanı: {niche_score}/100
- Kanal uyum puanı: {fit_score}/100
- Eksik girdiler: {', '.join(missing_inputs) if missing_inputs else 'Yok'}

## Gerçek sınırlar

- Public YouTube API CTR, retention ve gelir vermez.
- Veri eksikse karar BEKLET olur; SHP tahmin uydurmaz.
- SHP karar verir; video üretmez veya yayınlamaz.
"""
    (OUTPUT_DIR / "report.md").write_text(report, encoding="utf-8")

    print(f"CEO_DECISION={decision}")
    print(f"CEO_TOPIC={topic}")
    print(f"CEO_VIDEO_IDEA={video_idea}")
    print(f"CEO_CHANNEL_FIT={fit_score}")
    print(f"CEO_CONFIDENCE={max(0, confidence)}")
    print(f"REPORT={OUTPUT_DIR / 'report.md'}")


if __name__ == "__main__":
    main()
