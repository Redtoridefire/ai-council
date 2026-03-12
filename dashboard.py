import json
import re
import sqlite3

import pandas as pd
import streamlit as st

DB_PATH = "council_memory.db"

st.set_page_config(page_title="AI Council Dashboard", layout="wide")
st.title("AI Council Visualization Dashboard")


def load_decisions(limit: int = 100):
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            """
            SELECT id, question, final_decision, aggregate_json, responses_json, created_at
            FROM decisions
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    parsed = []
    for row in rows:
        parsed.append(
            {
                "id": row[0],
                "question": row[1],
                "final_decision": row[2],
                "aggregate": json.loads(row[3]),
                "responses": json.loads(row[4]),
                "created_at": row[5],
            }
        )
    return parsed


def load_telemetry(limit: int = 100):
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            """
            SELECT event_type, metadata_json, created_at
            FROM telemetry_events
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    parsed = []
    for event_type, metadata_json, created_at in rows:
        parsed.append(
            {
                "event_type": event_type,
                "metadata": json.loads(metadata_json),
                "created_at": created_at,
            }
        )
    return parsed


def _extract_recommendation(raw: str) -> str:
    """Extract the recommendation field from a structured agent response."""
    try:
        data = json.loads(raw)
        if isinstance(data, dict) and "recommendation" in data:
            return str(data["recommendation"]).strip().lower()
    except Exception:
        pass
    match = re.search(r"\{[\s\S]*\}", raw)
    if match:
        try:
            data = json.loads(match.group(0))
            if isinstance(data, dict) and "recommendation" in data:
                return str(data["recommendation"]).strip().lower()
        except Exception:
            pass
    return ""


def disagreement_score(responses: dict) -> float:
    """Fraction of unique recommendations across agents (0 = full consensus, 1 = all differ)."""
    recommendations = [
        rec
        for answer in responses.values()
        if isinstance(answer, str)
        for rec in [_extract_recommendation(answer)]
        if rec
    ]
    if not recommendations:
        return 0.0
    return round(len(set(recommendations)) / len(recommendations), 2)


records = load_decisions()
if not records:
    st.warning("No decisions found yet. Run `python council.py` first to populate memory.")
    st.stop()

chart_rows = []
for record in records:
    chart_rows.append(
        {
            "created_at": record["created_at"],
            "question": record["question"],
            "council_confidence": record["aggregate"].get("council_confidence", 0),
            "council_risk_score": record["aggregate"].get("council_risk_score", 0),
            "disagreement_score": disagreement_score(record["responses"]),
        }
    )

metrics_df = pd.DataFrame(chart_rows)

col1, col2, col3 = st.columns(3)
col1.metric("Avg Council Confidence", round(metrics_df["council_confidence"].mean(), 2))
col2.metric("Avg Council Risk", round(metrics_df["council_risk_score"].mean(), 2))
col3.metric("Avg Disagreement", round(metrics_df["disagreement_score"].mean(), 2))

st.subheader("Consensus & Risk Over Time")
st.line_chart(metrics_df.set_index("created_at")[["council_confidence", "council_risk_score"]])

st.subheader("Agent Disagreement Strength")
st.bar_chart(metrics_df.set_index("created_at")[["disagreement_score"]])

telemetry = load_telemetry()
if telemetry:
    st.subheader("Telemetry (Duration & Evidence Chunks)")
    telemetry_rows = []
    for row in telemetry:
        md = row["metadata"]
        telemetry_rows.append(
            {
                "created_at": row["created_at"],
                "duration_seconds": md.get("duration_seconds", 0),
                "evidence_chunk_count": md.get("evidence_chunk_count", 0),
                "agent_count": md.get("agent_count", 0),
            }
        )
    tdf = pd.DataFrame(telemetry_rows)
    st.line_chart(tdf.set_index("created_at")[["duration_seconds", "evidence_chunk_count"]])

st.subheader("Recent Decisions")
for record in records[:5]:
    with st.expander(f"{record['created_at']} — {record['question']}"):
        st.markdown("**Aggregate**")
        st.json(record["aggregate"])
        st.markdown("**Chairman Decision**")
        st.write(record["final_decision"])
