import json
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

from src.rag_core import retrieve

DATASET_FILE = Path("evaluation/golden_dataset.json")
OUTPUT_FILE = Path("evaluation/retrieval_results.json")


def load_dataset():
    with open(DATASET_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def main():

    dataset = load_dataset()

    results = []

    correct = 0

    print(f"Evaluating retrieval on {len(dataset)} questions...\n")

    for item in dataset:

        question = item["question"]
        expected_source = item["source"]

        retrieved_chunks = retrieve(question)

        retrieved_sources = []

        for chunk in retrieved_chunks:

            if chunk["source"] not in retrieved_sources:
                retrieved_sources.append(chunk["source"])

        hit = expected_source in retrieved_sources

        if hit:
            correct += 1

        result = {
            "id": item["id"],
            "question": question,
            "expected_source": expected_source,
            "retrieved_sources": retrieved_sources,
            "hit": hit
        }

        results.append(result)

        print(
            f"[{'✓' if hit else '✗'}] "
            f"Question {item['id']}: {question}"
        )

    accuracy = (correct / len(dataset)) * 100

    summary = {
        "total_questions": len(dataset),
        "correct_retrievals": correct,
        "retrieval_accuracy": round(accuracy, 2)
    }

    output = {
        "summary": summary,
        "results": results
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 50)
    print("RETRIEVAL EVALUATION COMPLETE")
    print("=" * 50)

    print(f"Total Questions: {len(dataset)}")
    print(f"Correct Retrievals: {correct}")
    print(f"Retrieval Accuracy: {accuracy:.2f}%")

    print(f"\nResults saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()