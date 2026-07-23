"""Query decomposition, multi-query expansion, and HyDE generation."""

from app.config import Settings
from app.llm import LLMClient
from app.prompts import DECOMPOSITION_PROMPT, EXPANSION_PROMPT, HYDE_PROMPT


class QueryDecomposer:
    def __init__(self, llm: LLMClient, settings: Settings) -> None:
        self._llm = llm
        self._max_sub_questions = settings.max_sub_questions

    async def decompose(self, question: str) -> list[str]:
        """Split a question into standalone sub-questions (falls back to the original)."""
        try:
            data = await self._llm.complete_json(DECOMPOSITION_PROMPT, question, small=True)
            sub_questions = [q.strip() for q in data.get("sub_questions", []) if q and q.strip()]
        except Exception:
            sub_questions = []
        return sub_questions[: self._max_sub_questions] or [question]

    async def expand(self, question: str) -> list[str]:
        """Generate paraphrased search queries for higher recall."""
        try:
            data = await self._llm.complete_json(EXPANSION_PROMPT, question, small=True)
            return [q.strip() for q in data.get("queries", []) if q and q.strip()][:3]
        except Exception:
            return []

    async def hyde(self, question: str) -> str | None:
        """Generate a hypothetical answer passage to use as a search query."""
        try:
            passage = await self._llm.complete(HYDE_PROMPT, question, small=True, temperature=0.3)
            return passage.strip() or None
        except Exception:
            return None
