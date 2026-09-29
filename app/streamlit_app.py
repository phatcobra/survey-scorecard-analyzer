"""Streamlit dashboard: survey/scorecard interpretation analyzer.

Run from the project root (venv):
    streamlit run app/streamlit_app.py

Reads data/analyzed_surveys.csv produced by `python3 src/main.py`.
Advisory only: surfaces interpretation conflicts and scorecard impact
for human review. Never changes a score or decides employment outcomes.
"""

from __future__ import annotations

import csv
import os
from collections import Counter

import streamlit as st

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(BASE, "data", "analyzed_surveys.csv")


def load_rows():
    with open(CSV_PATH, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def pct(x):
    try:
        return float(x) if x not in (None, "") else None
    except (TypeError, ValueError):
        return None


st.set_page_config(page_title="Survey / Scorecard Interpretation", layout="wide")
st.title("Customer Survey Interpretation & Scorecard Impact Analyzer")
st.caption("Synthetic data. Advisory only — exposes measurement conflicts for "
           "human review; does not change scores or decide employment outcomes.")

rows = load_rows()
branches = sorted({r["branch"] for r in rows})
branch = st.selectbox("Branch", branches)
brows = [r for r in rows if r["branch"] == branch]
brows.sort(key=lambda r: (r["timestamp"], r["survey_id"]))

last = brows[-1]
conflicts = [r for r in brows if r["interpretation_status"] == "score_comment_conflict"]
crossings = [r for r in brows if r["tier_crossed"] == "True"]

c1, c2, c3, c4 = st.columns(4)
c1.metric("Surveys", len(brows))
c2.metric("Scorecard", f"{last['scorecard_after_pct']}%",
          f"{last['tier_after']} (${ {'gold': 300, 'silver': 150}.get(last['tier_after'], 0)}/person)")
c3.metric("Score/comment conflicts", len(conflicts))
c4.metric("Tier-crossing surveys", len(crossings))

st.subheader("Branch scorecard over time (top-2-box % of 9–10)")
chart_data = [{"survey": r["survey_id"], "scorecard": pct(r["scorecard_after_pct"])}
              for r in brows]
st.line_chart(chart_data, x="survey", y="scorecard")
st.caption("Tier bands: gold ≥ 95% ($300/person), silver 90–95% ($150/person), "
           "below 90% no bonus. A single 1–8 survey can move the branch across a band.")

st.subheader("Surveys needing human review (score/comment conflicts)")
flagged = [r for r in brows if r["needs_human_review"] == "True"]
if not flagged:
    st.write("None.")
for r in flagged:
    title = (f"{r['survey_id']}: score {r['score']}/10 ({r['official_treatment']}) — "
             f"{r['interpretation_status']}"
             + (" — TIER CROSSING" if r["tier_crossed"] == "True" else ""))
    with st.expander(title):
        st.write(f"**Comment:** {r['comment'] or '(blank)'}")
        st.write(f"**Teller:** {r['teller']} · **When:** {r['timestamp']}")
        st.write(f"**Text evidence:** sentiment={r['sentiment_label'] or 'n/a'} "
                 f"({r['sentiment_status']}), resolution={r['resolution']}, "
                 f"positive themes=[{r['positive_themes'] or '—'}], "
                 f"negative themes=[{r['negative_themes'] or '—'}]")
        before = r["scorecard_before_pct"] or "—"
        st.write(f"**Scorecard impact:** {before}% ({r['tier_before'] or '—'}) → "
                 f"{r['scorecard_after_pct']}% ({r['tier_after']})"
                 + (f" — Δ {r['scorecard_delta_pp']}pp" if r["scorecard_delta_pp"] else ""))
        st.write(f"**Finding:** {r['reason']}")

st.subheader("Tier crossings (scorecard-impact events, not interpretation problems)")
if not crossings:
    st.write("None.")
for r in crossings:
    st.write(f"- **{r['survey_id']}**: score {r['score']}/10 ({r['official_treatment']}) moved "
             f"the branch from {r['scorecard_before_pct']}% ({r['tier_before']}) to "
             f"{r['scorecard_after_pct']}% ({r['tier_after']})"
             + (" — also a score/comment conflict" if r["conflict_flag"] == "True" else ""))

st.subheader("All surveys")
st.dataframe(
    [{"survey": r["survey_id"], "score": r["score"],
      "treatment": r["official_treatment"],
      "interpretation": r["interpretation_status"],
      "conflict": r["conflict_flag"],
      "tier crossed": r["tier_crossed"],
      "review": r["needs_human_review"],
      "sentiment": r["sentiment_label"] or "n/a",
      "resolution": r["resolution"],
      "Δpp": r["scorecard_delta_pp"] or "—"}
     for r in brows],
    use_container_width=True,
)

with st.expander("Methodology & boundaries"):
    st.write(
        "- **Official treatment** is a pure function of the score (≥9 PASS, ≤8 FAIL); "
        "the comment can never change it.\n"
        "- **Conflict** = the binary treatment contradicts the written evidence "
        "(either direction: FAIL with positive resolved text, or PASS with "
        "negative unresolved text).\n"
        "- **Scorecard** = % of 9–10 surveys, computed chronologically per branch; "
        "each survey shows before/after/Δ and any bonus-tier crossing.\n"
        "- Blank comments are *no* evidence, not negative evidence.\n"
        "- This tool surfaces conflicts for human review. It does not alter "
        "ratings and does not decide bonuses, promotions, discipline, raises, "
        "or performance ratings.")
