# IKRS — Institutional Knowledge Retrieval System

**TCS LLMOps Capstone · Use Case A**

A production-grade RAG system that answers questions about institutional documents (fees, regulations, admissions, hostel, bridge courses) using a fully observable LLMOps pipeline.

---

## Architecture

```
PDF Corpus (50+ docs)
       │
       ▼
   Chunking (RecursiveCharacterTextSplitter — 1000 tokens, 200 overlap)
       │
       ▼
   Embeddings (sentence-transformers/all-MiniLM-L6-v2)
       │
       ▼
   pgvector (PostgreSQL vector store)
       │
   Query ──► Guardrails ──► Retrieval (cosine similarity, k=3)
                                  │
                                  ▼
                          LangChain LCEL Chain
                          (PromptTemplate v2 → Gemini 2.0 Flash)
                                  │
                    ┌─────────────┴─────────────┐
                    ▼                           ▼
              Langfuse tracing           SQLite cost tracker
                    │                           │
                    └─────────────┬─────────────┘
                                  ▼
                           FastAPI backend
                                  │
                                  ▼
                        React frontend (this)
```

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2` |
| Vector store | pgvector (PostgreSQL extension) |
| RAG framework | LangChain LCEL |
| LLM | Gemini 2.0 Flash (gemini-2.0-flash) |
| Observability | Langfuse |
| Backend API | FastAPI + Uvicorn |
| Frontend | React + Vite |
| Cost tracking | SQLite (`cost_usage.db`) |
| Containerisation | Docker + Docker Compose |

---

## Project Structure

```
TCS/
├── backend/
│   ├── src/
│   │   ├── api.py              # FastAPI endpoints
│   │   ├── rag_chain.py        # LangChain LCEL RAG pipeline
│   │   ├── rag_core.py         # Core RAG logic (pgvector)
│   │   ├── guardrails.py       # Injection, OOB, length, confidence guards
│   │   ├── cost_tracker.py     # SQLite token/cost logger
│   │   ├── langfuse_logger.py  # Langfuse client
│   │   ├── chunking.py         # PDF → chunks pipeline
│   │   ├── embeddings.py       # sentence-transformers embedding pipeline
│   │   ├── vector_store.py     # pgvector search
│   │   ├── load_to_pgvector.py # Bulk insert embeddings → PostgreSQL
│   │   ├── database.py         # psycopg2 connection helper
│   │   ├── ingestion.py        # PDF ingestion & metadata
│   │   ├── retrieval.py        # Standalone retrieval script
│   │   └── answer_evaluator.py # LLM-as-judge evaluation
│   ├── evaluation/
│   │   ├── golden_dataset.json      # 20-question reference set
│   │   ├── retrieval_results.json   # 85% retrieval accuracy results
│   │   ├── evaluate.py              # Full evaluation runner
│   │   ├── retrieval_evaluate.py    # Retrieval-only evaluation
│   │   └── run_evaluation.py        # Convenience entry-point
│   ├── prompts/
│   │   ├── prompt_v1.txt       # Initial prompt
│   │   └── prompt_v2.txt       # Improved prompt (+16pp faithfulness)
│   ├── data/processed/
│   │   ├── chunks.json         # Pre-chunked document corpus
│   │   └── metadata.json       # Chunk metadata
│   ├── docs/
│   │   └── daily_log.md        # Development log
│   ├── app.py                  # Streamlit UI (alternative to React)
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── App.jsx             # Main React application
│   │   └── main.jsx            # Entry point
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## Quick Start

### 1. Clone & configure

```bash
git clone https://github.com/sushobhan16/TCS.git
cd TCS
cp .env.example .env
# Fill in GOOGLE_API_KEY, LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, DB_*
```

### 2. Start PostgreSQL with pgvector

```bash
docker-compose up -d db
```

### 3. Build vector store

```bash
cd backend
pip install -r requirements.txt
python src/chunking.py          # chunk PDFs
python src/embeddings.py        # generate embeddings
python src/load_to_pgvector.py  # load into PostgreSQL
```

### 4. Start FastAPI backend

```bash
uvicorn src.api:app --reload --port 8000
```

### 5. Start React frontend

```bash
cd frontend
npm install
npm run dev
# Open http://localhost:3000
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/query` | RAG query — guardrails → retrieval → generation |
| `GET`  | `/health` | Liveness check |
| `GET`  | `/dashboard/today` | Today's token + cost summary |
| `GET`  | `/dashboard/daily` | Last 30 days breakdown |
| `GET`  | `/dashboard/total` | All-time totals |
| `GET`  | `/dashboard/recent-queries` | Last N queries |
| `POST` | `/evaluate` | Trigger background evaluation |
| `GET`  | `/evaluate/status` | Poll evaluation status |
| `GET`  | `/evaluate/results` | Per-question results |
| `GET`  | `/prompts` | List prompt versions |
| `GET`  | `/prompts/{version}` | Get prompt content |

---

## Guardrails

| Guard | Trigger | Latency |
|-------|---------|---------|
| Length limiter | Query > 500 chars | ~15ms |
| Injection guard | Pattern match (jailbreak strings) | ~38ms |
| Out-of-scope filter | Non-institutional keyword match | ~42ms |
| Confidence threshold | Similarity score < 0.30 | ~50ms |

---

## Evaluation Results

| Metric | Prompt v1 | Prompt v2 | Delta |
|--------|-----------|-----------|-------|
| Faithfulness | 72% | 88% | +16pp |
| Relevance | 68% | 85% | +17pp |
| Retrieval hit@3 | 80% | 85% | +5pp |
| Guardrail precision | 91% | 97% | +6pp |

---

## TCS Capstone Deliverables

- [x] Public GitHub repository with complete application and evaluation suite
- [x] Golden-dataset evaluation report showing performance across iterations
- [x] Langfuse trace export demonstrating end-to-end observability
- [x] Recorded demonstration including out-of-scope query and prompt injection attempt
- [x] React frontend covering all required technology stack integrations
- [x] Cost governance dashboard (daily cost, tokens, cost-per-query)
- [x] Prompt versioning under Git with evaluation impact tracking
- [x] Guardrails: injection detection, OOB rejection, token limits, confidence threshold

---

*Prepared for TCS Industry Engagement – Academic Partnership Programme*
