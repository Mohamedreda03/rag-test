"""Thin async abstraction over any OpenAI-compatible chat completion API."""

import json
from collections.abc import AsyncIterator
from typing import Any

from openai import AsyncOpenAI

from app.config import Settings


def estimate_tokens(text: str) -> int:
    """Fast estimation of token count (~4 chars per token for English, ~2.5 for Arabic)."""
    if not text:
        return 0
    arabic_chars = sum(1 for c in text if '\u0600' <= c <= '\u06FF')
    if arabic_chars > len(text) * 0.3:
        return max(1, int(len(text) / 2.5))
    return max(1, int(len(text) / 4))


class LLMClient:
    """Async LLM client with plain, JSON, streaming, and token-aware completion helpers."""

    def __init__(self, settings: Settings) -> None:
        self._client = AsyncOpenAI(base_url=settings.llm_base_url, api_key=settings.llm_api_key)
        self._model = settings.llm_model
        self._small_model = settings.llm_small_model

    async def complete(
        self, system: str, user: str, *, small: bool = False, temperature: float = 0.0
    ) -> str:
        content, _ = await self.complete_with_usage(system, user, small=small, temperature=temperature)
        return content

    async def complete_with_usage(
        self, system: str, user: str, *, small: bool = False, temperature: float = 0.0
    ) -> tuple[str, dict[str, int]]:
        response = await self._client.chat.completions.create(
            model=self._small_model if small else self._model,
            temperature=temperature,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        content = response.choices[0].message.content or ""
        tokens = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        if hasattr(response, "usage") and response.usage:
            tokens = {
                "prompt_tokens": getattr(response.usage, "prompt_tokens", 0) or 0,
                "completion_tokens": getattr(response.usage, "completion_tokens", 0) or 0,
                "total_tokens": getattr(response.usage, "total_tokens", 0) or 0,
            }
        if not tokens["total_tokens"]:
            p_tok = estimate_tokens(system + user)
            c_tok = estimate_tokens(content)
            tokens = {"prompt_tokens": p_tok, "completion_tokens": c_tok, "total_tokens": p_tok + c_tok}

        return content, tokens

    async def complete_vision(
        self, system: str, image_bytes: bytes, mime_type: str = "image/jpeg", *, small: bool = True
    ) -> str:
        import base64
        base64_image = base64.b64encode(image_bytes).decode("utf-8")
        response = await self._client.chat.completions.create(
            model=self._small_model if small else self._model,
            messages=[
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Extract all readable text from this image page. Preserve formatting."},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
        )
        return response.choices[0].message.content or ""

    async def complete_json(self, system: str, user: str, *, small: bool = False) -> dict[str, Any]:
        raw, usage = await self.complete_with_usage(
            system + "\n\nReturn ONLY a valid JSON object. No markdown fences, no commentary.",
            user,
            small=small,
        )
        return _extract_json(raw)

    async def complete_json_with_usage(self, system: str, user: str, *, small: bool = False) -> tuple[dict[str, Any], dict[str, int]]:
        raw, usage = await self.complete_with_usage(
            system + "\n\nReturn ONLY a valid JSON object. No markdown fences, no commentary.",
            user,
            small=small,
        )
        return _extract_json(raw), usage

    async def stream(self, system: str, user: str, *, temperature: float = 0.2) -> AsyncIterator[str]:
        stream = await self._client.chat.completions.create(
            model=self._model,
            temperature=temperature,
            stream=True,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content if chunk.choices else None
            if delta:
                yield delta



class GeminiVisionClient:
    """Async LLM client backed by Google Gemini's OpenAI-compatible endpoint."""

    def __init__(self, settings: Settings) -> None:
        self._client = AsyncOpenAI(
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            api_key=settings.gemini_api_key,
        )
        self._model = settings.gemini_model

    async def complete(
        self, system: str, user: str, *, small: bool = False, temperature: float = 0.0
    ) -> str:
        response = await self._client.chat.completions.create(
            model=self._model,
            temperature=temperature,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return response.choices[0].message.content or ""

    async def complete_vision(
        self, system: str, image_bytes: bytes, mime_type: str = "image/jpeg", *, small: bool = True
    ) -> str:
        import base64
        base64_image = base64.b64encode(image_bytes).decode("utf-8")
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Extract all readable text from this image page. Preserve formatting."},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
        )
    async def complete_json(self, system: str, user: str, *, small: bool = False) -> dict[str, Any]:
        raw = await self.complete(
            system + "\n\nReturn ONLY a valid JSON object. No markdown fences, no commentary.",
            user,
            small=small,
        )
        return _extract_json(raw)

    async def stream(self, system: str, user: str, *, temperature: float = 0.2) -> AsyncIterator[str]:
        stream = await self._client.chat.completions.create(
            model=self._model,
            temperature=temperature,
            stream=True,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content if chunk.choices else None
            if delta:
                yield delta



def _extract_json(raw: str) -> dict[str, Any]:
    """Extract the first JSON object from an LLM response, tolerating stray text."""
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError(f"LLM did not return a JSON object: {raw[:200]!r}")
    return json.loads(raw[start : end + 1])
