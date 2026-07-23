"""Provider factories: build the LLM client and embedder from settings."""

from app.config import Settings
from app.core.embedder import Embedder
from app.llm import LLMClient


def create_llm(settings: Settings):
    if settings.llm_provider == "bedrock":
        from app.bedrock import BedrockLLMClient

        return BedrockLLMClient(settings)
    elif settings.llm_provider == "gemini":
        from app.llm import GeminiVisionClient

        return GeminiVisionClient(settings)
    return LLMClient(settings)



def create_vision_llm(settings: Settings):
    """Return vision-capable LLM client (defaults to primary LLM / Bedrock Mantle)."""
    return create_llm(settings)



def create_embedder(settings: Settings):
    if settings.embedding_provider == "bedrock":
        from app.bedrock import BedrockEmbedder

        return BedrockEmbedder(settings)
    elif settings.embedding_provider == "voyage":
        from app.voyage import VoyageEmbedder

        return VoyageEmbedder(settings)
    return Embedder(settings)
