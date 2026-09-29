"""End-to-end pipeline tests on the generated synthetic dataset."""

import csv
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.ingest import load_surveys  # noqa: E402
from src.interpreter import analyze  # noqa: E402
from src.report import summarize  # noqa: E402

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestPipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.surveys = load_surveys()
        cls.results = analyze(cls.surveys)
        cls.by_id = {r.survey_id: r for r in cls.results}

    def test_all_surveys_analyzed(self):
        self.assertEqual(len(self.results), len(self.surveys))
        self.assertGreater(len(self.results), 50)

    def test_fixture_statuses(self):
        by_id = self.by_id
        self.assertEqual(by_id["s_chase8"].interpretation_status, "score_comment_conflict")
        self.assertTrue(by_id["s_chase8"].tier_crossed)
        self.assertEqual(by_id["s_rev10"].interpretation_status, "score_comment_conflict")
        self.assertEqual(by_id["s_fail2"].interpretation_status,
                         "consistent_with_official_treatment")
        self.assertEqual(by_id["s_pass10"].interpretation_status,
                         "consistent_with_official_treatment")
        self.assertEqual(by_id["s_empty8"].interpretation_status,
                         "insufficient_text_evidence")

    def test_every_result_has_required_fields(self):
        for r in self.results:
            self.assertIn(r.official_treatment, ("PASS", "FAIL"))
            self.assertIn(r.interpretation_status, (
                "score_comment_conflict", "consistent_with_official_treatment",
                "insufficient_text_evidence", "text_inconclusive"))
            self.assertIsNotNone(r.scorecard_after_pct)
            self.assertIn(r.tier_after, ("gold", "silver", "none"))

    def test_summary_counts(self):
        summary = summarize(self.results)
        self.assertEqual(summary["n_surveys"], len(self.results))
        self.assertIn("downtown", summary["branch_summary"])
        self.assertGreaterEqual(len(summary["conflicts"]), 2)

    def test_csv_columns(self):
        with open(os.path.join(BASE, "data", "analyzed_surveys.csv"), newline="",
                  encoding="utf-8") as fh:
            header = next(csv.reader(fh))
        for col in ("official_treatment", "interpretation_status",
                    "scorecard_before_pct", "scorecard_after_pct",
                    "scorecard_delta_pp", "tier_before", "tier_after",
                    "tier_crossed", "conflict_flag", "needs_human_review", "reason"):
            self.assertIn(col, header)


if __name__ == "__main__":
    unittest.main()
