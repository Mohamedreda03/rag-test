"""CRAG-style retrieval grading: judge sufficiency and rewrite the query if needed."""

from dataclasses import dataclass

from app.core.retriever import ScoredChunk
from app.llm import LLMClient
from app.prompts import GRADER_PROMPT

_MAX_EXCERPTS = 12
_EXCERPT_CHARS = 500


@dataclass
class Grade:
    sufficient: bool
    rewritten_query: str


class RetrievalGrader:
    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    async def grade(self, question: str, chunks: list[ScoredChunk]) -> Grade:
        if not chunks:
            return Grade(sufficient=False, rewritten_query=question)
        excerpts = "\n\n".join(
            f"[{i + 1}] {chunk.child_text[:_EXCERPT_CHARS]}"
            for i, chunk in enumerate(chunks[:_MAX_EXCERPTS])
        )
        payload = f"## Question\n{question}\n\n## Retrieved excerpts\n{excerpts}"
        try:
            data = await self._llm.complete_json(GRADER_PROMPT, payload, small=True)
        except Exception:
            return Grade(sufficient=True, rewritten_query=question)
        rewritten = str(data.get("rewritten_query") or question).strip() or question
        return Grade(sufficient=bool(data.get("sufficient", True)), rewritten_query=rewritten)
