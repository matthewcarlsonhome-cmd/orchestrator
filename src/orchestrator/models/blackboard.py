"""Blackboard model for shared agent knowledge."""

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class EntryType(str, Enum):
    """Types of blackboard entries."""

    DISCOVERY = "discovery"  # Something learned about the codebase
    DECISION = "decision"  # An architectural/design decision made
    BLOCKER = "blocker"  # A problem blocking progress
    QUESTION = "question"  # A question for user or other agents
    CONTEXT = "context"  # Shared context information
    FILE_LOCK = "file_lock"  # File being edited (prevents conflicts)
    MESSAGE = "message"  # Inter-agent message
    PROGRESS = "progress"  # Progress update


class BlackboardEntry(BaseModel):
    """An entry on the shared blackboard."""

    id: str = Field(default_factory=lambda: uuid4().hex[:12])
    entry_type: EntryType
    agent_id: str = Field(..., description="Agent that created this entry")
    project: str = Field(..., description="Project this entry relates to")

    title: str = Field(..., description="Short title/summary")
    content: str = Field(..., description="Full content")
    metadata: dict[str, Any] = Field(default_factory=dict)

    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = Field(
        default=None, description="When this entry expires (e.g., file locks)"
    )
    is_resolved: bool = Field(default=False, description="Whether this has been addressed")

    # For file locks
    file_path: Optional[str] = Field(default=None)


class Blackboard(BaseModel):
    """Shared knowledge base for all agents."""

    project: str = Field(..., description="Project this blackboard is for")
    entries: list[BlackboardEntry] = Field(default_factory=list)

    # Quick access indexes
    file_locks: dict[str, str] = Field(
        default_factory=dict, description="file_path -> agent_id"
    )
    active_messages: list[BlackboardEntry] = Field(default_factory=list)

    def add_entry(self, entry: BlackboardEntry) -> None:
        """Add an entry to the blackboard."""
        self.entries.append(entry)

        # Update indexes
        if entry.entry_type == EntryType.FILE_LOCK and entry.file_path:
            self.file_locks[entry.file_path] = entry.agent_id
        elif entry.entry_type == EntryType.MESSAGE:
            self.active_messages.append(entry)

    def remove_entry(self, entry_id: str) -> None:
        """Remove an entry from the blackboard."""
        entry = next((e for e in self.entries if e.id == entry_id), None)
        if entry:
            self.entries.remove(entry)
            # Update indexes
            if entry.entry_type == EntryType.FILE_LOCK and entry.file_path:
                self.file_locks.pop(entry.file_path, None)
            elif entry.entry_type == EntryType.MESSAGE:
                self.active_messages = [m for m in self.active_messages if m.id != entry_id]

    def lock_file(self, file_path: str, agent_id: str) -> bool:
        """Attempt to lock a file for editing. Returns True if successful."""
        if file_path in self.file_locks:
            return self.file_locks[file_path] == agent_id  # Already locked by same agent

        entry = BlackboardEntry(
            entry_type=EntryType.FILE_LOCK,
            agent_id=agent_id,
            project=self.project,
            title=f"File lock: {file_path}",
            content=f"Agent {agent_id} is editing {file_path}",
            file_path=file_path,
        )
        self.add_entry(entry)
        return True

    def unlock_file(self, file_path: str, agent_id: str) -> bool:
        """Unlock a file. Returns True if successful."""
        if file_path not in self.file_locks:
            return True
        if self.file_locks[file_path] != agent_id:
            return False  # Not locked by this agent

        # Find and remove the lock entry
        lock_entry = next(
            (e for e in self.entries
             if e.entry_type == EntryType.FILE_LOCK and e.file_path == file_path),
            None
        )
        if lock_entry:
            self.remove_entry(lock_entry.id)
        return True

    def is_file_locked(self, file_path: str, by_agent_id: Optional[str] = None) -> bool:
        """Check if a file is locked, optionally by a specific agent."""
        if file_path not in self.file_locks:
            return False
        if by_agent_id:
            return self.file_locks[file_path] == by_agent_id
        return True

    def get_discoveries(self) -> list[BlackboardEntry]:
        """Get all discovery entries."""
        return [e for e in self.entries if e.entry_type == EntryType.DISCOVERY]

    def get_decisions(self) -> list[BlackboardEntry]:
        """Get all decision entries."""
        return [e for e in self.entries if e.entry_type == EntryType.DECISION]

    def get_blockers(self) -> list[BlackboardEntry]:
        """Get all unresolved blockers."""
        return [
            e for e in self.entries
            if e.entry_type == EntryType.BLOCKER and not e.is_resolved
        ]

    def get_messages_for_agent(self, agent_id: str) -> list[BlackboardEntry]:
        """Get messages targeted at a specific agent."""
        return [
            e for e in self.active_messages
            if e.metadata.get("to_agent_id") == agent_id
        ]

    def post_discovery(self, agent_id: str, title: str, content: str) -> BlackboardEntry:
        """Post a discovery to the blackboard."""
        entry = BlackboardEntry(
            entry_type=EntryType.DISCOVERY,
            agent_id=agent_id,
            project=self.project,
            title=title,
            content=content,
        )
        self.add_entry(entry)
        return entry

    def post_decision(
        self, agent_id: str, title: str, content: str, rationale: str = ""
    ) -> BlackboardEntry:
        """Post a decision to the blackboard."""
        entry = BlackboardEntry(
            entry_type=EntryType.DECISION,
            agent_id=agent_id,
            project=self.project,
            title=title,
            content=content,
            metadata={"rationale": rationale},
        )
        self.add_entry(entry)
        return entry

    def post_blocker(
        self, agent_id: str, title: str, content: str, severity: str = "medium"
    ) -> BlackboardEntry:
        """Post a blocker to the blackboard."""
        entry = BlackboardEntry(
            entry_type=EntryType.BLOCKER,
            agent_id=agent_id,
            project=self.project,
            title=title,
            content=content,
            metadata={"severity": severity},
        )
        self.add_entry(entry)
        return entry

    def send_message(
        self, from_agent_id: str, to_agent_id: str, message: str, context: dict = None
    ) -> BlackboardEntry:
        """Send a message between agents via the blackboard."""
        entry = BlackboardEntry(
            entry_type=EntryType.MESSAGE,
            agent_id=from_agent_id,
            project=self.project,
            title=f"Message to {to_agent_id}",
            content=message,
            metadata={
                "to_agent_id": to_agent_id,
                "context": context or {},
            },
        )
        self.add_entry(entry)
        return entry

    def get_summary(self) -> dict:
        """Get a summary of the blackboard state."""
        return {
            "total_entries": len(self.entries),
            "discoveries": len(self.get_discoveries()),
            "decisions": len(self.get_decisions()),
            "blockers": len(self.get_blockers()),
            "active_messages": len(self.active_messages),
            "locked_files": len(self.file_locks),
        }
