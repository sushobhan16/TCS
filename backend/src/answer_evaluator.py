"""
answer_evaluator.py — LLM-as-judge evaluation for RAG answers.

Scores each (question, reference_answer, rag_answer) triple on:
  • faithfulness  – is the answer grounded in retrieved context?
  • relevance     – does the answer actually address the question?
  • correctness   – does it match the reference answer?

Scores are 1-5.  We use a structured JSON prompt so the output is
machine-parseable even with a generative model.
"""

import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

# Use a cheap model for evaluation (it's called many times)
_judge = genai.GenerativeModel("gemini-2.0-flash")

JUDGE_PROMPT = """You are an expert evaluator for a RAG-based institutional knowledge chatbot.

Evaluate the following RAG answer against the reference answer and question.

Question: {question}

Reference Answer: {reference_answer}

RAG Answer: {rag_answer}

Score the RAG answer on three dimensions (1 = very poor, 5 = excellent):

1. faithfulness   – Is the answer grounded in real institutional knowledge and free of hallucination?
2. relevance      – Does the answer directly address the question asked?
3. correctness    – How closely does the answer match the reference answer in facts and meaning?

Respond ONLY with a valid JSON object in exactly this format (no markdown, no extra text):
{{
  "faithfulness": <1-5>,
  "relevance": <1-5>,
  "correctness": <1-5>,
  "reasoning": "<one sentence explanation>"
}}"""


def evaluate_answer(
    question: str,
    reference_answer: str,
    rag_answer: str,
    retries: int = 3,
) -> dict:
    """
    Returns a dict with faithfulness, relevance, correctness (all 1-5)
    and a reasoning string.
    """
    prompt = JUDGE_PROMPT.format(
        question=question,
        reference_answer=reference_answer,
        rag_answer=rag_answer,
    )

    for attempt in range(retries):
        try:
            response = _judge.generate_content(prompt)
            text = response.text.strip()

            # Strip any accidental markdown fences
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            text = text.strip()

            scores = json.loads(text)
            return {
                "faithfulness": int(scores.get("faithfulness", 0)),
                "relevance":    int(scores.get("relevance", 0)),
                "correctness":  int(scores.get("correctness", 0)),
                "reasoning":    scores.get("reasoning", ""),
                "error":        None,
            }

        except Exception as exc:
            if attempt < retries - 1:
                time.sleep(15)   # back off on rate limit
            else:
                return {
                    "faithfulness": 0,
                    "relevance":    0,
                    "correctness":  0,
                    "reasoning":    "",
                    "error":        str(exc),
                }


def run_evaluation_suite(
    dataset_path: str | Path,
    output_path: str | Path,
    answer_fn,   # callable(question) -> {"answer": str, "sources": list}
) -> dict:
    """
    Run the full golden-dataset evaluation and write results to JSON.

    Parameters
    ----------
    dataset_path : path to golden_dataset.json
    output_path  : where to write evaluation_results.json
    answer_fn    : function that answers a question (your RAG pipeline)

    Returns
    -------
    dict with aggregate metrics
    """
    dataset_path = Path(dataset_path)
    output_path = Path(output_path)

    with open(dataset_path, encoding="utf-8") as f:
        dataset = json.load(f)

    results = []
    total = len(dataset)

    print(f"Evaluating {total} questions with LLM-as-judge...\n")

    for i, item in enumerate(dataset, 1):
        question = item["question"]
        reference = item["reference_answer"]
        print(f"[{i}/{total}] {question[:60]}...")

        # Get RAG answer (with rate-limit retry baked in)
        for attempt in range(3):
            try:
                rag_result = answer_fn(question)
                break
            except Exception:
                time.sleep(15)

        rag_answer = rag_result.get("answer", "")
        sources = rag_result.get("sources", [])

        # Score it
        scores = evaluate_answer(question, reference, rag_answer)

        result = {
            "id":                item["id"],
            "question":          question,
            "reference_answer":  reference,
            "rag_answer":        rag_answer,
            "expected_source":   item.get("source", ""),
            "retrieved_sources": sources,
            "source_match":      item.get("source", "") in sources,
            **scores,
        }
        results.append(result)

        # Save incrementally so we don't lose progress
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        time.sleep(2)   # gentle throttle

    # Aggregate
    scored = [r for r in results if r["error"] is None]
    n = max(len(scored), 1)
    agg = {
        "total_questions":       total,
        "evaluated_successfully": len(scored),
        "avg_faithfulness":  round(sum(r["faithfulness"] for r in scored) / n, 2),
        "avg_relevance":     round(sum(r["relevance"]    for r in scored) / n, 2),
        "avg_correctness":   round(sum(r["correctness"]  for r in scored) / n, 2),
        "source_match_pct":  round(sum(r["source_match"] for r in results) / total * 100, 1),
    }
    agg["composite_score"] = round(
        (agg["avg_faithfulness"] + agg["avg_relevance"] + agg["avg_correctness"]) / 3, 2
    )

    # Append aggregate to output file
    summary_path = output_path.parent / "evaluation_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(agg, f, indent=2)

    print("\n── Evaluation Complete ──────────────────────────")
    for k, v in agg.items():
        print(f"  {k}: {v}")
    print(f"\nDetailed results → {output_path}")
    print(f"Summary          → {summary_path}")

    return agg
