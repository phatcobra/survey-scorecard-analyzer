"""CSV ingestion for surveys."""

from __future__ import annotations

import csv
import os

from .schemas import Survey

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

EXPECTED = ["survey_id", "branch", "teller", "score", "comment", "timestamp"]


def load_surveys(path: str | None = None) -> list[Survey]:
    path = path or os.path.join(BASE, "data", "surveys.csv")
    surveys = []
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            surveys.append(Survey(
                survey_id=row["survey_id"],
                branch=row["branch"],
                teller=row["teller"],
                score=int(row["score"]),
                comment=row["comment"],
                timestamp=row["timestamp"],
                cohort=row.get("cohort") or "new_way",
            ))
    return surveys
