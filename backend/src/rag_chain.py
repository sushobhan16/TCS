"""
rag_chain.py — LangChain-powered RAG pipeline.

Replaces the raw google.generativeai calls with a proper LangChain
LCEL chain, giving us: prompt versioning, token counting, and a clean
interface for the FastAPI layer.
"""

import os
import time
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores.pgvector import PGVector

from guardrails import (
    detect_prompt_injection,
    detect_out_of_scope,
    check_query_length,
    low_retrieval_confidence,
)
from langfuse_logger import langfuse
from cost_tracker import record_usage

load_dotenv()

# ──────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────
PROMPT_DIR = Path(__file__).parent.parent / "prompts"
PROMPT_VERSION = "v2"          # bump this when you edit the prompt
MODEL_NAME = "gemini-2.0-flash"   # cost-efficient tier

CONNECTION_STRING = PGVector.connection_string_from_db_params(
    driver="psycopg2",
    host=os.getenv("DB_HOST", "localhost"),
    port=int(os.getenv("DB_PORT", 5432)),
    database=os.getenv("DB_NAME", "ikrs"),
    user=os.getenv("DB_USER", "postgres"),
    password=os.getenv("DB_PASSWORD", ""),
)

COLLECTION_NAME = "document_chunks"
TOP_K = 3

# ──────────────────────────────────────────────────────────────
# Embedding model (same as ingestion — must stay consistent)
# ──────────────────────────────────────────────────────────────
embeddings = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2",
    model_kwargs={"device": "cpu"},
)

# ──────────────────────────────────────────────────────────────
# LangChain PGVector retriever
# ──────────────────────────────────────────────────────────────
vector_store = PGVector(
    connection_string=CONNECTION_STRING,
    embedding_function=embeddings,
    collection_name=COLLECTION_NAME,
)
retriever = vector_store.as_retriever(search_kwargs={"k": TOP_K})

# ──────────────────────────────────────────────────────────────
# LLM
# ──────────────────────────────────────────────────────────────
llm = ChatGoogleGenerativeAI(
    model=MODEL_NAME,
    google_api_key=os.getenv("GOOGLE_API_KEY"),
    temperature=0.0,          # deterministic answers
    max_output_tokens=512,
)

# ──────────────────────────────────────────────────────────────
# Prompt (versioned file on disk, tracked in Git)
# ──────────────────────────────────────────────────────────────
def _load_prompt(version: str = PROMPT_VERSION) -> PromptTemplate:
    prompt_file = PROMPT_DIR / f"prompt_{version}.txt"
    if not prompt_file.exists():
        # Fall back gracefully to v1
        prompt_file = PROMPT_DIR / "prompt_v1.txt"
    template = prompt_file.read_text(encoding="utf-8")
    return PromptTemplate.from_template(template)


def _format_docs(docs) -> str:
    return "\n\n".join(doc.page_content for doc in docs)


# ──────────────────────────────────────────────────────────────
# LCEL chain
# ──────────────────────────────────────────────────────────────
def build_chain():
    prompt = _load_prompt()
    chain = (
        {
            "context": retriever | RunnableLambda(_format_docs),
            "question": RunnablePassthrough(),
        }
        | prompt
        | llm
        | StrOutputParser()
    )
    return chain


_chain = None   # lazy-initialised so imports don't block


def get_chain():
    global _chain
    if _chain is None:
        _chain = build_chain()
    return _chain


# ──────────────────────────────────────────────────────────────
# Public API: answer_question
# ──────────────────────────────────────────────────────────────
def answer_question(question: str, session_id: Optional[str] = None) -> dict:
    """
    Full RAG pipeline with guardrails, observability, and cost tracking.

    Returns
    -------
    dict with keys:
        answer        – the generated answer string
        sources       – list of source document names
        guardrail     – None or the guardrail name that fired
        latency_ms    – total wall-clock time in milliseconds
        prompt_version – the prompt version used
    """
    start = time.perf_counter()

    trace = langfuse.trace(
        name="rag_query",
        input={"question": question},
        session_id=session_id,
        tags=[f"prompt:{PROMPT_VERSION}", f"model:{MODEL_NAME}"],
    )

    # ── Guardrails ───────────────────────────────────────────
    if check_query_length(question):
        return _guardrail_response(
            trace, start, "length_exceeded",
            "Query exceeds maximum allowed length.",
        )

    if detect_prompt_injection(question):
        return _guardrail_response(
            trace, start, "prompt_injection",
            "Prompt injection attempt detected. Query rejected.",
        )

    if detect_out_of_scope(question):
        return _guardrail_response(
            trace, start, "out_of_scope",
            "This question is outside the scope of institutional documents.",
        )

    # ── Retrieval ────────────────────────────────────────────
    retrieval_span = trace.span(name="retrieval")
    docs = retriever.invoke(question)

    retrieved = [
        {"score": float(getattr(d, "metadata", {}).get("score", 0.0)),
         "source": d.metadata.get("source", "unknown"),
         "text": d.page_content}
        for d in docs
    ]

    if low_retrieval_confidence(retrieved):
        retrieval_span.end(output={"chunks": len(retrieved), "fired": "low_confidence"})
        return _guardrail_response(
            trace, start, "low_confidence",
            "I could not find relevant information in the institutional documents.",
        )

    sources = list(dict.fromkeys(r["source"] for r in retrieved))
    retrieval_span.end(output={"sources": sources, "chunks": len(retrieved)})

    # ── Generation ───────────────────────────────────────────
    gen_span = trace.span(name="generation", input={"question": question})
    answer = get_chain().invoke(question)
    latency_ms = int((time.perf_counter() - start) * 1000)

    # Rough token estimate (Gemini doesn't expose exact counts via LangChain yet)
    input_tokens = (len(question) + sum(len(r["text"]) for r in retrieved)) // 4
    output_tokens = len(answer) // 4

    gen_span.end(
        output={"answer": answer, "latency_ms": latency_ms},
        metadata={
            "model": MODEL_NAME,
            "prompt_version": PROMPT_VERSION,
            "input_tokens_est": input_tokens,
            "output_tokens_est": output_tokens,
        },
    )

    # ── Cost tracking ────────────────────────────────────────
    record_usage(
        model=MODEL_NAME,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        query=question,
        session_id=session_id or "anon",
    )

    trace.update(
        output={"answer": answer, "sources": sources},
        metadata={"latency_ms": latency_ms, "prompt_version": PROMPT_VERSION},
    )
    langfuse.flush()

    return {
        "answer": answer,
        "sources": sources,
        "guardrail": None,
        "latency_ms": latency_ms,
        "prompt_version": PROMPT_VERSION,
    }


# ── Helper ───────────────────────────────────────────────────
def _guardrail_response(trace, start, name: str, message: str) -> dict:
    latency_ms = int((time.perf_counter() - start) * 1000)
    trace.update(
        output={"answer": message, "guardrail": name},
        metadata={"latency_ms": latency_ms},
    )
    langfuse.flush()
    return {
        "answer": message,
        "sources": [],
        "guardrail": name,
        "latency_ms": latency_ms,
        "prompt_version": PROMPT_VERSION,
    }
