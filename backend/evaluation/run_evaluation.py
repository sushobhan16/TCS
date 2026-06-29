"""
run_evaluation.py — CLI script to run the full LLM-as-judge evaluation.

Usage (from project root):
    python evaluation/run_evaluation.py

Outputs:
    evaluation/evaluation_results.json  — per-question scores
    evaluation/evaluation_summary.json  — aggregate metrics
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from answer_evaluator import run_evaluation_suite
from rag_chain import answer_question

if __name__ == "__main__":
    summary = run_evaluation_suite(
        dataset_path=Path(__file__).parent / "golden_dataset.json",
        output_path=Path(__file__).parent / "evaluation_results.json",
        answer_fn=answer_question,
    )
