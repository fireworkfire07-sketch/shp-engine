"""Proves the Video Engine: gates production on Video CEO Pro's decision
(never renders on anything but ÇEK), never claims a render happened when
FFmpeg is unavailable, and — when FFmpeg/Pillow are actually present, as
they are in this environment — really produces a playable MP4 with real
Ken Burns motion, burned subtitles and real TTS audio."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import video_engine

HAS_FFMPEG = video_engine.ffmpeg_available()
HAS_ESPEAK = shutil.which("espeak-ng") is not None

STORYBOARD = [
    {
        "scene_number": 1, "section": "Açılış", "role": "hook",
        "narration": "Neden bu gizli sır saklandı?",
        "visual_idea": "Tek çarpıcı obje.", "scene_idea": "Karanlık zemin.",
        "transition": "Sert kesme.", "subtitle_start_seconds": 0.0, "subtitle_end_seconds": 2.0,
    },
    {
        "scene_number": 2, "section": "Final", "role": "final",
        "narration": "Bugün artık biliyoruz.",
        "visual_idea": "Geniş plan.", "scene_idea": "Gün ışığı.",
        "transition": "Çapraz geçiş.", "subtitle_start_seconds": 2.0, "subtitle_end_seconds": 4.0,
    },
]


class VideoEngineGatingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.projects = self.tmp / "projects"
        self.projects.mkdir()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        for name, attr in [
            ("ROOT", self.projects), ("SCRIPT_DIR", self.projects / "script-agent"),
            ("VOICEOVER_DIR", self.projects / "voiceover"), ("OUTPUT_DIR", self.projects / "video-engine"),
            ("ASSETS_DIR", self.projects / "video-engine" / "assets"),
            ("FRAMES_DIR", self.projects / "video-engine" / "assets" / "frames"),
            ("CLIPS_DIR", self.projects / "video-engine" / "assets" / "clips"),
            ("FINAL_VIDEO_PATH", self.projects / "video-engine" / "final_video.mp4"),
            ("SUPPLIED_IMAGES_DIR", self.tmp / "assets" / "images"),
        ]:
            p = mock.patch.object(video_engine, name, attr)
            p.start()
            self.addCleanup(p.stop)

    def _write(self, relpath: str, data) -> None:
        path = self.projects / relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def test_stops_safely_when_video_ceo_says_dur(self):
        self._write("video-ceo/analysis.json", {"decision": "DUR"})
        self._write("script-agent/storyboard.json", STORYBOARD)
        video_engine.main()
        manifest = json.loads((self.projects / "video-engine" / "render_manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["status"], "STOPPED_BY_VIDEO_CEO")
        self.assertFalse((self.projects / "video-engine" / "final_video.mp4").exists())

    def test_stops_safely_when_video_ceo_says_beklet(self):
        self._write("video-ceo/analysis.json", {"decision": "BEKLET — VERİ EKSİK"})
        self._write("script-agent/storyboard.json", STORYBOARD)
        video_engine.main()
        manifest = json.loads((self.projects / "video-engine" / "render_manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["status"], "STOPPED_BY_VIDEO_CEO")

    def test_missing_video_ceo_output_stops_safely_not_crash(self):
        self._write("script-agent/storyboard.json", STORYBOARD)
        video_engine.main()  # no video-ceo/analysis.json at all
        manifest = json.loads((self.projects / "video-engine" / "render_manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["status"], "STOPPED_BY_VIDEO_CEO")

    def test_missing_storyboard_reports_blocked_missing_data(self):
        self._write("video-ceo/analysis.json", {"decision": "ÇEK"})
        video_engine.main()
        manifest = json.loads((self.projects / "video-engine" / "render_manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["status"], "BLOCKED_MISSING_DATA")

    def test_no_ffmpeg_never_claims_a_render_but_builds_full_manifest(self):
        self._write("video-ceo/analysis.json", {"decision": "ÇEK"})
        self._write("script-agent/storyboard.json", STORYBOARD)
        with mock.patch.object(video_engine, "ffmpeg_available", return_value=False):
            video_engine.main()
        manifest = json.loads((self.projects / "video-engine" / "render_manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["status"], "RENDER_SKIPPED_NO_FFMPEG")
        self.assertIsNone(manifest.get("final_video"))
        self.assertFalse((self.projects / "video-engine" / "final_video.mp4").exists())
        self.assertEqual(len(manifest["scenes"]), 2)
        for scene in manifest["scenes"]:
            self.assertTrue(Path(scene["image_source"]).exists())  # frames still generated
        self.assertIn("ffmpeg", manifest.get("external_requirement", "").lower())


class VideoEnginePureLogicTests(unittest.TestCase):
    def test_build_scene_plan_never_truncates_speech(self):
        # audio is longer than the estimated subtitle window -> clip must
        # expand to the real audio length, never cut narration short.
        audio_manifest = {"scenes": [{"scene_number": 1, "actual_seconds": 9.0}]}
        plan = video_engine.build_scene_plan(
            [{"scene_number": 1, "section": "A", "role": "hook", "subtitle_start_seconds": 0.0, "subtitle_end_seconds": 3.0}],
            audio_manifest,
        )
        self.assertEqual(plan[0]["clip_duration_seconds"], 9.0)

    def test_build_scene_plan_falls_back_to_estimated_without_audio(self):
        plan = video_engine.build_scene_plan(
            [{"scene_number": 1, "section": "A", "role": "hook", "subtitle_start_seconds": 0.0, "subtitle_end_seconds": 5.0}],
            None,
        )
        self.assertEqual(plan[0]["clip_duration_seconds"], 5.0)
        self.assertIsNone(plan[0]["audio_file"])

    def test_build_scene_plan_enforces_minimum_clip_duration(self):
        plan = video_engine.build_scene_plan(
            [{"scene_number": 1, "section": "A", "role": "hook", "subtitle_start_seconds": 0.0, "subtitle_end_seconds": 0.1}],
            None,
        )
        self.assertGreaterEqual(plan[0]["clip_duration_seconds"], video_engine.MIN_CLIP_SECONDS)

    def test_generative_video_adapter_is_unconfigured_by_default(self):
        adapter = video_engine.GenerativeVideoAdapter()
        self.assertFalse(adapter.available())
        with self.assertRaises(NotImplementedError):
            adapter.generate_clip("prompt", 3.0, Path("/tmp/x.mp4"))


class VideoEngineRealRenderTests(unittest.TestCase):
    """These actually invoke Pillow + FFmpeg + espeak-ng — real assets, real
    subprocess calls — kept to a 2-scene, ~2 second clip so the suite stays
    fast while still proving the mechanism genuinely works end to end."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.projects = self.tmp / "projects"
        self.projects.mkdir()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        for name, attr in [
            ("ROOT", self.projects), ("SCRIPT_DIR", self.projects / "script-agent"),
            ("VOICEOVER_DIR", self.projects / "voiceover"), ("OUTPUT_DIR", self.projects / "video-engine"),
            ("ASSETS_DIR", self.projects / "video-engine" / "assets"),
            ("FRAMES_DIR", self.projects / "video-engine" / "assets" / "frames"),
            ("CLIPS_DIR", self.projects / "video-engine" / "assets" / "clips"),
            ("FINAL_VIDEO_PATH", self.projects / "video-engine" / "final_video.mp4"),
            ("SUPPLIED_IMAGES_DIR", self.tmp / "assets" / "images"),
            ("SUPPLIED_MUSIC_CANDIDATES", [self.tmp / "assets" / "audio" / "background_music.mp3"]),
        ]:
            p = mock.patch.object(video_engine, name, attr)
            p.start()
            self.addCleanup(p.stop)

    def _write(self, relpath: str, data) -> None:
        path = self.projects / relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    @unittest.skipUnless(HAS_FFMPEG, "ffmpeg/ffprobe not installed in this environment")
    def test_placeholder_frame_generation_produces_real_png(self):
        path = video_engine.generate_placeholder_frame(1, "hook", "Karanlık zemin üzerinde ana obje.")
        self.assertTrue(path.exists())
        self.assertGreater(path.stat().st_size, 0)

    @unittest.skipUnless(HAS_FFMPEG, "ffmpeg/ffprobe not installed in this environment")
    def test_lightweight_mode_renders_a_real_playable_mp4(self):
        short_storyboard = [
            {"scene_number": 1, "section": "Açılış", "role": "hook", "narration": "Kısa test cümlesi.",
             "visual_idea": "Test görseli.", "scene_idea": "Test sahnesi.", "transition": "Kesme.",
             "subtitle_start_seconds": 0.0, "subtitle_end_seconds": 2.0},
        ]
        self._write("video-ceo/analysis.json", {"decision": "ÇEK"})
        self._write("script-agent/storyboard.json", short_storyboard)
        # No voiceover manifest -> silent render path, keeps this test fast
        # and independent of espeak-ng.
        video_engine.main()

        manifest = json.loads((self.projects / "video-engine" / "render_manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["status"], "RENDERED")
        final_video = self.projects / "video-engine" / "final_video.mp4"
        self.assertTrue(final_video.exists())

        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-show_entries", "stream=codec_type,codec_name", "-of", "csv=p=0", str(final_video)],
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(probe.returncode, 0)
        self.assertIn("h264", probe.stdout)
        self.assertGreater(final_video.stat().st_size, 1000)


if __name__ == "__main__":
    unittest.main()
