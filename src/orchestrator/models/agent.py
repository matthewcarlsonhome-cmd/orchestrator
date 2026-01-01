"""Agent model and types."""

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class AgentType(str, Enum):
    """Types of specialized agents."""

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


class AgentStatus(str, Enum):
    """Current status of an agent."""

    IDLE = "idle"
    WORKING = "working"
    WAITING_APPROVAL = "waiting_approval"  # Waiting for shell command approval
    BLOCKED = "blocked"
    ERROR = "error"
    STOPPED = "stopped"


# Agent type descriptions for task assignment
AGENT_CAPABILITIES: dict[AgentType, dict] = {
    AgentType.ARCHITECT: {
        "name": "Architect",
        "description": "Analyzes codebases, designs system architecture, creates implementation plans",
        "skills": ["system design", "code analysis", "planning", "documentation"],
        "primary_for": ["design", "planning", "architecture", "specification"],
    },
    AgentType.FRONTEND: {
        "name": "Frontend Developer",
        "description": "Builds UI components, styling, client-side logic, state management",
        "skills": ["react", "vue", "css", "tailwind", "typescript", "ui/ux"],
        "primary_for": ["ui", "components", "styling", "frontend", "client"],
    },
    AgentType.BACKEND: {
        "name": "Backend Developer",
        "description": "Builds APIs, database logic, server-side code, integrations",
        "skills": ["apis", "databases", "python", "node", "sql", "rest", "graphql"],
        "primary_for": ["api", "server", "database", "backend", "integration"],
    },
    AgentType.FULLSTACK: {
        "name": "Full-Stack Developer",
        "description": "End-to-end feature development, connecting frontend and backend",
        "skills": ["full-stack", "integration", "features"],
        "primary_for": ["feature", "end-to-end", "integration"],
    },
    AgentType.TESTER: {
        "name": "Test Engineer",
        "description": "Writes and runs tests, ensures code quality and coverage",
        "skills": ["testing", "jest", "pytest", "coverage", "e2e"],
        "primary_for": ["test", "testing", "quality", "coverage"],
    },
    AgentType.DEBUGGER: {
        "name": "Debugger",
        "description": "Investigates bugs, analyzes errors, fixes issues",
        "skills": ["debugging", "error analysis", "troubleshooting"],
        "primary_for": ["bug", "fix", "error", "debug", "issue"],
    },
    AgentType.DEVOPS: {
        "name": "DevOps Engineer",
        "description": "Build systems, deployment, CI/CD, infrastructure",
        "skills": ["docker", "ci/cd", "deployment", "infrastructure"],
        "primary_for": ["deploy", "build", "ci", "infrastructure", "docker"],
    },
    AgentType.REVIEWER: {
        "name": "Code Reviewer",
        "description": "Reviews code quality, security, best practices",
        "skills": ["code review", "security", "best practices"],
        "primary_for": ["review", "security", "audit", "quality"],
    },
    AgentType.RESEARCHER: {
        "name": "Researcher",
        "description": "Finds documentation, solutions, best practices",
        "skills": ["research", "documentation", "learning"],
        "primary_for": ["research", "find", "learn", "documentation"],
    },
    AgentType.COORDINATOR: {
        "name": "Coordinator",
        "description": "Manages workflow, resolves conflicts, merges work",
        "skills": ["coordination", "git", "merging", "conflict resolution"],
        "primary_for": ["merge", "coordinate", "conflict", "sync"],
    },
}


class Agent(BaseModel):
    """An AI agent that performs tasks."""

    id: str = Field(default_factory=lambda: f"agent-{uuid4().hex[:8]}")
    agent_type: AgentType
    status: AgentStatus = Field(default=AgentStatus.IDLE)

    # Current work
    current_task_id: Optional[str] = Field(default=None)
    current_project: Optional[str] = Field(default=None)

    # Health tracking
    last_heartbeat: datetime = Field(default_factory=datetime.utcnow)
    started_at: datetime = Field(default_factory=datetime.utcnow)
    tasks_completed: int = Field(default=0)
    errors_count: int = Field(default=0)

    # Conversation state (for direct agent-to-agent communication)
    pending_messages: list[dict] = Field(default_factory=list)

    @property
    def capabilities(self) -> dict:
        """Get this agent's capabilities."""
        return AGENT_CAPABILITIES[self.agent_type]

    @property
    def display_name(self) -> str:
        """Get display name for this agent."""
        return f"{self.capabilities['name']} ({self.id})"

    def heartbeat(self) -> None:
        """Update last heartbeat time."""
        self.last_heartbeat = datetime.utcnow()

    def is_healthy(self, timeout_seconds: int = 120) -> bool:
        """Check if agent is healthy (recent heartbeat)."""
        elapsed = (datetime.utcnow() - self.last_heartbeat).total_seconds()
        return elapsed < timeout_seconds

    def assign_task(self, task_id: str, project: str) -> None:
        """Assign a task to this agent."""
        self.current_task_id = task_id
        self.current_project = project
        self.status = AgentStatus.WORKING

    def complete_task(self) -> None:
        """Mark current task as complete."""
        self.current_task_id = None
        self.status = AgentStatus.IDLE
        self.tasks_completed += 1

    def record_error(self) -> None:
        """Record an error occurrence."""
        self.errors_count += 1

    def send_message(self, to_agent_id: str, message: str, context: dict = None) -> dict:
        """Create a message to send to another agent."""
        return {
            "from_agent_id": self.id,
            "to_agent_id": to_agent_id,
            "message": message,
            "context": context or {},
            "timestamp": datetime.utcnow().isoformat(),
        }

    def receive_message(self, message: dict) -> None:
        """Receive a message from another agent."""
        self.pending_messages.append(message)
