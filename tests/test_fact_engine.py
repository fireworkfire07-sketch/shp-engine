"""Proves the Fact Engine actually flags unsupported claims instead of
just reporting a heading that says it does."""

from __future__ import annotations

import unittest

from script_agent_v2.engines import fact_engine


class FactEngineTests(unittest.TestCase):
    def test_unsupported_claim_is_flagged_low_confidence(self):
        ledger = [{"text": "İpek Yolu ticareti MÖ 130 yılında başladı.", "category": "tarihsel", "confidence": "orta"}]
        sections = [{
            "name": "Köken",
            "voiceover": "Bu bitki 1850 yılında keşfedildi ve hiçbir kaynakta doğrulanmamıştır.",
        }]
        result = fact_engine.evaluate(sections, ledger)
        self.assertGreaterEqual(result["unverified_claim_count"], 1)
        note = result["section_notes"][0]["claims"][0]
        self.assertEqual(note["confidence"], "düşük")
        self.assertEqual(note["source_basis"], "doğrulanmamış")
        self.assertLess(result["overall_score"], 100)

    def test_claim_matching_ledger_is_not_flagged_unverified(self):
        ledger = [{"text": "İpek Yolu ticareti MÖ 130 yılında başladı ve Asya'yı Avrupa'ya bağladı.", "category": "tarihsel", "confidence": "yüksek"}]
        sections = [{
            "name": "Köken",
            "voiceover": "İpek Yolu ticareti MÖ 130 yılında başladı ve Asya'yı Avrupa'ya bağladı.",
        }]
        result = fact_engine.evaluate(sections, ledger)
        self.assertEqual(result["unverified_claim_count"], 0)
        self.assertEqual(result["overall_score"], 100)

    def test_hedged_claim_without_ledger_match_is_not_counted_unverified(self):
        ledger: list[dict] = []
        sections = [{"name": "Köken", "voiceover": "Kaynaklara göre, bu olay 1750 yılında yaşanmış olabilir."}]
        result = fact_engine.evaluate(sections, ledger)
        self.assertEqual(result["unverified_claim_count"], 0)

    def test_ledger_never_invents_facts_it_only_reshapes_knowledge_output(self):
        knowledge = {
            "facts": [{"text": "X olayı 1900'de gerçekleşti.", "category": "tarihsel", "confidence": "yüksek"}],
            "timeline": [{"date": "1905", "event": "Y keşfedildi."}],
        }
        ledger = fact_engine.build_ledger(knowledge)
        texts = [entry["text"] for entry in ledger]
        self.assertIn("X olayı 1900'de gerçekleşti.", texts)
        self.assertTrue(any("1905" in text for text in texts))
        self.assertEqual(len(ledger), 2)  # exactly what knowledge provided, nothing invented


if __name__ == "__main__":
    unittest.main()
