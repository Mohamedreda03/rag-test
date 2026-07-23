"""Voyage AI embedding and reranking clients."""

import os
import logging
from typing import Any
import httpx
from openai import AsyncOpenAI
from dataclasses import replace

from app.config import Settings
from app.core.retriever import ScoredChunk

logger = logging.getLogger("rag.voyage")


class VoyageEmbedder:
    """Async embedding client using Voyage AI's OpenAI-compatible API."""

    def __init__(self, settings: Settings) -> None:
        api_key = settings.voyage_api_key or os.environ.get("VOYAGE_API_KEY")
        if not api_key:
            logger.warning("Voyage API key not configured in settings or environment.")
        
        self._client = AsyncOpenAI(
            base_url="https://api.voyageai.com/v1",
            api_key=api_key or "missing-key"
        )
        self._model = settings.voyage_embedding_model
        self._batch_size = settings.embedding_batch_size

    async def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self._batch_size):
            batch = texts[start : start + self._batch_size]
            try:
                response = await self._client.embeddings.create(
                    model=self._model,
                    input=batch
                )
                vectors.extend(item.embedding for item in response.data)
            except Exception as e:
                logger.error(f"Voyage embedding failed: {e}")
                raise e
        return vectors


class VoyageReranker:
    """Async reranker client using Voyage AI's HTTP Rerank API."""

    def __init__(self, settings: Settings) -> None:
        self._api_key = settings.voyage_api_key or os.environ.get("VOYAGE_API_KEY")
        if not self._api_key:
            logger.warning("Voyage API key not configured in settings or environment.")
            
        self._model = settings.voyage_rerank_model

    async def rerank(
        self, question: str, chunks: list[ScoredChunk], top_n: int
    ) -> list[ScoredChunk]:
        if not chunks:
            return []
        
        # Voyage AI Rerank endpoint
        url = "https://api.voyageai.com/v1/rerank"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json"
        }
        
        # Prepare list of documents to rerank
        documents = [chunk.child_text for chunk in chunks]
        
        payload = {
            "query": question,
            "documents": documents,
            "model": self._model,
            "top_k": top_n
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=30.0
                )
                
            if response.status_code != 200:
                logger.error(f"Voyage rerank request failed: {response.status_code} - {response.text}")
                return chunks[:top_n]
                
            data = response.json()
            
            # Map index and relevance scores back to ScoredChunk objects
            scored_chunks = []
            for item in data.get("data", []):
                idx = item["index"]
                score = item["relevance_score"]
                if idx < len(chunks):
                    scored_chunks.append(replace(chunks[idx], score=score))
                    
            # Sort by score descending (high to low)
            scored_chunks.sort(key=lambda c: c.score, reverse=True)
            return scored_chunks
            
        except Exception as e:
            logger.error(f"Error during Voyage reranking: {e}")
            return chunks[:top_n]
