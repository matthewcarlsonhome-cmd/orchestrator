"""
Embedding Providers

CUSTOMIZATION POINT:
- "local": sentence-transformers (free, private, runs on your machine)
- "openai": OpenAI embeddings (good quality, requires API key)
- "voyage": Voyage AI (best for retrieval, requires API key)

Change in config.py:
    embedding_provider = "local" | "openai" | "voyage"
"""

from abc import ABC, abstractmethod
from typing import Optional
import asyncio

from nexus.config import config


class EmbeddingProvider(ABC):
    """Abstract base class for embedding providers."""

    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        """Generate embedding for a single text."""
        pass

    @abstractmethod
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts."""
        pass

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Return the embedding dimension."""
        pass


class LocalEmbeddingProvider(EmbeddingProvider):
    """
    Local embeddings using sentence-transformers.

    PROS: Free, private, no API calls
    CONS: Slower, requires local compute

    Models:
    - all-MiniLM-L6-v2 (default): Fast, 384 dimensions
    - all-mpnet-base-v2: Better quality, 768 dimensions
    """

    def __init__(self, model_name: str = None):
        self.model_name = model_name or config.local_embedding_model
        self._model = None

    def _load_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name)
        return self._model

    async def embed(self, text: str) -> list[float]:
        model = self._load_model()
        # Run in thread to not block
        embedding = await asyncio.to_thread(
            model.encode, text, convert_to_numpy=True
        )
        return embedding.tolist()

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        model = self._load_model()
        embeddings = await asyncio.to_thread(
            model.encode, texts, convert_to_numpy=True
        )
        return embeddings.tolist()

    @property
    def dimension(self) -> int:
        dimensions = {
            "all-MiniLM-L6-v2": 384,
            "all-mpnet-base-v2": 768,
            "all-MiniLM-L12-v2": 384,
        }
        return dimensions.get(self.model_name, 384)


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """
    OpenAI embeddings.

    PROS: Good quality, fast
    CONS: Costs money, data sent to OpenAI

    Models:
    - text-embedding-3-small: Cheaper, 1536 dimensions
    - text-embedding-3-large: Better, 3072 dimensions
    """

    def __init__(self, model_name: str = None, api_key: str = None):
        self.model_name = model_name or config.openai_embedding_model
        self.api_key = api_key or config.openai_api_key

        if not self.api_key:
            raise ValueError("OpenAI API key required. Set NEXUS_OPENAI_API_KEY")

        from openai import AsyncOpenAI
        self.client = AsyncOpenAI(api_key=self.api_key)

    async def embed(self, text: str) -> list[float]:
        response = await self.client.embeddings.create(
            model=self.model_name,
            input=text
        )
        return response.data[0].embedding

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        response = await self.client.embeddings.create(
            model=self.model_name,
            input=texts
        )
        return [item.embedding for item in response.data]

    @property
    def dimension(self) -> int:
        dimensions = {
            "text-embedding-3-small": 1536,
            "text-embedding-3-large": 3072,
            "text-embedding-ada-002": 1536,
        }
        return dimensions.get(self.model_name, 1536)


class VoyageEmbeddingProvider(EmbeddingProvider):
    """
    Voyage AI embeddings - optimized for retrieval.

    PROS: Best quality for retrieval tasks
    CONS: Costs money, requires API key

    Models:
    - voyage-2: General purpose, 1024 dimensions
    - voyage-code-2: Optimized for code
    """

    def __init__(self, model_name: str = None, api_key: str = None):
        self.model_name = model_name or config.voyage_embedding_model
        self.api_key = api_key or config.voyage_api_key

        if not self.api_key:
            raise ValueError("Voyage AI API key required. Set NEXUS_VOYAGE_API_KEY")

    async def embed(self, text: str) -> list[float]:
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.voyageai.com/v1/embeddings",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"model": self.model_name, "input": text}
            )
            data = response.json()
            return data["data"][0]["embedding"]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.voyageai.com/v1/embeddings",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"model": self.model_name, "input": texts}
            )
            data = response.json()
            return [item["embedding"] for item in data["data"]]

    @property
    def dimension(self) -> int:
        return 1024


# Singleton instance
_embedding_provider: Optional[EmbeddingProvider] = None


def get_embedding_provider() -> EmbeddingProvider:
    """Get the configured embedding provider."""
    global _embedding_provider

    if _embedding_provider is None:
        if config.embedding_provider == "local":
            _embedding_provider = LocalEmbeddingProvider()
        elif config.embedding_provider == "openai":
            _embedding_provider = OpenAIEmbeddingProvider()
        elif config.embedding_provider == "voyage":
            _embedding_provider = VoyageEmbeddingProvider()
        else:
            raise ValueError(f"Unknown embedding provider: {config.embedding_provider}")

    return _embedding_provider
