"""
User Profile and Preferences - Personalization models.
"""

from datetime import datetime
from typing import Optional, Any

from pydantic import BaseModel, Field


class UserPreferences(BaseModel):
    """User preferences for responses and behavior."""

    # Response style
    communication_style: str = Field(default="professional")  # casual, professional, technical
    response_length: str = Field(default="moderate")  # brief, moderate, detailed
    include_sources: bool = Field(default=True)
    include_follow_ups: bool = Field(default=True)

    # Notifications
    daily_briefing_enabled: bool = Field(default=True)
    daily_briefing_time: str = Field(default="07:00")  # HH:MM format
    weekly_review_enabled: bool = Field(default=True)
    weekly_review_day: int = Field(default=0)  # 0=Monday, 6=Sunday

    # Privacy
    store_voice_recordings: bool = Field(default=False)
    store_email_content: bool = Field(default=True)
    auto_delete_after_days: Optional[int] = Field(default=None)  # None = never


class Goal(BaseModel):
    """A user goal to track."""

    id: str
    title: str
    description: str
    category: str  # health, work, personal, learning, etc.
    target_date: Optional[datetime] = None
    progress: float = Field(default=0, ge=0, le=1)
    status: str = Field(default="active")  # active, completed, paused
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Tracking
    related_tags: list[str] = Field(default_factory=list)
    milestones: list[str] = Field(default_factory=list)


class DetectedPattern(BaseModel):
    """A pattern detected in user's data."""

    id: str
    category: str  # health, productivity, mood, spending, etc.
    description: str
    evidence: list[str]  # Entry IDs that support this pattern
    confidence: float = Field(ge=0, le=1)
    detected_at: datetime = Field(default_factory=datetime.utcnow)
    acknowledged: bool = Field(default=False)


class UserProfile(BaseModel):
    """
    User profile that learns over time.

    This stores learned information about the user to personalize responses.
    """

    id: str = Field(default="default")
    name: str = Field(default="")
    email: Optional[str] = None

    # Preferences
    preferences: UserPreferences = Field(default_factory=UserPreferences)

    # Learned attributes
    interests: dict[str, float] = Field(
        default_factory=dict,
        description="Interest areas with weight (0-1)"
    )
    communication_patterns: dict[str, Any] = Field(
        default_factory=dict,
        description="Detected communication patterns"
    )

    # Goals
    goals: list[Goal] = Field(default_factory=list)

    # Patterns
    detected_patterns: list[DetectedPattern] = Field(default_factory=list)

    # Stats
    total_entries: int = Field(default=0)
    entries_this_week: int = Field(default=0)
    most_used_tags: list[str] = Field(default_factory=list)
    most_active_collections: list[str] = Field(default_factory=list)

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_active: datetime = Field(default_factory=datetime.utcnow)
