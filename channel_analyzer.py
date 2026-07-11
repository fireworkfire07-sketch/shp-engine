from __future__ import annotations

import json
import os
import re
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import urlopen

API_BASE = "https://www.googleapis.com/youtube/v3"
OUTPUT_DIR = Path("projects/channel-health")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def youtube_get(endpoint: str, params: dict[str, str | int]) -> dict:
    with urlopen(f"{API_BASE}/{endpoint}?{urlencode(params)}", timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def compact(value: float) -> str:
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"{value / 1_000:.1f}K"
    return str(round(value, 1))


def parse_channel_input(value: str) -> tuple[str, str]:
    value = value.strip()
    if re.fullmatch(r"UC[A-Za-z0-9_-]{22}", value):
        return "id", value
    if value.startswith("@"):
        return "handle", value[1:]

    parsed = urlparse(value)
    host = parsed.netloc.lower().replace("www.", "")
    if host not in {"youtube.com", "m.youtube.com"}:
        raise SystemExit("Geçerli bir YouTube kanal URL'si, @handle veya channel ID gir.")

    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) >= 2 and parts[0] == "channel":
        return "id", parts[1]
    if parts and parts[0].startswith("@"):
        return "handle", parts[0][1:]

    query_id = parse_qs(parsed.query).get("channel_id", [""])[0]
    if query_id:
        return "id", query_id

    raise SystemExit("Kanal URL'si çözülemedi. @handle veya /channel/UC... bağlantısı kullan.")


def resolve_channel(api_key: str, kind: str, value: str) -> dict:
    params: dict[str, str] = {
        "part": "snippet,statistics,contentDetails",
        "key": api_key,
    }
    if kind == "id":
        params["id"] = value
    else:
        params["forHandle"] = value

    data = youtube_get("channels", params)
    items = data.get("items", [])
    if not items:
        raise SystemExit("Kanal bulunamadı veya YouTube API bu handle'ı çözemedi.")
    return items[0]


def fetch_upload_video_ids(api_key: str, playlist_id: str, limit: int = 50) -> list[str]:
    ids: list[str] = []
    token = ""
    while len(ids) < limit:
        params: dict[str, str | int] = {
            "part": "contentDetails",
            "playlistId": playlist_id,
            "maxResults": min(50, limit - len(ids)),
            "key": api_key,
        }
        if token:
            params["pageToken"] = token
        data = youtube_get("playlistItems", params)
        ids.extend(
            item.get("contentDetails", {}).get("videoId", "")
            for item in data.get("items", [])
        )
        ids = [video_id for video_id in ids if video_id]
        token = data.get("nextPageToken", "")
        if not token:
            break
    return ids[:limit]


def fetch_video_details(api_key: str, video_ids: list[str]) -> list[dict]:
    videos: list[dict] = []
    now = datetime.now(timezone.utc)
    for start in range(0, len(video_ids), 50):
        batch = video_ids[start : start + 50]
        data = youtube_get(
            "videos",
            {
                "part": "snippet,statistics,contentDetails,status",
                "id": ",".join(batch),
                "key": api_key,
            },
        )
        for item in data.get("items", []):
            snippet = item.get("snippet", {})
            stats = item.get("statistics", {})
            published_raw = snippet.get("publishedAt", "")
            if not published_raw:
                continue
            published = datetime.fromisoformat(published_raw.replace("Z", "+00:00"))
            age_days = max((now - published).total_seconds() / 86400, 1)
            views = int(stats.get("viewCount", 0) or 0)
            likes = int(stats.get("likeCount", 0) or 0)
            comments = int(stats.get("commentCount", 0) or 0)
            videos.append(
                {
                    "id": item["id"],
                    "title": snippet.get("title", ""),
                    "published_at": published_raw,
                    "views": views,
                    "likes": likes,
                    "comments": comments,
                    "views_per_day": round(views / age_days, 2),
                    "engagement_rate": round(((likes + comments) / views * 100) if views else 0, 2),
                    "privacy_status": item.get("status", {}).get("privacyStatus", "unknown"),
                    "url": f"https://www.youtube.com/watch?v={item['id']}",
                }
            )
    return videos


