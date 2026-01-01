"""Agent coordinator for conflict resolution and synchronization."""

import asyncio
from datetime import datetime
from typing import Optional, Callable, Awaitable
from enum import Enum

from pydantic import BaseModel, Field

from orchestrator.models.agent import Agent, AgentType
from orchestrator.models.blackboard import Blackboard, EntryType, BlackboardEntry
from orchestrator.core.messaging import MessageBus, Message, MessageType, MessagePriority


class ConflictType(str, Enum):
    """Types of conflicts that can occur."""
    FILE_EDIT = "file_edit"           # Multiple agents editing same file
    DEPENDENCY = "dependency"          # Circular or broken dependencies
    RESOURCE = "resource"              # Resource contention
    MERGE = "merge"                    # Git merge conflict
    DECISION = "decision"              # Conflicting decisions


class Conflict(BaseModel):
    """Represents a conflict between agents."""
    id: str
    conflict_type: ConflictType
    agents_involved: list[str]
    description: str
    file_path: Optional[str] = None
    context: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    resolved: bool = False
    resolution: Optional[str] = None


class AgentCoordinator:
    """
    Coordinates agents and resolves conflicts.

    Features:
    - File lock management
    - Conflict detection and resolution
    - Agent synchronization
    - Work merging coordination
    """

    def __init__(
        self,
        blackboard: Blackboard,
        message_bus: MessageBus,
        on_conflict: Optional[Callable[[Conflict], Awaitable[None]]] = None,
    ):
        self.blackboard = blackboard
        self.message_bus = message_bus
        self.on_conflict = on_conflict

        # Track active conflicts
        self.conflicts: dict[str, Conflict] = {}

        # File lock tracking (file_path -> agent_id)
        self.file_locks: dict[str, str] = {}

        # Agent work tracking (agent_id -> list of files being worked on)
        self.agent_work: dict[str, list[str]] = {}

    async def request_file_lock(
        self,
        agent_id: str,
        file_path: str,
        timeout: int = 30,
    ) -> bool:
        """
        Request a lock on a file for editing.

        Returns True if lock acquired, False otherwise.
        """
        # Check if already locked
        if file_path in self.file_locks:
            holder = self.file_locks[file_path]
            if holder == agent_id:
                return True  # Already own the lock

            # Try to wait for release
            for _ in range(timeout):
                await asyncio.sleep(1)
                if file_path not in self.file_locks:
                    break
            else:
                # Timeout - create conflict
                await self._create_conflict(
                    ConflictType.FILE_EDIT,
                    [agent_id, holder],
                    f"Both agents need to edit {file_path}",
                    file_path=file_path,
                )
                return False

        # Acquire lock
        self.file_locks[file_path] = agent_id
        self.blackboard.lock_file(file_path, agent_id)

        # Track in agent work
        if agent_id not in self.agent_work:
            self.agent_work[agent_id] = []
        self.agent_work[agent_id].append(file_path)

        return True

    async def release_file_lock(
        self,
        agent_id: str,
        file_path: str,
    ) -> bool:
        """Release a file lock."""
        if file_path not in self.file_locks:
            return True

        if self.file_locks[file_path] != agent_id:
            return False  # Not the lock holder

        del self.file_locks[file_path]
        self.blackboard.unlock_file(file_path, agent_id)

        # Remove from agent work
        if agent_id in self.agent_work and file_path in self.agent_work[agent_id]:
            self.agent_work[agent_id].remove(file_path)

        return True

    async def release_all_locks(self, agent_id: str) -> int:
        """Release all locks held by an agent."""
        files_to_release = [
            f for f, a in self.file_locks.items()
            if a == agent_id
        ]

        for file_path in files_to_release:
            await self.release_file_lock(agent_id, file_path)

        return len(files_to_release)

    async def check_for_conflicts(self) -> list[Conflict]:
        """Check for any conflicts in the current state."""
        new_conflicts = []

        # Check for file conflicts from blackboard
        blockers = self.blackboard.get_blockers()
        for blocker in blockers:
            if "conflict" in blocker.title.lower():
                conflict = Conflict(
                    id=blocker.id,
                    conflict_type=ConflictType.FILE_EDIT,
                    agents_involved=[blocker.agent_id],
                    description=blocker.content,
                )
                if conflict.id not in self.conflicts:
                    self.conflicts[conflict.id] = conflict
                    new_conflicts.append(conflict)

        return new_conflicts

    async def _create_conflict(
        self,
        conflict_type: ConflictType,
        agents: list[str],
        description: str,
        file_path: Optional[str] = None,
        context: dict = None,
    ) -> Conflict:
        """Create and track a new conflict."""
        from uuid import uuid4

        conflict = Conflict(
            id=uuid4().hex[:12],
            conflict_type=conflict_type,
            agents_involved=agents,
            description=description,
            file_path=file_path,
            context=context or {},
        )

        self.conflicts[conflict.id] = conflict

        # Post to blackboard
        self.blackboard.post_blocker(
            agent_id="coordinator",
            title=f"Conflict: {conflict_type.value}",
            content=description,
            severity="high",
        )

        # Notify involved agents
        for agent_id in agents:
            await self.message_bus.send(Message(
                message_type=MessageType.NOTIFICATION,
                priority=MessagePriority.URGENT,
                from_agent_id="coordinator",
                to_agent_id=agent_id,
                subject="Conflict Detected",
                content=description,
                payload={"conflict_id": conflict.id},
            ))

        # Callback
        if self.on_conflict:
            await self.on_conflict(conflict)

        return conflict

    async def resolve_conflict(
        self,
        conflict_id: str,
        resolution: str,
        resolved_by: str = "coordinator",
    ) -> bool:
        """Resolve a conflict."""
        if conflict_id not in self.conflicts:
            return False

        conflict = self.conflicts[conflict_id]
        conflict.resolved = True
        conflict.resolution = resolution

        # Notify agents
        for agent_id in conflict.agents_involved:
            await self.message_bus.send(Message(
                message_type=MessageType.NOTIFICATION,
                from_agent_id=resolved_by,
                to_agent_id=agent_id,
                subject="Conflict Resolved",
                content=resolution,
                payload={"conflict_id": conflict_id},
            ))

        # Update blackboard
        self.blackboard.post_decision(
            agent_id=resolved_by,
            title=f"Resolved: {conflict.conflict_type.value}",
            content=resolution,
            rationale=f"Resolved conflict between {', '.join(conflict.agents_involved)}",
        )

        return True

    async def synchronize_agents(self, agent_ids: list[str]) -> bool:
        """
        Synchronize multiple agents at a sync point.

        All agents must reach this point before continuing.
        """
        sync_id = f"sync-{datetime.utcnow().timestamp()}"

        # Send sync request to all agents
        for agent_id in agent_ids:
            await self.message_bus.send(Message(
                message_type=MessageType.SYNC,
                priority=MessagePriority.HIGH,
                from_agent_id="coordinator",
                to_agent_id=agent_id,
                subject="Sync Point",
                content="Please acknowledge sync point",
                payload={"sync_id": sync_id},
                expects_response=True,
            ))

        # Wait for all to acknowledge (with timeout)
        # In a real implementation, we'd track acknowledgments
        await asyncio.sleep(2)  # Simplified for now

        return True

    async def coordinate_merge(
        self,
        branches: list[str],
        target_branch: str,
        agent_id: str,
    ) -> dict:
        """
        Coordinate merging multiple branches.

        Returns merge result with any conflicts.
        """
        # Notify all agents that merge is starting
        await self.message_bus.broadcast(
            from_agent_id="coordinator",
            subject="Merge Starting",
            content=f"Merging branches into {target_branch}",
            payload={"branches": branches, "target": target_branch},
            priority=MessagePriority.HIGH,
        )

        # The actual merge would be handled by the agent
        # This just coordinates the process

        result = {
            "status": "coordinated",
            "branches": branches,
            "target": target_branch,
            "agent": agent_id,
        }

        return result

    def get_agent_workload(self, agent_id: str) -> dict:
        """Get current workload for an agent."""
        return {
            "files_locked": self.agent_work.get(agent_id, []),
            "lock_count": len(self.agent_work.get(agent_id, [])),
        }

    def get_status(self) -> dict:
        """Get coordinator status."""
        return {
            "active_locks": len(self.file_locks),
            "active_conflicts": len([c for c in self.conflicts.values() if not c.resolved]),
            "total_conflicts": len(self.conflicts),
            "agents_with_work": len(self.agent_work),
            "locks_by_agent": {
                agent: len(files)
                for agent, files in self.agent_work.items()
            },
        }
