"""Task model for work items."""

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    """Status of a task."""

    PENDING = "pending"
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskPriority(int, Enum):
    """Priority levels for tasks."""

    CRITICAL = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4


class AgentTypeHint(str, Enum):
    """Suggested agent type for a task."""

    ARCHITECT = "architect"
    FRONTEND = "frontend"
    BACKEND = "backend"
    FULLSTACK = "fullstack"
    TESTER = "tester"
    DEBUGGER = "debugger"
    DEVOPS = "devops"
    REVIEWER = "reviewer"
    RESEARCHER = "researcher"
    COORDINATOR = "coordinator"


class Task(BaseModel):
    """A unit of work to be performed by an agent."""

    id: str = Field(default_factory=lambda: uuid4().hex[:12])
    project_name: str = Field(..., description="Project this task belongs to")
    title: str = Field(..., description="Short task title")
    description: str = Field(..., description="Detailed task description")
    agent_type_hint: AgentTypeHint = Field(
        ..., description="Suggested agent type for this task"
    )

    # Status tracking
    status: TaskStatus = Field(default=TaskStatus.PENDING)
    priority: TaskPriority = Field(default=TaskPriority.MEDIUM)

    # Dependencies
    depends_on: list[str] = Field(
        default_factory=list, description="Task IDs this task depends on"
    )
    blocks: list[str] = Field(
        default_factory=list, description="Task IDs blocked by this task"
    )

    # Assignment
    assigned_agent_id: Optional[str] = Field(default=None)
    branch_name: Optional[str] = Field(default=None, description="Git branch for this task")

    # Timing
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = Field(default=None)
    completed_at: Optional[datetime] = Field(default=None)

    # Results
    result: Optional[str] = Field(default=None, description="Task completion result/summary")
    error: Optional[str] = Field(default=None, description="Error message if failed")
    files_modified: list[str] = Field(
        default_factory=list, description="Files modified by this task"
    )
    commits: list[str] = Field(
        default_factory=list, description="Commit hashes created"
    )

    # Context
    context: dict = Field(
        default_factory=dict, description="Additional context for the task"
    )
    parent_task_id: Optional[str] = Field(
        default=None, description="Parent task if this is a subtask"
    )

    def can_start(self, completed_task_ids: set[str]) -> bool:
        """Check if all dependencies are satisfied."""
        return all(dep in completed_task_ids for dep in self.depends_on)

    def mark_started(self, agent_id: str) -> None:
        """Mark task as started by an agent."""
        self.status = TaskStatus.IN_PROGRESS
        self.assigned_agent_id = agent_id
        self.started_at = datetime.utcnow()

    def mark_completed(self, result: str, files_modified: list[str] = None) -> None:
        """Mark task as completed."""
        self.status = TaskStatus.COMPLETED
        self.result = result
        self.completed_at = datetime.utcnow()
        if files_modified:
            self.files_modified = files_modified

    def mark_failed(self, error: str) -> None:
        """Mark task as failed."""
        self.status = TaskStatus.FAILED
        self.error = error
        self.completed_at = datetime.utcnow()

    @property
    def duration_seconds(self) -> Optional[float]:
        """Get task duration in seconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None
