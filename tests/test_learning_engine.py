"""Proves the Learning Engine learns real structural patterns (never
verbatim wording), always marks YouTube Analytics data unavailable (no
OAuth exists anywhere in this system), persists history across runs, and
that its lessons are actually consumed downstream — not just written to a
file nobody reads."""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import learning_engine
import niche_intelligence
import video_ceo
from script_agent_v2 import context as context_module

OWN_VIDEOS = [
    {"title": "Neden Bu Bitki Yasaklandı?", "views_per_day": 500, "privacy_status": "public"},
    {"title": "Bu Gizli Sır Nasıl Saklandı?", "views_per_day": 300, "privacy_status": "public"},
    {"title": "Bitkiler Hakkında Genel Bilgiler", "views_per_day": 10, "privacy_status": "public"},
]


class LearningEngineAnalysisTests(unittest.TestCase):
    def test_analytics_always_marked_unavailable_never_invented(self):
        analytics = learning_engine.analytics_availability()
        for key in ("ctr", "average_view_duration", "audience_retention"):
            self.assertIn("kullanılamıyor", analytics[key])

    def test_title_pattern_analysis_never_stores_raw_titles(self):
        result = learning_engine.analyze_title_patterns(OWN_VIDEOS)
        self.assertTrue(result["available"])
        serialized = json.dumps(result, ensure_ascii=False)
        for video in OWN_VIDEOS:
            self.assertNotIn(video["title"], serialized)  # structure only, never the wording

    def test_title_pattern_analysis_correlates_category_with_real_performance(self):
        result = learning_engine.analyze_title_patterns(OWN_VIDEOS)
        self.assertIn("soru", result["by_category"])
        self.assertGreater(result["by_category"]["soru"]["average_views_per_day"], 0)

    def test_no_public_videos_reports_unavailable_honestly(self):
        result = learning_engine.analyze_title_patterns([])
        self.assertFalse(result["available"])
        self.assertTrue(result["reason"])

    def test_trend_requires_at_least_two_data_points(self):
        history = {"gizem": [100.0]}
        lessons = learning_engine.build_lessons({}, {}, history)
        self.assertNotIn("gizem", lessons["trigger_category_trend"])
        history = {"gizem": [100.0, 150.0]}
        lessons = learning_engine.build_lessons({}, {}, history)
        self.assertEqual(lessons["trigger_category_trend"]["gizem"], "yükseliyor")


class LearningEngineMainFlowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.projects = self.tmp / "projects"
        self.projects.mkdir()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        for name, attr in [
            ("ROOT", self.projects), ("OUTPUT_DIR", self.projects / "learning-engine"),
            ("MEMORY_PATH", self.projects / "learning-engine" / "memory.json"),
        ]:
            p = mock.patch.object(learning_engine, name, attr)
            p.start()
            self.addCleanup(p.stop)

    def _write(self, relpath: str, data) -> None:
        path = self.projects / relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def test_runs_with_no_data_at_all_never_crashes(self):
        learning_engine.main()
        memory = json.loads((self.projects / "learning-engine" / "memory.json").read_text(encoding="utf-8"))
        self.assertEqual(memory["lessons"]["best_title_trigger_category"], None)

    def test_history_persists_and_accumulates_across_runs(self):
        self._write("channel-health/analysis.json", {"top_videos": OWN_VIDEOS, "bottom_videos": []})
        learning_engine.main()
        learning_engine.main()  # second run should append, not overwrite
        memory = json.loads((self.projects / "learning-engine" / "memory.json").read_text(encoding="utf-8"))
        self.assertEqual(len(memory["runs"]), 2)
        self.assertEqual(len(memory["trigger_category_performance"]["soru"]), 2)


class LessonsAreActuallyConsumedTests(unittest.TestCase):
    """The non-negotiable rule: a lesson only counts if it reaches a real
    input and affects a real downstream output — not just written to disk."""

    def test_niche_intelligence_candidate_queries_change_with_lessons(self):
        with mock.patch.object(niche_intelligence, "LEARNING_ENGINE_MEMORY", Path("/nonexistent/memory.json")):
            baseline = set(niche_intelligence.candidate_queries())

        tmp = Path(tempfile.mkdtemp())
        memory_path = tmp / "memory.json"
        memory_path.write_text(json.dumps({"lessons": {"best_title_trigger_category": "servet"}}), encoding="utf-8")
        with mock.patch.object(niche_intelligence, "LEARNING_ENGINE_MEMORY", memory_path):
            with_lessons = set(niche_intelligence.candidate_queries())

        self.assertNotEqual(baseline, with_lessons)
        self.assertTrue(any("imparatorluk" in q for q in with_lessons))

    def test_script_agent_context_carries_channel_lessons_through(self):
        tmp = Path(tempfile.mkdtemp())
        (tmp / "learning-engine").mkdir()
        memory_path = tmp / "learning-engine" / "memory.json"
        memory_path.write_text(json.dumps({"lessons": {"best_title_trigger_category": "gizem"}}), encoding="utf-8")
        with mock.patch.object(context_module, "LEARNING_ENGINE_MEMORY_PATH", memory_path), \
             mock.patch.object(context_module, "ROOT", tmp), \
             mock.patch.object(context_module, "OUTPUT_DIR", tmp / "script-agent"), \
             mock.patch.object(context_module, "MEMORY_PATH", tmp / "script-agent" / "memory.json"):
            (tmp / "script-agent").mkdir(exist_ok=True)
            ctx = context_module.build_context()
        self.assertEqual(ctx.channel_lessons["best_title_trigger_category"], "gizem")
        self.assertIn("channel_lessons", ctx.as_dict())

    def test_video_ceo_historical_note_reflects_real_lesson(self):
        tmp = Path(tempfile.mkdtemp())
        (tmp / "learning-engine").mkdir()
        memory_path = tmp / "learning-engine" / "memory.json"
        memory_path.write_text(json.dumps({"lessons": {"best_title_trigger_category": "gizem"}}), encoding="utf-8")
        with mock.patch.object(video_ceo, "LEARNING_ENGINE_MEMORY", memory_path):
            matching = video_ceo.historical_pattern_note("Bu Gizli Sır Nasıl Saklandı?")
            not_matching = video_ceo.historical_pattern_note("Bugün Hava Nasıl Olacak?")
        self.assertIn("gizem", matching)
        self.assertIn("Uyarı", not_matching)

    def test_video_ceo_note_absent_when_no_lessons_yet(self):
        with mock.patch.object(video_ceo, "LEARNING_ENGINE_MEMORY", Path("/nonexistent/memory.json")):
            self.assertIsNone(video_ceo.historical_pattern_note("Herhangi Bir Başlık"))


if __name__ == "__main__":
    unittest.main()
