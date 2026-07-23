"""Hybrid retrieval: Qdrant dense search + BM25 sparse search fused with RRF."""

import asyncio
import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Any

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams
from rank_bm25 import BM25Okapi

from app.config import Settings
from app.core.chunker import ChildChunk
from app.core.embedder import Embedder

logger = logging.getLogger("rag.retriever")


_TOKEN_RE = re.compile(r"[\w\u0600-\u06FF]+")
_TASHKEEL_TATWEEL_RE = re.compile(r"[\u064B-\u0652\u0640]")
_ARABIC_PREFIXES_RE = re.compile(r"^(?:بال|فال|كال|لل|ال|وا|ول|ف|ب|ك|ل)")
_ARABIC_SUFFIXES_RE = re.compile(r"(?:ات|ين|ون|ان|يه|ات)$")


def _normalize_arabic(text: str) -> str:
    """Normalize Arabic letters, remove diacritics (tashkeel), and tatweel."""
    text = _TASHKEEL_TATWEEL_RE.sub("", text)
    text = re.sub(r"[أإآ]", "ا", text)
    text = re.sub(r"ة", "ه", text)
    text = re.sub(r"ى", "ي", text)
    return text


def _tokenize(text: str) -> list[str]:
    raw_tokens = _TOKEN_RE.findall(text.lower())
    tokens: list[str] = []
    for token in raw_tokens:
        norm = _normalize_arabic(token)
        tokens.append(norm)
        
        # Stem prefix & suffix for Arabic words >= 4 chars
        if len(norm) >= 4:
            stemmed = _ARABIC_PREFIXES_RE.sub("", norm)
            stemmed = _ARABIC_SUFFIXES_RE.sub("", stemmed)
            if len(stemmed) >= 3 and stemmed != norm:
                tokens.append(stemmed)
    return tokens




@dataclass
class ScoredChunk:
    """A retrieved chunk with its retrieval score."""

    id: str
    parent_id: str
    source: str
    child_text: str
    parent_text: str
    score: float = 0.0
    document_id: str = ""


def _chunk_from_payload(point_id: Any, payload: dict[str, Any], score: float = 0.0) -> ScoredChunk:
    return ScoredChunk(
        id=str(point_id),
        parent_id=payload["parent_id"],
        source=payload["source"],
        child_text=payload["child_text"],
        parent_text=payload["parent_text"],
        score=score,
        document_id=payload.get("document_id", ""),
    )


class VectorStore:
    """Async Qdrant wrapper storing child chunks with parent context payloads."""

    def __init__(self, settings: Settings) -> None:
        self._client = AsyncQdrantClient(url=settings.qdrant_url)
        self._collection = settings.collection_name
        self._dim = settings.embedding_dim

    async def ensure_collection(self) -> None:
        if not await self._client.collection_exists(self._collection):
            await self._client.create_collection(
                collection_name=self._collection,
                vectors_config=VectorParams(size=self._dim, distance=Distance.COSINE),
            )

    async def upsert(self, chunks: list[ChildChunk], vectors: list[list[float]]) -> None:
        points = [
            PointStruct(
                id=chunk.id,
                vector=vector,
                payload={
                    "parent_id": chunk.parent_id,
                    "source": chunk.source,
                    "child_text": chunk.index_text,
                    "parent_text": chunk.parent_text,
                    "document_id": chunk.document_id,
                },
            )
            for chunk, vector in zip(chunks, vectors, strict=True)
        ]
        await self._client.upsert(collection_name=self._collection, points=points)

    async def search(self, vector: list[float], top_k: int) -> list[ScoredChunk]:
        try:
            result = await self._client.query_points(
                collection_name=self._collection, query=vector, limit=top_k, with_payload=True
            )
            return [
                _chunk_from_payload(point.id, point.payload or {}, float(point.score))
                for point in result.points
            ]
        except Exception as exc:
            logger.warning("Qdrant vector search failed (%s). Falling back gracefully.", exc)
            return []


    async def scroll_all(self) -> list[ScoredChunk]:
        chunks: list[ScoredChunk] = []
        offset = None
        while True:
            points, offset = await self._client.scroll(
                collection_name=self._collection,
                limit=256,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            chunks.extend(_chunk_from_payload(p.id, p.payload or {}) for p in points)
            if offset is None:
                break
        return chunks

    async def delete_document(self, document_id: str) -> None:
        """Delete all points associated with the given document_id."""
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        await self._client.delete(
            collection_name=self._collection,
            points_selector=Filter(
                must=[
                    FieldCondition(
                        key="document_id",
                        match=MatchValue(value=document_id),
                    )
                ]
            ),
        )



class BM25Index:
    """In-memory BM25 index over all indexed child chunks."""

    def __init__(self) -> None:
        self._bm25: BM25Okapi | None = None
        self._chunks: list[ScoredChunk] = []

    def build(self, chunks: list[ScoredChunk]) -> None:
        self._chunks = chunks
        corpus = [_tokenize(chunk.child_text) for chunk in chunks]
        self._bm25 = BM25Okapi(corpus) if corpus else None

    def search(self, query: str, top_k: int) -> list[ScoredChunk]:
        if self._bm25 is None:
            return []
        scores = self._bm25.get_scores(_tokenize(query))
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
        return [
            replace(self._chunks[i], score=float(scores[i])) for i in ranked if scores[i] > 0
        ]


class HybridRetriever:
    """Dense + sparse retrieval merged with Reciprocal Rank Fusion."""

    def __init__(
        self, embedder: Embedder, store: VectorStore, bm25: BM25Index, settings: Settings
    ) -> None:
        self._embedder = embedder
        self._store = store
        self._bm25 = bm25
        self._top_k = settings.top_k_per_query
        self._rrf_k = settings.rrf_k

    async def retrieve(self, query: str) -> list[ScoredChunk]:
        vector = (await self._embedder.embed([query]))[0]
        dense = await self._store.search(vector, self._top_k)
        sparse = self._bm25.search(query, self._top_k)
        return self.merge([dense, sparse])

    async def retrieve_many(self, queries: list[str]) -> list[ScoredChunk]:
        results = await asyncio.gather(*(self.retrieve(query) for query in queries))
        return self.merge(results)

    def merge(self, ranked_lists: Sequence[list[ScoredChunk]]) -> list[ScoredChunk]:
        """RRF-fuse ranked lists and deduplicate by parent chunk."""
        fused: dict[str, float] = {}
        items: dict[str, ScoredChunk] = {}
        for ranked in ranked_lists:
            for rank, chunk in enumerate(ranked):
                fused[chunk.id] = fused.get(chunk.id, 0.0) + 1.0 / (self._rrf_k + rank + 1)
                items[chunk.id] = chunk
        ordered = sorted(fused, key=lambda cid: fused[cid], reverse=True)
        seen_parents: set[str] = set()
        merged: list[ScoredChunk] = []
        for chunk_id in ordered:
            chunk = items[chunk_id]
            if chunk.parent_id in seen_parents:
                continue
            seen_parents.add(chunk.parent_id)
            merged.append(replace(chunk, score=fused[chunk_id]))
            if len(merged) >= self._top_k:
                break
        return merged
