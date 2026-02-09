"""
Query Models - Search and Ask interfaces.
"""

from datetime import datetime
from typing import Optional, Any

from pydantic import BaseModel, Field

from nexus.models.entry import EntryType


class SearchQuery(BaseModel):
    """Semantic search query."""

    query: str = Field(..., description="Natural language search query")

    # Filters
    types: Optional[list[EntryType]] = Field(default=None, description="Filter by entry types")
    tags: Optional[list[str]] = Field(default=None, description="Filter by tags (OR)")
    tags_all: Optional[list[str]] = Field(default=None, description="Filter by tags (AND)")
    collection_id: Optional[str] = Field(default=None, description="Filter by collection")

    # Date filters
    date_from: Optional[datetime] = Field(default=None, description="Entries after this date")
    date_to: Optional[datetime] = Field(default=None, description="Entries before this date")

    # Pagination
    limit: int = Field(default=10, ge=1, le=100)
    offset: int = Field(default=0, ge=0)

    # Options
    include_content: bool = Field(default=True, description="Include full content in results")
    min_score: float = Field(default=0.0, ge=0, le=1, description="Minimum similarity score")


class SearchResultEntry(BaseModel):
    """A single search result."""

    id: str
    type: EntryType
    title: Optional[str]
    content: str
    snippet: str = Field(description="Relevant snippet from content")
    score: float = Field(description="Similarity score 0-1")

    tags: list[str]
    created_at: datetime
    source: str

    # Highlighting
    highlights: list[str] = Field(default_factory=list, description="Highlighted matching phrases")


class SearchResult(BaseModel):
    """Search response."""

    query: str
    total: int
    entries: list[SearchResultEntry]
    search_time_ms: float


class AskQuery(BaseModel):
    """Ask a question and get an AI-generated response."""

    question: str = Field(..., description="Your question")

    # Context control
    context_types: Optional[list[EntryType]] = Field(default=None, description="Types to include in context")
    context_tags: Optional[list[str]] = Field(default=None, description="Tags to include in context")
    context_collection: Optional[str] = Field(default=None, description="Collection to search")

    # Date filters
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None

    # Options
    max_context_entries: int = Field(default=10, ge=1, le=50)
    include_sources: bool = Field(default=True, description="Include source citations")
    response_style: Optional[str] = Field(default=None, description="Override default response style")


class SourceCitation(BaseModel):
    """A source citation in an answer."""

    entry_id: str
    type: EntryType
    title: Optional[str]
    snippet: str
    date: datetime
    relevance: float


class AskResponse(BaseModel):
    """Response to an Ask query."""

    question: str
    answer: str
    confidence: float = Field(ge=0, le=1, description="Confidence in the answer")

    sources: list[SourceCitation] = Field(default_factory=list)
    context_used: int = Field(description="Number of entries used for context")
    tokens_used: int = Field(description="Total tokens used")

    # Follow-up suggestions
    follow_up_questions: list[str] = Field(default_factory=list)

    # Metadata
    model_used: str
    response_time_ms: float
