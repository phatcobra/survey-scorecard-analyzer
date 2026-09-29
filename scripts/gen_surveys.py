"""Deterministic synthetic survey data (seed=42). All fictional.

Planted fixtures (branch "downtown"):
  s_chase8 .... the motivating scenario: branch sits at 95.83% (gold) on 24
                surveys; an 8/10 reading "Excellent service and took care of
                all my needs." drops it to 92.0% (silver) — a gold->silver
                tier crossing on a survey whose text describes good service.
  s_rev10 ..... reverse conflict: 10/10 with a negative, unresolved comment.
  s_fail2 ..... consistent FAIL: 2/10 with a negative comment.
  s_pass10 .... consistent PASS: 10/10 with a positive comment.
  s_empty8 .... 8/10 with a blank comment: insufficient_text_evidence.

Plus random background surveys for tellers at "downtown" and "uptown".
Rows are deliberately shuffled out of chronological order in the CSV.
"""

from __future__ import annotations

import csv
import os
import random
from datetime import datetime, timedelta

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEED = 42

POSITIVE_COMMENTS = [
    "Excellent service, quick and professional.",
    "Great experience, the teller was friendly and knowledgeable.",
    "Very satisfied, everything was handled efficiently.",
    "Wonderful service, all my questions were answered clearly.",
    "Perfect visit, fast and courteous.",
]
NEGATIVE_COMMENTS = [
    "Terrible wait, nobody helped me.",
    "Rude service and my issue was never resolved.",
    "Awful experience, still waiting for a callback.",
    "Very disappointed, the teller was confusing and slow.",
    "Horrible, I was ignored for too long.",
]
NEUTRAL_COMMENTS = [
    "Standard visit, nothing special.",
    "It was fine.",
    "Average service today.",
]


def _row(rng, sid, branch, teller, score, comment, ts):
    return {
        "survey_id": sid, "branch": branch, "teller": teller,
        "score": score, "comment": comment,
        "timestamp": ts.isoformat(timespec="seconds"),
    }


def main() -> None:
    rng = random.Random(SEED)
    rows = []
    t0 = datetime(2026, 1, 5, 9, 0, 0)
    tellers_dt = [f"teller_{i:02d}" for i in range(1, 6)]
    sid = 0

    def nxt():
        nonlocal sid
        sid += 1
        return f"s{sid:04d}"

    # --- downtown background: 24 surveys, 23 pass -> 95.83% (gold) ---
    ts = t0
    for i in range(24):
        ts += timedelta(days=rng.randint(1, 3), hours=rng.randint(0, 6))
        if i == 7:
            score, comment = 7, rng.choice(NEGATIVE_COMMENTS)  # the lone fail
        else:
            score = rng.choice([9, 9, 10, 10, 9, 10])
            comment = rng.choice(POSITIVE_COMMENTS)
        rows.append(_row(rng, nxt(), "downtown", rng.choice(tellers_dt),
                         score, comment, ts))
    downtown_last = ts

    # --- the motivating fixture: an 8 that reads like a pass ---
    ts = downtown_last + timedelta(days=2, hours=3)
    rows.append(_row(
        rng, "s_chase8", "downtown", "teller_07", 8,
        "Excellent service and took care of all my needs.", ts))

    # --- reverse conflict: a 10 that reads like a fail ---
    ts += timedelta(hours=5)
    rows.append(_row(
        rng, "s_rev10", "downtown", "teller_03", 10,
        "Terrible experience, rude teller, they did not help with my issue at all.", ts))

    # --- consistent fixtures ---
    ts += timedelta(days=1)
    rows.append(_row(rng, "s_fail2", "downtown", "teller_02", 2,
                     "Nobody helped me, I am still waiting for a callback.", ts))
    ts += timedelta(hours=4)
    rows.append(_row(rng, "s_pass10", "downtown", "teller_01", 10,
                     "Great service, quick and professional, very satisfied.", ts))
    ts += timedelta(days=1)
    rows.append(_row(rng, "s_empty8", "downtown", "teller_04", 8, "", ts))

    # --- uptown background: ~40 random surveys ---
    ts = t0
    tellers_ut = [f"teller_{i:02d}" for i in range(11, 15)]
    for _ in range(40):
        ts += timedelta(days=rng.randint(1, 3), hours=rng.randint(0, 6))
        score = rng.choices([10, 9, 8, 7, 6, 5, 4, 3, 2, 1],
                            weights=[25, 25, 12, 8, 6, 5, 5, 4, 5, 5])[0]
        if score >= 9:
            comment = rng.choice(POSITIVE_COMMENTS)
        elif score >= 6:
            comment = rng.choice(NEUTRAL_COMMENTS + POSITIVE_COMMENTS)
        else:
            comment = rng.choice(NEGATIVE_COMMENTS)
        rows.append(_row(rng, nxt(), "uptown", rng.choice(tellers_ut),
                         score, comment, ts))

    # Deliberately out of chronological order in the CSV.
    rng.shuffle(rows)

    path = os.path.join(BASE, "data", "surveys.csv")
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=[
            "survey_id", "branch", "teller", "score", "comment", "timestamp"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {path}: {len(rows)} surveys")


if __name__ == "__main__":
    main()
