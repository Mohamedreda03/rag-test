"""Application settings loaded from environment variables (prefix: RAG_)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration for the RAG pipeline."""

    model_config = SettingsConfigDict(env_prefix="RAG_", env_file=".env", extra="ignore")

    # Provider selection: "openai" (any OpenAI-compatible API) or "bedrock"
    llm_provider: str = "openai"
    embedding_provider: str = "openai"

    # LLM (any OpenAI-compatible provider)
    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: str = "change-me"
    llm_model: str = "gpt-4o"
    llm_small_model: str = "gpt-4o-mini"  # used for routing, grading, enrichment, reranking

    # Embeddings (any OpenAI-compatible provider, including local servers)
    embedding_base_url: str = "https://api.openai.com/v1"
    embedding_api_key: str = "change-me"
    embedding_model: str = "text-embedding-3-large"
    embedding_dim: int = 3072
    embedding_batch_size: int = 64

    # AWS Bedrock (used when a provider is set to "bedrock").
    # Credentials are resolved by the standard AWS chain: AWS_ACCESS_KEY_ID /
    # AWS_SECRET_ACCESS_KEY env vars, shared config file, or IAM role.
    aws_region: str = "us-east-1"
    bedrock_llm_model_id: str = "us.anthropic.claude-sonnet-4-20250514-v1:0"
    bedrock_llm_small_model_id: str = "us.anthropic.claude-3-5-haiku-20241022-v1:0"
    bedrock_embedding_model_id: str = "amazon.titan-embed-text-v2:0"  # dims: 256/512/1024
    bedrock_embedding_concurrency: int = 8

    # Voyage AI
    voyage_api_key: str | None = None
    voyage_embedding_model: str = "voyage-3"
    voyage_rerank_model: str = "rerank-2"
    reranker_provider: str = "llm"  # llm | voyage

    # Database
    database_url: str = "postgresql+asyncpg://rag_user:rag_password@localhost:5433/rag_db"

    # Gemini config
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"




    # Vector store
    qdrant_url: str = "http://localhost:6333"
    collection_name: str = "rag_chunks"

    # Chunking (parent-child strategy)
    parent_chunk_chars: int = 6000
    child_chunk_chars: int = 1500
    child_chunk_overlap: int = 200
    enable_contextual_enrichment: bool = True
    enrichment_concurrency: int = 8

    # Retrieval
    top_k_per_query: int = 30
    rrf_k: int = 60
    rerank_top_n: int = 8
    max_retrieval_retries: int = 1
    max_sub_questions: int = 6


@lru_cache
def get_settings() -> Settings:
    return Settings()
