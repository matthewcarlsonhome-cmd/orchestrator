"""
Entry Model - The core data unit in Nexus.

An Entry represents any piece of information you store:
- Thoughts and notes
- Documents
- Conversations
- Tasks
- Custom types (workouts, recipes, etc.)
"""

from datetime import datetime
from enum import Enum
from typing import Optional, Any
from uuid import uuid4

from pydantic import BaseModel, Field


class EntryType(str, Enum):
    """Built-in entry types. Custom types can be added via collections."""

    # Core types
    THOUGHT = "thought"           # Quick notes, ideas
    DOCUMENT = "document"         # Parsed documents (PDF, Word, etc.)
    CONVERSATION = "conversation" # Chat logs, meeting notes
    TASK = "task"                 # Todo items, action items
    DECISION = "decision"         # Important decisions made
    LEARNING = "learning"         # Things you've learned

    # Life management
    CONTACT = "contact"           # People and relationships
    EVENT = "event"               # Calendar events, memories
    BOOKMARK = "bookmark"         # Web clips, saved links

    # Custom (defined in collections)
    CUSTOM = "custom"


class EntrySource(str, Enum):
    """How the entry was created."""
    MANUAL = "manual"           # Typed in directly
    VOICE = "voice"             # Voice memo transcribed
    DOCUMENT = "document"       # Extracted from document
    EMAIL = "email"             # From email integration
    WEB_CLIP = "web_clip"       # Browser extension
    CALENDAR = "calendar"       # From calendar
    CHAT = "chat"               # From chat export
    API = "api"                 # External API
    AGENT = "agent"             # Created by an agent


class Entry(BaseModel):
    """
    A single entry in the knowledge base.

    This is the fundamental unit of storage. Everything you input
    becomes an Entry with searchable content and metadata.
    """

    # Identity
    id: str = Field(default_factory=lambda: str(uuid4()))

    # Content
    type: EntryType = Field(default=EntryType.THOUGHT)
    custom_type: Optional[str] = Field(default=None, description="Custom type name if type=CUSTOM")
    title: Optional[str] = Field(default=None, description="Optional title/summary")
    content: str = Field(..., description="Main text content")

    # Metadata
    tags: list[str] = Field(default_factory=list)
    source: EntrySource = Field(default=EntrySource.MANUAL)
    source_url: Optional[str] = Field(default=None, description="Original URL if applicable")
    source_file: Optional[str] = Field(default=None, description="Original filename if applicable")

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    event_date: Optional[datetime] = Field(default=None, description="When this happened (if different from created)")

    # Relationships
    parent_id: Optional[str] = Field(default=None, description="Parent entry for threading")
    related_ids: list[str] = Field(default_factory=list, description="Related entries")
    collection_id: Optional[str] = Field(default=None, description="Custom collection this belongs to")

    # Custom fields (for collection-specific data)
    custom_fields: dict[str, Any] = Field(default_factory=dict)

    # Computed/Learned
    importance: float = Field(default=0.5, ge=0, le=1, description="Learned importance score")
    access_count: int = Field(default=0, description="How often this is accessed")
    last_accessed: Optional[datetime] = Field(default=None)

    # Vector embedding (stored separately in vector DB, but tracked here)
    embedding_id: Optional[str] = Field(default=None, description="ID in vector database")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class EntryCreate(BaseModel):
    """Schema for creating a new entry."""

    type: EntryType = Field(default=EntryType.THOUGHT)
    custom_type: Optional[str] = None
    title: Optional[str] = None
    content: str
    tags: list[str] = Field(default_factory=list)
    source: EntrySource = Field(default=EntrySource.MANUAL)
    source_url: Optional[str] = None
    source_file: Optional[str] = None
    event_date: Optional[datetime] = None
    parent_id: Optional[str] = None
    related_ids: list[str] = Field(default_factory=list)
    collection_id: Optional[str] = None
    custom_fields: dict[str, Any] = Field(default_factory=dict)


class EntryUpdate(BaseModel):
    """Schema for updating an entry."""

    title: Optional[str] = None
    content: Optional[str] = None
    tags: Optional[list[str]] = None
    event_date: Optional[datetime] = None
    related_ids: Optional[list[str]] = None
    custom_fields: Optional[dict[str, Any]] = None
    importance: Optional[float] = None


class EntryChunk(BaseModel):
    """
    A chunk of an entry for embedding.

    Long entries are split into chunks for better retrieval.
    Each chunk gets its own embedding but links back to the parent entry.
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    entry_id: str
    chunk_index: int
    content: str
    token_count: int = 0

    # Vector
    embedding: Optional[list[float]] = None
