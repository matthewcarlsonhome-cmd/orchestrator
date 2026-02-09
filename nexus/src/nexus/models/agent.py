"""
Agent Models - Proactive intelligence definitions.
"""

from datetime import datetime
from typing import Optional, Literal

from pydantic import BaseModel, Field
from uuid import uuid4


class AgentTrigger(BaseModel):
    """Defines when an agent runs."""

    type: Literal["schedule", "event", "manual"]

    # For scheduled triggers
    cron: Optional[str] = None  # Cron expression

    # For event triggers
    event: Optional[str] = None  # "on_ingest", "on_query", "calendar_upcoming"
    filter: Optional[str] = None  # Tag/type filter


class AgentConfig(BaseModel):
    """Configuration for a proactive agent."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    description: Optional[str] = None

    # When to run
    trigger: AgentTrigger

    # What to do
    prompt: str
    collection_id: Optional[str] = None  # Limit to specific collection

    # Output
    output_type: Literal["notification", "entry", "email", "webhook"] = "notification"
    output_config: dict = Field(default_factory=dict)

    # Status
    enabled: bool = True
    last_run: Optional[datetime] = None
    run_count: int = 0

    created_at: datetime = Field(default_factory=datetime.utcnow)


class AgentRun(BaseModel):
    """Record of an agent execution."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    agent_id: str
    agent_name: str

    # Execution
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    success: bool = False

    # Input
    trigger_reason: str
    context_entries: int = 0

    # Output
    result: Optional[str] = None
    entries_created: list[str] = Field(default_factory=list)
    notifications_sent: int = 0

    # Resources
    tokens_used: int = 0
    model_used: str = ""

    # Errors
    error: Optional[str] = None


# Built-in agent definitions
DAILY_BRIEFING_AGENT = AgentConfig(
    id="daily_briefing",
    name="Daily Briefing",
    description="Morning summary of what to focus on today",
    trigger=AgentTrigger(type="schedule", cron="0 7 * * *"),
    prompt="""Review my calendar for today, pending tasks, and recent entries.
Give me a concise morning briefing:
1. What's on my calendar today
2. Top 3 things I should focus on
3. Any follow-ups due
4. One insight from my recent notes that might be relevant today

Keep it brief and actionable.""",
    output_type="notification",
)

WEEKLY_REVIEW_AGENT = AgentConfig(
    id="weekly_review",
    name="Weekly Review",
    description="End of week summary and planning",
    trigger=AgentTrigger(type="schedule", cron="0 18 * * 5"),  # Friday 6 PM
    prompt="""Review my week:
1. What did I accomplish?
2. What decisions did I make?
3. What patterns do you notice?
4. What should I focus on next week?
5. Any loose ends or follow-ups?

Be specific and reference my actual entries.""",
    output_type="entry",
)

FOLLOW_UP_REMINDER_AGENT = AgentConfig(
    id="follow_up_reminder",
    name="Follow-up Reminder",
    description="Check for promised follow-ups",
    trigger=AgentTrigger(type="schedule", cron="0 9 * * *"),  # Daily 9 AM
    prompt="""Search my recent conversations and notes for any:
- Promised follow-ups ("I'll get back to you", "Let me check", etc.)
- Deadlines mentioned
- Commitments made

If any are due today or overdue, remind me.""",
    output_type="notification",
)

PATTERN_DETECTOR_AGENT = AgentConfig(
    id="pattern_detector",
    name="Pattern Detector",
    description="Detect patterns in your data",
    trigger=AgentTrigger(type="schedule", cron="0 20 * * 0"),  # Sunday 8 PM
    prompt="""Analyze my entries from the past week looking for:
- Recurring themes or topics
- Mood or energy patterns
- Productivity patterns
- Any concerning trends
- Positive habits forming

Only report significant patterns with evidence.""",
    output_type="entry",
)
