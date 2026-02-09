"""
Nexus Configuration

All settings can be customized via environment variables or .env file.
Prefix: NEXUS_

CUSTOMIZATION POINTS:
- Vector DB: ChromaDB (local) or Pinecone (cloud)
- Embeddings: Local (sentence-transformers) or Cloud (OpenAI, Voyage)
- LLM: Claude (Anthropic) or GPT (OpenAI)
- Metadata DB: SQLite (local) or PostgreSQL (cloud)
"""

import os
from pathlib import Path
from typing import Literal, Optional

from dotenv import load_dotenv
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load .env file from current directory and parent directories
load_dotenv()


class NexusConfig(BaseSettings):
    """Main configuration for Nexus."""

    model_config = SettingsConfigDict(
        env_prefix="NEXUS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ==========================================================================
    # API KEYS - Set these in your .env file
    # These read BOTH with and without NEXUS_ prefix for convenience
    # ==========================================================================
    anthropic_api_key: str = Field(default="", description="Anthropic API key for Claude")
    openai_api_key: str = Field(default="", description="OpenAI API key (optional, for embeddings)")
    pinecone_api_key: str = Field(default="", description="Pinecone API key (optional, for cloud vector DB)")
    voyage_api_key: str = Field(default="", description="Voyage AI API key (optional, for embeddings)")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Also check for non-prefixed API keys (more common convention)
        if not self.anthropic_api_key:
            self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY", "")
        if not self.openai_api_key:
            self.openai_api_key = os.getenv("OPENAI_API_KEY", "")
        if not self.pinecone_api_key:
            self.pinecone_api_key = os.getenv("PINECONE_API_KEY", "")
        if not self.voyage_api_key:
            self.voyage_api_key = os.getenv("VOYAGE_API_KEY", "")

    # ==========================================================================
    # VECTOR DATABASE - Choose your storage backend
    # Options: "chromadb" (local, free) | "pinecone" (cloud, scalable)
    # ==========================================================================
    vector_db: Literal["chromadb", "pinecone"] = Field(
        default="chromadb",
        description="Vector database backend"
    )
    chromadb_path: Path = Field(
        default=Path.home() / ".nexus" / "chromadb",
        description="Path for ChromaDB storage"
    )
    pinecone_index: str = Field(
        default="nexus",
        description="Pinecone index name"
    )
    pinecone_environment: str = Field(
        default="us-east-1",
        description="Pinecone environment/region"
    )

    # ==========================================================================
    # EMBEDDINGS - Choose your embedding model
    # Options: "local" (free, private) | "openai" (quality) | "voyage" (best for retrieval)
    # ==========================================================================
    embedding_provider: Literal["local", "openai", "voyage"] = Field(
        default="local",
        description="Embedding provider"
    )
    local_embedding_model: str = Field(
        default="all-MiniLM-L6-v2",
        description="Local sentence-transformer model"
    )
    openai_embedding_model: str = Field(
        default="text-embedding-3-small",
        description="OpenAI embedding model"
    )
    voyage_embedding_model: str = Field(
        default="voyage-2",
        description="Voyage AI embedding model"
    )
    embedding_dimension: int = Field(
        default=384,  # all-MiniLM-L6-v2 dimension
        description="Embedding vector dimension"
    )

    # ==========================================================================
    # LLM - Choose your language model
    # Options: "claude" (recommended) | "openai"
    # ==========================================================================
    llm_provider: Literal["claude", "openai"] = Field(
        default="claude",
        description="LLM provider for responses"
    )
    claude_model: str = Field(
        default="claude-3-5-haiku-20241022",  # Fast and cheap for most queries
        description="Claude model for responses"
    )
    claude_model_complex: str = Field(
        default="claude-sonnet-4-20250514",  # For complex reasoning
        description="Claude model for complex tasks"
    )
    openai_model: str = Field(
        default="gpt-4-turbo-preview",
        description="OpenAI model for responses"
    )

    # ==========================================================================
    # METADATA DATABASE - Structured data storage
    # Options: "sqlite" (local) | "postgresql" (cloud)
    # ==========================================================================
    metadata_db: Literal["sqlite", "postgresql"] = Field(
        default="sqlite",
        description="Metadata database backend"
    )
    sqlite_path: Path = Field(
        default=Path.home() / ".nexus" / "nexus.db",
        description="SQLite database path"
    )
    postgresql_url: str = Field(
        default="postgresql://localhost/nexus",
        description="PostgreSQL connection URL"
    )

    # ==========================================================================
    # SERVER SETTINGS
    # ==========================================================================
    api_host: str = Field(default="127.0.0.1", description="API server host")
    api_port: int = Field(default=8430, description="API server port")
    debug: bool = Field(default=False, description="Enable debug mode")

    # ==========================================================================
    # PATHS
    # ==========================================================================
    data_dir: Path = Field(
        default=Path.home() / ".nexus",
        description="Main data directory"
    )
    collections_dir: Path = Field(
        default=Path.home() / ".nexus" / "collections",
        description="Custom collections definitions"
    )
    uploads_dir: Path = Field(
        default=Path.home() / ".nexus" / "uploads",
        description="Uploaded files storage"
    )

    # ==========================================================================
    # RETRIEVAL SETTINGS
    # ==========================================================================
    default_search_limit: int = Field(default=10, description="Default search results limit")
    max_context_entries: int = Field(default=20, description="Max entries in LLM context")
    context_token_budget: int = Field(default=8000, description="Max tokens for context")

    # ==========================================================================
    # AGENT SETTINGS
    # ==========================================================================
    enable_agents: bool = Field(default=True, description="Enable proactive agents")
    agent_check_interval_minutes: int = Field(default=15, description="How often agents check for tasks")

    # ==========================================================================
    # PERSONALIZATION
    # ==========================================================================
    user_name: str = Field(default="", description="User's name for personalized responses")
    communication_style: Literal["casual", "professional", "technical"] = Field(
        default="professional",
        description="Preferred response style"
    )
    response_length: Literal["brief", "moderate", "detailed"] = Field(
        default="moderate",
        description="Preferred response length"
    )

    def ensure_dirs(self) -> None:
        """Create necessary directories."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.collections_dir.mkdir(parents=True, exist_ok=True)
        self.uploads_dir.mkdir(parents=True, exist_ok=True)
        self.chromadb_path.mkdir(parents=True, exist_ok=True)
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)

    def get_embedding_dimension(self) -> int:
        """Get the correct embedding dimension based on provider."""
        if self.embedding_provider == "local":
            # Common dimensions for sentence-transformers
            dimensions = {
                "all-MiniLM-L6-v2": 384,
                "all-mpnet-base-v2": 768,
                "all-MiniLM-L12-v2": 384,
            }
            return dimensions.get(self.local_embedding_model, 384)
        elif self.embedding_provider == "openai":
            dimensions = {
                "text-embedding-3-small": 1536,
                "text-embedding-3-large": 3072,
                "text-embedding-ada-002": 1536,
            }
            return dimensions.get(self.openai_embedding_model, 1536)
        elif self.embedding_provider == "voyage":
            return 1024  # Voyage-2 dimension
        return 384


# Global config instance
config = NexusConfig()
