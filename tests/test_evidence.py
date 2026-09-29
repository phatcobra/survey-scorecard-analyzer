"""Text-evidence tests: resolution signal, themes, blank comments."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.evidence import _resolution_signal, extract_evidence  # noqa: E402
from src.sentiment import RuleBasedProvider  # noqa: E402

PROVIDER = RuleBasedProvider()


def ev_for(comment):
    return extract_evidence(
        comment, PROVIDER.analyze_batch([comment])[0])


class TestResolution(unittest.TestCase):
    def test_resolved(self):
        self.assertEqual(_resolution_signal("Excellent service and took care of all my needs."),
                         "resolved")
        self.assertEqual(_resolution_signal("Issue resolved, all fixed."), "resolved")

    def test_unresolved_wins_over_substring(self):
        # "never resolved" contains "resolved" -- unresolved must win.
        self.assertEqual(_resolution_signal("My issue was never resolved."),
                         "unresolved")
        self.assertEqual(_resolution_signal("They did not help with my issue at all."),
                         "unresolved")
        self.assertEqual(_resolution_signal("Still waiting for a callback."),
                         "unresolved")

    def test_unknown(self):
        self.assertEqual(_resolution_signal("It was fine."), "unknown")


class TestEvidence(unittest.TestCase):
    def test_blank_comment(self):
        ev = ev_for("")
        self.assertFalse(ev.has_text)
        self.assertEqual(ev.sentiment_status, "unavailable")
        self.assertIsNone(ev.sentiment_label)

    def test_themes_follow_polarity(self):
        pos = ev_for("Excellent service, quick and professional.")
        self.assertNotEqual(pos.positive_themes, ())
        self.assertEqual(pos.negative_themes, ())
        neg = ev_for("Terrible experience, rude teller, they did not help with my issue at all.")
        self.assertNotEqual(neg.negative_themes, ())
        self.assertEqual(neg.positive_themes, ())


if __name__ == "__main__":
    unittest.main()
