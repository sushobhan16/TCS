import json
import numpy as np
from pathlib import Path

from pgvector.psycopg2 import register_vector

from database import get_connection

CHUNKS_FILE = Path("data/processed/chunks.json")
EMBEDDINGS_FILE = Path("data/processed/embeddings.npy")


def main():

    print("Loading chunks...")
    with open(CHUNKS_FILE, "r", encoding="utf-8") as f:
        chunks = json.load(f)

    print("Loading embeddings...")
    embeddings = np.load(EMBEDDINGS_FILE)

    print(f"Chunks: {len(chunks)}")
    print(f"Embeddings: {embeddings.shape}")

    conn = get_connection()

    register_vector(conn)

    cur = conn.cursor()

    print("Inserting into PostgreSQL...")

    for chunk, embedding in zip(chunks, embeddings):

        cur.execute(
            """
            INSERT INTO document_chunks
            (chunk_id, source, content, embedding)
            VALUES (%s, %s, %s, %s)
            """,
            (
                chunk["chunk_id"],
                chunk["source"],
                chunk["text"],
                embedding.tolist()
            )
        )

    conn.commit()

    print("Insertion Complete!")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()