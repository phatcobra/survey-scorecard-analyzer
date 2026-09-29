"""Pipeline entry point: ingest -> sentiment -> evidence -> scorecard -> interpret.

Usage:
  python3 src/main.py                          # rule-based sentiment (default)
  python3 src/main.py --sentiment comprehend   # Amazon Comprehend (needs AWS creds)
"""

from __future__ import annotations

import argparse
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.ingest import load_surveys  # noqa: E402
from src.interpreter import analyze  # noqa: E402
from src.report import render_text, summarize  # noqa: E402
from src.sentiment import ComprehendProvider, RuleBasedProvider  # noqa: E402

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

COLUMNS = [
    "survey_id", "branch", "teller", "score", "comment", "timestamp",
    "cohort",
    "official_treatment",
    "has_text", "sentiment_status", "sentiment_label",
    "positive_themes", "negative_themes", "resolution",
    "interpretation_status",
    "scorecard_before_pct", "scorecard_after_pct", "scorecard_delta_pp",
    "tier_before", "tier_after", "tier_crossed",
    "conflict_flag", "needs_human_review", "reason",
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sentiment", choices=["rules", "comprehend"],
                        default="rules")
    parser.add_argument("--region", default="us-east-1")
    args = parser.parse_args()

    if args.sentiment == "comprehend":
        try:
            provider = ComprehendProvider(region=args.region)
        except ImportError:
            sys.exit("boto3 is required for --sentiment comprehend: pip install boto3")
        print(f"Sentiment provider: Amazon Comprehend ({args.region})")
    else:
        provider = RuleBasedProvider()
        print("Sentiment provider: rule-based lexicon (default)")

    input_path = os.path.join(BASE, "data", "surveys.csv")
    output_path = os.path.join(BASE, "data", "analyzed_surveys.csv")
    report_path = os.path.join(BASE, "data", "report.txt")

    surveys = load_surveys(input_path)
    results = analyze(surveys, provider=provider)
    summary = summarize(results)

    with open(output_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(COLUMNS)
        for r in results:
            writer.writerow([
                r.survey_id, r.branch, r.teller, r.score, r.comment, r.timestamp,
                r.cohort,
                r.official_treatment,
                r.has_text, r.sentiment_status, r.sentiment_label,
                ";".join(r.positive_themes), ";".join(r.negative_themes),
                r.resolution,
                r.interpretation_status,
                r.scorecard_before_pct, r.scorecard_after_pct, r.scorecard_delta_pp,
                r.tier_before, r.tier_after, r.tier_crossed,
                r.conflict_flag, r.needs_human_review, r.reason,
            ])

    report = render_text(summary)
    with open(report_path, "w", encoding="utf-8") as fh:
        fh.write(report + "\n")

    print(report)
    print(f"\nWrote {output_path}")
    print(f"Wrote {report_path}")


if __name__ == "__main__":
    main()
