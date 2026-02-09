"""
Retrieval Service - Semantic search across all your data.

Handles:
- Natural language queries
- Semantic similarity search
- Filtering by type, tags, date
- Context assembly for LLM
"""

import time
from datetime import datetime
from typing import Optional

from nexus.config import config
from nexus.models.entry import Entry, EntryType
from nexus.models.query import SearchQuery, SearchResult, SearchResultEntry
from nexus.storage import get_vector_store, get_metadata_store, get_embedding_provider


class RetrievalService:
    """
    Service for retrieving content from Nexus.

    Usage:
        service = RetrievalService()

        # Semantic search
        results = await service.search("what did I decide about the pricing?")

        # With filters
        results = await service.search(
            "meeting notes",
            types=[EntryType.DOCUMENT],
            tags=["work"],
            date_from=datetime(2024, 1, 1)
        )

        # Get context for LLM
        context = await service.get_context_for_query(
            "What should I focus on today?",
            max_entries=10
        )
    """

    def __init__(self):
        self.vector_store = get_vector_store()
        self.metadata_store = get_metadata_store()
        self.embedding_provider = get_embedding_provider()

    async def search(
        self,
        query: str,
        types: list[EntryType] = None,
        tags: list[str] = None,
        collection_id: str = None,
        date_from: datetime = None,
        date_to: datetime = None,
        limit: int = 10,
        min_score: float = 0.3,
    ) -> SearchResult:
        """
        Perform semantic search across all entries.

        Returns entries ranked by relevance to the query.
        """
        start_time = time.time()

        # 1. Generate embedding for query
        query_embedding = await self.embedding_provider.embed(query)

        # 2. Build filters for vector search
        vector_filters = {}
        if types:
            vector_filters["type"] = [t.value for t in types]
        if collection_id:
            vector_filters["collection_id"] = collection_id

        # 3. Search vector store
        vector_results = await self.vector_store.search(
            embedding=query_embedding,
            limit=limit * 2,  # Get extra for post-filtering
            filters=vector_filters if vector_filters else None,
            min_score=min_score,
        )

        # 4. Get full entries from metadata store
        entry_ids = [r["id"] for r in vector_results]
        entries = await self.metadata_store.search_entries(
            entry_ids=entry_ids,
            types=types,
            tags=tags,
            date_from=date_from,
            date_to=date_to,
            limit=limit * 2,
        )

        # 5. Create score map
        score_map = {r["id"]: r["score"] for r in vector_results}

        # 6. Build results with scores
        results = []
        for entry in entries:
            score = score_map.get(entry.id, 0)
            if score >= min_score:
                results.append(SearchResultEntry(
                    id=entry.id,
                    type=entry.type,
                    title=entry.title,
                    content=entry.content,
                    snippet=self._extract_snippet(entry.content, query),
                    score=score,
                    tags=entry.tags,
                    created_at=entry.created_at,
                    source=entry.source.value,
                    highlights=self._find_highlights(entry.content, query),
                ))

        # 7. Sort by score and limit
        results.sort(key=lambda x: -x.score)
        results = results[:limit]

        search_time = (time.time() - start_time) * 1000

        return SearchResult(
            query=query,
            total=len(results),
            entries=results,
            search_time_ms=search_time,
        )

    async def search_by_query(self, query: SearchQuery) -> SearchResult:
        """Search using a SearchQuery object."""
        return await self.search(
            query=query.query,
            types=query.types,
            tags=query.tags,
            collection_id=query.collection_id,
            date_from=query.date_from,
            date_to=query.date_to,
            limit=query.limit,
            min_score=query.min_score,
        )

    async def get_context_for_query(
        self,
        query: str,
        types: list[EntryType] = None,
        tags: list[str] = None,
        collection_id: str = None,
        max_entries: int = 10,
        max_tokens: int = 8000,
    ) -> tuple[str, list[Entry]]:
        """
        Get relevant context for an LLM query.

        Returns:
            - Formatted context string for the LLM
            - List of entries used
        """
        # Search for relevant entries
        results = await self.search(
            query=query,
            types=types,
            tags=tags,
            collection_id=collection_id,
            limit=max_entries,
            min_score=0.25,  # Lower threshold for context
        )

        # Build context string
        context_parts = []
        entries_used = []
        total_chars = 0
        max_chars = max_tokens * 4  # Rough token estimate

        for result in results.entries:
            entry_context = self._format_entry_for_context(result)
            entry_chars = len(entry_context)

            if total_chars + entry_chars > max_chars:
                break

            context_parts.append(entry_context)
            total_chars += entry_chars

            # Get full entry
            entry = await self.metadata_store.get_entry(result.id)
            if entry:
                entries_used.append(entry)

        context = "\n\n---\n\n".join(context_parts)
        return context, entries_used

    async def get_related_entries(
        self,
        entry_id: str,
        limit: int = 5,
    ) -> list[Entry]:
        """Find entries related to a given entry."""
        # Get the entry
        entry = await self.metadata_store.get_entry(entry_id)
        if not entry:
            return []

        # Search for similar entries
        results = await self.search(
            query=entry.content[:500],  # Use first 500 chars
            limit=limit + 1,  # Extra because we'll exclude the original
            min_score=0.5,
        )

        # Filter out the original entry
        related = []
        for result in results.entries:
            if result.id != entry_id:
                full_entry = await self.metadata_store.get_entry(result.id)
                if full_entry:
                    related.append(full_entry)

        return related[:limit]

    async def get_recent_entries(
        self,
        types: list[EntryType] = None,
        limit: int = 10,
    ) -> list[Entry]:
        """Get most recent entries."""
        return await self.metadata_store.search_entries(
            types=types,
            limit=limit,
        )

    async def get_entries_by_tag(
        self,
        tag: str,
        limit: int = 50,
    ) -> list[Entry]:
        """Get entries with a specific tag."""
        return await self.metadata_store.search_entries(
            tags=[tag],
            limit=limit,
        )

    # ==========================================================================
    # HELPERS
    # ==========================================================================

    def _extract_snippet(
        self,
        content: str,
        query: str,
        max_length: int = 200
    ) -> str:
        """Extract a relevant snippet from content."""
        if len(content) <= max_length:
            return content

        # Try to find query terms in content
        query_terms = query.lower().split()
        content_lower = content.lower()

        # Find the best position to start the snippet
        best_pos = 0
        best_score = 0

        for i in range(0, len(content) - max_length, 50):
            window = content_lower[i:i + max_length]
            score = sum(1 for term in query_terms if term in window)
            if score > best_score:
                best_score = score
                best_pos = i

        snippet = content[best_pos:best_pos + max_length]

        # Clean up snippet edges
        if best_pos > 0:
            snippet = "..." + snippet.lstrip()
        if best_pos + max_length < len(content):
            snippet = snippet.rstrip() + "..."

        return snippet

    def _find_highlights(
        self,
        content: str,
        query: str,
        max_highlights: int = 3
    ) -> list[str]:
        """Find phrases in content that match query terms."""
        highlights = []
        query_terms = query.lower().split()
        content_lower = content.lower()

        for term in query_terms:
            if term in content_lower:
                # Find the term with some context
                idx = content_lower.find(term)
                if idx >= 0:
                    start = max(0, idx - 20)
                    end = min(len(content), idx + len(term) + 20)
                    highlight = content[start:end].strip()
                    if start > 0:
                        highlight = "..." + highlight
                    if end < len(content):
                        highlight = highlight + "..."
                    highlights.append(highlight)

                    if len(highlights) >= max_highlights:
                        break

        return highlights

    def _format_entry_for_context(self, result: SearchResultEntry) -> str:
        """Format an entry for inclusion in LLM context."""
        parts = [f"[{result.type.value.upper()}]"]

        if result.title:
            parts.append(f"Title: {result.title}")

        parts.append(f"Date: {result.created_at.strftime('%Y-%m-%d')}")

        if result.tags:
            parts.append(f"Tags: {', '.join(result.tags)}")

        parts.append(f"\n{result.content}")

        return "\n".join(parts)
