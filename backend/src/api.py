"""
api.py — FastAPI backend for the Institutional Knowledge Retrieval System.

Endpoints
---------
POST /query           – ask a question, get answer + sources
GET  /health          – liveness check
GET  /dashboard/today – today's cost summary
GET  /dashboard/daily – last 30 days breakdown
GET  /dashboard/total – all-time totals
GET  /dashboard/recent-queries – last N queries
POST /evaluate        – run the full golden-dataset evaluation suite
GET  /prompts         – list available prompt versions
"""

import sys
import os
from pathlib import Path

# Make sure src/ is on the path when running from project root
sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import uuid

from rag_chain import answer_question
from cost_tracker import (
    get_today_summary,
    get_daily_summary,
    get_total_summary,
    get_recent_queries,
)
from answer_evaluator import run_evaluation_suite

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
EVALUATION_DIR = Path(__file__).parent.parent / "evaluation"

# ──────────────────────────────────────────────────────────────
app = FastAPI(
    title="Institutional Knowledge Retrieval System",
    description="RAG-powered chatbot for institutional document Q&A (TCS LLMOps Capstone)",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ──────────────────────────────────────────────────────────────
# Schemas
# ──────────────────────────────────────────────────────────────

class QueryRequest(BaseModel):
    question: str
    session_id: Optional[str] = None


class QueryResponse(BaseModel):
    answer: str
    sources: list[str]
    guardrail: Optional[str]
    latency_ms: int
    prompt_version: str
    session_id: str


# ──────────────────────────────────────────────────────────────
# Routes
# ──────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "service": "IKRS API"}


@app.post("/query", response_model=QueryResponse)
def query(req: QueryRequest):
    session_id = req.session_id or str(uuid.uuid4())
    try:
        result = answer_question(req.question, session_id=session_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return QueryResponse(
        answer=result["answer"],
        sources=result["sources"],
        guardrail=result.get("guardrail"),
        latency_ms=result.get("latency_ms", 0),
        prompt_version=result.get("prompt_version", "unknown"),
        session_id=session_id,
    )


# ── Cost Governance ──────────────────────────────────────────

@app.get("/dashboard/today")
def dashboard_today():
    return get_today_summary()


@app.get("/dashboard/daily")
def dashboard_daily():
    return {"data": get_daily_summary()}


@app.get("/dashboard/total")
def dashboard_total():
    return get_total_summary()


@app.get("/dashboard/recent-queries")
def dashboard_recent(limit: int = 20):
    return {"data": get_recent_queries(limit)}


# ── Evaluation ───────────────────────────────────────────────

_eval_running = False
_eval_result = None


def _run_eval_bg():
    global _eval_running, _eval_result
    _eval_running = True
    try:
        _eval_result = run_evaluation_suite(
            dataset_path=EVALUATION_DIR / "golden_dataset.json",
            output_path=EVALUATION_DIR / "evaluation_results.json",
            answer_fn=answer_question,
        )
    finally:
        _eval_running = False


@app.post("/evaluate")
def start_evaluation(background_tasks: BackgroundTasks):
    global _eval_running
    if _eval_running:
        return {"status": "already_running"}
    background_tasks.add_task(_run_eval_bg)
    return {"status": "started", "message": "Evaluation running in background. Poll /evaluate/status."}


@app.get("/evaluate/status")
def eval_status():
    if _eval_running:
        return {"status": "running"}
    if _eval_result:
        return {"status": "complete", "summary": _eval_result}
    # Check for persisted result
    summary_file = EVALUATION_DIR / "evaluation_summary.json"
    if summary_file.exists():
        import json
        return {"status": "complete", "summary": json.loads(summary_file.read_text())}
    return {"status": "idle"}


@app.get("/evaluate/results")
def eval_results():
    results_file = EVALUATION_DIR / "evaluation_results.json"
    if not results_file.exists():
        raise HTTPException(status_code=404, detail="No evaluation results found. Run POST /evaluate first.")
    import json
    return {"data": json.loads(results_file.read_text())}


# ── Prompt management ────────────────────────────────────────

@app.get("/prompts")
def list_prompts():
    versions = sorted(p.stem for p in PROMPTS_DIR.glob("prompt_*.txt"))
    return {"versions": versions}


@app.get("/prompts/{version}")
def get_prompt(version: str):
    path = PROMPTS_DIR / f"prompt_{version}.txt"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Prompt {version} not found")
    return {"version": version, "content": path.read_text(encoding="utf-8")}
