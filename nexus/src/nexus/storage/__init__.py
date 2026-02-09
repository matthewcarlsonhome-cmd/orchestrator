"""
Nexus Storage Layer

CUSTOMIZATION POINT:
- Vector DB: ChromaDB (local) or Pinecone (cloud)
- Metadata DB: SQLite (local) or PostgreSQL (cloud)

Change in config.py:
    vector_db = "chromadb" | "pinecone"
    metadata_db = "sqlite" | "postgresql"
"""

from nexus.storage.vector import VectorStore, get_vector_store
from nexus.storage.metadata import MetadataStore, get_metadata_store
from nexus.storage.embeddings import EmbeddingProvider, get_embedding_provider

__all__ = [
    "VectorStore", "get_vector_store",
    "MetadataStore", "get_metadata_store",
    "EmbeddingProvider", "get_embedding_provider",
]
