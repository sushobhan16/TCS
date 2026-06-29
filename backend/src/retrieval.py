import json
import numpy as np
from pathlib import Path
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

# File paths
CHUNKS_FILE = Path("-Institutional_Knowledge_Retrieval_System_/data/processed/chunks.json")
EMBEDDINGS_FILE = Path("-Institutional_Knowledge_Retrieval_System_/data/processed/embeddings.npy")

TOP_K = 5


def load_data():
    """Load chunks and embeddings."""
    with open(CHUNKS_FILE, "r", encoding="utf-8") as f:
        chunks = json.load(f)

    embeddings = np.load(EMBEDDINGS_FILE)

    return chunks, embeddings


def load_model():
    """Load the same model used for document embeddings."""
    return SentenceTransformer(
        "sentence-transformers/all-MiniLM-L6-v2"
    )


def retrieve(query, model, chunks, embeddings, top_k=TOP_K):
    """Retrieve most relevant chunks."""

    query_embedding = model.encode(
        [query],
        convert_to_numpy=True
    )

    similarity_scores = cosine_similarity(
        embeddings,
        query_embedding
    ).flatten()

    top_indices = similarity_scores.argsort()[::-1][:top_k]

    results = []

    for idx in top_indices:
        results.append({
            "score": float(similarity_scores[idx]),
            "source": chunks[idx]["source"],
            "chunk_id": chunks[idx]["chunk_id"],
            "text": chunks[idx]["text"]
        })

    return results


def main():

    print("Loading data...")
    chunks, embeddings = load_data()

    print("Loading embedding model...")
    model = load_model()

    while True:

        query = input("\nAsk a question (or type 'exit'): ")

        if query.lower() == "exit":
            break

        results = retrieve(
            query=query,
            model=model,
            chunks=chunks,
            embeddings=embeddings
        )

        print("\nTop Retrieved Chunks")
        print("=" * 80)

        for rank, result in enumerate(results, start=1):

            print(f"\nRank #{rank}")
            print(f"Similarity Score: {result['score']:.4f}")
            print(f"Source: {result['source']}")
            print(f"Chunk ID: {result['chunk_id']}")
            print("\nPreview:")
            print(result["text"][:500])
            print("-" * 80)


if __name__ == "__main__":
    main()