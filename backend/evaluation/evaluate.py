import json
from pathlib import Path
import sys
from pathlib import Path
import time
from google.api_core.exceptions import ResourceExhausted

project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

from src.rag_core import answer_question

# Files
DATASET_FILE = Path("evaluation/golden_dataset.json")
OUTPUT_FILE = Path("evaluation/evaluation_results.json")


def load_dataset():
    with open(DATASET_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def main():

    dataset = load_dataset()

    results = []

    total_questions = len(dataset)

    print(f"Evaluating {total_questions} questions...\n")

    for item in dataset:

        question = item["question"]

        print(f"Question: {question}")

        while True:
            try:
                rag_result = answer_question(question)
                break

            except ResourceExhausted:
                print("Rate limit reached. Waiting 30 seconds...")
                time.sleep(15)
        

        result = {
            "id": item["id"],
            "question": question,
            "reference_answer": item["reference_answer"],
            "rag_answer": rag_result["answer"],
            "expected_source": item["source"],
            "retrieved_sources": rag_result["sources"]
        }

        results.append(result)

        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

    print("\nEvaluation completed.")
    print(f"Results saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()