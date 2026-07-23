"""Query routing: classify the question type and decide whether to use HyDE."""

from dataclasses import dataclass

from app.llm import LLMClient
from app.prompts import ROUTER_PROMPT

_VALID_TYPES = {"simple", "multi_part", "inferential", "comparative"}


@dataclass
class Route:
    type: str
    use_hyde: bool


class QueryRouter:
    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    async def classify(self, question: str) -> Route:
        try:
            data = await self._llm.complete_json(ROUTER_PROMPT, question, small=True)
        except Exception:
            return Route(type="simple", use_hyde=False)
        question_type = data.get("type", "simple")
        if question_type not in _VALID_TYPES:
            question_type = "simple"
        return Route(type=question_type, use_hyde=bool(data.get("use_hyde", False)))
