"""Shared GROQ caller used by every engine that needs generative reasoning.

Every engine works without an API key: each call site defines its own
deterministic fallback. This module only centralizes the HTTP plumbing so
the 14 engines do not each reimplement it.
"""

from __future__ import annotations

import json
import os
from urllib.request import Request, urlopen

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


class LLM:
    """Thin GROQ chat-completions client with JSON-mode support."""

    def __init__(self) -> None:
        self.api_key = os.getenv("GROQ_API_KEY", "").strip()
        self.model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        self.calls = 0
        self.failures = 0

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def complete_json(
        self,
        system: str,
        user: str,
        temperature: float = 0.6,
        timeout: int = 90,
    ) -> dict | list | None:
        """Call GROQ in JSON mode. Returns None on any failure so the caller
        can fall back to deterministic logic — never raises."""
        if not self.api_key:
            return None

        body = {
            "model": self.model,
            "temperature": temperature,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        request = Request(
            GROQ_URL,
            data=json.dumps(body).encode("utf-8"),
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
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
