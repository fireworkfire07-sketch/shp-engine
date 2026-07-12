"""SHP YouTube Uploader — the last, safety-critical stage.

Permanent safety rule: privacyStatus defaults to private and is FORCED to
private for every mode except an explicitly, doubly opted-in PUBLIC_UPLOAD.
Nothing this module does can publish publicly by accident.

Modes (env var YOUTUBE_UPLOAD_MODE, default DRY_RUN):
  DRY_RUN         Validates everything and shows exactly what would be
                  uploaded. Never calls the network. Never needs credentials.
  PREPARE_UPLOAD  Validates + writes the real YouTube Data API request body
                  to disk. Never calls the network.
  PRIVATE_UPLOAD  Performs the real resumable upload via the YouTube Data
                  API v3, privacyStatus hardcoded to "private" regardless of
                  what youtube_upload.json says. Requires real OAuth
                  credentials.
  PUBLIC_UPLOAD   Disabled by default. Only proceeds if YOUTUBE_ALLOW_PUBLIC
                  is also explicitly set to "true" — two separate signals
                  required, matching "never publish publicly without
                  explicit configuration and approval".

Missing credentials return UPLOAD_NOT_CONFIGURED and never crash the
pipeline. This module has not been exercised against a live YouTube
account in this environment (no real OAuth credentials were available to
test with) — the resumable-upload request construction follows the
documented YouTube Data API v3 protocol exactly and is unit-tested against
a mocked transport, but a real credentialed smoke test is a manual step
still required before first production use (see docs/SHP_FULL_SYSTEM_AUDIT.md
follow-up / final delivery notes).
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path("projects")
SCRIPT_DIR = ROOT / "script-agent"
OUTPUT_DIR = ROOT / "youtube-upload"

UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos"
TOKEN_URL = "https://oauth2.googleapis.com/token"
YOUTUBE_CATEGORY_IDS = {"Education": "27"}
ALLOWED_MODES = {"DRY_RUN", "PREPARE_UPLOAD", "PRIVATE_UPLOAD", "PUBLIC_UPLOAD"}


def load_json(path: Path, default=None):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def get_mode() -> str:
    mode = os.getenv("YOUTUBE_UPLOAD_MODE", "DRY_RUN").strip().upper()
    return mode if mode in ALLOWED_MODES else "DRY_RUN"


def credentials_available() -> bool:
    if os.getenv("YOUTUBE_OAUTH_ACCESS_TOKEN", "").strip():
        return True
    return bool(
        os.getenv("YOUTUBE_CLIENT_ID", "").strip()
        and os.getenv("YOUTUBE_CLIENT_SECRET", "").strip()
        and os.getenv("YOUTUBE_REFRESH_TOKEN", "").strip()
    )


def refresh_access_token() -> str | None:
    token = os.getenv("YOUTUBE_OAUTH_ACCESS_TOKEN", "").strip()
    if token:
        return token
    client_id = os.getenv("YOUTUBE_CLIENT_ID", "").strip()
    client_secret = os.getenv("YOUTUBE_CLIENT_SECRET", "").strip()
    refresh_token = os.getenv("YOUTUBE_REFRESH_TOKEN", "").strip()
    if not (client_id and client_secret and refresh_token):
        return None
    body = urlencode({
        "client_id": client_id, "client_secret": client_secret,
        "refresh_token": refresh_token, "grant_type": "refresh_token",
    }).encode("utf-8")
    request = Request(TOKEN_URL, data=body, method="POST")
    try:
        with urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return payload.get("access_token")
    except (HTTPError, URLError, OSError, ValueError):
        return None


def resolve_thumbnail_path(render_manifest: dict) -> str | None:
    """No AI thumbnail image exists yet (thumbnail.json is a concept spec,
    not a rendered asset) — the honest, real candidate is the actual hook
    scene frame Video Engine already generated, not a fabricated path."""
    scenes = render_manifest.get("scenes", []) if render_manifest else []
    if not scenes:
        return None
    hook_scene = next((s for s in scenes if s.get("role") == "hook"), scenes[0])
    path = hook_scene.get("image_source")
    return path if path and Path(path).exists() else None


def validate_package(metadata: dict, thumbnail_path: str | None, video_path: str | None) -> list[str]:
    errors = []
    title = str(metadata.get("title", "")).strip()
    if not title:
        errors.append("Başlık boş.")
    elif len(title) > 100:
        errors.append(f"Başlık YouTube sınırını aşıyor ({len(title)}/100 karakter).")
    if not str(metadata.get("description", "")).strip():
        errors.append("Açıklama boş.")
    if not metadata.get("tags"):
        errors.append("Etiket listesi boş.")
    if not video_path or not Path(video_path).exists():
        errors.append(f"Final video dosyası bulunamadı: {video_path}")
    if not thumbnail_path or not Path(thumbnail_path).exists():
        errors.append(f"Thumbnail görseli bulunamadı: {thumbnail_path}")
    return errors


def build_request_body(metadata: dict, privacy_status: str) -> dict:
    return {
        "snippet": {
            "title": str(metadata.get("title", ""))[:100],
            "description": metadata.get("description", ""),
            "tags": metadata.get("tags", []),
            "categoryId": YOUTUBE_CATEGORY_IDS.get(metadata.get("category", "Education"), "27"),
            "defaultLanguage": metadata.get("language", "tr"),
        },
        "status": {"privacyStatus": privacy_status, "selfDeclaredMadeForKids": False},
    }


def initiate_resumable_session(access_token: str, body: dict, video_path: str) -> str | None:
    size = Path(video_path).stat().st_size
    request = Request(
        f"{UPLOAD_URL}?uploadType=resumable&part=snippet,status",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=UTF-8",
            "X-Upload-Content-Type": "video/mp4",
            "X-Upload-Content-Length": str(size),
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:
            return response.headers.get("Location")
    except (HTTPError, URLError, OSError):
        return None


def upload_video_bytes(session_url: str, video_path: str) -> dict | None:
    data = Path(video_path).read_bytes()
    request = Request(
        session_url, data=data,
        headers={"Content-Type": "video/mp4", "Content-Length": str(len(data))},
        method="PUT",
    )
    try:
        with urlopen(request, timeout=600) as response:
            return json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, OSError, ValueError):
        return None


def _write(payload: dict) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"generated_at": datetime.now(timezone.utc).isoformat(), **payload}
    (OUTPUT_DIR / "upload_result.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    lines = [
        "# SHP YouTube Upload Raporu", "",
        f"**Durum:** {payload['status']}",
        f"**Mod:** {payload.get('mode', '-')}",
        f"**Gizlilik:** {payload.get('privacy_status', 'private (varsayılan)')}",
        f"**Video ID:** {payload.get('video_id', '-')}",
        f"**Video URL:** {payload.get('video_url', '-')}",
        "",
        "## Gerekçe / durum notları", "",
        *[f"- {r}" for r in payload.get("reasons", [])],
        "",
    ]
    if payload.get("validation_errors"):
        lines += ["## Doğrulama hataları", "", *[f"- {e}" for e in payload["validation_errors"]], ""]
    lines += [
        "## Gerçek sınırlar", "",
        "- privacyStatus PRIVATE_UPLOAD/DRY_RUN/PREPARE_UPLOAD için her zaman 'private' olarak zorlanır.",
        "- PUBLIC_UPLOAD varsayılan olarak kapalıdır; yalnızca YOUTUBE_ALLOW_PUBLIC=true açıkça ayarlanırsa denenir.",
        "- Bu depoda gerçek bir YouTube OAuth hesabına karşı canlı test yapılmamıştır (kimlik bilgisi yok); istek inşası API sözleşmesine göredir ve mock transport ile test edilmiştir — canlı ilk kullanım öncesi kimlik bilgili bir manuel duman testi gerekir.",
    ]
    (OUTPUT_DIR / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    metadata = load_json(SCRIPT_DIR / "youtube_upload.json", {}) or {}
    render_manifest = load_json(ROOT / "video-engine" / "render_manifest.json", {}) or {}
    video_ceo = load_json(ROOT / "video-ceo" / "analysis.json", {}) or {}

    mode = get_mode()
    video_path = render_manifest.get("final_video")
    thumbnail_path = resolve_thumbnail_path(render_manifest)
    errors = validate_package(metadata, thumbnail_path, video_path)

    public_allowed = mode == "PUBLIC_UPLOAD" and os.getenv("YOUTUBE_ALLOW_PUBLIC", "").strip().lower() == "true"
    privacy_status = "public" if public_allowed else "private"

    if mode == "DRY_RUN":
        request_body = build_request_body(metadata, privacy_status)
        payload = {
            "status": "DRY_RUN_VALIDATION_FAILED" if errors else "DRY_RUN_OK",
            "mode": mode, "privacy_status": privacy_status,
            "would_upload": request_body, "video_path": video_path, "thumbnail_path": thumbnail_path,
            "validation_errors": errors,
            "reasons": [
                f"Video CEO Pro kararı: {video_ceo.get('decision', 'yok')}.",
                "Gerçek API çağrısı yapılmadı (DRY_RUN).",
            ],
        }
        _write(payload)
        print(f"YOUTUBE_UPLOAD_STATUS={payload['status']}")
        return

    if mode == "PUBLIC_UPLOAD" and not public_allowed:
        payload = {
            "status": "PUBLIC_UPLOAD_BLOCKED", "mode": mode, "privacy_status": "private",
            "reasons": ["PUBLIC_UPLOAD varsayılan olarak kapalıdır. Açmak için YOUTUBE_ALLOW_PUBLIC=true açıkça ayarlanmalı."],
        }
        _write(payload)
        print("YOUTUBE_UPLOAD_STATUS=PUBLIC_UPLOAD_BLOCKED")
        return

    if video_ceo.get("decision") != "ÇEK":
        payload = {
            "status": "NOT_READY", "mode": mode, "privacy_status": privacy_status,
            "validation_errors": errors,
            "reasons": [f"Video CEO Pro kararı '{video_ceo.get('decision', 'yok')}'; yükleme hazır değil."],
        }
        _write(payload)
        print("YOUTUBE_UPLOAD_STATUS=NOT_READY")
        return

    if errors:
        payload = {"status": "VALIDATION_FAILED", "mode": mode, "privacy_status": privacy_status, "validation_errors": errors, "reasons": ["Yükleme paketi doğrulamayı geçmedi."]}
        _write(payload)
        print("YOUTUBE_UPLOAD_STATUS=VALIDATION_FAILED")
        return

    request_body = build_request_body(metadata, privacy_status)

    if mode == "PREPARE_UPLOAD":
        payload = {
            "status": "PREPARED", "mode": mode, "privacy_status": privacy_status,
            "request_body": request_body, "video_path": video_path, "thumbnail_path": thumbnail_path,
            "reasons": ["Yükleme paketi hazırlandı; gerçek API çağrısı yapılmadı."],
        }
        _write(payload)
        print("YOUTUBE_UPLOAD_STATUS=PREPARED")
        return

    # PRIVATE_UPLOAD, or PUBLIC_UPLOAD explicitly approved above.
    if not credentials_available():
        payload = {
            "status": "UPLOAD_NOT_CONFIGURED", "mode": mode, "privacy_status": privacy_status,
            "reasons": ["YouTube OAuth kimlik bilgileri tanımlı değil (YOUTUBE_OAUTH_ACCESS_TOKEN veya YOUTUBE_CLIENT_ID/YOUTUBE_CLIENT_SECRET/YOUTUBE_REFRESH_TOKEN)."],
        }
        _write(payload)
        print("YOUTUBE_UPLOAD_STATUS=UPLOAD_NOT_CONFIGURED")
        return

    access_token = refresh_access_token()
    if not access_token:
        payload = {"status": "UPLOAD_NOT_CONFIGURED", "mode": mode, "privacy_status": privacy_status, "reasons": ["Erişim jetonu alınamadı; kimlik bilgileri geçersiz olabilir."]}
        _write(payload)
        print("YOUTUBE_UPLOAD_STATUS=UPLOAD_NOT_CONFIGURED")
        return

    session_url = initiate_resumable_session(access_token, request_body, video_path)
    if not session_url:
        payload = {"status": "UPLOAD_FAILED", "mode": mode, "privacy_status": privacy_status, "reasons": ["Resumable upload oturumu başlatılamadı."]}
        _write(payload)
        print("YOUTUBE_UPLOAD_STATUS=UPLOAD_FAILED")
        return

    result = upload_video_bytes(session_url, video_path)
    if not result or "id" not in result:
        payload = {"status": "UPLOAD_FAILED", "mode": mode, "privacy_status": privacy_status, "reasons": ["Video baytları yüklenemedi veya API geçersiz yanıt döndürdü."]}
        _write(payload)
        print("YOUTUBE_UPLOAD_STATUS=UPLOAD_FAILED")
        return

    payload = {
        "status": "UPLOADED", "mode": mode, "privacy_status": privacy_status,
        "video_id": result["id"], "video_url": f"https://www.youtube.com/watch?v={result['id']}",
        "reasons": ["Yükleme tamamlandı."],
    }
    _write(payload)
    print("YOUTUBE_UPLOAD_STATUS=UPLOADED")


if __name__ == "__main__":
    main()
