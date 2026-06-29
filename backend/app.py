"""
app.py — Streamlit UI for the Institutional Knowledge Retrieval System.

Run with:
    streamlit run app.py

Requires the FastAPI backend to be running:
    uvicorn src.api:app --reload --port 8000
"""

import streamlit as st
import httpx
import json
import uuid
import pandas as pd
import plotly.express as px
from datetime import datetime

API_BASE = "http://localhost:8000"

# ──────────────────────────────────────────────────────────────
# Page config
# ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="IKRS — Institutional Knowledge Retrieval",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ──────────────────────────────────────────────────────────────
# Session state
# ──────────────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

if "page" not in st.session_state:
    st.session_state.page = "Chat"

# ──────────────────────────────────────────────────────────────
# Sidebar
# ──────────────────────────────────────────────────────────────
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/b/b1/Tata_Consultancy_Services_Logo.svg", width=120)
    st.title("IKRS")
    st.caption("Institutional Knowledge Retrieval System")
    st.divider()

    page = st.radio(
        "Navigate",
        ["💬 Chat", "📊 Cost Dashboard", "🧪 Evaluation"],
        index=["💬 Chat", "📊 Cost Dashboard", "🧪 Evaluation"].index(
            f"{'💬 Chat' if st.session_state.page == 'Chat' else ('📊 Cost Dashboard' if st.session_state.page == 'Dashboard' else '🧪 Evaluation')}"
        ),
    )
    st.session_state.page = page.split(" ", 1)[1].strip() if " " in page else page

    st.divider()
    st.caption(f"Session: `{st.session_state.session_id[:8]}…`")

    if st.button("🔄 New Session"):
        st.session_state.messages = []
        st.session_state.session_id = str(uuid.uuid4())
        st.rerun()

# ──────────────────────────────────────────────────────────────
# Helper
# ──────────────────────────────────────────────────────────────
def api_get(path: str):
    try:
        r = httpx.get(f"{API_BASE}{path}", timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"API error: {e}")
        return None


def api_post(path: str, body: dict):
    try:
        r = httpx.post(f"{API_BASE}{path}", json=body, timeout=60)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"API error: {e}")
        return None


# ──────────────────────────────────────────────────────────────
# Page: Chat
# ──────────────────────────────────────────────────────────────
if "Chat" in page:
    st.title("🎓 Institutional Knowledge Assistant")
    st.caption("Ask anything about fees, regulations, hostel, exams, bridge courses, placements…")

    # Chat history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg["role"] == "assistant" and msg.get("sources"):
                with st.expander("📄 Sources", expanded=False):
                    for src in msg["sources"]:
                        st.markdown(f"• `{src}`")
            if msg["role"] == "assistant" and msg.get("meta"):
                meta = msg["meta"]
                cols = st.columns(3)
                cols[0].caption(f"⏱ {meta.get('latency_ms', '?')} ms")
                cols[1].caption(f"🔖 Prompt {meta.get('prompt_version', '?')}")
                if meta.get("guardrail"):
                    cols[2].caption(f"🛡 Guardrail: `{meta['guardrail']}`")

    # Input
    if question := st.chat_input("Ask a question about institutional policies…"):
        st.session_state.messages.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)

        with st.chat_message("assistant"):
            with st.spinner("Searching institutional documents…"):
                result = api_post("/query", {
                    "question": question,
                    "session_id": st.session_state.session_id,
                })

            if result:
                st.markdown(result["answer"])

                if result.get("sources"):
                    with st.expander("📄 Sources", expanded=False):
                        for src in result["sources"]:
                            st.markdown(f"• `{src}`")

                cols = st.columns(3)
                cols[0].caption(f"⏱ {result.get('latency_ms', '?')} ms")
                cols[1].caption(f"🔖 Prompt {result.get('prompt_version', '?')}")
                if result.get("guardrail"):
                    cols[2].caption(f"🛡 Guardrail: `{result['guardrail']}`")

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": result["answer"],
                    "sources": result.get("sources", []),
                    "meta": {
                        "latency_ms": result.get("latency_ms"),
                        "prompt_version": result.get("prompt_version"),
                        "guardrail": result.get("guardrail"),
                    },
                })

