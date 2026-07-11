from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path("projects")
OUTPUT_DIR = ROOT / "script-agent"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def build_context() -> dict:
    ceo = load_json(ROOT / "ceo-decision" / "analysis.json")
    growth = load_json(ROOT / "growth-advisor" / "analysis.json")
    niche = load_json(ROOT / "niche-intelligence" / "analysis.json")
    video_dna_root = ROOT / "video-dna"
    video_dna = {}
    if video_dna_root.exists():
        candidates = sorted(video_dna_root.glob("*/analysis.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        if candidates:
            video_dna = load_json(candidates[0])

    winner = niche.get("winner", {}) or {}
    return {
        "topic": ceo.get("video_idea") or winner.get("first_10_video_ideas", [""])[0] or winner.get("niche", ""),
        "niche": winner.get("niche") or ceo.get("topic", ""),
        "decision": ceo.get("decision", ""),
        "effort_verdict": ceo.get("effort_verdict", ""),
        "first_3_seconds": growth.get("first_3_seconds", ""),
        "retention_plan": growth.get("retention_plan", []),
        "engagement_plan": growth.get("engagement_plan", []),
        "keywords": growth.get("trending_keywords", []),
        "hashtags": growth.get("hashtags", []),
        "competitor_reference": ceo.get("competitor_reference", {}),
        "video_dna": video_dna,
    }


def fallback_script(context: dict) -> dict:
    topic = context["topic"] or "İnsanlık Tarihini Değiştiren Gizemli Bitki"
    hook = context["first_3_seconds"] or f"Bu hikâyede, {topic.lower()} sandığınızdan çok daha büyük bir sırrı saklıyor."
    sections = [
        {"name": "Açılış", "duration": "0:00-0:30", "voiceover": hook + " Cevabı birazdan göreceksiniz; fakat önce bu sırrın başladığı yere dönelim."},
        {"name": "Köken", "duration": "0:30-1:30", "voiceover": f"{topic} yalnızca bir doğa hikâyesi değildir. Kökeni ticaret, güç ve insanların hayatta kalma mücadelesiyle iç içedir."},
        {"name": "İlk kırılma", "duration": "1:30-3:00", "voiceover": "Değerinin anlaşılmasıyla birlikte dengeler değişti. Onu kontrol edenler yalnızca bir ürünü değil, dönemin en değerli bilgisini de kontrol ediyordu."},
        {"name": "Gizem derinleşiyor", "duration": "3:00-5:00", "voiceover": "Fakat anlatılan resmi hikâye eksikti. Kayıtların arasındaki küçük ayrıntılar, olayın arkasında daha büyük bir çıkar çatışması olduğunu gösteriyor."},
        {"name": "Büyük cevap", "duration": "5:00-6:30", "voiceover": "Asıl sır şuydu: Bu doğal kaynak, insanların günlük yaşamını değiştirmekten çok daha fazlasını yaptı; ticaret yollarını, siyasi kararları ve toplumların kaderini etkiledi."},
        {"name": "Final", "duration": "6:30-7:00", "voiceover": "Bugün sıradan görünen şeylerin geçmişte nasıl güç araçlarına dönüştüğünü bilmek, tarihe bambaşka bakmamızı sağlıyor. Sizce doğanın sakladığı en büyük sır hangisi?"},
    ]
    return {
        "title": topic,
        "language": "tr",
        "target_duration_minutes": 7,
        "hook": hook,
        "sections": sections,
        "source_mode": "rule_based_fallback",
    }


def generate_with_groq(context: dict) -> dict | None:
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        return None

    model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    system = (
        "Sen SHP Script Agent'sın. Türkçe YouTube belgesel senaryosu yaz. "
        "Rakip metnini kopyalama; yalnızca yapı, merak ve tempo kalıplarından öğren. "
        "Çıktın geçerli JSON olsun: title, language, target_duration_minutes, hook, sections. "
        "sections listesinde name, duration, voiceover alanları bulunsun. "
        "İlk 3 saniye çok güçlü, ilk 30 saniye merak odaklı ve final yorum çağrılı olsun."
    )
    body = {
        "model": model,
        "temperature": 0.65,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(context, ensure_ascii=False)},
        ],
    }
    request = Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=90) as response:
            payload = json.loads(response.read().decode("utf-8"))
        content = payload["choices"][0]["message"]["content"]
        result = json.loads(content)
        result["source_mode"] = "groq"
        return result
    except Exception as exc:
        print(f"GROQ_GENERATION_FAILED={exc}")
        return None


def validate_script(script: dict) -> None:
    required = ["title", "hook", "sections"]
    missing = [key for key in required if not script.get(key)]
    if missing:
        raise SystemExit(f"Script eksik alanlar: {missing}")
    if not isinstance(script["sections"], list) or len(script["sections"]) < 5:
        raise SystemExit("Script en az 5 bölüm içermeli.")
    total_words = sum(len(str(item.get("voiceover", "")).split()) for item in script["sections"])
    if total_words < 100:
        raise SystemExit("Script çok kısa.")


def main() -> None:
    context = build_context()
    if not context["topic"]:
        raise SystemExit("Video CEO somut video fikri üretmedi.")

    script = generate_with_groq(context) or fallback_script(context)
    validate_script(script)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "agent": "SHP Script Agent",
        "status": "READY",
        "context": context,
        "script": script,
        "rules": [
            "Rakip metni kopyalanmaz.",
            "Özgün anlatım ve yeni cümle yapısı kullanılır.",
            "İlk 3 saniye ve ilk 30 saniye Video CEO planına uyar.",
        ],
    }
    (OUTPUT_DIR / "script.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# SHP Script Agent", "", f"**Durum:** READY", f"**Başlık:** {script['title']}",
        f"**Üretim modu:** {script.get('source_mode', 'unknown')}", "", "## Hook", "", str(script["hook"]), "", "## Tam senaryo", "",
    ]
    for section in script["sections"]:
        lines.extend([f"### {section.get('name', 'Bölüm')} — {section.get('duration', '')}", "", str(section.get("voiceover", "")), ""])
    (OUTPUT_DIR / "script.md").write_text("\n".join(lines), encoding="utf-8")

    handoff = {
        "status": "READY_FOR_VIDEO_ENGINE",
        "title": script["title"],
        "language": script.get("language", "tr"),
        "target_duration_minutes": script.get("target_duration_minutes", 7),
        "voiceover_sections": script["sections"],
        "thumbnail_direction": load_json(ROOT / "ceo-decision" / "analysis.json").get("thumbnail_direction", ""),
        "hashtags": context.get("hashtags", []),
    }
    (OUTPUT_DIR / "video-engine-handoff.json").write_text(json.dumps(handoff, ensure_ascii=False, indent=2), encoding="utf-8")

    print("SCRIPT_AGENT_STATUS=READY")
    print(f"SCRIPT_MODE={script.get('source_mode', 'unknown')}")
    print(f"SCRIPT_TITLE={script['title']}")
    print(f"REPORT={OUTPUT_DIR / 'script.md'}")


if __name__ == "__main__":
    main()
