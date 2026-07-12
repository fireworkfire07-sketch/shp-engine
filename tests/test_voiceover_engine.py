"""Proves the voiceover adapter system never requires a paid provider,
honestly reports TEXT_ONLY when no TTS is available, and — when espeak-ng
and ffmpeg are actually present (as they are in this environment) — really
synthesizes audible speech rather than a stub file."""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import voiceover_engine

HAS_ESPEAK = shutil.which("espeak-ng") is not None
HAS_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


class VoiceoverAdapterTests(unittest.TestCase):
    def test_provider_never_required_when_unconfigured(self):
        with mock.patch.dict("os.environ", {"ELEVENLABS_API_KEY": ""}, clear=False):
            self.assertIsNone(voiceover_engine.provider_configured())

    def test_provider_detected_when_key_present(self):
        with mock.patch.dict("os.environ", {"ELEVENLABS_API_KEY": "x"}, clear=False):
            self.assertEqual(voiceover_engine.provider_configured(), "elevenlabs")

    def test_unwired_provider_never_crashes_falls_back_honestly(self):
        # No real provider implementation ships -> must return False, not raise.
        ok = voiceover_engine._synthesize_with_provider("elevenlabs", "test", Path("/tmp/does-not-matter.wav"))
        self.assertFalse(ok)

    def test_synthesize_storyboard_text_only_when_no_tts_available(self):
        with mock.patch.object(voiceover_engine, "local_tts_available", return_value=False), \
             mock.patch.object(voiceover_engine, "provider_configured", return_value=None), \
             mock.patch.object(voiceover_engine, "AUDIO_DIR", Path(tempfile.mkdtemp())):
            mode, scenes = voiceover_engine.synthesize_storyboard(
                [{"scene_number": 1, "section": "A", "narration": "Test metni."}]
            )
        self.assertEqual(mode, "TEXT_ONLY")
        self.assertIsNone(scenes[0]["audio_file"])
        self.assertGreater(scenes[0]["estimated_seconds"], 0)

    @unittest.skipUnless(HAS_ESPEAK and HAS_FFMPEG, "espeak-ng/ffmpeg not installed in this environment")
    def test_local_tts_produces_real_audible_audio(self):
        tmp = Path(tempfile.mkdtemp())
        out = tmp / "voice.wav"
        ok = voiceover_engine.synthesize_local_tts("Neden bu gizli sır saklandı?", out, "tr")
        self.assertTrue(ok)
        self.assertGreater(out.stat().st_size, 0)
        duration = voiceover_engine.probe_duration_seconds(out)
        self.assertGreater(duration, 0)

    @unittest.skipUnless(HAS_ESPEAK and HAS_FFMPEG, "espeak-ng/ffmpeg not installed in this environment")
    def test_synthesize_storyboard_and_concatenate_end_to_end(self):
        tmp = Path(tempfile.mkdtemp())
        with mock.patch.object(voiceover_engine, "ROOT", tmp), \
             mock.patch.object(voiceover_engine, "AUDIO_DIR", tmp / "scenes"):
            mode, scenes = voiceover_engine.synthesize_storyboard([
                {"scene_number": 1, "section": "A", "narration": "Birinci sahne metni."},
                {"scene_number": 2, "section": "B", "narration": "İkinci sahne metni burada."},
            ])
            self.assertEqual(mode, "LOCAL_TTS")
            for scene in scenes:
                self.assertIsNotNone(scene["audio_file"])
                self.assertGreater(scene["actual_seconds"], 0)

            full = tmp / "full.wav"
            ok = voiceover_engine.concatenate_audio(scenes, full)
        self.assertTrue(ok)
        self.assertTrue(full.exists())
        total = voiceover_engine.probe_duration_seconds(full)
        self.assertGreater(total, 0)


class VoiceoverMainFlowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.projects = self.tmp / "projects"
        self.projects.mkdir()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        for name, attr in [
            ("ROOT", self.projects), ("SCRIPT_DIR", self.projects / "script-agent"),
            ("OUTPUT_DIR", self.projects / "voiceover"), ("AUDIO_DIR", self.projects / "voiceover" / "scenes"),
            ("FULL_AUDIO_PATH", self.projects / "voiceover" / "voiceover.wav"),
        ]:
            p = mock.patch.object(voiceover_engine, name, attr)
            p.start()
            self.addCleanup(p.stop)

    def test_missing_storyboard_reports_text_only_honestly(self):
        voiceover_engine.main()
        manifest = json.loads((self.projects / "voiceover" / "audio_manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["mode"], "TEXT_ONLY")
        self.assertEqual(manifest["scenes"], [])


if __name__ == "__main__":
    unittest.main()
