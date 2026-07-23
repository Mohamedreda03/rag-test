"""LLM-based listwise reranking of retrieved chunks."""

from dataclasses import replace

from app.core.retriever import ScoredChunk
from app.llm import LLMClient
from app.prompts import RERANK_PROMPT

_EXCERPT_CHARS = 1200


class Reranker:
    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    async def rerank(
        self, question: str, chunks: list[ScoredChunk], top_n: int
    ) -> list[ScoredChunk]:
        if len(chunks) <= top_n:
            return chunks
        excerpts = "\n\n".join(
            f"[{i + 1}] {chunk.child_text[:_EXCERPT_CHARS]}" for i, chunk in enumerate(chunks)
        )
        payload = f"## Question\n{question}\n\n## Excerpts\n{excerpts}"
        try:
            data = await self._llm.complete_json(RERANK_PROMPT, payload, small=True)
            raw_scores: dict[str, float] = {
                str(key): float(value) for key, value in data.get("scores", {}).items()
            }
        except Exception:
            return chunks[:top_n]
        scored = [
            replace(chunk, score=raw_scores.get(str(i + 1), 0.0))
            for i, chunk in enumerate(chunks)
        ]
        scored.sort(key=lambda chunk: chunk.score, reverse=True)
        return scored[:top_n]
