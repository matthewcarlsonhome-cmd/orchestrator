"""
Daily Notes Service - Automatic daily note management.

Features:
- Auto-create daily note for any date
- Calendar view with entry indicators
- Streak tracking
- Templates
"""

from datetime import datetime, date, timedelta
from typing import Optional
from pydantic import BaseModel

from nexus.config import config
from nexus.models.entry import EntryType


class DailyNote(BaseModel):
    """A daily note entry."""
    date: date
    content: str
    word_count: int
    created_at: datetime
    updated_at: datetime
    entry_id: Optional[str] = None


class DailyNotesService:
    """
    Service for managing daily notes.

    Usage:
        service = DailyNotesService(metadata_store)

        # Get or create today's note
        note = await service.get_daily(date.today())

        # Update note content
        await service.update_daily(date.today(), "My thoughts...")

        # Get calendar data
        calendar = await service.get_calendar_month(2026, 2)
    """

    def __init__(self, metadata_store, ingestion_service=None):
        self.metadata_store = metadata_store
        self.ingestion = ingestion_service

    async def get_daily(self, target_date: date) -> DailyNote:
        """Get or create a daily note for a specific date."""
        # Search for existing daily note
        date_str = target_date.isoformat()

        entries = await self.metadata_store.search_entries(
            types=[EntryType.NOTE],
            tags=["daily", date_str],
            limit=1
        )

        if entries:
            entry = entries[0]
            return DailyNote(
                date=target_date,
                content=entry.content,
                word_count=len(entry.content.split()),
                created_at=entry.created_at,
                updated_at=entry.updated_at or entry.created_at,
                entry_id=entry.id
            )

        # Return empty note (will be created on first save)
        now = datetime.utcnow()
        return DailyNote(
            date=target_date,
            content="",
            word_count=0,
            created_at=now,
            updated_at=now
        )

    async def update_daily(self, target_date: date, content: str) -> DailyNote:
        """Update or create a daily note."""
        date_str = target_date.isoformat()
        now = datetime.utcnow()

        # Check if note exists
        entries = await self.metadata_store.search_entries(
            types=[EntryType.NOTE],
            tags=["daily", date_str],
            limit=1
        )

        if entries:
            # Update existing
            entry = entries[0]
            entry.content = content
            entry.updated_at = now
            await self.metadata_store.update_entry(entry)

            return DailyNote(
                date=target_date,
                content=content,
                word_count=len(content.split()),
                created_at=entry.created_at,
                updated_at=now,
                entry_id=entry.id
            )
        else:
            # Create new via ingestion service if available
            if self.ingestion:
                entry = await self.ingestion.ingest_text(
                    content=content,
                    title=f"Daily Note - {target_date.strftime('%B %d, %Y')}",
                    tags=["daily", date_str],
                    entry_type=EntryType.NOTE
                )

                return DailyNote(
                    date=target_date,
                    content=content,
                    word_count=len(content.split()),
                    created_at=now,
                    updated_at=now,
                    entry_id=entry.id
                )
            else:
                # Just return the note data without persisting
                return DailyNote(
                    date=target_date,
                    content=content,
                    word_count=len(content.split()),
                    created_at=now,
                    updated_at=now
                )

    async def get_calendar_month(self, year: int, month: int) -> dict:
        """Get calendar data showing which days have entries."""
        # Get first and last day of month
        first_day = date(year, month, 1)
        if month == 12:
            last_day = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            last_day = date(year, month + 1, 1) - timedelta(days=1)

        # Get all daily notes for this month
        entries = await self.metadata_store.search_entries(
            types=[EntryType.NOTE],
            tags=["daily"],
            date_from=datetime.combine(first_day, datetime.min.time()),
            date_to=datetime.combine(last_day, datetime.max.time()),
            limit=31
        )

        # Extract dates with entries
        dates_with_entries = set()
        for entry in entries:
            for tag in entry.tags:
                try:
                    entry_date = date.fromisoformat(tag)
                    if first_day <= entry_date <= last_day:
                        dates_with_entries.add(entry_date.isoformat())
                except ValueError:
                    continue

        return {
            "year": year,
            "month": month,
            "days_with_entries": list(dates_with_entries),
            "total_entries": len(dates_with_entries)
        }

    async def get_streak(self) -> int:
        """Calculate current daily notes streak."""
        streak = 0
        check_date = date.today()

        while True:
            note = await self.get_daily(check_date)
            if note.content.strip():
                streak += 1
                check_date -= timedelta(days=1)
            else:
                break

            # Don't check more than 365 days back
            if streak > 365:
                break

        return streak

    async def get_recent_daily_notes(self, limit: int = 7) -> list[DailyNote]:
        """Get recent daily notes."""
        notes = []
        check_date = date.today()

        for _ in range(limit):
            note = await self.get_daily(check_date)
            if note.content.strip():
                notes.append(note)
            check_date -= timedelta(days=1)

        return notes
