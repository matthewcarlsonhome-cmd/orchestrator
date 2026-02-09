"""
Collection Model - Custom entry types and schemas.

Collections allow users to define custom entry types with specific fields.
Example: A "fitness" collection with workout logs, meals, body metrics.
"""

from datetime import datetime
from typing import Optional, Any, Literal

from pydantic import BaseModel, Field
from uuid import uuid4


class CollectionField(BaseModel):
    """A field definition in a collection schema."""

    name: str
    type: Literal["str", "int", "float", "bool", "date", "list", "enum"]
    required: bool = False
    default: Optional[Any] = None
    description: Optional[str] = None

    # For enum type
    enum_values: Optional[list[str]] = None

    # Validation
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    min_length: Optional[int] = None
    max_length: Optional[int] = None


class CollectionEntryType(BaseModel):
    """An entry type within a collection."""

    name: str  # e.g., "workout", "meal"
    display_name: str  # e.g., "Workout Log"
    description: Optional[str] = None
    icon: Optional[str] = None  # Emoji or icon name
    fields: list[CollectionField] = Field(default_factory=list)


class CollectionAgent(BaseModel):
    """An agent definition within a collection."""

    name: str
    description: Optional[str] = None

    # Trigger
    schedule: Optional[str] = None  # Cron expression
    trigger: Optional[str] = None  # "on_ingest", "on_query", etc.
    filter: Optional[str] = None  # Tag/type filter

    # Prompt
    prompt: str


class Collection(BaseModel):
    """
    A custom collection with its own entry types and agents.

    Collections let you extend Nexus for specific use cases:
    - Fitness tracking
    - Recipe management
    - Project notes
    - Travel planning
    - etc.
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str  # e.g., "fitness"
    display_name: str  # e.g., "Fitness Tracker"
    description: Optional[str] = None
    icon: Optional[str] = None

    # Schema
    entry_types: list[CollectionEntryType] = Field(default_factory=list)

    # Agents
    agents: list[CollectionAgent] = Field(default_factory=list)

    # Settings
    default_tags: list[str] = Field(default_factory=list)
    auto_tag: bool = Field(default=True, description="Auto-tag entries based on content")

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Stats
    entry_count: int = Field(default=0)


# Example built-in collections
FITNESS_COLLECTION = Collection(
    id="fitness",
    name="fitness",
    display_name="Fitness Tracker",
    description="Track workouts, meals, and body metrics",
    icon="💪",
    entry_types=[
        CollectionEntryType(
            name="workout",
            display_name="Workout Log",
            fields=[
                CollectionField(name="exercise_type", type="str", required=True),
                CollectionField(name="duration_minutes", type="int"),
                CollectionField(name="intensity", type="int", min_value=1, max_value=10),
                CollectionField(name="calories_burned", type="int"),
            ]
        ),
        CollectionEntryType(
            name="meal",
            display_name="Meal Log",
            fields=[
                CollectionField(
                    name="meal_type", type="enum",
                    enum_values=["breakfast", "lunch", "dinner", "snack"]
                ),
                CollectionField(name="foods", type="list"),
                CollectionField(name="calories", type="int"),
                CollectionField(name="protein_g", type="int"),
            ]
        ),
        CollectionEntryType(
            name="body_metric",
            display_name="Body Metric",
            fields=[
                CollectionField(name="weight_kg", type="float"),
                CollectionField(name="body_fat_pct", type="float"),
                CollectionField(name="notes", type="str"),
            ]
        ),
    ],
    agents=[
        CollectionAgent(
            name="weekly_fitness_review",
            schedule="0 18 * * 0",  # Sunday 6 PM
            prompt="Analyze my workouts and meals this week. How did I do? Any patterns or recommendations?"
        ),
        CollectionAgent(
            name="workout_reminder",
            schedule="0 17 * * 1-5",  # Weekdays 5 PM
            prompt="Check if I've worked out today. If not, give me a gentle reminder with a quick workout suggestion."
        ),
    ],
    default_tags=["health", "fitness"],
)

WORK_COLLECTION = Collection(
    id="work",
    name="work",
    display_name="Work Notes",
    description="Meeting notes, decisions, and project updates",
    icon="💼",
    entry_types=[
        CollectionEntryType(
            name="meeting_note",
            display_name="Meeting Note",
            fields=[
                CollectionField(name="attendees", type="list"),
                CollectionField(name="action_items", type="list"),
                CollectionField(name="decisions", type="list"),
            ]
        ),
        CollectionEntryType(
            name="decision",
            display_name="Decision Record",
            fields=[
                CollectionField(name="context", type="str"),
                CollectionField(name="options_considered", type="list"),
                CollectionField(name="chosen_option", type="str"),
                CollectionField(name="rationale", type="str"),
            ]
        ),
    ],
    agents=[
        CollectionAgent(
            name="meeting_prep",
            trigger="calendar_event_upcoming",
            prompt="Prepare me for this meeting. What context do I have about the attendees and topics?"
        ),
        CollectionAgent(
            name="weekly_work_review",
            schedule="0 17 * * 5",  # Friday 5 PM
            prompt="Review my work week. What did I accomplish? What decisions were made? Any follow-ups needed?"
        ),
    ],
    default_tags=["work"],
)
