"""FastAPI application entrypoint."""

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

# Load .env file manually into os.environ for botocore credentials resolution
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip()
                # Strip quotes if present
                if val.startswith('"') and val.endswith('"'):
                    val = val[1:-1]
                elif val.startswith("'") and val.endswith("'"):
                    val = val[1:-1]
                os.environ[key] = val

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from app.api.ingest import router as ingest_router
from app.api.query import router as query_router
from app.api.traces import router as traces_router
from app.api.conversations import router as conversations_router
from app.config import get_settings
from app.core.retriever import BM25Index, VectorStore
from app.db import DatabaseHelper
from app.pipeline import RAGPipeline
from app.providers import create_embedder, create_llm, create_vision_llm

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize clients and indexes once at startup."""
    settings = get_settings()
    app.state.settings = settings
    
    # Initialize DB (optional, falls back gracefully if Postgres is offline)
    try:
        app.state.db = DatabaseHelper(settings.database_url)
        await app.state.db.init_tables()
        logging.info("Connected to PostgreSQL database successfully.")
    except Exception as exc:
        logging.warning(
            "Could not connect to PostgreSQL database (%s).\n"
            "Pipeline will run in-memory without conversation DB persistence.\n"
            "To enable DB persistence, run: docker compose -f docker-compose.dev.yml up -d",
            exc,
        )
        app.state.db = None

    app.state.llm = create_llm(settings)
    app.state.vision_llm = create_vision_llm(settings)
    app.state.embedder = create_embedder(settings)
    app.state.store = VectorStore(settings)
    try:
        await app.state.store.ensure_collection()
        all_points = await app.state.store.scroll_all()
        logging.info("Connected to Qdrant Vector Database successfully.")
    except Exception as exc:
        logging.warning(
            "Could not connect to Qdrant Vector Database (%s).\n"
            "Pipeline will run using BM25 index & in-memory store.\n"
            "To enable Qdrant, run: docker compose -f docker-compose.dev.yml up -d",
            exc,
        )
        all_points = []

    app.state.bm25 = BM25Index()
    app.state.bm25.build(all_points)
    app.state.pipeline = RAGPipeline(
        settings, app.state.llm, app.state.embedder, app.state.store, app.state.bm25, app.state.db
    )
    yield




app = FastAPI(
    title="Advanced RAG System",
    description="Multi-stage RAG pipeline: routing, decomposition, hybrid retrieval, "
    "grading, reranking, grounded generation, and verification.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ingest_router, tags=["ingestion"])
app.include_router(query_router, tags=["query"])
app.include_router(traces_router, tags=["tracing"])
app.include_router(conversations_router, tags=["conversations"])


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/dashboard", response_class=HTMLResponse, include_in_schema=False)
@app.get("/traces-dashboard", response_class=HTMLResponse, include_in_schema=False)
async def serve_dashboard_page() -> HTMLResponse:
    from app.api.traces import _get_dashboard_html
    return HTMLResponse(_get_dashboard_html())

