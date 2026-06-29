"""
cost_tracker.py — Tracks token usage and cost per invocation.

Stores data in a local SQLite DB (cost_usage.db) so it works without
any extra infrastructure.  The FastAPI /dashboard endpoint reads from
this same DB to build the governance dashboard.

Gemini 2.0 Flash pricing (as of 2025-06):
  Input:  $0.10 / 1M tokens
  Output: $0.40 / 1M tokens
"""

import sqlite3
import time
from datetime import datetime, date
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "cost_usage.db"

# ── Pricing table (USD per 1 M tokens) ───────────────────────
PRICING = {
    "gemini-2.0-flash":     {"input": 0.10, "output": 0.40},
    "gemini-1.5-flash":     {"input": 0.075, "output": 0.30},
    "gpt-4o-mini":          {"input": 0.15,  "output": 0.60},
    "claude-haiku-4-5":     {"input": 0.25,  "output": 1.25},
}
DEFAULT_PRICING = {"input": 0.10, "output": 0.40}


def _conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(str(DB_PATH))


def init_db():
    """Create the usage table if it doesn't exist."""
    with _conn() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS usage_log (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                ts             TEXT    NOT NULL,
                date           TEXT    NOT NULL,
                session_id     TEXT,
                model          TEXT    NOT NULL,
                input_tokens   INTEGER NOT NULL,
                output_tokens  INTEGER NOT NULL,
                cost_usd       REAL    NOT NULL,
                query_preview  TEXT
            )
        """)


init_db()


def _cost(model: str, input_tok: int, output_tok: int) -> float:
    p = PRICING.get(model, DEFAULT_PRICING)
    return (input_tok * p["input"] + output_tok * p["output"]) / 1_000_000


def record_usage(
    model: str,
    input_tokens: int,
    output_tokens: int,
    query: str = "",
    session_id: str = "anon",
):
    """Write one row to the usage log."""
    now = datetime.utcnow()
    cost = _cost(model, input_tokens, output_tokens)
    with _conn() as con:
        con.execute(
            """INSERT INTO usage_log
               (ts, date, session_id, model, input_tokens, output_tokens, cost_usd, query_preview)
               VALUES (?,?,?,?,?,?,?,?)""",
            (
                now.isoformat(),
                now.date().isoformat(),
                session_id,
                model,
                input_tokens,
                output_tokens,
                cost,
                query[:120],
            ),
        )


# ── Read helpers for the dashboard ───────────────────────────

def get_daily_summary() -> list[dict]:
    """Return per-day totals."""
    with _conn() as con:
        rows = con.execute("""
            SELECT date,
                   COUNT(*)           AS queries,
                   SUM(input_tokens)  AS input_tokens,
                   SUM(output_tokens) AS output_tokens,
                   SUM(cost_usd)      AS cost_usd
            FROM usage_log
            GROUP BY date
            ORDER BY date DESC
            LIMIT 30
        """).fetchall()
    return [
        {
            "date": r[0], "queries": r[1],
            "input_tokens": r[2], "output_tokens": r[3],
            "cost_usd": round(r[4], 6),
        }
        for r in rows
    ]


def get_total_summary() -> dict:
    """All-time totals."""
    with _conn() as con:
        r = con.execute("""
            SELECT COUNT(*),
                   COALESCE(SUM(input_tokens), 0),
                   COALESCE(SUM(output_tokens), 0),
                   COALESCE(SUM(cost_usd), 0)
            FROM usage_log
        """).fetchone()
    return {
        "total_queries": r[0],
        "total_input_tokens": r[1],
        "total_output_tokens": r[2],
        "total_cost_usd": round(r[3], 6),
        "avg_cost_per_query": round(r[3] / max(r[0], 1), 6),
    }


def get_today_summary() -> dict:
    today = date.today().isoformat()
    with _conn() as con:
        r = con.execute("""
            SELECT COUNT(*),
                   COALESCE(SUM(input_tokens), 0),
                   COALESCE(SUM(output_tokens), 0),
                   COALESCE(SUM(cost_usd), 0)
            FROM usage_log WHERE date = ?
        """, (today,)).fetchone()
    return {
        "date": today,
        "queries": r[0],
        "input_tokens": r[1],
        "output_tokens": r[2],
        "cost_usd": round(r[3], 6),
    }


def get_recent_queries(limit: int = 20) -> list[dict]:
    with _conn() as con:
        rows = con.execute("""
            SELECT ts, session_id, model, input_tokens, output_tokens,
                   cost_usd, query_preview
            FROM usage_log
            ORDER BY id DESC LIMIT ?
        """, (limit,)).fetchall()
    return [
        {
            "ts": r[0], "session_id": r[1], "model": r[2],
            "input_tokens": r[3], "output_tokens": r[4],
            "cost_usd": round(r[5], 6), "query": r[6],
        }
        for r in rows
    ]
