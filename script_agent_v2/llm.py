"""Shared LLM caller used by every engine that needs generative reasoning.

Provider order: OpenAI (primary, OPENAI_API_KEY) -> Groq (optional secondary
fallback, GROQ_API_KEY) -> None. Every engine works without any key: each
call site defines its own deterministic rule_based_fallback for when this
returns None. This module only centralizes the HTTP plumbing so the 14
engines do not each reimplement it.
"""

from __future__ import annotations

import json
import os
from urllib.request import Request, urlopen

OPENAI_URL = "https://api.openai.com/v1/chat/completions"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


class LLM:
    """Thin OpenAI-primary/Groq-secondary chat-completions client with
    JSON-mode support."""

    def __init__(self) -> None:
        self.openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()
        self.openai_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.groq_api_key = os.getenv("GROQ_API_KEY", "").strip()
        self.groq_model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        self.calls = 0
        self.failures = 0
        self.last_provider: str | None = None  # "openai" | "groq" | None

    @property
    def available(self) -> bool:
        return bool(self.openai_api_key or self.groq_api_key)

    def complete_json(
        self,
        system: str,
        user: str,
        temperature: float = 0.6,
        timeout: int = 90,
    ) -> dict | list | None:
        """Try OpenAI first, then Groq as an optional secondary fallback.
        Returns None on total failure so the caller can fall back to
        deterministic logic — never raises."""
        if self.openai_api_key:
            result = self._call(OPENAI_URL, self.openai_api_key, self.openai_model, system, user, temperature, timeout)
            if result is not None:
                self.last_provider = "openai"
                return result

        if self.groq_api_key:
            result = self._call(GROQ_URL, self.groq_api_key, self.groq_model, system, user, temperature, timeout)
            if result is not None:
                self.last_provider = "groq"
                return result

        self.last_provider = None
        return None

    def _call(
        self,
        url: str,
        api_key: str,
        model: str,
        system: str,
        user: str,
        temperature: float,
        timeout: int,
    ) -> dict | list | None:
        body = {
            "model": model,
            "temperature": temperature,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        request = Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        self.calls += 1
        try:
            with urlopen(request, timeout=timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
            content = payload["choices"][0]["message"]["content"]
            return json.loads(content)
        except Exception as exc:  # noqa: BLE001 — must never crash the pipeline
            self.failures += 1
            print(f"SCRIPT_AGENT_V2_LLM_CALL_FAILED={exc}")
            return None
