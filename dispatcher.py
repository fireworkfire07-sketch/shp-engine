from __future__ import annotations

import json
import os
import re
import unicodedata
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("projects")
CHANNELS_FILE = Path("channels.json")
LOG_FILE = ROOT / "dispatch-log.json"
GITHUB_API = "https://api.github.com"
MIN_SCORE = 75

# Meta/aggregate project folders are not niche-topic reports and must never be dispatched.
META_PROJECT_DIRS = {
    "ceo-decision", "channel-health", "competitor-health",
    "niche-intelligence", "growth-advisor", "script-agent", "video-dna",
}

# Small TR -> EN concept dictionary used to translate the winning niche's
# top-video vocabulary into an English angle, since every target channel
# publishes in English.
TR_EN_CONCEPTS = {
    "bitki": "plant", "bitkiler": "plants", "agac": "tree", "agacinin": "tree",
    "baharat": "spice", "zehir": "poison", "zehirli": "poisonous", "sifali": "healing",
    "mantar": "mushroom", "tohum": "seed", "yaprak": "leaf", "kok": "root",
    "cicek": "flower", "doga": "nature", "dogal": "natural", "antik": "ancient",
    "kadim": "ancient", "tarih": "history", "tarihi": "history", "gizem": "mystery",
    "gizemli": "mystery", "gizli": "secret", "efsane": "legend", "ipek": "silk",
    "zengin": "wealth", "zenginlik": "wealth", "para": "money", "servet": "fortune",
    "yatirim": "investment", "borsa": "market", "finans": "finance", "bereket": "abundance",
    "psikoloji": "psychology", "yasam": "life", "hayat": "life", "insan": "human",
    "gercek": "truth", "gercekler": "truths", "sir": "secret", "sirlar": "secrets",
    "iliski": "relationship", "mutluluk": "happiness", "basari": "success",
    "itiraf": "confession", "davranis": "behavior", "zihin": "mind",
}

STOPWORDS = {
    "bir", "bu", "ve", "ile", "icin", "gibi", "daha", "cok", "en", "ne", "nasil",
    "neden", "mi", "mu", "de", "da", "the", "a", "of", "to", "and", "in", "on",
}

# One template list per target channel so generated angles match each channel's tone.
ANGLE_TEMPLATES = {
    "AITUBE2": [
        "why nobody warns you about {c}",
        "the {c} secret the wealthy never explain out loud",
        "the ancient {c} rule that still builds fortunes today",
        "why the poor misunderstand {c} completely",
        "the hidden discipline behind {c} schools never teach",
    ],
    "secret-history-plants": [
        "the hidden history of {c} nobody was taught",
        "how {c} secretly changed an empire's fate",
        "why {c} was hidden from ordinary people for centuries",
        "the dangerous secret behind {c}",
        "the forgotten ritual tied to {c}",
    ],
    "Nobody-Tells-You": [
        "nobody tells you what {c} really costs you",
        "the {c} truth everyone discovers too late",
        "why {c} quietly ruins more lives than people admit",
        "the uncomfortable math behind {c}",
        "what {c} does to you that no one warns about",
    ],
}


