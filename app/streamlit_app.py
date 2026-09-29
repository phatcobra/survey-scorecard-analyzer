"""Streamlit dashboard: survey/scorecard interpretation analyzer.

Run from the project root (venv):
    streamlit run app/streamlit_app.py

Reads data/analyzed_surveys.csv produced by `python3 src/main.py`.
Advisory only: surfaces interpretation conflicts and scorecard impact
for human review. Never changes a score or decides employment outcomes.

The dataset holds two cohorts of 50 branches each:
  new_way ... full analyzer (scorecard + interpretation screening)
  old_way ... scorecard only; the interpretation layer is never applied,
              so score/comment conflicts in these branches go unflagged
              by construction. Same underlying survey distributions —
              the cohorts differ only in the method applied.
"""

from __future__ import annotations

import csv
import os
from collections import Counter

import streamlit as st

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(BASE, "data", "analyzed_surveys.csv")

COHORT_LABELS = {
    "compare": "Old way vs new way (comparison)",
    "new_way": "New way — analyzer (50 branches)",
    "old_way": "Old way — scorecard only (50 branches)",
}


def load_rows():
    with open(CSV_PATH, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def pct(x):
    try:
        return float(x) if x not in (None, "") else None
    except (TypeError, ValueError):
        return None


def cohort_stats(rows, cohort):
    rs = [r for r in rows if r.get("cohort", "new_way") == cohort]
    branches = sorted({r["branch"] for r in rs})
    conflicts = [r for r in rs if r["interpretation_status"] == "score_comment_conflict"]
    crossings = [r for r in rs if r["tier_crossed"] == "True"]
    explained = [r for r in crossings if r["conflict_flag"] == "True"]
    return {
        "surveys": len(rs), "branches": len(branches),
        "conflicts": len(conflicts), "crossings": len(crossings),
        "explained": len(explained),
    }


st.set_page_config(page_title="Survey / Scorecard Interpretation", layout="wide")
st.title("Customer Survey Interpretation & Scorecard Impact Analyzer")
st.caption("Synthetic data. Advisory only — exposes measurement conflicts for "
           "human review; does not change scores or decide employment outcomes.")

rows = load_rows()

mode = st.selectbox("Method", list(COHORT_LABELS), format_func=COHORT_LABELS.get)

if mode == "compare":
    old = cohort_stats(rows, "old_way")
    new = cohort_stats(rows, "new_way")
    st.subheader("What the new way catches that the old way buries")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Old way — scorecard only** (50 branches)")
        st.metric("Surveys (never screened)", old["surveys"])
        st.metric("Tier crossings", old["crossings"])
        st.metric("Conflicts surfaced", 0)
        st.metric("Tier crossings with a flagged cause", 0)
    with c2:
        st.markdown("**New way — analyzer** (50 branches)")
        st.metric("Surveys screened", new["surveys"])
        st.metric("Tier crossings", new["crossings"])
        st.metric("Conflicts surfaced for human review", new["conflicts"])
        st.metric("Tier crossings with a flagged cause", new["explained"])
    st.caption(
        "Controlled comparison: both cohorts were generated from the same survey "
        "distributions, so the underlying conflicts exist in both. The old-way "
        "branches were never screened for them (interpretation_status = "
        "'not_screened'); the new-way branches surface each one with its written "
        "evidence and scorecard impact. A tier crossing the old way leaves "
        "unexplained, the new way attributes to the survey that caused it.")
    st.divider()

# ---- per-cohort (or comparison-wide) branch explorer ----
if mode == "compare":
    brows_all = sorted(rows, key=lambda r: (r.get("cohort", ""), r["branch"],
                                            r["timestamp"], r["survey_id"]))
    branch_options = ["All branches"] + sorted({r["branch"] for r in rows})
else:
    brows_all = sorted([r for r in rows if r.get("cohort", "new_way") == mode],
                       key=lambda r: (r["branch"], r["timestamp"], r["survey_id"]))
    branch_options = ["All branches"] + sorted({r["branch"] for r in brows_all})

branch = st.selectbox("Branch", branch_options)
if branch == "All branches":
    brows = brows_all
    all_view = True
else:
    brows = [r for r in brows_all if r["branch"] == branch]
    all_view = False

is_old_view = mode == "old_way" or (
    mode == "compare" and brows and all(r.get("cohort") == "old_way" for r in brows))

conflicts = [r for r in brows if r["interpretation_status"] == "score_comment_conflict"]
crossings = [r for r in brows if r["tier_crossed"] == "True"]

c1, c2, c3, c4 = st.columns(4)
c1.metric("Surveys", len(brows))
c2.metric("Score/comment conflicts", len(conflicts))
c3.metric("Tier-crossing surveys", len(crossings))
if all_view:
    c4.metric("Branches", len({r["branch"] for r in brows}))
else:
    last = brows[-1]
    c4.metric("Scorecard", f"{last['scorecard_after_pct']}%",
              f"{last['tier_after']} (${ {'gold': 300, 'silver': 150}.get(last['tier_after'], 0)}/person)")

st.subheader("Branch scorecard over time (top-2-box % of 9–10)")
if all_view:
    # Cohort-average lines. One line per branch (100 lines) is unreadable
    # spaghetti; the average per survey-step shows the comparison cleanly.
    series = []
    for cohort, label in (("old_way", "Old way — branch average"),
                          ("new_way", "New way — branch average")):
        crows = [r for r in brows if r.get("cohort", "new_way") == cohort]
        if not crows:
            continue
        by_step = {}
        for b in {r["branch"] for r in crows}:
            br = sorted([r for r in crows if r["branch"] == b],
                        key=lambda r: (r["timestamp"], r["survey_id"]))
            for i, r in enumerate(br, start=1):
                v = pct(r["scorecard_after_pct"])
                if v is not None:
                    by_step.setdefault(i, []).append(v)
        for i in sorted(by_step):
            vals = by_step[i]
            series.append({"step": i, "scorecard": sum(vals) / len(vals),
                           "method": label})
    st.line_chart(series, x="step", y="scorecard", color="method")
    st.caption("Average running scorecard per survey-step across the branches "
               "in view. Early steps swing wildly (one survey decides "
               "everything); lines settle as surveys accumulate.")
else:
    chart_data = [{"survey": r["survey_id"], "scorecard": pct(r["scorecard_after_pct"])}
                  for r in brows]
    st.line_chart(chart_data, x="survey", y="scorecard")
st.caption("Tier bands: gold ≥ 95% ($300/person), silver 90–95% ($150/person), "
           "below 90% no bonus. A single 1–8 survey can move the branch across a band.")

st.subheader("Surveys needing human review (score/comment conflicts)")
if is_old_view:
    st.write("The old way never screens written feedback — none of these "
             f"{len(brows)} surveys were ever checked for score/comment conflicts. "
             "Any conflicts in this data went unflagged by construction.")
else:
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
    st.write(f"- **{r['survey_id']}** ({r['branch']}): score {r['score']}/10 ({r['official_treatment']}) moved "
             f"the branch from {r['scorecard_before_pct']}% ({r['tier_before']}) to "
             f"{r['scorecard_after_pct']}% ({r['tier_after']})"
             + (" — also a score/comment conflict" if r["conflict_flag"] == "True" else ""))

st.subheader("All surveys")
st.dataframe(
    [{"survey": r["survey_id"], "branch": r["branch"], "score": r["score"],
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
        "- **Old way vs new way** is a controlled comparison: both cohorts were "
        "generated from the same survey distributions. Old-way branches got the "
        "scorecard only (interpretation_status = 'not_screened'); new-way branches "
        "got the full analyzer.\n"
        "- Blank comments are *no* evidence, not negative evidence.\n"
        "- This tool surfaces conflicts for human review. It does not alter "
        "ratings and does not decide bonuses, promotions, discipline, raises, "
        "or performance ratings.")
