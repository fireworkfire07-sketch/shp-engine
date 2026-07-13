"""Shared LLM caller used by every engine that needs generative reasoning.

Provider order: Gemini (primary, GEMINI_API_KEY, via the official Google
GenAI SDK) -> OpenAI (optional secondary, OPENAI_API_KEY) -> Groq (optional
secondary, GROQ_API_KEY) -> None. Every engine works without any key: each
call site defines its own deterministic rule_based_fallback for when this
returns None. This module only centralizes the HTTP/SDK plumbing so the 14
engines do not each reimplement it.

The Gemini model is never hardcoded: on first use, the client lists the
account's available models and picks the newest stable (non-experimental,
non-preview) Gemini Flash model that supports generateContent. An optional
GEMINI_MODEL env var can force a specific model, matching the same
override pattern OPENAI_MODEL/GROQ_MODEL already use.
"""

from __future__ import annotations

import json
import os
import re
from urllib.request import Request, urlopen

try:
    from google import genai
    from google.genai import types as genai_types
    _GENAI_SDK_AVAILABLE = True
except ImportError:  # pragma: no cover - only true if the dependency is missing
    _GENAI_SDK_AVAILABLE = False

OPENAI_URL = "https://api.openai.com/v1/chat/completions"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

_STABLE_FLASH_PATTERN = re.compile(r"^gemini-\d+(?:\.\d+)?-flash$")
_UNSTABLE_MARKERS = ("exp", "preview", "thinking", "8b", "lite", "tuning")
_VERSION_PATTERN = re.compile(r"gemini-(\d+(?:\.\d+)?)-flash")


def _gemini_version_key(name: str) -> float:
    match = _VERSION_PATTERN.search(name)
    return float(match.group(1)) if match else 0.0


class LLM:
    """Gemini-primary / OpenAI-and-Groq-secondary chat-completions client
    with JSON-mode support."""

    def __init__(self) -> None:
        self.gemini_api_key = os.getenv("GEMINI_API_KEY", "").strip()
        self.gemini_model_override = os.getenv("GEMINI_MODEL", "").strip()
        self._gemini_client = None
        self._gemini_model_resolved: str | None = None
        self._gemini_discovery_failed = False

        self.openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()
        self.openai_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

        self.groq_api_key = os.getenv("GROQ_API_KEY", "").strip()
        self.groq_model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

        self.calls = 0
        self.failures = 0
        self.last_provider: str | None = None  # "gemini" | "openai" | "groq" | None
        self.last_model: str | None = None

    @property
    def available(self) -> bool:
        return bool(self.gemini_api_key or self.openai_api_key or self.groq_api_key)

    def complete_json(
        self,
        system: str,
        user: str,
        temperature: float = 0.6,
        timeout: int = 90,
    ) -> dict | list | None:
        """Try Gemini first, then OpenAI, then Groq as optional secondary
        fallbacks. Returns None on total failure so the caller can fall back
        to deterministic logic — never raises."""
        if self.gemini_api_key and _GENAI_SDK_AVAILABLE:
            result = self._call_gemini(system, user, temperature)
            if result is not None:
                self.last_provider = "gemini"
                return result

        if self.openai_api_key:
            result = self._call_openai_compatible(OPENAI_URL, self.openai_api_key, self.openai_model, system, user, temperature, timeout)
            if result is not None:
                self.last_provider = "openai"
                self.last_model = self.openai_model
                return result

        if self.groq_api_key:
            result = self._call_openai_compatible(GROQ_URL, self.groq_api_key, self.groq_model, system, user, temperature, timeout)
            if result is not None:
                self.last_provider = "groq"
                self.last_model = self.groq_model
                return result

        self.last_provider = None
        self.last_model = None
        return None

    # -- Gemini (primary) ---------------------------------------------------

    def _resolve_gemini_model(self) -> str | None:
        if self.gemini_model_override:
            return self.gemini_model_override
        if self._gemini_model_resolved:
            return self._gemini_model_resolved
        if self._gemini_discovery_failed:
            return None

        try:
            strict, loose = [], []
            for model in self._gemini_client.models.list():
                name = str(getattr(model, "name", "") or "")
                short = name.rsplit("/", 1)[-1]
                if not short or "flash" not in short:
                    continue
                actions = getattr(model, "supported_actions", None)
                if actions and "generateContent" not in actions:
                    continue
                if any(marker in short for marker in _UNSTABLE_MARKERS):
                    continue
                (strict if _STABLE_FLASH_PATTERN.match(short) else loose).append(short)

            candidates = strict or loose
            if not candidates:
                self._gemini_discovery_failed = True
                print("SCRIPT_AGENT_V2_LLM_CALL_FAILED=Gemini: no stable flash model found in account's model list")
                return None

            candidates.sort(key=_gemini_version_key, reverse=True)
            self._gemini_model_resolved = candidates[0]
            return self._gemini_model_resolved
        except Exception as exc:  # noqa: BLE001 — must never crash the pipeline
            self._gemini_discovery_failed = True
            self.failures += 1
            print(f"SCRIPT_AGENT_V2_LLM_CALL_FAILED=Gemini model discovery: {exc}")
            return None

    def _call_gemini(self, system: str, user: str, temperature: float) -> dict | list | None:
        if self._gemini_client is None:
            try:
                self._gemini_client = genai.Client(api_key=self.gemini_api_key)
            except Exception as exc:  # noqa: BLE001
                self.failures += 1
                print(f"SCRIPT_AGENT_V2_LLM_CALL_FAILED=Gemini client init: {exc}")
                return None

        model = self._resolve_gemini_model()
        if not model:
            return None

        self.calls += 1
        try:
            response = self._gemini_client.models.generate_content(
                model=model,
                contents=user,
                config=genai_types.GenerateContentConfig(
                    system_instruction=system,
                    temperature=temperature,
                    response_mime_type="application/json",
                ),
            )
            result = json.loads(response.text)
            self.last_model = model
            return result
        except Exception as exc:  # noqa: BLE001 — must never crash the pipeline
            self.failures += 1
            print(f"SCRIPT_AGENT_V2_LLM_CALL_FAILED=Gemini {model}: {exc}")
            return None

    # -- OpenAI / Groq (optional secondary fallbacks) ------------------------

    def _call_openai_compatible(
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
