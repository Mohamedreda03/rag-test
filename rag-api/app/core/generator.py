"""Grounded answer generation with mandatory citations (Egyptian Arabic output)."""

from collections.abc import AsyncIterator

from app.core.retriever import ScoredChunk
from app.llm import LLMClient
from app.prompts import GENERATION_SYSTEM_PROMPT


def build_context_block(chunks: list[ScoredChunk]) -> str:
    """Render chunks as numbered source excerpts (parent text for full context)."""
    return "\n\n".join(
        f"[{i + 1}] (source: {chunk.source})\n{chunk.parent_text}"
        for i, chunk in enumerate(chunks)
    )


class Generator:
    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    async def generate(self, question: str, sub_questions: list[str], context: str) -> str:
        return await self._llm.complete(
            GENERATION_SYSTEM_PROMPT,
            self._build_user_prompt(question, sub_questions, context),
            temperature=0.2,
        )

    def stream(
        self, question: str, sub_questions: list[str], context: str
    ) -> AsyncIterator[str]:
        return self._llm.stream(
            GENERATION_SYSTEM_PROMPT,
            self._build_user_prompt(question, sub_questions, context),
            temperature=0.2,
        )

    @staticmethod
    def _build_user_prompt(question: str, sub_questions: list[str], context: str) -> str:
        sub_question_lines = "\n".join(f"{i + 1}. {sq}" for i, sq in enumerate(sub_questions)) if sub_questions else "N/A"
        return (
            f"## Student Question\n{question}\n\n"
            f"## Key Sub-questions to address explicitly\n{sub_question_lines}\n\n"
            f"## Source Excerpts\n{context}\n\n"
            "Respond in warm, clear Egyptian Arabic. Format your answer with clear section headings (###), distinct paragraphs separated by double newlines (\\n\\n), and clean Markdown tables/bullet lists where appropriate."
        )