def normalize(text: str) -> str:
    lowered = text.casefold()
    decomposed = unicodedata.normalize("NFKD", lowered)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def load_json(path: Path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def load_channels() -> dict:
    data = load_json(CHANNELS_FILE)
    if not data:
        raise SystemExit("channels.json bulunamadi veya bozuk.")
    return data


def is_niche_report(data) -> bool:
    return (
        isinstance(data, dict)
        and isinstance(data.get("videos"), list)
        and isinstance(data.get("niche_score"), (int, float))
        and isinstance(data.get("topic"), str)
    )


def find_qualifying_projects() -> list[tuple[Path, dict]]:
    found = []
    if not ROOT.exists():
        return found
    for project_dir in sorted(ROOT.iterdir()):
        if not project_dir.is_dir() or project_dir.name in META_PROJECT_DIRS:
            continue
        data = load_json(project_dir / "analysis.json")
        if not is_niche_report(data):
            continue
        if float(data.get("niche_score", 0)) < MIN_SCORE:
            continue
        found.append((project_dir, data))
    return found


def extract_concepts(topic: str, videos: list[dict], limit: int = 5) -> list[str]:
    text_parts = [topic] + [str(v.get("title", "")) for v in videos[:8]]
    words = re.findall(r"[a-z0-9]+", normalize(" ".join(text_parts)))
    concepts: list[str] = []
    seen: set[str] = set()
    for word in words:
        if word in STOPWORDS or len(word) < 4:
            continue
        concept = TR_EN_CONCEPTS.get(word)
        if not concept or concept in seen:
            continue
        seen.add(concept)
        concepts.append(concept)
        if len(concepts) >= limit:
            break
    if not concepts:
        first_word = normalize(topic).split()[0] if topic.strip() else ""
        fallback = TR_EN_CONCEPTS.get(first_word)
        concepts = [fallback] if fallback else ["this topic"]
    return concepts


def match_channel(channels: dict, topic: str, videos: list[dict]) -> str | None:
    haystack = normalize(topic + " " + " ".join(str(v.get("title", "")) for v in videos[:8]))
    best_channel = None
    best_hits = 0
    for name, cfg in channels.items():
        hits = sum(1 for kw in cfg.get("keywords", []) if normalize(kw) in haystack)
        if hits > best_hits:
            best_hits = hits
            best_channel = name
    return best_channel if best_hits > 0 else None


def build_candidate_topics(channel_name: str, concepts: list[str]) -> list[str]:
    templates = ANGLE_TEMPLATES.get(channel_name, ["the untold story of {c}"])
    candidates: list[str] = []
    for i, concept in enumerate(concepts):
        candidate = templates[i % len(templates)].format(c=concept)
        if candidate not in candidates:
            candidates.append(candidate)
    if concepts:
        for template in templates:
            if len(candidates) >= 3:
                break
            candidate = template.format(c=concepts[0])
            if candidate not in candidates:
                candidates.append(candidate)
    return candidates[:5]


def load_log() -> list[dict]:
    return load_json(LOG_FILE) or []


def already_dispatched(log: list[dict], repo: str, topic: str) -> bool:
    normalized_topic = normalize(topic)
    return any(
        entry.get("repo") == repo and normalize(entry.get("topic", "")) == normalized_topic
        for entry in log
    )


def send_dispatch(repo: str, event_type: str, payload: dict, token: str, dry_run: bool) -> bool:
    if dry_run:
        print(f"[DRY RUN] {repo} <- {event_type}: {json.dumps(payload, ensure_ascii=False)}")
        return True
    url = f"{GITHUB_API}/repos/{repo}/dispatches"
    body = json.dumps({"event_type": event_type, "client_payload": payload}).encode("utf-8")
    request = urllib.request.Request(url, data=body, method="POST")
    request.add_header("Authorization", f"token {token}")
    request.add_header("Accept", "application/vnd.github+json")
    request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return 200 <= response.status < 300
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "ignore")
        print(f"HATA: {repo} icin dispatch basarisiz: HTTP {exc.code}: {detail}")
        return False
    except urllib.error.URLError as exc:
        print(f"HATA: {repo} icin dispatch basarisiz: {exc}")
        return False


def main() -> None:
    token = os.environ.get("CROSS_REPO_TOKEN", "").strip()
    dry_run = os.environ.get("DISPATCH_DRY_RUN", "").strip().lower() in {"1", "true", "yes"}
    if not token and not dry_run:
        raise SystemExit("CROSS_REPO_TOKEN bulunamadi. GitHub secrets icine ekle.")

    channels = load_channels()
    qualifying = find_qualifying_projects()
    log = load_log()

    if not qualifying:
        print(f"Hicbir nis {MIN_SCORE}+ puana ulasmadi. Dispatch edilecek konu yok.")

    sent = 0
    failed = 0
    for project_dir, data in qualifying:
        topic = str(data.get("topic", project_dir.name))
        score = int(data.get("niche_score", 0))
        videos = sorted(data.get("videos", []), key=lambda v: v.get("views_per_day", 0), reverse=True)

        channel_name = match_channel(channels, topic, videos)
        if not channel_name:
            print(f"ATLA: '{topic}' hicbir kanal temasiyla eslesmedi.")
            continue

        repo_cfg = channels[channel_name]
        repo = repo_cfg["repo"]
        event_type = repo_cfg.get("event_type", "new_topic")

        concepts = extract_concepts(topic, videos)
        candidates = build_candidate_topics(channel_name, concepts)

        chosen_topic = next((c for c in candidates if not already_dispatched(log, repo, c)), None)
        if not chosen_topic:
            print(f"ATLA: '{topic}' icin turetilen tum konular zaten '{repo}' repouna gonderilmis.")
            continue

        alternates = [c for c in candidates if c != chosen_topic]
        payload = {"topic": chosen_topic, "score": score, "niche": topic, "alternates": alternates}

        ok = send_dispatch(repo, event_type, payload, token, dry_run)
        if ok:
            sent += 1
            log.append({
                "repo": repo,
                "niche": topic,
                "topic": chosen_topic,
                "score": score,
                "dispatched_at": datetime.now(timezone.utc).isoformat(),
            })
            print(f"GONDERILDI: {repo} <- '{chosen_topic}' (nis: {topic}, puan: {score})")
        else:
            failed += 1

    ROOT.mkdir(exist_ok=True)
    LOG_FILE.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Ozet: {sent} konu gonderildi, {failed} hata.")
    if failed:
        raise SystemExit(f"{failed} repository_dispatch cagrisi basarisiz oldu.")


if __name__ == "__main__":
    main()
