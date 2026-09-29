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
                "insufficient_text_evidence", "text_inconclusive",
                "not_screened"))
            self.assertIn(r.cohort, ("old_way", "new_way"))
            self.assertIsNotNone(r.scorecard_after_pct)
            self.assertIn(r.tier_after, ("gold", "silver", "none"))

    def test_old_way_cohort_is_never_screened(self):
        old = [r for r in self.results if r.cohort == "old_way"]
        new = [r for r in self.results if r.cohort == "new_way"]
        self.assertGreater(len(old), 0)
        self.assertGreater(len(new), 0)
        for r in old:
            self.assertEqual(r.interpretation_status, "not_screened")
            self.assertFalse(r.conflict_flag)
            self.assertFalse(r.needs_human_review)
            # The old way still has the scorecard: impact math is intact.
            self.assertIsNotNone(r.scorecard_after_pct)
        # New-way cohort actually screens: some conflicts must surface.
        self.assertGreater(
            sum(1 for r in new
                if r.interpretation_status == "score_comment_conflict"), 0)

    def test_cohort_branch_counts(self):
        branches = {}
        for r in self.results:
            branches.setdefault(r.cohort, set()).add(r.branch)
        self.assertEqual(len(branches["old_way"]), 50)
        self.assertEqual(len(branches["new_way"]), 50)

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
