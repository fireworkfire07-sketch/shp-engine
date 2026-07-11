from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("projects")
OUT = ROOT / "growth-advisor"
OUT.mkdir(parents=True, exist_ok=True)


def load_json(path: Path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def words(text: str) -> list[str]:
    stop = {"ve", "ile", "bir", "bu", "ne", "nasıl", "neden", "için", "mi", "mı", "mu", "mü", "the", "and", "of"}
    items = re.findall(r"[A-Za-zÇĞİÖŞÜçğıöşü0-9]+", text.lower())
    return [w for w in items if len(w) >= 4 and w not in stop]


def main() -> None:
    channel = load_json(ROOT / "channel-health" / "analysis.json") or {}
    competitors = load_json(ROOT / "competitor-health" / "analysis.json") or {}
    ceo = load_json(ROOT / "ceo-decision" / "analysis.json") or {}

    own_top = channel.get("top_videos", []) or []
    rival_channels = competitors.get("competitors", []) or []
    rival_top = []
    for rival in rival_channels:
        rival_top.extend(rival.get("top_videos", []) or [])

    all_titles = [v.get("title", "") for v in own_top + rival_top]
    keyword_counts = Counter()
    for title in all_titles:
        keyword_counts.update(words(title))

    trending_keywords = [w for w, _ in keyword_counts.most_common(12)]
    video_idea = str(ceo.get("video_idea", "")).strip() or "Kanal temasına uygun yeni video fikri"
    decision = str(ceo.get("decision", "BEKLET"))

    top_publish_hours = []
    for video in own_top + rival_top:
        raw = str(video.get("published_at", ""))
        try:
            hour = datetime.fromisoformat(raw.replace("Z", "+00:00")).hour
            top_publish_hours.append(hour)
        except Exception:
            pass
    if top_publish_hours:
        hour_counts = Counter(top_publish_hours)
        best_hours = [h for h, _ in hour_counts.most_common(3)]
        timing = ", ".join(f"{h:02d}:00 UTC" for h in sorted(best_hours))
        timing_note = "Başarılı örneklerin yayın saatlerinden türetildi."
    else:
        timing = "19:00–22:00 Türkiye saati"
        timing_note = "Kanal verisi yetersiz olduğu için güvenli genel aralık kullanıldı."

    hashtags = []
    for token in words(video_idea) + trending_keywords:
        tag = "#" + token.replace("ı", "i").replace("ğ", "g").replace("ş", "s").replace("ö", "o").replace("ü", "u").replace("ç", "c")
        if tag not in hashtags:
            hashtags.append(tag)
        if len(hashtags) >= 10:
            break

    hook = f"İlk 3 saniye: ‘{video_idea}’ fikrinin en şaşırtıcı sonucunu göster ve cevabı verme."
    retention = [
        "İlk 3 saniyede tek güçlü soru veya şok bilgi kullan.",
        "İlk 30 saniyede giriş yapma; doğrudan çatışmayı göster.",
        "Her 20–30 saniyede yeni bilgi, görsel veya soru ekle.",
        "Videonun ortasında yeni bir sır veya ters köşe aç.",
        "Finalde baştaki soruyu net cevapla ve sonraki videoya merak bırak.",
    ]
    engagement = [
        "Videonun ortasında tek net soru sor.",
        "Son 20 saniyede izleyiciden yorumda seçim yapmasını iste.",
        "Genel ‘abone ol’ yerine videonun konusuna bağlı çağrı kullan.",
    ]

    if decision in {"ÇEK", "TEST ET"}:
        verdict = "EMEĞİNE DEĞER"
    elif decision == "BEKLET":
        verdict = "SADECE KÜÇÜK TESTE DEĞER"
    else:
        verdict = "EMEĞİNE DEĞMEZ"

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "verdict": verdict,
        "video_idea": video_idea,
        "trending_keywords": trending_keywords,
        "first_3_seconds": hook,
        "retention_plan": retention,
        "engagement_plan": engagement,
        "recommended_publish_time": timing,
        "timing_note": timing_note,
        "hashtags": hashtags,
        "limits": [
            "Public YouTube API gerçek keşfet dağıtımını, retention ve CTR verisini göstermez.",
            "Yayın saati önerisi başarılı videoların yayın saatlerinden veya güvenli genel aralıktan türetilir.",
            "Video URL verilirse ayrı Video DNA analizi ilk 30 saniyeyi daha ayrıntılı inceler.",
        ],
    }

    (OUT / "analysis.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    report = f"""# SHP Keşfet ve Büyüme Planı

## CEO kararı

# {verdict}

**Video:** {video_idea}

## İlk 3 saniye

- {hook}

## İzlenme süresi planı

{chr(10).join(f'- {x}' for x in retention)}

## Etkileşim planı

{chr(10).join(f'- {x}' for x in engagement)}

## Yayın zamanı

- **Öneri:** {timing}
- {timing_note}

## Anahtar kelimeler

{', '.join(trending_keywords) if trending_keywords else 'Yeterli veri yok.'}

## Hashtagler

{' '.join(hashtags) if hashtags else 'Yeterli veri yok.'}

## Gerçek sınırlar

{chr(10).join(f'- {x}' for x in payload['limits'])}
"""
    (OUT / "report.md").write_text(report, encoding="utf-8")
    print(f"GROWTH_VERDICT={verdict}")
    print(f"GROWTH_REPORT={OUT / 'report.md'}")


if __name__ == "__main__":
    main()
