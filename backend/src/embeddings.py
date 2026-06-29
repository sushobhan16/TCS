import json
import numpy as np
from pathlib import Path
from sentence_transformers import SentenceTransformer

# Paths
CHUNKS_FILE = Path("data/processed/chunks.json")
EMBEDDINGS_FILE = Path("data/processed/embeddings.npy")
METADATA_FILE = Path("data/processed/metadata.json")


def load_chunks():
    """Load chunks from JSON file."""
    with open(CHUNKS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def generate_embeddings(texts):
    """Generate embeddings using Sentence Transformers."""
    model = SentenceTransformer(
        "sentence-transformers/all-MiniLM-L6-v2"
    )

    embeddings = model.encode(
        texts,
        batch_size=32,
        show_progress_bar=True,
        convert_to_numpy=True
    )

    return embeddings


def save_metadata(chunks):
    """Save metadata separately."""
    metadata = []

    for chunk in chunks:
        metadata.append({
            "source": chunk["source"],
            "chunk_id": chunk["chunk_id"]
        })

    with open(METADATA_FILE, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    print(f"Metadata saved to {METADATA_FILE}")


def main():

    print("Loading chunks...")
    chunks = load_chunks()

    texts = [chunk["text"] for chunk in chunks]

    print(f"Loaded {len(texts)} chunks")

    print("Generating embeddings...")
    embeddings = generate_embeddings(texts)

    print("Saving embeddings...")
    np.save(EMBEDDINGS_FILE, embeddings)

    print(f"Embeddings saved to {EMBEDDINGS_FILE}")
    print(f"Embedding shape: {embeddings.shape}")

    save_metadata(chunks)

    print("Embedding pipeline completed successfully.")


if __name__ == "__main__":
    main()