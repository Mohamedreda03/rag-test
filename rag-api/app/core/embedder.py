"""Async embedding client for any OpenAI-compatible embeddings API."""

from openai import AsyncOpenAI

from app.config import Settings


class Embedder:
    """Batched async text embedder."""

    def __init__(self, settings: Settings) -> None:
        self._client = AsyncOpenAI(
            base_url=settings.embedding_base_url, api_key=settings.embedding_api_key
        )
        self._model = settings.embedding_model
        self._batch_size = settings.embedding_batch_size

    async def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self._batch_size):
            batch = texts[start : start + self._batch_size]
            response = await self._client.embeddings.create(model=self._model, input=batch)
            vectors.extend(item.embedding for item in response.data)
        return vectors
