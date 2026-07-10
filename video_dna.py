from __future__ import annotations

import json
import os
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import urlopen

from story_score import score_title

API_BASE = "https://www.googleapis.com/youtube/v3"
OUTPUT_ROOT = Path("projects/video-dna")
OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

HOOK_TRIGGERS = {
    "soru": ["neden", "nasil", "kim", "ne oldu", "gercek mi", "hic dusundun"],
    "gizem": ["gizli", "gizem", "sir", "sakli", "bilinmeyen", "kimse bilmiyor"],
    "tehlike": ["olum", "oldur", "zehir", "yasak", "savas", "lanet", "tehlike"],
    "servet": ["milyon", "milyar", "servet", "altin", "krallik", "imparatorluk"],
    "ters_kose": ["ama", "aslinda", "fakat", "gercekte", "beklenmedik"],
}


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", text.lower()).strip()


def youtube_get(endpoint: str, params: dict[str, str]) -> dict:
    with urlopen(f"{API_BASE}/{endpoint}?{urlencode(params)}", timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def video_id_from_input(value: str) -> str:
    value = value.strip()
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", value):
        return value

    parsed = urlparse(value)
    host = parsed.netloc.lower().replace("www.", "")
    if host == "youtu.be":
        candidate = parsed.path.strip("/").split("/")[0]
    elif host in {"youtube.com", "m.youtube.com", "music.youtube.com"}:
        if parsed.path == "/watch":
            candidate = parse_qs(parsed.query).get("v", [""])[0]
        elif parsed.path.startswith(("/shorts/", "/embed/", "/live/")):
            candidate = parsed.path.strip("/").split("/")[1]
        else:
            candidate = ""
    else:
        candidate = ""

    if not re.fullmatch(r"[A-Za-z0-9_-]{11}", candidate):
        raise SystemExit("Gecerli bir YouTube video URL'si veya 11 karakterli video ID gir.")
    return candidate


def parse_duration_seconds(value: str) -> int:
    match = re.fullmatch(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", value or "")
    if not match:
        return 0
    hours, minutes, seconds = (int(part or 0) for part in match.groups())
    return hours * 3600 + minutes * 60 + seconds


def compact(value: float) -> str:
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"{value / 1_000:.1f}K"
    return str(round(value, 1))


def classify_format(duration_seconds: int) -> str:
    if duration_seconds <= 180:
        return "Shorts / kisa video"
    if duration_seconds <= 600:
        return "Kisa-orta video"
    if duration_seconds <= 1200:
        return "Uzun video"
    return "Cok uzun video"


def performance_score(views_per_day: float, engagement_rate: float, title_score: int, hook_score: int | None) -> int:
    velocity = min(40, views_per_day / 5000 * 40)
    engagement = min(20, engagement_rate / 8 * 20)
    title = title_score * 0.25
    hook = (hook_score or 0) * 0.15
    return round(min(100, velocity + engagement + title + hook))


def fetch_transcript(video_id: str) -> tuple[list[dict], str | None]:
    try:
        from youtube_transcript_api import YouTubeTranscriptApi

        try:
            fetched = YouTubeTranscriptApi().fetch(video_id, languages=["tr", "en"])
            rows = [
                {"text": item.text, "start": float(item.start), "duration": float(item.duration)}
                for item in fetched
            ]
            return rows, None
        except AttributeError:
            rows = YouTubeTranscriptApi.get_transcript(video_id, languages=["tr", "en"])
            return rows, None
    except Exception as exc:
        return [], f"Transkript alinamadi: {type(exc).__name__}: {exc}"


def analyze_hook(transcript: list[dict]) -> dict | None:
    first_30 = [row for row in transcript if float(row.get("start", 0)) < 30]
    if not first_30:
        return None

    text = " ".join(str(row.get("text", "")) for row in first_30).strip()
    normalized = normalize(text)
    hits: dict[str, list[str]] = {}
    score = 20

    for category, words in HOOK_TRIGGERS.items():
        found = [word for word in words if word in normalized]
        hits[category] = found
        score += min(16, len(found) * 8)

    if "?" in text:
        score += 10
    word_count = len(text.split())
    if 35 <= word_count <= 95:
        score += 10
    elif word_count < 15:
        score -= 10

    if any(phrase in normalized for phrase in ["merhaba", "kanalima hos geldiniz", "bugun sizlere"]):
        score -= 20

    score = max(0, min(100, score))
    if score >= 80:
        verdict = "ZEHIRLI HOOK: Ilk 30 saniye merak ve gerilim aciyor."
    elif score >= 60:
        verdict = "GUCLU HOOK: Izleyiciyi tutacak ogeler var."
    elif score >= 40:
        verdict = "ORTA HOOK: Bilgi var ama acik dongu zayif."
    else:
        verdict = "ZAYIF HOOK: Giris yavas veya ansiklopedi gibi."

    return {
        "score": score,
        "verdict": verdict,
        "text": text,
        "word_count": word_count,
        "trigger_hits": hits,
    }


def main() -> None:
    api_key = os.getenv("YOUTUBE_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("YOUTUBE_API_KEY secret bulunamadi.")

    raw_input = " ".join(sys.argv[1:]).strip()
    if not raw_input:
        raise SystemExit("Video URL'si gerekli.")

    video_id = video_id_from_input(raw_input)
    data = youtube_get(
        "videos",
        {
            "part": "snippet,statistics,contentDetails,status",
            "id": video_id,
            "key": api_key,
        },
    )
    items = data.get("items", [])
    if not items:
        raise SystemExit("Video bulunamadi veya herkese acik degil.")

    item = items[0]
    snippet = item.get("snippet", {})
    stats = item.get("statistics", {})
    details = item.get("contentDetails", {})

    title = snippet.get("title", "")
    published_at = datetime.fromisoformat(snippet["publishedAt"].replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)
    age_days = max((now - published_at).total_seconds() / 86400, 1)
    views = int(stats.get("viewCount", 0))
    likes = int(stats.get("likeCount", 0))
    comments = int(stats.get("commentCount", 0))
    views_per_day = views / age_days
    engagement_rate = ((likes + comments) / views * 100) if views else 0
    duration_seconds = parse_duration_seconds(details.get("duration", ""))
    title_dna = score_title(title)

    transcript, transcript_error = fetch_transcript(video_id)
    hook_dna = analyze_hook(transcript)
    dna_score = performance_score(
        views_per_day,
        engagement_rate,
        title_dna["score"],
        hook_dna["score"] if hook_dna else None,
    )

    thumbnails = snippet.get("thumbnails", {})
    thumbnail_url = (
        thumbnails.get("maxres", {}).get("url")
        or thumbnails.get("standard", {}).get("url")
        or thumbnails.get("high", {}).get("url")
        or ""
    )

    result = {
        "video_id": video_id,
        "url": f"https://www.youtube.com/watch?v={video_id}",
        "analyzed_at": now.isoformat(),
        "title": title,
        "channel": snippet.get("channelTitle", ""),
        "published_at": snippet.get("publishedAt", ""),
        "description_preview": snippet.get("description", "")[:500],
        "thumbnail_url": thumbnail_url,
        "duration_seconds": duration_seconds,
        "format": classify_format(duration_seconds),
        "views": views,
        "likes": likes,
        "comments": comments,
        "views_per_day": round(views_per_day, 2),
        "engagement_rate": round(engagement_rate, 2),
        "title_dna": title_dna,
        "transcript_available": bool(transcript),
        "transcript_error": transcript_error,
        "transcript_preview": " ".join(row.get("text", "") for row in transcript[:20])[:1500],
        "hook_dna": hook_dna,
        "video_dna_score": dna_score,
        "limitations": [
            "YouTube Data API izleyici tutma grafigini vermez.",
            "Hook skoru transkriptin ilk 30 saniyesindeki dil kaliplarina dayanan sezgisel bir skordur.",
            "Thumbnail gorsel icerik analizi henuz yapilmaz.",
        ],
    }

    output_dir = OUTPUT_ROOT / video_id
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "analysis.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    if transcript:
        (output_dir / "transcript.json").write_text(
            json.dumps(transcript, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    trigger_lines = []
    for category, hits in title_dna["trigger_hits"].items():
        trigger_lines.append(f"- {category}: {', '.join(hits) if hits else 'yok'}")

    hook_lines = []
    if hook_dna:
        for category, hits in hook_dna["trigger_hits"].items():
            hook_lines.append(f"- {category}: {', '.join(hits) if hits else 'yok'}")
        hook_section = f"""## Ilk 30 saniye Hook DNA

**Hook skoru:** **{hook_dna['score']}/100**  
**Karar:** {hook_dna['verdict']}

> {hook_dna['text']}

{chr(10).join(hook_lines)}
"""
    else:
        hook_section = f"""## Ilk 30 saniye Hook DNA

Hook analiz edilemedi. {transcript_error or 'Transkript bulunamadi.'}
"""

    minutes, seconds = divmod(duration_seconds, 60)
    report = f"""# SHP Video DNA Raporu

![Thumbnail]({thumbnail_url})

**Video:** [{title}](https://www.youtube.com/watch?v={video_id})  
**Kanal:** {snippet.get('channelTitle', '')}  
**Format:** {classify_format(duration_seconds)}  
**Sure:** {minutes}:{seconds:02d}  

## DNA skoru

**Genel Video DNA:** **{dna_score}/100**  
**Baslik merak skoru:** **{title_dna['score']}/100**  
**Karar:** {title_dna['verdict']}

## Gercek performans

- Izlenme: {compact(views)}
- Gunluk izlenme hizi: {compact(views_per_day)}
- Begeni: {compact(likes)}
- Yorum: {compact(comments)}
- Etkilesim orani: %{engagement_rate:.2f}

## Baslik DNA

{chr(10).join(trigger_lines)}
- Zayif kelimeler: {', '.join(title_dna['weak_hits']) if title_dna['weak_hits'] else 'yok'}

{hook_section}

## SHP yorumu

- Baslik skoru yuksek, gunluk hiz dusukse paket guclu fakat konu veya dagitim zayif olabilir.
- Gunluk hiz yuksek, baslik skoru dusukse konu gucludur; daha keskin baslikla buyume sansi vardir.
- Hook skoru dusukse ilk 30 saniyede selamlama ve genel bilgi yerine soru, tehlike veya acik dongu gerekir.

## Sinirlar

- YouTube Data API izleyici tutma grafigini vermez.
- Transkript kapaliysa Hook DNA uretilmez.
- Thumbnail raporda gorunur; yuz, renk ve obje analizi henuz yapilmaz.
"""
    (output_dir / "report.md").write_text(report, encoding="utf-8")

    print(f"VIDEO_DNA_SCORE={dna_score}")
    print(f"TITLE_SCORE={title_dna['score']}")
    print(f"HOOK_SCORE={hook_dna['score'] if hook_dna else 'N/A'}")
    print(f"TRANSCRIPT_AVAILABLE={bool(transcript)}")
    print(f"REPORT={output_dir / 'report.md'}")


if __name__ == "__main__":
    main()
