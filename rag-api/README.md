# Advanced RAG System

A production-grade Retrieval-Augmented Generation (RAG) pipeline built with **Python** and **FastAPI**. It is designed to handle hard questions: multi-part questions whose parts need different chunks, inference/reasoning questions, and comparisons - all in a single pipeline.

Answers are always returned in **Egyptian Arabic**, while all code and prompts are in English.

## Pipeline

```
question
  -> Query Router        (simple / multi_part / inferential / comparative, HyDE on/off)
  -> Query Decomposer    (standalone sub-questions, one retrieval each)
  -> Multi-Query Expansion (+ HyDE for inferential questions)
  -> Hybrid Retrieval    (Qdrant dense + BM25 sparse, fused with RRF, per sub-question)
  -> Retrieval Grader    (CRAG-style: rewrite query and retry if context is insufficient)
  -> Reranker            (LLM listwise scoring, top-N)
  -> Generator           (grounded answer in Egyptian Arabic with [n] citations)
  -> Verifier            (completeness + groundedness check, auto-revision)
```

Ingestion uses **parent-child chunking** (small chunks indexed, large parents returned for context) with **contextual enrichment** (an LLM-generated summary prepended to every chunk before indexing).

## Project layout

```
app/
  main.py            # FastAPI app + lifespan (models/clients loaded once)
  pipeline.py        # orchestrator wiring all stages (fully traced)
  config.py          # pydantic-settings (env prefix RAG_)
  schemas.py         # request/response models
  prompts.py         # all English prompts
  llm.py             # OpenAI-compatible async LLM client
  bedrock.py         # AWS Bedrock LLM (Converse API) + Titan embeddings
  providers.py       # provider factories (openai | bedrock)
  dashboard.py       # self-contained HTML debug dashboard
  api/
    ingest.py        # POST /ingest, GET /ingest/status/{job_id}
    query.py         # POST /query, POST /query/stream (SSE)
    traces.py        # GET /traces, GET /traces/{id}, GET /dashboard
  core/
    chunker.py       # parsing + parent-child chunking
    embedder.py      # batched async embeddings (OpenAI-compatible)
    retriever.py     # Qdrant + BM25 + RRF hybrid retrieval
    router.py        # question classification
    decomposer.py    # decomposition, expansion, HyDE
    grader.py        # CRAG retrieval grading
    reranker.py      # LLM listwise reranking
    generator.py     # grounded generation with citations
    verifier.py      # answer verification and revision
    status.py        # user-facing progress messages for streaming
    tracing.py       # step-by-step tracing (logs + trace store)
```

## Quick start

1. Copy the environment template and fill in your keys:

```bash
cp .env.example .env
```

2. Run with Docker Compose (starts Qdrant + the API):

```bash
docker compose up --build
```

Or run locally (requires a running Qdrant at `RAG_QDRANT_URL`):

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## API usage

Ingest documents (PDF, DOCX, TXT, MD, HTML):

```bash
curl -X POST http://localhost:8000/ingest -F "files=@document.pdf"
curl http://localhost:8000/ingest/status/<job_id>
```

Ask a question (answer in Egyptian Arabic, with citations, sources, and a trace_id):

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question": "Compare X and Y, and explain why Z happens"}'
```

Stream the answer over SSE. Events arrive in this order:

1. `status` - user-facing progress messages in Egyptian Arabic, one per pipeline stage (`understanding`, `searching`, `ranking`, `generating`). The `searching` message adapts to the detected question type, e.g. it mentions how many parts a multi-part question has. Payload: `{"stage": "...", "message": "..."}`.
2. `meta` - question type, sub-questions, sources, and `trace_id` (JSON).
3. `token` - answer text chunks, streamed incrementally.
4. `done` - end of stream.

```bash
curl -N -X POST http://localhost:8000/query/stream \
  -H "Content-Type: application/json" \
  -d '{"question": "..."}'
