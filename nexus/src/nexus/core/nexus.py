"""
Nexus - Main orchestrator class.

This is the primary interface for interacting with Nexus.
"""

from datetime import datetime
from typing import Optional

from nexus.config import config
from nexus.models.entry import Entry, EntryCreate, EntryType, EntrySource
from nexus.models.query import SearchResult, AskResponse
from nexus.core.ingestion import IngestionService
from nexus.core.retrieval import RetrievalService
from nexus.core.response import ResponseService
from nexus.storage import get_metadata_store, get_vector_store


class Nexus:
    """
    Main Nexus interface.

    Usage:
        nexus = Nexus()
        await nexus.init()

        # Add content
        entry = await nexus.add("Had a great idea about the product...")

        # Search
        results = await nexus.search("product ideas")

        # Ask questions
        response = await nexus.ask("What are my recent product ideas?")

        # Get briefing
        briefing = await nexus.briefing("daily")
    """

    def __init__(self):
        self.ingestion = IngestionService()
        self.retrieval = RetrievalService()
        self.response = ResponseService(self.retrieval)

        self._initialized = False

    async def init(self):
        """Initialize Nexus - create directories and database tables."""
        if self._initialized:
            return

        # Ensure directories exist
        config.ensure_dirs()

        # Initialize database
        metadata_store = get_metadata_store()
        await metadata_store.init_db()

        self._initialized = True

    # ==========================================================================
    # QUICK ACCESS METHODS
    # ==========================================================================

    async def add(
        self,
        content: str,
        title: str = None,
        tags: list[str] = None,
        entry_type: EntryType = EntryType.THOUGHT,
    ) -> Entry:
        """
        Quick add content.

        Examples:
            await nexus.add("My thought here")
            await nexus.add("Meeting with John", tags=["work", "john"])
            await nexus.add("Recipe for pasta", entry_type=EntryType.CUSTOM)
        """
        return await self.ingestion.ingest_text(
            content=content,
            title=title,
            tags=tags,
            entry_type=entry_type,
        )

    async def search(
        self,
        query: str,
        types: list[EntryType] = None,
        tags: list[str] = None,
        limit: int = 10,
    ) -> SearchResult:
        """
        Search your knowledge base.

        Examples:
            results = await nexus.search("meeting notes")
            results = await nexus.search("recipes", types=[EntryType.CUSTOM])
        """
        return await self.retrieval.search(
            query=query,
            types=types,
            tags=tags,
            limit=limit,
        )

    async def ask(
        self,
        question: str,
        context_types: list[EntryType] = None,
        context_tags: list[str] = None,
    ) -> AskResponse:
        """
        Ask a question and get an AI-generated answer.

        Examples:
            response = await nexus.ask("What did I decide about pricing?")
            response = await nexus.ask("Summarize my week", context_tags=["work"])
        """
        return await self.response.ask(
            question=question,
            context_types=context_types,
            context_tags=context_tags,
        )

    async def briefing(self, briefing_type: str = "daily") -> str:
        """
        Get a personalized briefing.

        Types:
        - "daily": Morning briefing
        - "weekly": Week in review
        """
        return await self.response.generate_briefing(briefing_type)

    # ==========================================================================
    # ENTRY MANAGEMENT
    # ==========================================================================

    async def get(self, entry_id: str) -> Optional[Entry]:
        """Get an entry by ID."""
        metadata_store = get_metadata_store()
        return await metadata_store.get_entry(entry_id)

    async def delete(self, entry_id: str) -> bool:
        """Delete an entry."""
        metadata_store = get_metadata_store()
        vector_store = get_vector_store()

        # Delete from both stores
        await vector_store.delete(entry_id)
        return await metadata_store.delete_entry(entry_id)

    async def recent(self, limit: int = 10) -> list[Entry]:
        """Get recent entries."""
        return await self.retrieval.get_recent_entries(limit=limit)

    async def by_tag(self, tag: str, limit: int = 50) -> list[Entry]:
        """Get entries by tag."""
        return await self.retrieval.get_entries_by_tag(tag, limit=limit)

    async def related(self, entry_id: str, limit: int = 5) -> list[Entry]:
        """Get entries related to a given entry."""
        return await self.retrieval.get_related_entries(entry_id, limit=limit)

    # ==========================================================================
    # DOCUMENT INGESTION
    # ==========================================================================

    async def add_document(
        self,
        file_path: str,
        tags: list[str] = None,
    ) -> list[Entry]:
        """Add a document file."""
        return await self.ingestion.ingest_document(
            file_path=file_path,
            tags=tags,
        )

    async def add_voice(
        self,
        audio_file: str,
        tags: list[str] = None,
    ) -> Entry:
        """Add a voice memo."""
        return await self.ingestion.ingest_voice(
            audio_file=audio_file,
            tags=tags,
        )

    async def add_web_clip(
        self,
        url: str,
        tags: list[str] = None,
    ) -> Entry:
        """Add a web page clip."""
        return await self.ingestion.ingest_web_clip(
            url=url,
            tags=tags,
        )

    # ==========================================================================
    # STATS
    # ==========================================================================

    async def stats(self) -> dict:
        """Get Nexus statistics."""
        metadata_store = get_metadata_store()
        vector_store = get_vector_store()

        entry_count = await metadata_store.count_entries()
        tags = await metadata_store.get_tags(limit=10)
        vector_stats = await vector_store.get_stats()

        return {
            "entries": entry_count,
            "top_tags": tags,
            "vector_store": vector_stats,
        }


# Singleton instance
_nexus: Optional[Nexus] = None


def get_nexus() -> Nexus:
    """Get the Nexus singleton."""
    global _nexus
    if _nexus is None:
        _nexus = Nexus()
    return _nexus
