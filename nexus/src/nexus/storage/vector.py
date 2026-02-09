"""
Vector Database Storage

CUSTOMIZATION POINT:
- "chromadb": Local vector DB (free, no setup)
- "pinecone": Cloud vector DB (scalable, requires account)

Change in config.py:
    vector_db = "chromadb" | "pinecone"
"""

from abc import ABC, abstractmethod
from typing import Optional
from datetime import datetime

from nexus.config import config
from nexus.models.entry import Entry


class VectorStore(ABC):
    """Abstract base class for vector storage."""

    @abstractmethod
    async def add(self, entry_id: str, embedding: list[float], metadata: dict) -> str:
        """Add an embedding to the store."""
        pass

    @abstractmethod
    async def add_batch(self, items: list[tuple[str, list[float], dict]]) -> list[str]:
        """Add multiple embeddings."""
        pass

    @abstractmethod
    async def search(
        self,
        embedding: list[float],
        limit: int = 10,
        filters: dict = None,
        min_score: float = 0.0
    ) -> list[dict]:
        """Search for similar embeddings."""
        pass

    @abstractmethod
    async def delete(self, entry_id: str) -> bool:
        """Delete an embedding."""
        pass

    @abstractmethod
    async def update(self, entry_id: str, embedding: list[float], metadata: dict) -> bool:
        """Update an embedding."""
        pass

    @abstractmethod
    async def get_stats(self) -> dict:
        """Get store statistics."""
        pass


class ChromaDBStore(VectorStore):
    """
    ChromaDB local vector store.

    PROS: Free, local, no setup, persistent
    CONS: Single machine, limited scale

    Perfect for personal use.
    """

    def __init__(self, path: str = None, collection_name: str = "nexus"):
        self.path = path or str(config.chromadb_path)
        self.collection_name = collection_name
        self._client = None
        self._collection = None

    def _get_collection(self):
        if self._collection is None:
            import chromadb
            from chromadb.config import Settings

            self._client = chromadb.PersistentClient(
                path=self.path,
                settings=Settings(anonymized_telemetry=False)
            )
            self._collection = self._client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"}
            )
        return self._collection

    async def add(self, entry_id: str, embedding: list[float], metadata: dict) -> str:
        collection = self._get_collection()

        # ChromaDB metadata must be flat (no nested dicts/lists)
        flat_metadata = self._flatten_metadata(metadata)

        collection.add(
            ids=[entry_id],
            embeddings=[embedding],
            metadatas=[flat_metadata]
        )
        return entry_id

    async def add_batch(self, items: list[tuple[str, list[float], dict]]) -> list[str]:
        collection = self._get_collection()

        ids = [item[0] for item in items]
        embeddings = [item[1] for item in items]
        metadatas = [self._flatten_metadata(item[2]) for item in items]

        collection.add(
            ids=ids,
            embeddings=embeddings,
            metadatas=metadatas
        )
        return ids

    async def search(
        self,
        embedding: list[float],
        limit: int = 10,
        filters: dict = None,
        min_score: float = 0.0
    ) -> list[dict]:
        collection = self._get_collection()

        # Build where clause from filters
        where = None
        if filters:
            where = self._build_where_clause(filters)

        results = collection.query(
            query_embeddings=[embedding],
            n_results=limit,
            where=where,
            include=["metadatas", "distances"]
        )

        # Convert to list of dicts with scores
        output = []
        if results["ids"] and results["ids"][0]:
            for i, entry_id in enumerate(results["ids"][0]):
                # ChromaDB returns distance, convert to similarity score
                distance = results["distances"][0][i] if results["distances"] else 0
                score = 1 - distance  # Cosine distance to similarity

                if score >= min_score:
                    output.append({
                        "id": entry_id,
                        "score": score,
                        "metadata": results["metadatas"][0][i] if results["metadatas"] else {}
                    })

        return output

    async def delete(self, entry_id: str) -> bool:
        collection = self._get_collection()
        try:
            collection.delete(ids=[entry_id])
            return True
        except Exception:
            return False

    async def update(self, entry_id: str, embedding: list[float], metadata: dict) -> bool:
        collection = self._get_collection()
        try:
            collection.update(
                ids=[entry_id],
                embeddings=[embedding],
                metadatas=[self._flatten_metadata(metadata)]
            )
            return True
        except Exception:
            return False

    async def get_stats(self) -> dict:
        collection = self._get_collection()
        return {
            "backend": "chromadb",
            "path": self.path,
            "collection": self.collection_name,
            "count": collection.count()
        }

    def _flatten_metadata(self, metadata: dict) -> dict:
        """Flatten metadata for ChromaDB (no nested structures)."""
        flat = {}
        for key, value in metadata.items():
            if isinstance(value, (str, int, float, bool)):
                flat[key] = value
            elif isinstance(value, datetime):
                flat[key] = value.isoformat()
            elif isinstance(value, list):
                flat[key] = ",".join(str(v) for v in value)
            elif value is None:
                continue
            else:
                flat[key] = str(value)
        return flat

    def _build_where_clause(self, filters: dict) -> dict:
        """Build ChromaDB where clause from filters."""
        conditions = []

        for key, value in filters.items():
            if isinstance(value, list):
                conditions.append({key: {"$in": value}})
            else:
                conditions.append({key: value})

        if len(conditions) == 1:
            return conditions[0]
        elif len(conditions) > 1:
            return {"$and": conditions}
        return None


