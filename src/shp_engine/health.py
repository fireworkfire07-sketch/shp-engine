from __future__ import annotations

from dataclasses import asdict, dataclass

from .config import get_settings


@dataclass
class HealthReport:
    project_name: str
    output_dir: str
    youtube_privacy_status: str
    secrets_loaded: dict[str, bool]
    safe_to_test: bool


def check_health() -> HealthReport:
    settings = get_settings()
    settings.ensure_output_dir()

    secrets_loaded = {
        "OPENAI_API_KEY": bool(settings.openai_api_key),
        "ANTHROPIC_API_KEY": bool(settings.anthropic_api_key),
        "ELEVENLABS_API_KEY": bool(settings.elevenlabs_api_key),
        "YOUTUBE_CLIENT_ID": bool(settings.youtube_client_id),
        "YOUTUBE_CLIENT_SECRET": bool(settings.youtube_client_secret),
        "YOUTUBE_REFRESH_TOKEN": bool(settings.youtube_refresh_token),
    }

    return HealthReport(
        project_name=settings.project_name,
        output_dir=str(settings.output_dir),
        youtube_privacy_status=settings.youtube_privacy_status,
        secrets_loaded=secrets_loaded,
        safe_to_test=settings.youtube_privacy_status == "private",
    )


def health_as_dict() -> dict:
    return asdict(check_health())
