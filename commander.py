from __future__ import annotations

import json
import os
import re
import statistics
import sys
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

ROOT = Path("projects")
ROOT.mkdir(exist_ok=True)
API_BASE = "https://www.googleapis.com/youtube/v3"


def slugify(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_text).strip("-").lower()
    return slug or "youtube-arastirma"


def save(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def youtube_get(endpoint: str, params: dict[str, str | int]) -> dict:
    query = urlencode(params)
    with urlopen(f"{API_BASE}/{endpoint}?{query}", timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def parse_duration(value: str) -> int:
    match = re.fullmatch(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", value or "")
    if not match:
        return 0
    hours, minutes, seconds = (int(part or 0) for part in match.groups())
    return hours * 3600 + minutes * 60 + seconds


def compact_number(value: float) -> str:
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"{value / 1_000:.1f}K"
    return str(int(value))


def score_niche(videos: list[dict]) -> tuple[int, str, dict]:
    velocities = [video["views_per_day"] for video in videos]
    views = [video["views"] for video in videos]
    channels = {video["channel"] for video in videos}

    median_velocity = statistics.median(velocities) if velocities else 0
    top_velocity = max(velocities, default=0)
    median_views = statistics.median(views) if views else 0
    channel_diversity = len(channels) / max(len(videos), 1)

    demand = min(45, 45 * (median_velocity / 50_000))
    breakout = min(25, 25 * (top_velocity / 250_000))
    diversity = min(20, 20 * (channel_diversity / 0.7))
    proof = min(10, 10 * (median_views / 500_000))
    final_score = round(demand + breakout + diversity + proof)

    if final_score >= 75:
        decision = "GIR: Güçlü talep ve birden fazla kanalda başarı işareti var."
    elif final_score >= 55:
        decision = "TEST ET: 5-10 video ile format doğrulaması yap."
    else:
        decision = "BEKLET: Talep zayıf veya başarı birkaç kanalda toplanmış."

    metrics = {
        "median_views": round(median_views),
        "median_views_per_day": round(median_velocity),
        "top_views_per_day": round(top_velocity),
        "channel_diversity": round(channel_diversity, 2),
    }
    return final_score, decision, metrics


def main() -> None:
    api_key = os.getenv("YOUTUBE_API_KEY", "").strip()
    if not api_key:
        raise SystemExit(
            "YOUTUBE_API_KEY bulunamadi. Once terminalde API anahtarini tanimla. "
            "README.md icindeki adimlari uygula."
        )

    topic = " ".join(sys.argv[1:]).strip() or input("Arastirilacak nis/konu: ").strip()
    if not topic:
        raise SystemExit("Konu bos olamaz.")

    days = 90
    published_after = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat().replace("+00:00", "Z")

    search_data = youtube_get(
        "search",
        {
            "part": "snippet",
            "q": topic,
            "type": "video",
            "order": "viewCount",
            "publishedAfter": published_after,
            "maxResults": 25,
            "regionCode": "TR",
            "relevanceLanguage": "tr",
            "key": api_key,
        },
    )

    video_ids = [item["id"]["videoId"] for item in search_data.get("items", [])]
    if not video_ids:
        raise SystemExit("Bu konu icin son 90 gunde video bulunamadi.")

    details = youtube_get(
        "videos",
        {
            "part": "snippet,statistics,contentDetails",
            "id": ",".join(video_ids),
            "key": api_key,
        },
    )

    now = datetime.now(timezone.utc)
    videos = []
    for item in details.get("items", []):
        snippet = item.get("snippet", {})
        stats = item.get("statistics", {})
        published = datetime.fromisoformat(snippet["publishedAt"].replace("Z", "+00:00"))
        age_days = max((now - published).total_seconds() / 86400, 1)
        views = int(stats.get("viewCount", 0))
        videos.append(
            {
                "id": item["id"],
                "title": snippet.get("title", ""),
                "channel": snippet.get("channelTitle", ""),
                "published_at": snippet.get("publishedAt", ""),
                "views": views,
                "views_per_day": round(views / age_days),
                "likes": int(stats.get("likeCount", 0)),
                "comments": int(stats.get("commentCount", 0)),
                "duration_seconds": parse_duration(item.get("contentDetails", {}).get("duration", "")),
                "url": f"https://www.youtube.com/watch?v={item['id']}",
            }
        )

    videos.sort(key=lambda item: item["views_per_day"], reverse=True)
    score, decision, metrics = score_niche(videos)

    project_dir = ROOT / slugify(topic)
    project_dir.mkdir(exist_ok=True)

    analysis = {
        "topic": topic,
        "created_at": now.isoformat(),
        "period_days": days,
        "videos_analyzed": len(videos),
        "niche_score": score,
        "decision": decision,
        "metrics": metrics,
        "videos": videos,
    }
    save(project_dir / "analysis.json", json.dumps(analysis, ensure_ascii=False, indent=2))

    rows = []
    for index, video in enumerate(videos[:15], start=1):
        duration = video["duration_seconds"]
        duration_text = f"{duration // 60}:{duration % 60:02d}"
        rows.append(
            f"| {index} | {video['title'].replace('|', '-')} | {video['channel']} | "
            f"{compact_number(video['views'])} | {compact_number(video['views_per_day'])} | "
            f"{duration_text} | [Ac]({video['url']}) |"
        )

    report = f"""# SHP YouTube Nis Raporu

**Konu:** {topic}  
**Donem:** Son {days} gun  
**Analiz edilen video:** {len(videos)}  
**Nis puani:** **{score}/100**  
**Karar:** **{decision}**

## Temel gostergeler

- Medyan goruntulenme: {compact_number(metrics['median_views'])}
- Medyan gunluk izlenme hizi: {compact_number(metrics['median_views_per_day'])}
- En yuksek gunluk izlenme hizi: {compact_number(metrics['top_views_per_day'])}
- Kanal cesitliligi: {metrics['channel_diversity']}

## Son 90 gunun en hizli videolari

| # | Baslik | Kanal | Izlenme | Gunluk hiz | Sure | Video |
|---|---|---|---:|---:|---:|---|
{chr(10).join(rows)}

## Sonraki aksiyon

1. Ilk 5 videonun baslik yapisini ve ilk 30 saniyesini incele.
2. Ayni merak duygusunu kullanan fakat kopya olmayan 10 konu uret.
3. Once 5 video yayinla; otomasyona ancak format dogrulaninca gec.
"""
    save(project_dir / "report.md", report)

    print("\n" + "=" * 60)
    print(f"SHP RAPORU: {topic}")
    print(f"Nis puani: {score}/100")
    print(decision)
    print(f"Rapor: {project_dir / 'report.md'}")
    print("=" * 60)


if __name__ == "__main__":
    main()