class PineconeStore(VectorStore):
    """
    Pinecone cloud vector store.

    PROS: Scalable, managed, fast
    CONS: Costs money, data in cloud

    Good for larger scale or team use.
    """

    def __init__(
        self,
        api_key: str = None,
        index_name: str = None,
        environment: str = None
    ):
        self.api_key = api_key or config.pinecone_api_key
        self.index_name = index_name or config.pinecone_index
        self.environment = environment or config.pinecone_environment

        if not self.api_key:
            raise ValueError("Pinecone API key required. Set NEXUS_PINECONE_API_KEY")

        self._index = None

    def _get_index(self):
        if self._index is None:
            from pinecone import Pinecone

            pc = Pinecone(api_key=self.api_key)
            self._index = pc.Index(self.index_name)
        return self._index

    async def add(self, entry_id: str, embedding: list[float], metadata: dict) -> str:
        index = self._get_index()
        index.upsert(vectors=[(entry_id, embedding, metadata)])
        return entry_id

    async def add_batch(self, items: list[tuple[str, list[float], dict]]) -> list[str]:
        index = self._get_index()
        vectors = [(item[0], item[1], item[2]) for item in items]
        index.upsert(vectors=vectors)
        return [item[0] for item in items]

    async def search(
        self,
        embedding: list[float],
        limit: int = 10,
        filters: dict = None,
        min_score: float = 0.0
    ) -> list[dict]:
        index = self._get_index()

        results = index.query(
            vector=embedding,
            top_k=limit,
            filter=filters,
            include_metadata=True
        )

        output = []
        for match in results.matches:
            if match.score >= min_score:
                output.append({
                    "id": match.id,
                    "score": match.score,
                    "metadata": match.metadata or {}
                })

        return output

    async def delete(self, entry_id: str) -> bool:
        index = self._get_index()
        try:
            index.delete(ids=[entry_id])
            return True
        except Exception:
            return False

    async def update(self, entry_id: str, embedding: list[float], metadata: dict) -> bool:
        return await self.add(entry_id, embedding, metadata)  # Upsert

    async def get_stats(self) -> dict:
        index = self._get_index()
        stats = index.describe_index_stats()
        return {
            "backend": "pinecone",
            "index": self.index_name,
            "count": stats.total_vector_count,
            "dimension": stats.dimension
        }


# Singleton instance
_vector_store: Optional[VectorStore] = None


def get_vector_store() -> VectorStore:
    """Get the configured vector store."""
    global _vector_store

    if _vector_store is None:
        if config.vector_db == "chromadb":
            _vector_store = ChromaDBStore()
        elif config.vector_db == "pinecone":
            _vector_store = PineconeStore()
        else:
            raise ValueError(f"Unknown vector DB: {config.vector_db}")

    return _vector_store
