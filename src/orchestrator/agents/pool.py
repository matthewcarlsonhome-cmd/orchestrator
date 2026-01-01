"""Agent pool management for dynamic agent allocation."""

import asyncio
from datetime import datetime
from typing import Optional, Callable, Awaitable
from collections import defaultdict

from orchestrator.models.agent import Agent, AgentType, AgentStatus, AGENT_CAPABILITIES
from orchestrator.models.task import Task, AgentTypeHint
from orchestrator.config import config


class AgentPool:
    """
    Manages a pool of agents with dynamic allocation.

    Features:
    - Dynamic agent creation based on task needs
    - Agent health monitoring
    - Load balancing across agents
    - Agent recycling after errors
    """

    def __init__(
        self,
        max_agents: int = None,
        on_agent_created: Optional[Callable[[Agent], Awaitable[None]]] = None,
        on_agent_removed: Optional[Callable[[Agent], Awaitable[None]]] = None,
    ):
        self.max_agents = max_agents or config.max_agents
        self.on_agent_created = on_agent_created
        self.on_agent_removed = on_agent_removed

        self.agents: dict[str, Agent] = {}
        self.agent_by_type: dict[AgentType, list[str]] = defaultdict(list)

        # Track agent performance
        self.agent_stats: dict[str, dict] = {}

        # Lock for thread-safe operations
        self._lock = asyncio.Lock()

    @property
    def size(self) -> int:
        """Current pool size."""
        return len(self.agents)

    @property
    def available_slots(self) -> int:
        """Number of agents that can still be created."""
        return self.max_agents - self.size

    async def create_agent(self, agent_type: AgentType) -> Optional[Agent]:
        """Create a new agent of the specified type."""
        async with self._lock:
            if self.size >= self.max_agents:
                return None

            agent = Agent(agent_type=agent_type)
            self.agents[agent.id] = agent
            self.agent_by_type[agent_type].append(agent.id)

            # Initialize stats
            self.agent_stats[agent.id] = {
                "created_at": datetime.utcnow(),
                "tasks_completed": 0,
                "tasks_failed": 0,
                "total_duration": 0,
                "avg_task_duration": 0,
            }

            if self.on_agent_created:
                await self.on_agent_created(agent)

            return agent

    async def remove_agent(self, agent_id: str) -> bool:
        """Remove an agent from the pool."""
        async with self._lock:
            if agent_id not in self.agents:
                return False

            agent = self.agents[agent_id]

            # Don't remove working agents
            if agent.status == AgentStatus.WORKING:
                return False

            del self.agents[agent_id]
            self.agent_by_type[agent.agent_type].remove(agent_id)

            if agent_id in self.agent_stats:
                del self.agent_stats[agent_id]

            if self.on_agent_removed:
                await self.on_agent_removed(agent)

            return True

    def get_agent(self, agent_id: str) -> Optional[Agent]:
        """Get an agent by ID."""
        return self.agents.get(agent_id)

    def get_idle_agents(self) -> list[Agent]:
        """Get all idle agents."""
        return [a for a in self.agents.values() if a.status == AgentStatus.IDLE]

    def get_agents_by_type(self, agent_type: AgentType) -> list[Agent]:
        """Get all agents of a specific type."""
        agent_ids = self.agent_by_type.get(agent_type, [])
        return [self.agents[aid] for aid in agent_ids if aid in self.agents]

    def get_idle_agent_by_type(self, agent_type: AgentType) -> Optional[Agent]:
        """Get an idle agent of a specific type."""
        for agent in self.get_agents_by_type(agent_type):
            if agent.status == AgentStatus.IDLE:
                return agent
        return None

    async def get_or_create_agent(self, agent_type: AgentType) -> Optional[Agent]:
        """Get an idle agent of the type, or create one if possible."""
        # First try to get an existing idle agent
        agent = self.get_idle_agent_by_type(agent_type)
        if agent:
            return agent

        # Try to create a new one
        return await self.create_agent(agent_type)

    async def get_best_agent_for_task(self, task: Task) -> Optional[Agent]:
        """
        Get the best available agent for a task.

        Priority:
        1. Idle agent of exact matching type
        2. Idle fullstack agent
        3. Create new agent of matching type
        4. Create new fullstack agent
        5. Any idle agent
        """
        from orchestrator.core.scheduler import HINT_TO_TYPE

        target_type = HINT_TO_TYPE.get(task.agent_type_hint, AgentType.FULLSTACK)

        # 1. Try exact match
        agent = self.get_idle_agent_by_type(target_type)
        if agent:
            return agent

        # 2. Try fullstack
        if target_type != AgentType.FULLSTACK:
            agent = self.get_idle_agent_by_type(AgentType.FULLSTACK)
            if agent:
                return agent

        # 3. Create new agent of target type
        agent = await self.create_agent(target_type)
        if agent:
            return agent

        # 4. Create fullstack if different
        if target_type != AgentType.FULLSTACK:
            agent = await self.create_agent(AgentType.FULLSTACK)
            if agent:
                return agent

        # 5. Any idle agent
        idle = self.get_idle_agents()
        if idle:
            return idle[0]

        return None

    def record_task_completion(self, agent_id: str, duration: float, success: bool) -> None:
        """Record task completion statistics."""
        if agent_id not in self.agent_stats:
            return

        stats = self.agent_stats[agent_id]
        if success:
            stats["tasks_completed"] += 1
        else:
            stats["tasks_failed"] += 1

        stats["total_duration"] += duration
        total_tasks = stats["tasks_completed"] + stats["tasks_failed"]
        stats["avg_task_duration"] = stats["total_duration"] / total_tasks

    def check_agent_health(self, timeout_seconds: int = 120) -> list[Agent]:
        """Check all agents and return list of unhealthy ones."""
        unhealthy = []
        for agent in self.agents.values():
            if not agent.is_healthy(timeout_seconds):
                unhealthy.append(agent)
        return unhealthy

    async def recycle_unhealthy_agents(self, timeout_seconds: int = 120) -> int:
        """Remove unhealthy agents and return count removed."""
        unhealthy = self.check_agent_health(timeout_seconds)
        removed = 0

        for agent in unhealthy:
            # Mark as error first
            agent.status = AgentStatus.ERROR
            if await self.remove_agent(agent.id):
                removed += 1

        return removed

    def get_pool_status(self) -> dict:
        """Get comprehensive pool status."""
        status_counts = defaultdict(int)
        type_counts = defaultdict(int)

        for agent in self.agents.values():
            status_counts[agent.status.value] += 1
            type_counts[agent.agent_type.value] += 1

        total_completed = sum(s["tasks_completed"] for s in self.agent_stats.values())
        total_failed = sum(s["tasks_failed"] for s in self.agent_stats.values())

        return {
            "size": self.size,
            "max_agents": self.max_agents,
            "available_slots": self.available_slots,
            "by_status": dict(status_counts),
            "by_type": dict(type_counts),
            "total_tasks_completed": total_completed,
            "total_tasks_failed": total_failed,
        }

    async def scale_for_tasks(self, pending_tasks: list[Task]) -> list[Agent]:
        """
        Dynamically scale pool based on pending tasks.

        Returns list of newly created agents.
        """
        from orchestrator.core.scheduler import HINT_TO_TYPE

        # Count needed agent types
        type_needs: dict[AgentType, int] = defaultdict(int)
        for task in pending_tasks:
            agent_type = HINT_TO_TYPE.get(task.agent_type_hint, AgentType.FULLSTACK)
            type_needs[agent_type] += 1

        # Count available agents by type
        type_available: dict[AgentType, int] = defaultdict(int)
        for agent in self.get_idle_agents():
            type_available[agent.agent_type] += 1

        # Create agents to fill gaps
        new_agents = []
        for agent_type, needed in type_needs.items():
            available = type_available.get(agent_type, 0)
            to_create = min(needed - available, self.available_slots)

            for _ in range(to_create):
                agent = await self.create_agent(agent_type)
                if agent:
                    new_agents.append(agent)
                else:
                    break  # No more slots

        return new_agents

    async def shutdown(self) -> None:
        """Gracefully shutdown all agents."""
        for agent in list(self.agents.values()):
            agent.status = AgentStatus.STOPPED
            await self.remove_agent(agent.id)