def health_score(videos: list[dict]) -> tuple[int, list[str]]:
    public = [video for video in videos if video["privacy_status"] == "public"]
    if not public:
        return 0, ["Herkese açık video bulunamadı."]

    speeds = [video["views_per_day"] for video in public]
    engagements = [video["engagement_rate"] for video in public]
    recent = public[:10]

    median_speed = statistics.median(speeds)
    top_speed = max(speeds)
    median_engagement = statistics.median(engagements)
    recent_median = statistics.median([video["views_per_day"] for video in recent]) if recent else 0

    score = 0.0
    score += min(35, median_speed / 100 * 35)
    score += min(25, top_speed / 1000 * 25)
    score += min(20, median_engagement / 5 * 20)
    score += min(20, recent_median / 150 * 20)
    final = round(min(100, score))

    reasons: list[str] = []
    reasons.append(f"Medyan günlük izlenme hızı: {compact(median_speed)}")
    reasons.append(f"En güçlü günlük izlenme hızı: {compact(top_speed)}")
    reasons.append(f"Medyan etkileşim oranı: %{median_engagement:.2f}")
    reasons.append(f"Son 10 videonun medyan günlük hızı: {compact(recent_median)}")
    return final, reasons


def main() -> None:
    api_key = os.getenv("YOUTUBE_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("YOUTUBE_API_KEY secret bulunamadı.")

    raw = " ".join(sys.argv[1:]).strip()
    if not raw:
        raise SystemExit("Kanal URL'si, @handle veya channel ID gerekli.")

    kind, value = parse_channel_input(raw)
    channel = resolve_channel(api_key, kind, value)
    snippet = channel.get("snippet", {})
    stats = channel.get("statistics", {})
    uploads = channel.get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads", "")
    if not uploads:
        raise SystemExit("Kanalın uploads playlist bilgisi alınamadı.")

    video_ids = fetch_upload_video_ids(api_key, uploads, limit=50)
    videos = fetch_video_details(api_key, video_ids)
    videos.sort(key=lambda item: item["published_at"], reverse=True)

    ranked = sorted(videos, key=lambda item: item["views_per_day"], reverse=True)
    strongest = ranked[0] if ranked else None
    weakest = ranked[-1] if ranked else None
    score, reasons = health_score(videos)

    result = {
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
        "channel": {
            "id": channel.get("id", ""),
            "title": snippet.get("title", ""),
            "description": snippet.get("description", "")[:500],
            "published_at": snippet.get("publishedAt", ""),
            "subscribers": int(stats.get("subscriberCount", 0) or 0),
            "total_views": int(stats.get("viewCount", 0) or 0),
            "video_count": int(stats.get("videoCount", 0) or 0),
        },
        "health_score": score,
        "health_reasons": reasons,
        "videos_analyzed": len(videos),
        "strongest_video": strongest,
        "weakest_video": weakest,
        "top_videos": ranked[:10],
        "bottom_videos": list(reversed(ranked[-10:])),
        "limitations": [
            "Public YouTube Data API; CTR ve izlenme süresi vermez.",
            "CTR, retention ve gelir için ileride YouTube Analytics OAuth gerekir.",
            "Bu modül karar vermez; kanal verisini Decision Engine'e hazırlar.",
        ],
    }

    (OUTPUT_DIR / "analysis.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    top_rows = []
    for index, video in enumerate(ranked[:10], start=1):
        top_rows.append(
            f"| {index} | {video['title'].replace('|', '-')} | {compact(video['views'])} | "
            f"{compact(video['views_per_day'])} | %{video['engagement_rate']:.2f} | [Aç]({video['url']}) |"
        )

    report = f"""# SHP Kanal Sağlığı Raporu

**Kanal:** {snippet.get('title', '')}  
**Abone:** {compact(int(stats.get('subscriberCount', 0) or 0))}  
**Toplam görüntülenme:** {compact(int(stats.get('viewCount', 0) or 0))}  
**Toplam video:** {stats.get('videoCount', 0)}  
**Analiz edilen son video:** {len(videos)}  
**Kanal sağlık skoru:** **{score}/100**

## Sağlık gerekçeleri

{chr(10).join(f'- {reason}' for reason in reasons)}

## En güçlü video

{f"**[{strongest['title']}]({strongest['url']})** — günlük {compact(strongest['views_per_day'])} izlenme" if strongest else 'Video bulunamadı.'}

## En zayıf video

{f"**[{weakest['title']}]({weakest['url']})** — günlük {compact(weakest['views_per_day'])} izlenme" if weakest else 'Video bulunamadı.'}

## En güçlü 10 video

| # | Başlık | İzlenme | Günlük hız | Etkileşim | Video |
|---:|---|---:|---:|---:|---|
{chr(10).join(top_rows)}

## Gerçek sınırlar

- Public API, CTR ve ortalama izlenme süresini vermez.
- Bu değerler için YouTube Analytics OAuth bağlantısı gereklidir.
- Bu modül yalnızca kanal verisini toplar; CEO kararı Decision Engine tarafından verilir.
"""
    (OUTPUT_DIR / "report.md").write_text(report, encoding="utf-8")

    print(f"CHANNEL_HEALTH_SCORE={score}")
    print(f"REPORT={OUTPUT_DIR / 'report.md'}")


if __name__ == "__main__":
    main()
