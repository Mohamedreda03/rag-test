"""Final answer verification: completeness, groundedness, citations, and language."""

from app.llm import LLMClient
from app.prompts import VERIFIER_PROMPT


class Verifier:
    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    async def finalize(self, question: str, context: str, draft: str) -> tuple[str, bool]:
        """Return the final answer and whether it passed (or was fixed by) verification."""
        payload = (
            f"## Question\n{question}\n\n"
            f"## Source excerpts\n{context}\n\n"
            f"## Draft answer\n{draft}"
        )
        try:
            data = await self._llm.complete_json(VERIFIER_PROMPT, payload)
        except Exception:
            return draft, False
        if data.get("ok", False):
            return draft, True
        revised = str(data.get("revised_answer") or "").strip()
        return (revised, True) if revised else (draft, False)
