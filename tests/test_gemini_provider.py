"""Proves Gemini is genuinely the primary provider: tried first, its model
is discovered from the real account model list (never hardcoded, never an
experimental/preview/lite variant), and OpenAI/Groq only get called when
Gemini is unavailable or fails — using the real google-genai SDK types for
the mocked model list, only the network transport is faked."""

from __future__ import annotations

import json
import unittest
from unittest import mock

from google.genai import types

import script_agent_v2.llm as llmmod
from script_agent_v2.llm import LLM


def _model(name: str) -> types.Model:
    return types.Model(name=f"models/{name}", supported_actions=["generateContent"])


class FakeModelsAPI:
    def __init__(self, models, fail=False):
        self._models = models
        self._fail = fail

    def list(self):
        if self._fail:
            raise Exception("model list unavailable")
        return self._models

    def generate_content(self, model, contents, config):
        return type("Resp", (), {"text": json.dumps({"ok": True, "model": model})})()


class FakeClient:
    def __init__(self, models=None, fail_list=False, fail_init=False):
        if fail_init:
            raise Exception("gemini client init failed")
        self.models = FakeModelsAPI(models or [], fail=fail_list)


class GeminiProviderTests(unittest.TestCase):
    def setUp(self):
        self._env_patch = mock.patch.dict(
            "os.environ", {"GEMINI_API_KEY": "fake-key", "OPENAI_API_KEY": "", "GROQ_API_KEY": ""}, clear=False
        )
        self._env_patch.start()
        self.addCleanup(self._env_patch.stop)

    def test_gemini_tried_first_and_is_primary(self):
        models = [_model("gemini-2.5-flash")]
        with mock.patch.object(llmmod, "genai", mock.Mock(Client=lambda api_key=None: FakeClient(models))):
            llm = LLM()
            result = llm.complete_json("sys", "user")
        self.assertEqual(result, {"ok": True, "model": "gemini-2.5-flash"})
        self.assertEqual(llm.last_provider, "gemini")
        self.assertEqual(llm.last_model, "gemini-2.5-flash")

    def test_model_discovery_excludes_experimental_preview_and_lite(self):
        models = [
            _model("gemini-1.5-flash"),
            _model("gemini-2.0-flash-exp"),
            _model("gemini-2.0-flash"),
            _model("gemini-2.5-flash-preview-05-20"),
            _model("gemini-2.5-flash"),
            _model("gemini-2.5-flash-lite"),
            _model("gemini-2.5-pro"),
        ]
        with mock.patch.object(llmmod, "genai", mock.Mock(Client=lambda api_key=None: FakeClient(models))):
            llm = LLM()
            llm.complete_json("sys", "user")
        self.assertEqual(llm.last_model, "gemini-2.5-flash")

    def test_model_discovery_falls_back_to_loose_match_when_no_strict_match(self):
        # Only a non-exact "flash" name exists (no clean "gemini-N-flash").
        models = [_model("gemini-2.5-flash-thinking-999")]  # excluded (unstable marker)
        models2 = [_model("gemini-2.5-flash-image")]  # not strict, but no unstable marker -> loose match
        with mock.patch.object(llmmod, "genai", mock.Mock(Client=lambda api_key=None: FakeClient(models2))):
            llm = LLM()
            llm.complete_json("sys", "user")
        self.assertEqual(llm.last_model, "gemini-2.5-flash-image")

    def test_gemini_model_env_override_skips_discovery(self):
        with mock.patch.dict("os.environ", {"GEMINI_MODEL": "gemini-9.9-flash-custom"}, clear=False):
            calls = {"list": 0}

            class NoListModelsAPI(FakeModelsAPI):
                def list(self):
                    calls["list"] += 1
                    return super().list()

            client = FakeClient([])
            client.models = NoListModelsAPI([])
            with mock.patch.object(llmmod, "genai", mock.Mock(Client=lambda api_key=None: client)):
                llm = LLM()
                llm.complete_json("sys", "user")
            self.assertEqual(llm.last_model, "gemini-9.9-flash-custom")
            self.assertEqual(calls["list"], 0)  # override skips discovery entirely

    def test_no_stable_flash_model_available_falls_through_honestly(self):
        models = [_model("gemini-2.0-flash-exp"), _model("gemini-2.5-pro")]  # no usable flash
        with mock.patch.dict("os.environ", {"OPENAI_API_KEY": "fake-openai"}, clear=False), \
             mock.patch.object(llmmod, "genai", mock.Mock(Client=lambda api_key=None: FakeClient(models))), \
             mock.patch.object(llmmod, "urlopen") as fake_urlopen:
            fake_urlopen.side_effect = Exception("openai down too")
            llm = LLM()
            result = llm.complete_json("sys", "user")
        self.assertIsNone(result)
        self.assertIsNone(llm.last_provider)

    def test_gemini_client_init_failure_falls_through_to_openai(self):
        with mock.patch.dict("os.environ", {"OPENAI_API_KEY": "fake-openai"}, clear=False), \
             mock.patch.object(llmmod, "genai", mock.Mock(Client=lambda api_key=None: FakeClient(fail_init=True))):
            class FakeResponse:
                def __enter__(self): return self
                def __exit__(self, *a): return False
                def read(self):
                    return json.dumps({"choices": [{"message": {"content": json.dumps({"via": "openai"})}}]}).encode()

            with mock.patch.object(llmmod, "urlopen", return_value=FakeResponse()):
                llm = LLM()
                result = llm.complete_json("sys", "user")
        self.assertEqual(result, {"via": "openai"})
        self.assertEqual(llm.last_provider, "openai")

    def test_gemini_model_list_failure_falls_through_honestly(self):
        with mock.patch.object(llmmod, "genai", mock.Mock(Client=lambda api_key=None: FakeClient([], fail_list=True))):
            llm = LLM()
            result = llm.complete_json("sys", "user")
        self.assertIsNone(result)
        self.assertIsNone(llm.last_provider)

    def test_missing_sdk_never_crashes_falls_through(self):
        with mock.patch.object(llmmod, "_GENAI_SDK_AVAILABLE", False):
            llm = LLM()
            self.assertTrue(llm.available)  # key present, even if SDK missing
            result = llm.complete_json("sys", "user")
        self.assertIsNone(result)  # no other providers configured in setUp


if __name__ == "__main__":
    unittest.main()
