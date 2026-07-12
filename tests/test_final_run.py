"""Proves the final-run report classifies every outcome correctly (never
claims SYSTEM_SUCCESS unless Video CEO Pro's real on-disk decision is
ÇEK), never crashes on missing data, and reports which stage failed."""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import final_run


class ClassifyTests(unittest.TestCase):
    def test_missing_stages_blocks(self):
        status, reasons = final_run.classify(["video-ceo"], {}, {}, {}, {}, {})
        self.assertEqual(status, "BLOCKED_MISSING_DATA")

    def test_missing_niche_winner_blocks(self):
        status, _ = final_run.classify([], {}, {}, {"status": "REJECT"}, {"decision": "DUR"}, {})
        self.assertEqual(status, "BLOCKED_MISSING_DATA")

    def test_video_ceo_beklet_blocks(self):
        status, _ = final_run.classify(
            [], {"winner": {"niche": "x"}}, {}, {"status": "REJECT"},
            {"decision": "BEKLET — VERİ EKSİK"}, {},
        )
        self.assertEqual(status, "BLOCKED_MISSING_DATA")

    def test_technical_failure_on_invalid_script_status(self):
        status, _ = final_run.classify(
            [], {"winner": {"niche": "x"}}, {}, {"status": "GARBAGE"}, {"decision": "DUR"}, {},
        )
        self.assertEqual(status, "TECHNICAL_FAILURE")

    def test_technical_failure_on_video_engine_technical_failure(self):
        status, _ = final_run.classify(
            [], {"winner": {"niche": "x"}}, {}, {"status": "REJECT"}, {"decision": "DUR"},
            {"status": "TECHNICAL_FAILURE", "reasons": ["ffmpeg crashed"]},
        )
        self.assertEqual(status, "TECHNICAL_FAILURE")

    def test_quality_reject_on_honest_dur(self):
        status, _ = final_run.classify(
            [], {"winner": {"niche": "x"}}, {}, {"status": "REJECT"}, {"decision": "DUR"}, {},
        )
        self.assertEqual(status, "QUALITY_REJECT")

    def test_quality_reject_on_duzelt(self):
        status, _ = final_run.classify(
            [], {"winner": {"niche": "x"}}, {}, {"status": "APPROVE"}, {"decision": "DÜZELT"}, {},
        )
        self.assertEqual(status, "QUALITY_REJECT")

    def test_system_success_only_on_real_cek(self):
        status, reasons = final_run.classify(
            [], {"winner": {"niche": "x"}}, {}, {"status": "APPROVE"}, {"decision": "ÇEK"}, {},
        )
        self.assertEqual(status, "SYSTEM_SUCCESS")
        self.assertTrue(any("ÇEK" in r for r in reasons))

    def test_invalid_video_ceo_decision_is_technical_failure_not_success(self):
        status, _ = final_run.classify(
            [], {"winner": {"niche": "x"}}, {}, {"status": "APPROVE"}, {"decision": "MAYBE"}, {},
        )
        self.assertEqual(status, "TECHNICAL_FAILURE")


class NextActionTests(unittest.TestCase):
    def test_success_action_mentions_final_video_when_rendered(self):
        action = final_run.next_action_for_osman(
            "SYSTEM_SUCCESS", {}, {"status": "RENDERED", "final_video": "projects/video-engine/final_video.mp4"}, {"status": "DRY_RUN_OK"},
        )
        self.assertIn("final_video.mp4", action)
        self.assertIn("PRIVATE_UPLOAD", action)

    def test_success_action_mentions_credentials_when_upload_not_configured(self):
        action = final_run.next_action_for_osman(
            "SYSTEM_SUCCESS", {}, {"status": "RENDERED", "final_video": "x.mp4"}, {"status": "UPLOAD_NOT_CONFIGURED"},
        )
        self.assertIn("secret", action.lower())

    def test_quality_reject_action_includes_real_reasons(self):
        action = final_run.next_action_for_osman(
            "QUALITY_REJECT", {"reasons": ["İlk 3 saniye zayıf."]}, {}, {},
        )
        self.assertIn("İlk 3 saniye zayıf.", action)

    def test_blocked_action_is_actionable(self):
        action = final_run.next_action_for_osman("BLOCKED_MISSING_DATA", {}, {}, {})
        self.assertTrue(action.strip())


class MainFlowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.projects = self.tmp / "projects"
        self.projects.mkdir()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.patches = []
        for name, attr in [("ROOT", self.projects), ("OUTPUT_DIR", self.projects / "final-run")]:
            p = mock.patch.object(final_run, name, attr)
            p.start()
            self.patches.append(p)
        self.addCleanup(lambda: [p.stop() for p in self.patches])

    def _write(self, relpath: str, data) -> None:
        path = self.projects / relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def test_no_data_at_all_reports_blocked_never_crashes(self):
        with mock.patch.object(final_run, "REQUIRED_STAGE_FILES", {
            name: self.projects / Path(p).name for name, p in {
                "channel-health": "channel-health/analysis.json", "competitor-health": "competitor-health/analysis.json",
                "niche-intelligence": "niche-intelligence/analysis.json", "ceo-decision": "ceo-decision/analysis.json",
                "growth-advisor": "growth-advisor/analysis.json", "script-agent": "script-agent/script.json",
                "video-ceo": "video-ceo/analysis.json", "voiceover": "voiceover/audio_manifest.json",
                "video-engine": "video-engine/render_manifest.json", "youtube-upload": "youtube-upload/upload_result.json",
                "learning-engine": "learning-engine/memory.json",
            }.items()
        }):
            final_run.main()
        analysis = json.loads((self.projects / "final-run" / "analysis.json").read_text(encoding="utf-8"))
        self.assertEqual(analysis["status"], "BLOCKED_MISSING_DATA")

    def test_full_success_run_produces_correct_summary(self):
        stage_files = {
            "channel-health": self.projects / "channel-health" / "analysis.json",
            "competitor-health": self.projects / "competitor-health" / "analysis.json",
            "niche-intelligence": self.projects / "niche-intelligence" / "analysis.json",
            "ceo-decision": self.projects / "ceo-decision" / "analysis.json",
            "growth-advisor": self.projects / "growth-advisor" / "analysis.json",
            "script-agent": self.projects / "script-agent" / "script.json",
            "video-ceo": self.projects / "video-ceo" / "analysis.json",
            "voiceover": self.projects / "voiceover" / "audio_manifest.json",
            "video-engine": self.projects / "video-engine" / "render_manifest.json",
            "youtube-upload": self.projects / "youtube-upload" / "upload_result.json",
            "learning-engine": self.projects / "learning-engine" / "memory.json",
        }
        for name in stage_files:
            self._write(f"{name}/{'script.json' if name == 'script-agent' else ('analysis.json' if name in {'channel-health','competitor-health','niche-intelligence','ceo-decision','growth-advisor','video-ceo'} else ('audio_manifest.json' if name == 'voiceover' else ('render_manifest.json' if name == 'video-engine' else ('upload_result.json' if name == 'youtube-upload' else 'memory.json'))))}", {})

        self._write("niche-intelligence/analysis.json", {"winner": {"niche": "Zehirli Bitkiler"}})
        self._write("ceo-decision/analysis.json", {"topic": "Zehirli Bitkilerin Tarihi", "missing_inputs": []})
        self._write("script-agent/script.json", {
            "status": "APPROVE", "script": {"title": "Test Başlık"}, "ceo_review": {"ceo_score": 90},
        })
        self._write("video-ceo/analysis.json", {"decision": "ÇEK", "video_ceo_score": 88, "reasons": ["ok"]})
        self._write("video-engine/render_manifest.json", {"status": "RENDERED", "final_video": "projects/video-engine/final_video.mp4"})
        self._write("youtube-upload/upload_result.json", {"status": "DRY_RUN_OK"})

        with mock.patch.object(final_run, "REQUIRED_STAGE_FILES", stage_files):
            final_run.main()

        analysis = json.loads((self.projects / "final-run" / "analysis.json").read_text(encoding="utf-8"))
        self.assertEqual(analysis["status"], "SYSTEM_SUCCESS")
        self.assertEqual(analysis["selected_niche"], "Zehirli Bitkiler")
        self.assertEqual(analysis["video_ceo_decision"], "ÇEK")
        self.assertEqual(analysis["production_status"], "RENDERED")
        self.assertIn("final_video.mp4", analysis["next_action_for_osman"])


if __name__ == "__main__":
    unittest.main()
