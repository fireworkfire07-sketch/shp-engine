"""SHP Final Run Report — the single, truthful summary of what actually
happened in this run of the master workflow (run-shp.yml).

Classifies every run into exactly one of:
  SYSTEM_SUCCESS       Video CEO Pro said ÇEK — the full chain cleared
                       every quality gate and production is approved.
  QUALITY_REJECT       The chain ran end to end without technical failure,
                       but a quality gate (Script Agent V2 or Video CEO
                       Pro) honestly said no. This is a correct, valid
                       outcome, not a bug.
  BLOCKED_MISSING_DATA Required upstream data was missing (niche/channel/
                       CEO decision), so no real judgment could be made.
  TECHNICAL_FAILURE    A stage actually broke (missing required output
                       file, invalid status/decision enum, exception).

Never reports SYSTEM_SUCCESS unless Video CEO Pro's real, on-disk decision
is ÇEK — this module does not re-derive or override that decision, only
reads and reports it.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("projects")
OUTPUT_DIR = ROOT / "final-run"

REQUIRED_STAGE_FILES = {
    "channel-health": ROOT / "channel-health" / "analysis.json",
    "competitor-health": ROOT / "competitor-health" / "analysis.json",
    "niche-intelligence": ROOT / "niche-intelligence" / "analysis.json",
    "ceo-decision": ROOT / "ceo-decision" / "analysis.json",
    "growth-advisor": ROOT / "growth-advisor" / "analysis.json",
    "script-agent": ROOT / "script-agent" / "script.json",
    "video-ceo": ROOT / "video-ceo" / "analysis.json",
    "voiceover": ROOT / "voiceover" / "audio_manifest.json",
    "video-engine": ROOT / "video-engine" / "render_manifest.json",
    "youtube-upload": ROOT / "youtube-upload" / "upload_result.json",
    "learning-engine": ROOT / "learning-engine" / "memory.json",
}


def load_json(path: Path, default=None):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def find_missing_stages() -> list[str]:
    return [name for name, path in REQUIRED_STAGE_FILES.items() if not path.exists()]


def classify(missing_stages: list[str], niche: dict, ceo_decision: dict, script: dict, video_ceo: dict, video_engine: dict) -> tuple[str, list[str]]:
    reasons = []

    if missing_stages:
        reasons.append(f"Eksik aşama çıktıları: {', '.join(missing_stages)}.")
        return "BLOCKED_MISSING_DATA", reasons

    if not niche.get("winner") or ceo_decision.get("missing_inputs"):
        reasons.append("Niş kazananı veya CEO kararı için gerekli girdiler eksik.")
        return "BLOCKED_MISSING_DATA", reasons

    if video_engine.get("status") == "TECHNICAL_FAILURE":
        reasons.append(f"Video Engine teknik hata bildirdi: {video_engine.get('reasons')}.")
        return "TECHNICAL_FAILURE", reasons

    script_status = script.get("status")
    if script_status not in {"APPROVE", "REJECT"}:
        reasons.append(f"Script Agent V2 geçersiz durum döndürdü: {script_status}.")
        return "TECHNICAL_FAILURE", reasons

    video_ceo_decision = video_ceo.get("decision")
    if video_ceo_decision not in {"ÇEK", "DÜZELT", "DUR", "BEKLET — VERİ EKSİK"}:
        reasons.append(f"Video CEO Pro geçersiz karar döndürdü: {video_ceo_decision}.")
        return "TECHNICAL_FAILURE", reasons

    if video_ceo_decision == "BEKLET — VERİ EKSİK":
        reasons.append("Video CEO Pro veri eksikliği nedeniyle bekletti.")
        return "BLOCKED_MISSING_DATA", reasons

    if video_ceo_decision == "ÇEK":
        reasons.append("Video CEO Pro üretimi onayladı (ÇEK).")
        return "SYSTEM_SUCCESS", reasons

    reasons.append(f"Script Agent V2 durumu: {script_status}. Video CEO Pro kararı: {video_ceo_decision}.")
    return "QUALITY_REJECT", reasons


def next_action_for_osman(status: str, video_ceo: dict, video_engine: dict, upload: dict) -> str:
    if status == "BLOCKED_MISSING_DATA":
        return "Eksik veri kaynaklarını doğrula (YOUTUBE_API_KEY, kanal/rakip erişimi) ve workflow'u tekrar çalıştır."
    if status == "TECHNICAL_FAILURE":
        return "GitHub Actions run loglarını incele; hata veren aşamayı düzelt ve tekrar çalıştır. Bu bir kalite reddi değil, gerçek bir teknik arızadır."
    if status == "QUALITY_REJECT":
        reasons = (video_ceo.get("reasons") or [])[:3]
        reason_text = " ".join(reasons) if reasons else "Gerekçe için projects/video-ceo/report.md dosyasına bak."
        return f"Üretim onaylanmadı, bir şey yapmana gerek yok. Gerekçe: {reason_text}"
    if status == "SYSTEM_SUCCESS":
        render_status = video_engine.get("status")
        if render_status == "RENDERED":
            base = f"Videoyu incele: {video_engine.get('final_video')}."
        elif render_status == "RENDER_SKIPPED_NO_FFMPEG":
            base = "Render manifesti hazır ama bu ortamda FFmpeg yoktu; FFmpeg kurulu bir ortamda `python video_engine.py` çalıştır."
        else:
            base = f"Video Engine durumu: {render_status}."
        upload_status = upload.get("status")
        if upload_status in {"DRY_RUN_OK", "PREPARED"}:
            base += " Onaylarsan gerçek kimlik bilgileriyle YOUTUBE_UPLOAD_MODE=PRIVATE_UPLOAD ile tekrar çalıştır."
        elif upload_status == "UPLOAD_NOT_CONFIGURED":
            base += " YouTube'a gerçekten yüklemek için YOUTUBE_OAUTH_ACCESS_TOKEN (veya CLIENT_ID/SECRET/REFRESH_TOKEN) secret'larını tanımla."
        elif upload_status == "UPLOADED":
            base += f" Video zaten yüklendi: {upload.get('video_url')}."
        return base
    return "Durum tanınmadı; projects/final-run/report.md dosyasını manuel incele."


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    missing_stages = find_missing_stages()

    niche = load_json(ROOT / "niche-intelligence" / "analysis.json", {}) or {}
    ceo_decision = load_json(ROOT / "ceo-decision" / "analysis.json", {}) or {}
    script_payload = load_json(ROOT / "script-agent" / "script.json", {}) or {}
    video_ceo = load_json(ROOT / "video-ceo" / "analysis.json", {}) or {}
    video_engine = load_json(ROOT / "video-engine" / "render_manifest.json", {}) or {}
    upload = load_json(ROOT / "youtube-upload" / "upload_result.json", {}) or {}

    status, reasons = classify(missing_stages, niche, ceo_decision, script_payload, video_ceo, video_engine)
    action = next_action_for_osman(status, video_ceo, video_engine, upload)

    script_body = script_payload.get("script", {}) or {}
    ceo_review = script_payload.get("ceo_review", {}) or {}

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "reasons": reasons,
        "selected_niche": (niche.get("winner") or {}).get("niche"),
        "selected_topic": ceo_decision.get("topic"),
        "video_title": script_body.get("title"),
        "script_status": script_payload.get("status"),
        "script_ceo_score": ceo_review.get("ceo_score"),
        "video_ceo_decision": video_ceo.get("decision"),
        "video_ceo_score": video_ceo.get("video_ceo_score"),
        "production_status": video_engine.get("status"),
        "video_path_or_manifest": video_engine.get("final_video") or str(ROOT / "video-engine" / "render_manifest.json"),
        "upload_status": upload.get("status"),
        "next_action_for_osman": action,
        "missing_stages": missing_stages,
    }
    (OUTPUT_DIR / "analysis.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# SHP Final Run Report", "",
        f"# {status}", "",
        f"**Seçilen niş:** {payload['selected_niche'] or '-'}",
        f"**Seçilen konu:** {payload['selected_topic'] or '-'}",
        f"**Video başlığı:** {payload['video_title'] or '-'}",
        f"**Script durumu:** {payload['script_status'] or '-'} (CEO puanı: {payload['script_ceo_score'] if payload['script_ceo_score'] is not None else '-'})",
        f"**Video CEO kararı:** {payload['video_ceo_decision'] or '-'} ({payload['video_ceo_score'] if payload['video_ceo_score'] is not None else '-'}/100)",
        f"**Üretim durumu:** {payload['production_status'] or '-'}",
        f"**Video/manifest yolu:** {payload['video_path_or_manifest']}",
        f"**Yükleme durumu:** {payload['upload_status'] or '-'}",
        "",
        "## Osman için tam sonraki adım", "",
        f"> {action}", "",
        "## Gerekçe", "",
        *[f"- {r}" for r in reasons],
        "",
    ]
    if missing_stages:
        lines += ["## Eksik aşamalar", "", *[f"- {s}" for s in missing_stages], ""]
    lines += [
        "## Gerçek sınırlar", "",
        "- Bu rapor hiçbir aşamayı yeniden değerlendirmez; yalnızca her aşamanın gerçek diskteki çıktısını okur ve özetler.",
        "- SYSTEM_SUCCESS yalnızca Video CEO Pro'nun gerçek kararı ÇEK olduğunda verilir.",
    ]
    (OUTPUT_DIR / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"FINAL_RUN_STATUS={status}")
    print(f"FINAL_RUN_NEXT_ACTION={action}")


if __name__ == "__main__":
    main()
