from __future__ import annotations

import json
import math
import os
import re
import statistics
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

API_BASE = "https://www.googleapis.com/youtube/v3"
ROOT = Path("projects")
OUT = ROOT / "niche-intelligence"
OUT.mkdir(parents=True, exist_ok=True)

BASE_SEEDS = [
    "gizemli bitkiler", "zehirli bitkiler", "şifalı bitkiler", "baharatların tarihi",
    "antik dünyanın bitkileri", "unutulmuş bitkiler", "bitkiler ve imparatorluklar",
    "bitki mitolojisi", "ipek yolu bitkileri", "bitkilerin karanlık tarihi",
]

EXPANSIONS = [
    "tarih", "gizem", "yasak", "savaş", "imparatorluk", "antik", "kadim",
    "zehir", "şifa", "ticaret", "efsane", "unutulmuş", "karanlık gerçekler",
]


def youtube_get(endpoint: str, params: dict) -> dict:
    with urlopen(f"{API_BASE}/{endpoint}?{urlencode(params)}", timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def normalize(text: str) -> str:
    value = unicodedata.normalize("NFKD", text.casefold())
    return "".join(ch for ch in value if not unicodedata.combining(ch))


def load_channel_terms() -> list[str]:
    path = ROOT / "channel-health" / "analysis.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    titles = [str((data.get("channel") or {}).get("title", ""))]
    for video in data.get("top_videos", []) or []:
        titles.append(str(video.get("title", "")))
    words = []
    stop = {"ve", "bir", "bu", "ile", "nasıl", "neden", "gizli", "gizemli", "dünya", "tarihi"}
    for word in re.findall(r"[A-Za-zÇĞİÖŞÜçğıöşü]{4,}", " ".join(titles)):
        if normalize(word) not in stop:
            words.append(word)
    counts: dict[str, int] = {}
    for word in words:
        counts[word] = counts.get(word, 0) + 1
    return [w for w, _ in sorted(counts.items(), key=lambda x: x[1], reverse=True)[:8]]


LEARNING_ENGINE_MEMORY = ROOT / "learning-engine" / "memory.json"

CATEGORY_TO_SEED_WORD = {
    "gizem": "gizem",
    "catismа": "savaş",
    "servet": "imparatorluk",
    "soru": "gizem",
    "saskinlik": "karanlık gerçekler",
}


def load_learning_lessons() -> dict:
    """Real structural lesson from learning_engine.py's persisted history
    (which title trigger category has actually performed best on the
    channel's own published videos) — not available on a channel's first
    run, and never treated as required."""
    if not LEARNING_ENGINE_MEMORY.exists():
        return {}
    try:
        data = json.loads(LEARNING_ENGINE_MEMORY.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data.get("lessons", {}) or {}


def candidate_queries() -> list[str]:
    candidates = set(BASE_SEEDS)
    terms = load_channel_terms()
    for term in terms[:5]:
        candidates.add(f"{term} tarihi")
        candidates.add(f"{term} gizemi")
        candidates.add(f"{term} karanlık tarihi")
    for seed in BASE_SEEDS[:5]:
        for suffix in EXPANSIONS[:5]:
            candidates.add(f"{seed} {suffix}")

    lessons = load_learning_lessons()
    best_category = lessons.get("best_title_trigger_category")
    seed_word = CATEGORY_TO_SEED_WORD.get(best_category)
    if seed_word:
        for seed in BASE_SEEDS:
            candidates.add(f"{seed} {seed_word}")

    return sorted(candidates)[:40]


def fetch_videos(api_key: str, query: str, days: int, max_results: int = 25) -> list[dict]:
    published_after = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat().replace("+00:00", "Z")
    search = youtube_get("search", {
        "part": "snippet", "q": query, "type": "video", "order": "viewCount",
        "publishedAfter": published_after, "maxResults": max_results,
        "regionCode": "TR", "relevanceLanguage": "tr", "key": api_key,
    })
    ids = [x.get("id", {}).get("videoId") for x in search.get("items", [])]
    ids = [x for x in ids if x]
    if not ids:
        return []
    details = youtube_get("videos", {
        "part": "snippet,statistics,contentDetails", "id": ",".join(ids), "key": api_key,
    })
    now = datetime.now(timezone.utc)
    videos = []
    for item in details.get("items", []):
        snippet = item.get("snippet", {})
        stats = item.get("statistics", {})
        published = datetime.fromisoformat(snippet.get("publishedAt", "").replace("Z", "+00:00"))
        age_days = max((now - published).total_seconds() / 86400, 1)
        views = int(stats.get("viewCount", 0) or 0)
        videos.append({
            "id": item.get("id", ""), "title": snippet.get("title", ""),
            "channel": snippet.get("channelTitle", ""), "views": views,
            "views_per_day": round(views / age_days, 2),
            "likes": int(stats.get("likeCount", 0) or 0),
            "comments": int(stats.get("commentCount", 0) or 0),
            "url": f"https://www.youtube.com/watch?v={item.get('id','')}",
        })
    return videos


def score_candidate(query: str, recent: list[dict], mid: list[dict], yearly: list[dict]) -> dict:
    all_videos = {v["id"]: v for group in (recent, mid, yearly) for v in group}.values()
    all_videos = list(all_videos)
    if not all_videos:
        return {"niche": query, "error": "Veri bulunamadı", "final_score": 0}

    speeds = [v["views_per_day"] for v in all_videos]
    recent_speeds = [v["views_per_day"] for v in recent]
    mid_speeds = [v["views_per_day"] for v in mid]
    channels = {v["channel"] for v in all_videos}
    median_speed = statistics.median(speeds) if speeds else 0
    recent_median = statistics.median(recent_speeds) if recent_speeds else 0
    mid_median = statistics.median(mid_speeds) if mid_speeds else 0
    growth_ratio = recent_median / max(mid_median, 1)
    diversity = len(channels) / max(len(all_videos), 1)
    top_speed = max(speeds, default=0)
    breakout_count = sum(1 for x in speeds if x >= max(1000, median_speed * 3))

    demand = min(30, 30 * math.log10(median_speed + 1) / 4)
    momentum = min(20, max(0, growth_ratio) * 10)
    breakout = min(15, breakout_count * 3)
    diversity_score = min(15, diversity * 25)
    evergreen = min(10, len(yearly) / 2.5)
    saturation_penalty = max(0, (1 - diversity) * 15)
    automation = 8 if any(k in normalize(query) for k in ["tarih", "gizem", "antik", "efsane", "karanlik"]) else 5
    final = round(max(0, min(100, demand + momentum + breakout + diversity_score + evergreen + automation - saturation_penalty)))

    if final >= 70:
        decision = "GİR"
    elif final >= 50:
        decision = "TEST ET"
    else:
        decision = "GİRME"

    top = sorted(all_videos, key=lambda x: x["views_per_day"], reverse=True)[:5]
    gap = "Rakip başarısı birkaç kanala sıkışmış; özgün seri fırsatı var." if diversity < 0.35 else "Pazar geniş; farklı açı ve güçlü paketleme gerekli."
    return {
        "niche": query,
        "final_score": final,
        "decision": decision,
        "metrics": {
            "median_views_per_day": round(median_speed, 2),
            "recent_growth_ratio": round(growth_ratio, 2),
            "top_views_per_day": round(top_speed, 2),
            "channel_diversity": round(diversity, 2),
            "videos_analyzed": len(all_videos),
            "breakout_videos": breakout_count,
            "evergreen_score": round(evergreen * 10),
            "competition_score": round((1 - diversity) * 100),
            "automation_score": automation * 10,
            "effort_value_score": final,
        },
        "gap": gap,
        "top_videos": top,
        "first_10_video_ideas": [
            f"{query}: İnsanların Bilmediği 7 Gerçek",
            f"{query}: Bir İmparatorluğu Değiştiren Hikâye",
            f"{query}: Yüzyıllarca Saklanan Sır",
            f"{query}: Yasaklanmasının Gerçek Nedeni",
            f"{query}: Ticaret Yollarını Değiştiren Olay",
            f"{query}: Ölümcül Gerçekler",
            f"{query}: Antik Dünyadaki Kullanımı",
            f"{query}: Mitoloji ve Gerçek Arasındaki Bağ",
            f"{query}: Bugüne Kadar Nasıl Geldi?",
            f"{query}: En Büyük Yanlış Bilinenler",
        ],
    }


def main() -> None:
    api_key = os.getenv("YOUTUBE_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("YOUTUBE_API_KEY secret bulunamadı.")

    candidates = candidate_queries()
    results = []
    for index, query in enumerate(candidates, 1):
        print(f"[{index}/{len(candidates)}] {query}")
        try:
            recent = fetch_videos(api_key, query, 30, 15)
            mid = fetch_videos(api_key, query, 90, 15)
            yearly = fetch_videos(api_key, query, 365, 15)
            results.append(score_candidate(query, recent, mid, yearly))
        except Exception as exc:
            results.append({"niche": query, "error": str(exc), "final_score": 0, "decision": "GİRME"})

    ranked = sorted(results, key=lambda x: x.get("final_score", 0), reverse=True)
    winner = ranked[0] if ranked else None
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "candidates_scanned": len(candidates),
        "winner": winner,
        "top_10": ranked[:10],
        "all_results": ranked,
        "ceo_decision": "Enerjini yalnızca kazanan nişe harca." if winner and winner.get("decision") == "GİR" else "Önce küçük test yap; tam üretime geçme.",
        "limits": [
            "YouTube Data API gerçek RPM/gelir vermez; gelir potansiyeli dolaylı puanlanır.",
            "CTR ve retention için YouTube Analytics OAuth gerekir.",
        ],
    }
    (OUT / "analysis.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = ["# SHP PRO Niş Intelligence Raporu", ""]
    if winner:
        lines += [
            "## CEO SON KARARI", "",
            f"# {winner.get('decision', 'BEKLET')}", "",
            f"**Kazanan niş:** {winner.get('niche', '-')}",
            f"**Toplam puan:** {winner.get('final_score', 0)}/100",
            f"**Efor/Getiri:** {winner.get('metrics', {}).get('effort_value_score', 0)}/100",
            f"**Gap:** {winner.get('gap', '-')}", "",
        ]
    lines += [
        "## En güçlü 10 niş", "",
        "| # | Niş | Puan | Karar | Günlük medyan | Büyüme | Rekabet | Evergreen |",
        "|---:|---|---:|---|---:|---:|---:|---:|",
    ]
    for i, item in enumerate(ranked[:10], 1):
        m = item.get("metrics", {})
        lines.append(
            f"| {i} | {item.get('niche','-')} | {item.get('final_score',0)} | {item.get('decision','-')} | "
            f"{m.get('median_views_per_day','-')} | {m.get('recent_growth_ratio','-')} | "
            f"{m.get('competition_score','-')} | {m.get('evergreen_score','-')} |"
        )
    if winner:
        lines += ["", "## İlk 10 video", ""] + [f"{i}. {idea}" for i, idea in enumerate(winner.get("first_10_video_ideas", []), 1)]
    lines += ["", "## Gerçek sınırlar", "", "- RPM tahmini doğrudan gelir verisi değildir.", "- CTR ve retention için OAuth gerekir."]
    (OUT / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"NICHE_WINNER={winner.get('niche','-') if winner else '-'}")
    print(f"NICHE_SCORE={winner.get('final_score',0) if winner else 0}")
    print(f"REPORT={OUT / 'report.md'}")


if __name__ == "__main__":
    main()
