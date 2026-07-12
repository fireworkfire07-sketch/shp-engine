"""Proves the Decision Engine actually blocks off-niche topics rather than
just listing keywords that are never checked."""

from __future__ import annotations

import unittest

import decision_engine_v2 as decision_engine


class DecisionEngineOffNicheTests(unittest.TestCase):
    def test_off_niche_topic_is_blocked(self):
        score, reasons = decision_engine.topic_fit_score("Yapay Zeka Haberleri Bugün Ne Oldu?", "")
        self.assertEqual(score, 0)
        self.assertTrue(any("engellendi" in reason for reason in reasons))

    def test_on_theme_topic_scores_positively(self):
        score, reasons = decision_engine.topic_fit_score(
            "Zehirli Bitkilerin Gizli Tarihi", "bitki gizem tarih doga"
        )
        self.assertGreater(score, 0)

    def test_choose_topic_rejects_all_off_niche_candidates(self):
        batch = [
            {"topic": "Kripto Para Haberleri", "niche_score": 90},
            {"topic": "Minecraft En İyi Anlar", "niche_score": 85},
        ]
        topic, score, reasons, fit_score = decision_engine.choose_topic(batch, {})
        # every candidate was off-niche -> falls back to the channel's fixed theme
        self.assertEqual(fit_score, 100)
        self.assertTrue(any("elendi" in reason or "sabit" in reason for reason in reasons))

    def test_choose_topic_picks_on_niche_candidate_over_off_niche(self):
        batch = [
            {"topic": "Kripto Para Haberleri", "niche_score": 99},
            {"topic": "Zehirli Bitkilerin Gizli Tarihi", "niche_score": 40},
        ]
        topic, score, reasons, fit_score = decision_engine.choose_topic(batch, {})
        self.assertEqual(topic, "Zehirli Bitkilerin Gizli Tarihi")


if __name__ == "__main__":
    unittest.main()
