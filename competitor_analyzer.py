from __future__ import annotations

import json
import os
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

from channel_analyzer import (
    fetch_upload_video_ids,
    fetch_video_details,
    health_score,
    parse_channel_input,
    resolve_channel,
)

OUTPUT_DIR = Path("projects/competitor-health")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def compact(value: float) -> str:
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"{value / 1_000:.1f}K"
    return str(round(value, 1))


def analyze_channel(api_key: str, raw_channel: str) -> dict:
    kind, value = parse_channel_input(raw_channel)
    channel = resolve_channel(api_key, kind, value)
    snippet = channel.get("snippet", {})
    stats = channel.get("statistics", {})
    uploads = channel.get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads", "")
    if not uploads:
        raise RuntimeError(f"Uploads playlist bulunamadı: {raw_channel}")

    video_ids = fetch_upload_video_ids(api_key, uploads, limit=50)
    videos = fetch_video_details(api_key, video_ids)
    ranked = sorted(videos, key=lambda item: item["views_per_day"], reverse=True)
    score, reasons = health_score(videos)
    public = [video for video in videos if video.get("privacy_status") == "public"]
    median_speed = statistics.median([video["views_per_day"] for video in public]) if public else 0
    median_engagement = statistics.median([video["engagement_rate"] for video in public]) if public else 0

    return {
        "input": raw_channel,
        "channel": {
            "id": channel.get("id", ""),
            "title": snippet.get("title", ""),
            "subscribers": int(stats.get("subscriberCount", 0) or 0),
            "total_views": int(stats.get("viewCount", 0) or 0),
            "video_count": int(stats.get("videoCount", 0) or 0),
        },
        "health_score": score,
        "health_reasons": reasons,
        "median_views_per_day": round(median_speed, 2),
        "median_engagement_rate": round(median_engagement, 2),
        "videos_analyzed": len(videos),
        "strongest_video": ranked[0] if ranked else None,
        "top_videos": ranked[:10],
    }


def compare(own: dict, rival: dict) -> dict:
    own_speed = own.get("median_views_per_day", 0)
    rival_speed = rival.get("median_views_per_day", 0)
    own_eng = own.get("median_engagement_rate", 0)
    rival_eng = rival.get("median_engagement_rate", 0)

    gaps: list[str] = []
    advantages: list[str] = []

    if rival_speed > own_speed:
        gaps.append(f"Rakibin medyan günlük izlenme hızı daha yüksek: {rival_speed} vs {own_speed}.")
    else:
        advantages.append(f"Medyan günlük izlenme hızında öndesiniz: {own_speed} vs {rival_speed}.")

    if rival_eng > own_eng:
        gaps.append(f"Rakibin medyan etkileşim oranı daha yüksek: %{rival_eng:.2f} vs %{own_eng:.2f}.")
    else:
        advantages.append(f"Medyan etkileşim oranında öndesiniz: %{own_eng:.2f} vs %{rival_eng:.2f}.")

    if rival.get("health_score", 0) > own.get("health_score", 0):
        gaps.append(f"Rakip kanal sağlık skorunda önde: {rival['health_score']} vs {own['health_score']}.")
    else:
        advantages.append(f"Kanal sağlık skorunda öndesiniz: {own['health_score']} vs {rival['health_score']}.")

    strongest = rival.get("strongest_video") or {}
    ceo_action = (
        f"Rakibin en hızlı videosunun konu ve başlık yapısını incele: {strongest.get('title', 'veri yok')}. "
        "Başlığı kopyalama; aynı izleyici ihtiyacına özgün bir açı üret."
    )

    return {
        "competitor": rival["channel"]["title"],
        "gaps": gaps,
        "advantages": advantages,
        "ceo_action": ceo_action,
    }


def main() -> None:
    api_key = os.getenv("YOUTUBE_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("YOUTUBE_API_KEY secret bulunamadı.")

    if len(sys.argv) < 3:
        raise SystemExit("Kullanım: python competitor_analyzer.py <kendi_kanalın> <rakip1,rakip2,...>")

    own_input = sys.argv[1].strip()
    competitor_inputs = [item.strip() for item in sys.argv[2].split(",") if item.strip()]
    if not competitor_inputs:
        raise SystemExit("En az bir rakip kanal gerekli.")

    own = analyze_channel(api_key, own_input)
    competitors = []
    errors = []
    for raw in competitor_inputs:
        try:
            competitors.append(analyze_channel(api_key, raw))
        except Exception as exc:
            errors.append({"input": raw, "error": str(exc)})

    competitors.sort(key=lambda item: item["health_score"], reverse=True)
    comparisons = [compare(own, rival) for rival in competitors]

    result = {
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
        "own_channel": own,
        "competitors": competitors,
        "comparisons": comparisons,
        "errors": errors,
        "limitations": [
            "Public API CTR ve izlenme süresi vermez.",
            "Thumbnail görsel kalitesi ve gerçek retention ayrıca analiz edilmelidir.",
            "Bu modül rakip verisini hazırlar; nihai karar Decision Engine tarafından verilir.",
        ],
    }

    (OUTPUT_DIR / "analysis.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    competitor_rows = []
    for index, rival in enumerate(competitors, start=1):
        strongest = rival.get("strongest_video") or {}
        competitor_rows.append(
            f"| {index} | {rival['channel']['title']} | {compact(rival['channel']['subscribers'])} | "
            f"{rival['health_score']}/100 | {compact(rival['median_views_per_day'])} | "
            f"{strongest.get('title', '-').replace('|', '-')} |"
        )

    comparison_sections = []
    for item in comparisons:
        comparison_sections.extend(
            [
                f"## {item['competitor']}",
                "",
                "### Rakibin üstün olduğu alanlar",
                *(f"- {text}" for text in item["gaps"]),
                "" if item["gaps"] else "- Belirgin üstünlük bulunamadı.",
                "### Bizim avantajlarımız",
                *(f"- {text}" for text in item["advantages"]),
                "" if item["advantages"] else "- Belirgin avantaj bulunamadı.",
                "### CEO aksiyonu",
                f"- {item['ceo_action']}",
                "",
            ]
        )

    report = f"""# SHP Rakip Analizi Raporu

**Kendi kanalımız:** {own['channel']['title']}  
**Kanal sağlık skoru:** {own['health_score']}/100  
**Analiz edilen rakip:** {len(competitors)}

## Rakip sıralaması

| # | Kanal | Abone | Sağlık | Medyan günlük hız | En güçlü video |
|---:|---|---:|---:|---:|---|
{chr(10).join(competitor_rows) if competitor_rows else '| - | Rakip verisi yok | - | - | - | - |'}

{chr(10).join(comparison_sections)}
## Gerçek sınırlar

- Public API CTR ve ortalama izlenme süresini vermez.
- Bu modül thumbnail estetiğini ve transkript kalitesini doğrudan ölçmez.
- Nihai YAP / BEKLET / YAPMA kararı Decision Engine tarafından verilir.
"""
    (OUTPUT_DIR / "report.md").write_text(report, encoding="utf-8")

    print(f"COMPETITORS_ANALYZED={len(competitors)}")
    print(f"REPORT={OUTPUT_DIR / 'report.md'}")


if __name__ == "__main__":
    main()
