"""
Streamlit GUI for AI Council.

Run with:  streamlit run app.py
Terminal mode is still available via:  python council.py
"""

import json
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import streamlit as st

from council import (
    AGENTS,
    _critique_phase_safe,
    _format_recent_memory,
    _format_role_memory,
    _rebuttal_phase,
    _resolve_agent_models,
    _run_agent_safe,
    chairman_decision,
)
from memory_store import CouncilMemory
from rag import EvidenceRetriever, format_evidence_for_prompt
from security import pseudonymize_text, redact_sensitive_text
from telemetry import TelemetryStore
from voting import aggregate_weighted_scores, parse_structured_response

DB_PATH = "council_memory.db"

st.set_page_config(page_title="AI Council", layout="wide", page_icon="🏛️")
st.title("🏛️ AI Council")

tab_run, tab_history = st.tabs(["▶ Live Run", "📊 History & Metrics"])


# ── helpers ──────────────────────────────────────────────────────────────────

def _agent_card(role: str, parsed, raw: str) -> str:
    """Render a filled agent card as markdown."""
    rec = parsed.recommendation
    conf = int(parsed.confidence)
    risk = int(parsed.risk_score)
    reasoning = (parsed.reasoning or "")[:220].strip()
    conf_bar = "🟩" * (conf // 20) + "⬜" * (5 - conf // 20)
    risk_bar = "🟥" * (risk // 20) + "⬜" * (5 - risk // 20)
    return (
        f"**{role}**\n\n"
        f"**Rec:** {rec}\n\n"
        f"Conf {conf_bar} {conf}  |  Risk {risk_bar} {risk}\n\n"
        f"_{reasoning}..._"
    )


def _agent_grid(label: str, roles: list[str]) -> dict:
    """Render a phase header + 3-col grid of empty placeholders. Returns {role: placeholder}."""
    st.markdown(f"#### {label}")
    cols = st.columns(3)
    placeholders = {}
    for i, role in enumerate(roles):
        with cols[i % 3]:
            ph = st.empty()
            ph.info(f"⏳ **{role}**\n\n_Waiting..._")
            placeholders[role] = ph
    return placeholders


def _critique_card(role: str, critique: str) -> str:
    snippet = critique[:280].strip()
    return f"**{role}**\n\n_{snippet}..._"


# ── Live Run tab ──────────────────────────────────────────────────────────────

with tab_run:
    with st.form("council_form"):
        question = st.text_area(
            "Question for the Council",
            height=100,
            placeholder="e.g. Should we adopt a zero-trust network architecture?",
        )
        col_a, col_b = st.columns(2)
        debate_rounds = col_a.slider("Debate rounds", 0, 3, 0)
        docs_dir = col_b.text_input("Docs directory", value="docs")
        submitted = st.form_submit_button("Run Council ▶", type="primary")

    if submitted and question.strip():
        start = time.time()
        agent_models = _resolve_agent_models()

        # RAG + memory
        retriever = EvidenceRetriever.from_docs_dir(docs_dir)
        evidence_chunks = retriever.retrieve(question, top_k=4)
        evidence_context = format_evidence_for_prompt(evidence_chunks)

        memory = CouncilMemory(DB_PATH)
        memory_context = _format_recent_memory(memory)

        # ── Phase 1 ──────────────────────────────────────────────────────────
        phase1_placeholders = _agent_grid("Phase 1 — Agent Analysis", AGENTS)

        responses: dict = {}
        parsed_responses: dict = {}

        with ThreadPoolExecutor() as executor:
            future_to_role = {
                executor.submit(
                    _run_agent_safe,
                    role,
                    question,
                    evidence_context,
                    memory_context,
                    agent_models,
                    _format_role_memory(memory, role),
                ): role
                for role in AGENTS
            }
            for future in as_completed(future_to_role):
                role, answer = future.result()
                responses[role] = answer
                parsed = parse_structured_response(answer)
                parsed_responses[role] = parsed
                phase1_placeholders[role].success(_agent_card(role, parsed, answer))

        aggregate = aggregate_weighted_scores(parsed_responses)

        # Council metrics
        st.markdown("---")
        m1, m2, m3 = st.columns(3)
        m1.metric("Council Confidence", aggregate.get("council_confidence", "N/A"))
        m2.metric("Council Risk Score", aggregate.get("council_risk_score", "N/A"))
        m3.metric("Leading Recommendation", aggregate.get("leading_recommendation", "N/A"))

        with st.expander("Full agent responses (JSON)"):
            for role, answer in responses.items():
                st.markdown(f"**{role}**")
                st.code(answer, language="json")

        # ── Phase 2: Critique ─────────────────────────────────────────────────
        st.markdown("---")
        phase2_placeholders = _agent_grid("Phase 2 — Critique", AGENTS)
        compiled = "".join(f"\n\n[{r}]\n{a}" for r, a in responses.items())

        critiques: dict = {}
        with ThreadPoolExecutor() as executor:
            critique_futures = {
                executor.submit(
                    _critique_phase_safe,
                    role,
                    compiled,
                    question,
                    evidence_context,
                    agent_models,
                ): role
                for role in AGENTS
            }
            for future in as_completed(critique_futures):
                role, critique = future.result()
                critiques[role] = critique
                phase2_placeholders[role].success(_critique_card(role, critique))

        # ── Optional debate rounds ─────────────────────────────────────────────
        debate_history: dict = {}
        current_critiques = critiques

        for round_num in range(1, debate_rounds + 1):
            round_label = f"Debate Round {round_num}"
            st.markdown("---")
            rebuttal_placeholders = _agent_grid(f"{round_label} — Rebuttals", AGENTS)

            critiques_text = "".join(
                f"\n[{r} critique]\n{c}" for r, c in current_critiques.items()
            )

            rebuttal_responses: dict = {}
            with ThreadPoolExecutor() as executor:
                rebuttal_futures = {
                    executor.submit(
                        _rebuttal_phase,
                        role,
                        critiques_text,
                        question,
                        evidence_context,
                        agent_models,
                    ): role
                    for role in AGENTS
                }
                for future in as_completed(rebuttal_futures):
                    role, answer = future.result()
                    rebuttal_responses[role] = answer
                    parsed = parse_structured_response(answer)
                    rebuttal_placeholders[role].success(
                        _agent_card(role, parsed, answer)
                    )

            compiled_rebuttal = "".join(
                f"\n\n[{r}]\n{a}" for r, a in rebuttal_responses.items()
            )

            new_critique_placeholders = _agent_grid(
                f"{round_label} — New Critiques", AGENTS
            )
            new_critiques: dict = {}
            with ThreadPoolExecutor() as executor:
                nc_futures = {
                    executor.submit(
                        _critique_phase_safe,
                        role,
                        compiled_rebuttal,
                        question,
                        evidence_context,
                        agent_models,
                    ): role
                    for role in AGENTS
                }
                for future in as_completed(nc_futures):
                    role, critique = future.result()
                    new_critiques[role] = critique
                    new_critique_placeholders[role].success(
                        _critique_card(role, critique)
                    )

            debate_history[round_label] = (rebuttal_responses, new_critiques)
            current_critiques = new_critiques

        # ── Phase 3: Chairman ─────────────────────────────────────────────────
        st.markdown("---")
        st.markdown("#### Phase 3 — Chairman Decision")
        chairman_placeholder = st.empty()
        chairman_text = ""

        def _stream_cb(token: str):
            global chairman_text
            chairman_text += token
            chairman_placeholder.markdown(chairman_text + " ▌")

        # Use a mutable container so the nested function can update it
        _buf = {"text": ""}

        def _make_cb(buf: dict, ph):
            def cb(token: str):
                buf["text"] += token
                ph.markdown(buf["text"] + " ▌")
            return cb

        decision = chairman_decision(
            question,
            responses,
            critiques,
            aggregate,
            evidence_context,
            memory_context,
            debate_history=debate_history if debate_history else None,
            stream_callback=_make_cb(_buf, chairman_placeholder),
        )
        chairman_placeholder.markdown(_buf["text"])

        # Save + telemetry
        memory.save_decision(
            question=question,
            final_decision=decision,
            aggregate=aggregate,
            responses=responses,
        )
        TelemetryStore(DB_PATH).log_event(
            "council_run_completed",
            {
                "question_hash": pseudonymize_text(question),
                "question_preview": redact_sensitive_text(question[:120]),
                "agent_count": len(AGENTS),
                "evidence_chunk_count": len(evidence_chunks),
                "duration_seconds": round(time.time() - start, 2),
                "council_confidence": aggregate.get("council_confidence"),
                "council_risk_score": aggregate.get("council_risk_score"),
                "leading_recommendation": aggregate.get("leading_recommendation"),
                "debate_rounds": debate_rounds,
            },
        )

        elapsed = round(time.time() - start, 1)
        st.success(f"Council run complete in {elapsed}s")

    elif submitted:
        st.warning("Please enter a question.")


# ── History & Metrics tab ─────────────────────────────────────────────────────

def _load_decisions(limit: int = 100):
    try:
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
    except Exception:
        return []

    parsed = []
    for row in rows:
        try:
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
        except Exception:
            continue
    return parsed


def _load_telemetry(limit: int = 100):
    try:
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
    except Exception:
        return []

    return [
        {"event_type": et, "metadata": json.loads(mj), "created_at": ca}
        for et, mj, ca in rows
    ]


def _disagreement_score(responses: dict) -> float:
    import re

    recs = []
    for raw in responses.values():
        if not isinstance(raw, str):
            continue
        try:
            data = json.loads(raw)
            if isinstance(data, dict) and "recommendation" in data:
                recs.append(str(data["recommendation"]).strip().lower())
                continue
        except Exception:
            pass
        m = re.search(r"\{[\s\S]*\}", raw)
        if m:
            try:
                data = json.loads(m.group(0))
                if isinstance(data, dict) and "recommendation" in data:
                    recs.append(str(data["recommendation"]).strip().lower())
            except Exception:
                pass
    if not recs:
        return 0.0
    return round(len(set(recs)) / len(recs), 2)


with tab_history:
    records = _load_decisions()
    if not records:
        st.info("No decisions yet. Run a council session first.")
    else:
        chart_rows = [
            {
                "created_at": r["created_at"],
                "question": r["question"],
                "council_confidence": r["aggregate"].get("council_confidence", 0),
                "council_risk_score": r["aggregate"].get("council_risk_score", 0),
                "disagreement_score": _disagreement_score(r["responses"]),
            }
            for r in records
        ]
        df = pd.DataFrame(chart_rows)

        c1, c2, c3 = st.columns(3)
        c1.metric("Avg Confidence", round(df["council_confidence"].mean(), 2))
        c2.metric("Avg Risk", round(df["council_risk_score"].mean(), 2))
        c3.metric("Avg Disagreement", round(df["disagreement_score"].mean(), 2))

        st.subheader("Confidence & Risk Over Time")
        st.line_chart(
            df.set_index("created_at")[["council_confidence", "council_risk_score"]]
        )

        st.subheader("Agent Disagreement Strength")
        st.bar_chart(df.set_index("created_at")[["disagreement_score"]])

        telemetry = _load_telemetry()
        if telemetry:
            st.subheader("Telemetry")
            tdf = pd.DataFrame(
                [
                    {
                        "created_at": t["created_at"],
                        "duration_seconds": t["metadata"].get("duration_seconds", 0),
                        "evidence_chunk_count": t["metadata"].get("evidence_chunk_count", 0),
                        "agent_count": t["metadata"].get("agent_count", 0),
                    }
                    for t in telemetry
                ]
            )
            st.line_chart(
                tdf.set_index("created_at")[["duration_seconds", "evidence_chunk_count"]]
            )

        st.subheader("Recent Decisions")
        for record in records[:10]:
            with st.expander(f"{record['created_at']}  —  {record['question'][:80]}"):
                st.markdown("**Aggregate**")
                st.json(record["aggregate"])
                st.markdown("**Chairman Decision**")
                st.write(record["final_decision"])
