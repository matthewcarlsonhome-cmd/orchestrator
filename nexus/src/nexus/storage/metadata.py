"""
Metadata Database Storage

CUSTOMIZATION POINT:
- "sqlite": Local SQLite database (free, simple)
- "postgresql": PostgreSQL (scalable, team use)

Change in config.py:
    metadata_db = "sqlite" | "postgresql"
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional
import json

from sqlalchemy import (
    create_engine, Column, String, Text, DateTime, Float, Integer, Boolean, JSON,
    Index, and_, or_
)
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.future import select

from nexus.config import config
from nexus.models.entry import Entry, EntryCreate, EntryUpdate, EntryType, EntrySource

Base = declarative_base()


class EntryTable(Base):
    """SQLAlchemy model for entries."""

    __tablename__ = "entries"

    id = Column(String(36), primary_key=True)
    type = Column(String(50), index=True)
    custom_type = Column(String(100), nullable=True)
    title = Column(String(500), nullable=True)
    content = Column(Text, nullable=False)

    # Metadata stored as JSON
    tags = Column(JSON, default=list)
    source = Column(String(50), default="manual")
    source_url = Column(String(1000), nullable=True)
    source_file = Column(String(500), nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    event_date = Column(DateTime, nullable=True)

    # Relationships
    parent_id = Column(String(36), nullable=True, index=True)
    related_ids = Column(JSON, default=list)
    collection_id = Column(String(50), nullable=True, index=True)

    # Custom fields
    custom_fields = Column(JSON, default=dict)

    # Computed
    importance = Column(Float, default=0.5)
    access_count = Column(Integer, default=0)
    last_accessed = Column(DateTime, nullable=True)

    # Vector reference
    embedding_id = Column(String(36), nullable=True)

    # Indexes
    __table_args__ = (
        Index("idx_type_created", "type", "created_at"),
        Index("idx_collection_type", "collection_id", "type"),
    )

    def to_entry(self) -> Entry:
        """Convert to Entry model."""
        return Entry(
            id=self.id,
            type=EntryType(self.type),
            custom_type=self.custom_type,
            title=self.title,
            content=self.content,
            tags=self.tags or [],
            source=EntrySource(self.source),
            source_url=self.source_url,
            source_file=self.source_file,
            created_at=self.created_at,
            updated_at=self.updated_at,
            event_date=self.event_date,
            parent_id=self.parent_id,
            related_ids=self.related_ids or [],
            collection_id=self.collection_id,
            custom_fields=self.custom_fields or {},
            importance=self.importance,
            access_count=self.access_count,
            last_accessed=self.last_accessed,
            embedding_id=self.embedding_id,
        )


class CollectionTable(Base):
    """SQLAlchemy model for collections."""

    __tablename__ = "collections"

    id = Column(String(50), primary_key=True)
    name = Column(String(100), unique=True)
    display_name = Column(String(200))
    description = Column(Text, nullable=True)
    icon = Column(String(10), nullable=True)

    # Schema stored as JSON
    entry_types = Column(JSON, default=list)
    agents = Column(JSON, default=list)
    default_tags = Column(JSON, default=list)
    auto_tag = Column(Boolean, default=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    entry_count = Column(Integer, default=0)


class UserProfileTable(Base):
    """SQLAlchemy model for user profile."""

    __tablename__ = "user_profile"

    id = Column(String(50), primary_key=True, default="default")
    name = Column(String(200), default="")
    email = Column(String(300), nullable=True)

    preferences = Column(JSON, default=dict)
    interests = Column(JSON, default=dict)
    communication_patterns = Column(JSON, default=dict)
    goals = Column(JSON, default=list)
    detected_patterns = Column(JSON, default=list)

    total_entries = Column(Integer, default=0)
    entries_this_week = Column(Integer, default=0)
    most_used_tags = Column(JSON, default=list)
    most_active_collections = Column(JSON, default=list)

    created_at = Column(DateTime, default=datetime.utcnow)
    last_active = Column(DateTime, default=datetime.utcnow)


class AgentRunTable(Base):
    """SQLAlchemy model for agent runs."""

    __tablename__ = "agent_runs"

    id = Column(String(36), primary_key=True)
    agent_id = Column(String(50), index=True)
    agent_name = Column(String(200))

    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    success = Column(Boolean, default=False)

    trigger_reason = Column(String(200))
    context_entries = Column(Integer, default=0)

    result = Column(Text, nullable=True)
    entries_created = Column(JSON, default=list)
    notifications_sent = Column(Integer, default=0)

    tokens_used = Column(Integer, default=0)
    model_used = Column(String(100), default="")
    error = Column(Text, nullable=True)


class MetadataStore:
    """
    Metadata storage using SQLAlchemy.

    Handles all structured data: entries, collections, user profile, agent runs.
    """

    def __init__(self, db_url: str = None):
        if db_url:
            self.db_url = db_url
        elif config.metadata_db == "sqlite":
            self.db_url = f"sqlite+aiosqlite:///{config.sqlite_path}"
        else:
            self.db_url = config.postgresql_url.replace(
                "postgresql://", "postgresql+asyncpg://"
            )

        self.engine = create_async_engine(self.db_url, echo=config.debug)
        self.async_session = sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )

    async def init_db(self):
        """Create all tables."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    # ==========================================================================
    # ENTRY OPERATIONS
    # ==========================================================================

    async def create_entry(self, entry: EntryCreate) -> Entry:
        """Create a new entry."""
        from uuid import uuid4

        entry_id = str(uuid4())
        entry_dict = entry.model_dump()
        entry_dict["id"] = entry_id
        entry_dict["type"] = entry_dict["type"].value
        entry_dict["source"] = entry_dict["source"].value

        async with self.async_session() as session:
            db_entry = EntryTable(**entry_dict)
            session.add(db_entry)
            await session.commit()
            await session.refresh(db_entry)
            return db_entry.to_entry()

    async def get_entry(self, entry_id: str) -> Optional[Entry]:
        """Get an entry by ID."""
        async with self.async_session() as session:
            result = await session.execute(
                select(EntryTable).where(EntryTable.id == entry_id)
            )
            db_entry = result.scalar_one_or_none()
            if db_entry:
                # Update access tracking
                db_entry.access_count += 1
                db_entry.last_accessed = datetime.utcnow()
                await session.commit()
                return db_entry.to_entry()
            return None

    async def update_entry(self, entry_id: str, update: EntryUpdate) -> Optional[Entry]:
        """Update an entry."""
        async with self.async_session() as session:
            result = await session.execute(
                select(EntryTable).where(EntryTable.id == entry_id)
            )
            db_entry = result.scalar_one_or_none()
            if not db_entry:
                return None

            update_data = update.model_dump(exclude_unset=True)
            for key, value in update_data.items():
                setattr(db_entry, key, value)

            db_entry.updated_at = datetime.utcnow()
            await session.commit()
            return db_entry.to_entry()

    async def delete_entry(self, entry_id: str) -> bool:
        """Delete an entry."""
        async with self.async_session() as session:
            result = await session.execute(
                select(EntryTable).where(EntryTable.id == entry_id)
            )
            db_entry = result.scalar_one_or_none()
            if db_entry:
                await session.delete(db_entry)
                await session.commit()
                return True
            return False

    async def search_entries(
        self,
        entry_ids: list[str] = None,
        types: list[EntryType] = None,
        tags: list[str] = None,
        collection_id: str = None,
        date_from: datetime = None,
        date_to: datetime = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Entry]:
        """Search entries with filters."""
        async with self.async_session() as session:
            query = select(EntryTable)

            conditions = []

            if entry_ids:
                conditions.append(EntryTable.id.in_(entry_ids))

            if types:
                type_values = [t.value for t in types]
                conditions.append(EntryTable.type.in_(type_values))

            if collection_id:
                conditions.append(EntryTable.collection_id == collection_id)

            if date_from:
                conditions.append(EntryTable.created_at >= date_from)

            if date_to:
                conditions.append(EntryTable.created_at <= date_to)

            if conditions:
                query = query.where(and_(*conditions))

            query = query.order_by(EntryTable.created_at.desc())
            query = query.limit(limit).offset(offset)

            result = await session.execute(query)
            entries = result.scalars().all()

            # Filter by tags in Python (JSON field)
            if tags:
                entries = [
                    e for e in entries
                    if any(tag in (e.tags or []) for tag in tags)
                ]

            return [e.to_entry() for e in entries]

    async def count_entries(self, types: list[EntryType] = None) -> int:
        """Count entries."""
        from sqlalchemy import func

        async with self.async_session() as session:
            query = select(func.count(EntryTable.id))

            if types:
                type_values = [t.value for t in types]
                query = query.where(EntryTable.type.in_(type_values))

            result = await session.execute(query)
            return result.scalar() or 0

    async def get_tags(self, limit: int = 50) -> list[tuple[str, int]]:
        """Get most used tags with counts."""
        async with self.async_session() as session:
            result = await session.execute(select(EntryTable.tags))
            all_tags = result.scalars().all()

            # Count tags
            tag_counts = {}
            for tags in all_tags:
                for tag in (tags or []):
                    tag_counts[tag] = tag_counts.get(tag, 0) + 1

            # Sort by count
            sorted_tags = sorted(tag_counts.items(), key=lambda x: -x[1])
            return sorted_tags[:limit]

    # ==========================================================================
    # USER PROFILE
    # ==========================================================================

    async def get_user_profile(self, user_id: str = "default"):
        """Get user profile."""
        async with self.async_session() as session:
            result = await session.execute(
                select(UserProfileTable).where(UserProfileTable.id == user_id)
            )
            profile = result.scalar_one_or_none()

            if not profile:
                # Create default profile
                profile = UserProfileTable(id=user_id)
                session.add(profile)
                await session.commit()

            return profile

    async def update_user_profile(self, user_id: str, updates: dict):
        """Update user profile."""
        async with self.async_session() as session:
            result = await session.execute(
                select(UserProfileTable).where(UserProfileTable.id == user_id)
            )
            profile = result.scalar_one_or_none()

            if profile:
                for key, value in updates.items():
                    if hasattr(profile, key):
                        setattr(profile, key, value)
                profile.last_active = datetime.utcnow()
                await session.commit()


# Singleton instance
_metadata_store: Optional[MetadataStore] = None


def get_metadata_store() -> MetadataStore:
    """Get the metadata store instance."""
    global _metadata_store

    if _metadata_store is None:
        _metadata_store = MetadataStore()

    return _metadata_store
