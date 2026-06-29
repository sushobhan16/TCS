import os
import json
import numpy as np
from pathlib import Path
from dotenv import load_dotenv

from sentence_transformers import SentenceTransformer
# from sklearn.metrics.pairwise import cosine_similarity
from vector_store import search_similar
from langfuse_logger import langfuse

import google.generativeai as genai
from guardrails import (
    detect_prompt_injection,
    detect_out_of_scope,
    check_query_length,
    low_retrieval_confidence
)

# ==========================================
# Configuration
# ==========================================

CHUNKS_FILE = Path("data/processed/chunks.json")
EMBEDDINGS_FILE = Path("data/processed/embeddings.npy")
PROMPT_FILE = Path("prompts/prompt_v1.txt")

def load_prompt():

    with open(PROMPT_FILE, "r", encoding="utf-8") as f:
        return f.read()

TOP_K = 3

# ==========================================
# Load API Key
# ==========================================

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

genai.configure(api_key=GOOGLE_API_KEY)

llm = genai.GenerativeModel("gemini-2.5-flash")

# ==========================================
# Load Embedding Model
# ==========================================

embedding_model = SentenceTransformer(
    "sentence-transformers/all-MiniLM-L6-v2"
)

# ==========================================
# Load Documents & Embeddings
# ==========================================

print("Loading chunks...")

with open(CHUNKS_FILE, "r", encoding="utf-8") as f:
    chunks = json.load(f)

embeddings = np.load(EMBEDDINGS_FILE)

print(f"Loaded {len(chunks)} chunks")
print(f"Embeddings Shape: {embeddings.shape}")

# ==========================================
# Retrieval Function
# ==========================================

# def retrieve(query, top_k=TOP_K):

#     query_embedding = embedding_model.encode(
#         [query],
#         convert_to_numpy=True
#     )

#     similarity_scores = cosine_similarity(
#         embeddings,
#         query_embedding
#     ).flatten()

#     top_indices = similarity_scores.argsort()[::-1][:top_k]

#     results = []

#     for idx in top_indices:

#         results.append({
#             "score": float(similarity_scores[idx]),
#             "source": chunks[idx]["source"],
#             "chunk_id": chunks[idx]["chunk_id"],
#             "text": chunks[idx]["text"]
#         })

#     return results
def retrieve(query, top_k=TOP_K):

    query_embedding = embedding_model.encode(
        query,
        convert_to_numpy=True
    )

    rows = search_similar(
        query_embedding,
        top_k
    )

    results = []

    for row in rows:

        chunk_id, source, text, distance = row

        results.append({
            "score": 1 - float(distance),
            "source": source,
            "chunk_id": chunk_id,
            "text": text
        })

    return results

# ==========================================
# RAG Function
# ==========================================

def answer_question(question):

    langfuse.create_event(
        name="question_received",
        input={
            "question": question
        }
    )

    # -------------------------
    # Guardrails
    # -------------------------

    if check_query_length(question):

        return {
            "answer":
            "Query exceeds maximum allowed length.",
            "sources": []
        }

    if detect_prompt_injection(question):

        return {
            "answer":
            "Prompt injection attempt detected. Query rejected.",
            "sources": []
        }

    if detect_out_of_scope(question):

        return {
            "answer":
            "This question is outside the scope of institutional documents.",
            "sources": []
        }

    # -------------------------
    # Retrieval
    # -------------------------

    retrieved_chunks = retrieve(question)

    if low_retrieval_confidence(retrieved_chunks):

        return {
            "answer":
            "I could not find relevant information in the institutional documents.",
            "sources": []
        }

    context = "\n\n".join(
        chunk["text"]
        for chunk in retrieved_chunks
    )

    # Preserve order of retrieved sources
    sources = []

    for chunk in retrieved_chunks:

        if chunk["source"] not in sources:
            sources.append(chunk["source"])

    # Log Retrieval Event
    langfuse.create_event(
        name="retrieval",
        metadata={
            "sources": sources
        }
    )

    # -------------------------
    # Prompt
    # -------------------------

    prompt_template = load_prompt()

    prompt = prompt_template.format(
        context=context,
        question=question
    )

    # -------------------------
    # Generation
    # -------------------------

    response = llm.generate_content(prompt)

    langfuse.create_event(
        name="generation",
        input={
            "question": question
        },
        output={
            "answer": response.text
        }
    )

    langfuse.flush()

    return {
        "answer": response.text,
        "sources": sources
    }