```

## Tracing, logs, and dashboard

Every pipeline stage is recorded step by step (inputs, outputs, durations):

- **Logs**: the `rag.pipeline` logger prints one line per step (`trace=<id> step=routing duration_ms=... output=...`), so you can follow everything in the console.
- **`GET /traces`**: summaries of the most recent runs (bounded in-memory store).
- **`GET /traces/{trace_id}`**: the full trace as JSON - routing decision, sub-questions, expanded queries, HyDE passage, grader verdicts, rewritten queries, retrieved chunks with scores, reranking selection, draft answer, and verification result. Every `/query` response includes its `trace_id`.
- **`GET /dashboard`**: a built-in web dashboard (Arabic, RTL) listing recent questions. Click one to see every step with its result, copy any single step, copy the whole pipeline trace as JSON, or copy the final answer - ideal for iterating on retrieval quality.

## Model providers

The pipeline is provider-agnostic. Choose per component via env vars:

```bash
RAG_LLM_PROVIDER=openai|bedrock
RAG_EMBEDDING_PROVIDER=openai|bedrock
```

### OpenAI-compatible (default)

Works with OpenAI or any compatible endpoint (Groq, Together, vLLM, Ollama, ...). Configure `RAG_LLM_BASE_URL`, `RAG_LLM_API_KEY`, `RAG_LLM_MODEL`, `RAG_LLM_SMALL_MODEL`, and the `RAG_EMBEDDING_*` equivalents.

### AWS Bedrock

Uses the **Converse API** for chat (with streaming) and **Titan Text Embeddings v2** via `invoke_model`. Credentials are resolved by the standard AWS chain (`AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` env vars, shared config file, or IAM role).

```bash
RAG_LLM_PROVIDER=bedrock
RAG_EMBEDDING_PROVIDER=bedrock
RAG_AWS_REGION=us-east-1
RAG_BEDROCK_LLM_MODEL_ID=us.anthropic.claude-sonnet-4-20250514-v1:0
RAG_BEDROCK_LLM_SMALL_MODEL_ID=us.anthropic.claude-3-5-haiku-20241022-v1:0
RAG_BEDROCK_EMBEDDING_MODEL_ID=amazon.titan-embed-text-v2:0
RAG_EMBEDDING_DIM=1024   # Titan v2 supports 256, 512, or 1024
```

Notes:
- Any Bedrock chat model that supports the Converse API works (Anthropic Claude, Meta Llama, Amazon Nova, Mistral, ...). Use cross-region inference profile IDs (`us.`/`eu.` prefix) where required.
- You can mix providers, e.g. Bedrock for the LLM and an OpenAI-compatible server for embeddings.
- Changing `RAG_EMBEDDING_DIM` requires re-creating the Qdrant collection (delete it or change `RAG_COLLECTION_NAME`) and re-ingesting documents.

## Configuration

All settings are environment variables with the `RAG_` prefix (see `.env.example`).

| Variable | Purpose |
|---|---|
| `RAG_LLM_PROVIDER` / `RAG_EMBEDDING_PROVIDER` | `openai` (any compatible API) or `bedrock` |
| `RAG_LLM_MODEL` / `RAG_LLM_SMALL_MODEL` | main generation model / cheap model for routing, grading, enrichment |
| `RAG_BEDROCK_LLM_MODEL_ID` / `RAG_BEDROCK_LLM_SMALL_MODEL_ID` | Bedrock model IDs (Converse API) |
| `RAG_EMBEDDING_MODEL` / `RAG_EMBEDDING_DIM` | embedding model and its vector size |
| `RAG_ENABLE_CONTEXTUAL_ENRICHMENT` | toggle LLM contextual summaries during ingestion |
| `RAG_RERANK_TOP_N` | number of chunks passed to the generator |
| `RAG_MAX_RETRIEVAL_RETRIES` | CRAG retry budget per sub-question |
