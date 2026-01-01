"""Task scheduling and assignment."""

from collections import defaultdict
from typing import Optional

from orchestrator.models.task import Task, TaskStatus, AgentTypeHint
from orchestrator.models.agent import Agent, AgentType, AgentStatus


# Mapping from task agent hints to agent types
HINT_TO_TYPE = {
    AgentTypeHint.ARCHITECT: AgentType.ARCHITECT,
    AgentTypeHint.FRONTEND: AgentType.FRONTEND,
    AgentTypeHint.BACKEND: AgentType.BACKEND,
    AgentTypeHint.FULLSTACK: AgentType.FULLSTACK,
    AgentTypeHint.TESTER: AgentType.TESTER,
    AgentTypeHint.DEBUGGER: AgentType.DEBUGGER,
    AgentTypeHint.DEVOPS: AgentType.DEVOPS,
    AgentTypeHint.REVIEWER: AgentType.REVIEWER,
    AgentTypeHint.RESEARCHER: AgentType.RESEARCHER,
    AgentTypeHint.COORDINATOR: AgentType.COORDINATOR,
}


class TaskScheduler:
    """Schedules and assigns tasks to agents."""

    def __init__(self, max_concurrent: int = 3):
        self.max_concurrent = max_concurrent
        self.tasks: dict[str, Task] = {}
        self.agents: dict[str, Agent] = {}
        self.task_queue: list[str] = []  # Task IDs in priority order

    def add_tasks(self, tasks: list[Task]) -> None:
        """Add tasks to the scheduler."""
        for task in tasks:
            self.tasks[task.id] = task
            task.status = TaskStatus.QUEUED
        self._rebuild_queue()

    def add_agent(self, agent: Agent) -> None:
        """Register an agent with the scheduler."""
        self.agents[agent.id] = agent

    def remove_agent(self, agent_id: str) -> None:
        """Remove an agent from the scheduler."""
        if agent_id in self.agents:
            del self.agents[agent_id]

    def _rebuild_queue(self) -> None:
        """Rebuild the task queue in priority order."""
        # Get pending/queued tasks
        pending = [
            t for t in self.tasks.values()
            if t.status in (TaskStatus.PENDING, TaskStatus.QUEUED)
        ]

        # Sort by priority (lower number = higher priority)
        pending.sort(key=lambda t: t.priority.value)

        self.task_queue = [t.id for t in pending]

    def get_completed_task_ids(self) -> set[str]:
        """Get IDs of all completed tasks."""
        return {
            task_id for task_id, task in self.tasks.items()
            if task.status == TaskStatus.COMPLETED
        }

    def get_next_task(self, agent_type: Optional[AgentType] = None) -> Optional[Task]:
        """
        Get the next available task, optionally filtered by agent type.

        Returns a task that:
        1. Has all dependencies satisfied
        2. Matches the agent type (if specified)
        3. Is highest priority among candidates
        """
        completed = self.get_completed_task_ids()

        for task_id in self.task_queue:
            task = self.tasks[task_id]

            # Skip if already in progress
            if task.status != TaskStatus.QUEUED:
                continue

            # Check dependencies
            if not task.can_start(completed):
                continue

            # Check agent type match
            if agent_type:
                expected_type = HINT_TO_TYPE.get(task.agent_type_hint)
                if expected_type and expected_type != agent_type:
                    continue

            return task

        return None

    def assign_task(self, task: Task, agent: Agent) -> bool:
        """Assign a task to an agent."""
        if task.status != TaskStatus.QUEUED:
            return False

        if agent.status != AgentStatus.IDLE:
            return False

        task.mark_started(agent.id)
        agent.assign_task(task.id, task.project_name)

        return True

    def complete_task(self, task_id: str, result: str, files_modified: list[str] = None) -> None:
        """Mark a task as completed."""
        if task_id in self.tasks:
            task = self.tasks[task_id]
            task.mark_completed(result, files_modified)

            # Free up the assigned agent
            if task.assigned_agent_id and task.assigned_agent_id in self.agents:
                self.agents[task.assigned_agent_id].complete_task()

            self._rebuild_queue()

    def fail_task(self, task_id: str, error: str) -> None:
        """Mark a task as failed."""
        if task_id in self.tasks:
            task = self.tasks[task_id]
            task.mark_failed(error)

            # Free up the assigned agent
            if task.assigned_agent_id and task.assigned_agent_id in self.agents:
                agent = self.agents[task.assigned_agent_id]
                agent.complete_task()
                agent.record_error()

            self._rebuild_queue()

    def get_idle_agents(self) -> list[Agent]:
        """Get all idle agents."""
        return [a for a in self.agents.values() if a.status == AgentStatus.IDLE]

    def get_running_count(self) -> int:
        """Get count of currently running tasks."""
        return sum(
            1 for t in self.tasks.values()
            if t.status == TaskStatus.IN_PROGRESS
        )

    def can_schedule_more(self) -> bool:
        """Check if we can schedule more tasks."""
        return self.get_running_count() < self.max_concurrent

    def get_status(self) -> dict:
        """Get scheduler status summary."""
        status_counts = defaultdict(int)
        for task in self.tasks.values():
            status_counts[task.status.value] += 1

        agent_counts = defaultdict(int)
        for agent in self.agents.values():
            agent_counts[agent.status.value] += 1

        return {
            "tasks": dict(status_counts),
            "agents": dict(agent_counts),
            "queue_length": len(self.task_queue),
            "running": self.get_running_count(),
            "max_concurrent": self.max_concurrent,
        }

    def get_next_assignments(self) -> list[tuple[Task, Agent]]:
        """
        Get the next batch of task-agent assignments.

        Returns list of (task, agent) tuples that can be started.
        """
        assignments = []
        idle_agents = self.get_idle_agents()

        if not idle_agents:
            return []

        completed = self.get_completed_task_ids()

        for task_id in self.task_queue:
            if not self.can_schedule_more():
                break

            if not idle_agents:
                break

            task = self.tasks[task_id]

            if task.status != TaskStatus.QUEUED:
                continue

            if not task.can_start(completed):
                continue

            # Find best matching agent
            expected_type = HINT_TO_TYPE.get(task.agent_type_hint)
            best_agent = None

            # First try to find exact match
            for agent in idle_agents:
                if agent.agent_type == expected_type:
                    best_agent = agent
                    break

            # If no exact match, use fullstack or any available
            if not best_agent:
                for agent in idle_agents:
                    if agent.agent_type == AgentType.FULLSTACK:
                        best_agent = agent
                        break

            if not best_agent and idle_agents:
                best_agent = idle_agents[0]

            if best_agent:
                assignments.append((task, best_agent))
                idle_agents.remove(best_agent)

        return assignments