# ──────────────────────────────────────────────────────────────
# Page: Cost Dashboard
# ──────────────────────────────────────────────────────────────
elif "Dashboard" in page:
    st.title("📊 Cost Governance Dashboard")
    st.caption("Token usage and cost tracking across all queries")

    col1, col2, col3, col4 = st.columns(4)

    totals = api_get("/dashboard/total")
    today = api_get("/dashboard/today")

    if totals:
        col1.metric("Total Queries", f"{totals['total_queries']:,}")
        col2.metric("Total Cost (USD)", f"${totals['total_cost_usd']:.4f}")
        col3.metric("Avg Cost / Query", f"${totals['avg_cost_per_query']:.6f}")
        col4.metric("Total Tokens", f"{(totals['total_input_tokens'] + totals['total_output_tokens']):,}")

    st.divider()

    if today:
        st.subheader(f"Today — {today['date']}")
        t1, t2, t3, t4 = st.columns(4)
        t1.metric("Queries Today", today["queries"])
        t2.metric("Cost Today", f"${today['cost_usd']:.4f}")
        t3.metric("Input Tokens", f"{today['input_tokens']:,}")
        t4.metric("Output Tokens", f"{today['output_tokens']:,}")

    st.divider()
    st.subheader("Daily Usage (Last 30 Days)")

    daily = api_get("/dashboard/daily")
    if daily and daily.get("data"):
        df = pd.DataFrame(daily["data"])
        df["date"] = pd.to_datetime(df["date"])

        col_a, col_b = st.columns(2)
        with col_a:
            fig = px.bar(df, x="date", y="cost_usd",
                         title="Daily Cost (USD)",
                         color_discrete_sequence=["#1f77b4"])
            st.plotly_chart(fig, use_container_width=True)

        with col_b:
            fig2 = px.line(df, x="date", y="queries",
                           title="Daily Query Volume",
                           markers=True,
                           color_discrete_sequence=["#ff7f0e"])
            st.plotly_chart(fig2, use_container_width=True)

        st.subheader("Token Breakdown")
        fig3 = px.area(df, x="date",
                       y=["input_tokens", "output_tokens"],
                       title="Token Usage Over Time")
        st.plotly_chart(fig3, use_container_width=True)

        with st.expander("📋 Raw Daily Table"):
            st.dataframe(df.sort_values("date", ascending=False), use_container_width=True)

    st.divider()
    st.subheader("Recent Queries")
    recent = api_get("/dashboard/recent-queries?limit=15")
    if recent and recent.get("data"):
        df_r = pd.DataFrame(recent["data"])
        df_r["cost_usd"] = df_r["cost_usd"].apply(lambda x: f"${x:.6f}")
        st.dataframe(df_r, use_container_width=True)

# ──────────────────────────────────────────────────────────────
# Page: Evaluation
# ──────────────────────────────────────────────────────────────
elif "Evaluation" in page:
    st.title("🧪 Answer Evaluation — LLM as Judge")
    st.caption("Evaluate RAG answers against the golden dataset using Gemini as judge")

    status = api_get("/evaluate/status")
    if status:
        if status["status"] == "running":
            st.info("⏳ Evaluation is currently running in the background…")
            st.button("🔄 Refresh", on_click=st.rerun)
        elif status["status"] == "complete":
            st.success("✅ Evaluation complete!")
            summary = status.get("summary", {})
            if summary:
                st.subheader("Aggregate Scores (1–5 scale)")
                m1, m2, m3, m4, m5 = st.columns(5)
                m1.metric("Faithfulness", f"{summary.get('avg_faithfulness', 0):.2f} / 5")
                m2.metric("Relevance",    f"{summary.get('avg_relevance', 0):.2f} / 5")
                m3.metric("Correctness",  f"{summary.get('avg_correctness', 0):.2f} / 5")
                m4.metric("Composite",    f"{summary.get('composite_score', 0):.2f} / 5")
                m5.metric("Source Match", f"{summary.get('source_match_pct', 0):.1f}%")
        else:
            st.info("No evaluation has been run yet.")

    st.divider()

    col_run, col_results = st.columns([1, 2])

    with col_run:
        st.subheader("Run Evaluation")
        st.warning("⚠️ This calls the LLM for every question in the golden dataset and will consume tokens.")
        if st.button("▶ Start Evaluation Suite", type="primary"):
            resp = api_post("/evaluate", {})
            if resp:
                st.success(resp.get("message", "Started!"))
                st.rerun()

    with col_results:
        st.subheader("Per-Question Results")
        results_data = api_get("/evaluate/results")
        if results_data and results_data.get("data"):
            df_eval = pd.DataFrame(results_data["data"])
            score_cols = ["faithfulness", "relevance", "correctness"]
            avail_cols = [c for c in score_cols if c in df_eval.columns]
            if avail_cols:
                df_display = df_eval[
                    ["id", "question", "source_match"] + avail_cols + ["reasoning"]
                ].copy()
                df_display["question"] = df_display["question"].str[:60] + "…"

                # Color-code the scores
                st.dataframe(
                    df_display.style.background_gradient(
                        subset=avail_cols, cmap="RdYlGn", vmin=1, vmax=5
                    ),
                    use_container_width=True,
                )

                # Score distribution chart
                fig = px.box(
                    df_eval[avail_cols].melt(var_name="Metric", value_name="Score"),
                    x="Metric", y="Score", color="Metric",
                    title="Score Distribution by Metric",
                    range_y=[0, 5.5],
                )
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Run evaluation to see per-question results here.")
