from database import get_connection
from pgvector.psycopg2 import register_vector

def search_similar(query_embedding, top_k=5):

    conn = get_connection()
    register_vector(conn)

    cur = conn.cursor()

    cur.execute(
        """
        SELECT
            chunk_id,
            source,
            content,
            embedding <=> %s::vector AS distance
        FROM document_chunks
        ORDER BY embedding <=> %s::vector
        LIMIT %s
        """,
        (
            query_embedding.tolist(),
            query_embedding.tolist(),
            top_k
        )
    )

    rows = cur.fetchall()

    cur.close()
    conn.close()
    # print("Using PostgreSQL pgvector retrieval...")

    return rows