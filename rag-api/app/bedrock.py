"""AWS Bedrock providers: LLM via the Converse API and embeddings via invoke_model.

Both classes expose the same interface as their OpenAI-compatible counterparts
(`app.llm.LLMClient` and `app.core.embedder.Embedder`), so the rest of the
pipeline is provider-agnostic.
"""

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

import aioboto3

from app.config import Settings
from app.llm import _extract_json

_JSON_SUFFIX = "\n\nReturn ONLY a valid JSON object. No markdown fences, no commentary."


class BedrockLLMClient:
    """Async LLM client backed by the AWS Bedrock Converse API."""

    def __init__(self, settings: Settings) -> None:
        self._session = aioboto3.Session(region_name=settings.aws_region)
        self._model = settings.bedrock_llm_model_id
        self._small_model = settings.bedrock_llm_small_model_id

    async def complete(
        self, system: str, user: str, *, small: bool = False, temperature: float = 0.0
    ) -> str:
        async with self._session.client("bedrock-runtime") as client:
            response = await client.converse(
                modelId=self._small_model if small else self._model,
                system=[{"text": system}],
                messages=[{"role": "user", "content": [{"text": user}]}],
                inferenceConfig={"temperature": temperature},
            )
        parts = response["output"]["message"]["content"]
        return "".join(part.get("text", "") for part in parts)

    async def complete_vision(
        self, system: str, image_bytes: bytes, mime_type: str = "image/jpeg", *, small: bool = True
    ) -> str:
        fmt = mime_type.split("/")[-1]
        if fmt == "jpg":
            fmt = "jpeg"
        async with self._session.client("bedrock-runtime") as client:
            response = await client.converse(
                modelId=self._small_model if small else self._model,
                system=[{"text": system}],
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "image": {
                                    "format": fmt,
                                    "source": {"bytes": image_bytes},
                                }
                            },
                            {"text": "Extract all readable text from this image page. Preserve formatting."}
                        ],
                    }
                ],
            )
        parts = response["output"]["message"]["content"]
        return "".join(part.get("text", "") for part in parts)

    async def complete_json(self, system: str, user: str, *, small: bool = False) -> dict[str, Any]:
        raw = await self.complete(system + _JSON_SUFFIX, user, small=small)
        return _extract_json(raw)

    async def stream(
        self, system: str, user: str, *, temperature: float = 0.2
    ) -> AsyncIterator[str]:
        async with self._session.client("bedrock-runtime") as client:
            response = await client.converse_stream(
                modelId=self._model,
                system=[{"text": system}],
                messages=[{"role": "user", "content": [{"text": user}]}],
                inferenceConfig={"temperature": temperature},
            )
            async for event in response["stream"]:
                delta = event.get("contentBlockDelta", {}).get("delta", {}).get("text")
                if delta:
                    yield delta


class BedrockEmbedder:
    """Async embedder backed by Amazon Titan Text Embeddings (invoke_model).

    Titan accepts one text per request, so requests run concurrently with a
    bounded semaphore instead of provider-side batching.
    """

    def __init__(self, settings: Settings) -> None:
        self._session = aioboto3.Session(region_name=settings.aws_region)
        self._model = settings.bedrock_embedding_model_id
        self._dim = settings.embedding_dim
        self._concurrency = settings.bedrock_embedding_concurrency

    async def embed(self, texts: list[str]) -> list[list[float]]:
        semaphore = asyncio.Semaphore(self._concurrency)
        async with self._session.client("bedrock-runtime") as client:

            async def embed_one(text: str) -> list[float]:
                async with semaphore:
                    response = await client.invoke_model(
                        modelId=self._model,
                        body=json.dumps(
                            {"inputText": text, "dimensions": self._dim, "normalize": True}
                        ),
                    )
                    payload = json.loads(await response["body"].read())
                    return payload["embedding"]

            return list(await asyncio.gather(*(embed_one(text) for text in texts)))
