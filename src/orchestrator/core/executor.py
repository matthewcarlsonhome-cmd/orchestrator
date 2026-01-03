"""Parallel task executor with agent coordination."""

import asyncio
from datetime import datetime
from typing import Optional, Callable, Awaitable, Any
from dataclasses import dataclass, field

from orchestrator.config import config
from orchestrator.models.agent import Agent, AgentStatus
from orchestrator.models.task import Task, TaskStatus
from orchestrator.models.project import Project
from orchestrator.models.blackboard import Blackboard
from orchestrator.agents.base import BaseAgent
from orchestrator.agents.pool import AgentPool
from orchestrator.core.messaging import MessageBus, Message, MessageType
from orchestrator.core.scheduler import TaskScheduler


@dataclass
class TaskExecution:
    """Tracks a single task execution."""
    task: Task
    agent: Agent
    started_at: datetime = field(default_factory=datetime.utcnow)
    future: Optional[asyncio.Future] = None


class ParallelExecutor:
    """
    Executes tasks in parallel across multiple agents.

    Features:
    - True parallel execution using asyncio
    - Dynamic agent allocation from pool
    - Task dependency management
    - Progress tracking and callbacks
    - Graceful shutdown
    """

    def __init__(
        self,
        pool: AgentPool,
        scheduler: TaskScheduler,
        message_bus: MessageBus,
        approval_callback: Optional[Callable[[str], Awaitable[bool]]] = None,
        on_task_start: Optional[Callable[[Task, Agent], Awaitable[None]]] = None,
        on_task_complete: Optional[Callable[[Task, dict], Awaitable[None]]] = None,
        on_task_error: Optional[Callable[[Task, str], Awaitable[None]]] = None,
        on_agent_status: Optional[Callable[[dict], Awaitable[None]]] = None,
    ):
        self.pool = pool
        self.scheduler = scheduler
        self.message_bus = message_bus
        self.approval_callback = approval_callback
        self.on_task_start = on_task_start
        self.on_task_complete = on_task_complete
        self.on_task_error = on_task_error
        self.on_agent_status = on_agent_status  # For real-time status updates

        # Active executions
        self.active_executions: dict[str, TaskExecution] = {}

        # Control
        self.running = False
        self._shutdown_event = asyncio.Event()

    async def execute_all(
        self,
        project: Project,
        blackboard: Blackboard,
        timeout_minutes: int = 240,  # 4 hours default
    ) -> dict:
        """
        Execute all scheduled tasks to completion.

        Returns summary of execution.
        """
        self.running = True
        self._shutdown_event.clear()
        start_time = datetime.utcnow()

        results = {
            "completed": [],
            "failed": [],
            "cancelled": [],
        }

        try:
            timeout = timeout_minutes * 60
            await asyncio.wait_for(
                self._execution_loop(project, blackboard, results),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            # Graceful timeout
            await self.shutdown()
            results["timeout"] = True
        except asyncio.CancelledError:
            await self.shutdown()
            results["cancelled"] = True

        end_time = datetime.utcnow()
        results["duration_seconds"] = (end_time - start_time).total_seconds()
        results["status"] = self.scheduler.get_status()

        return results

    async def _execution_loop(
        self,
        project: Project,
        blackboard: Blackboard,
        results: dict,
    ) -> None:
        """Main execution loop."""
        while self.running:
            # Check if all tasks are done
            status = self.scheduler.get_status()
            pending = status["tasks"].get("queued", 0) + status["tasks"].get("pending", 0)
            in_progress = status["tasks"].get("in_progress", 0)

            if pending == 0 and in_progress == 0:
                break

            # Start new tasks if we have capacity
            await self._start_available_tasks(project, blackboard)

            # Wait for any task to complete or timeout
            if self.active_executions:
                done, pending_futures = await asyncio.wait(
                    [ex.future for ex in self.active_executions.values() if ex.future],
                    timeout=1.0,
                    return_when=asyncio.FIRST_COMPLETED,
                )

                # Process completed tasks
                for future in done:
                    await self._handle_completed_future(future, results)
            else:
                # No active tasks, wait a bit before checking for new ones
                await asyncio.sleep(0.5)

            # Check for shutdown
            if self._shutdown_event.is_set():
                break

    async def _start_available_tasks(
        self,
        project: Project,
        blackboard: Blackboard,
    ) -> None:
        """Start tasks that are ready to run."""
        while self.scheduler.can_schedule_more():
            # Get next task
            task = self.scheduler.get_next_task()
            if not task:
                break

            # Get an agent for the task
            agent = await self.pool.get_best_agent_for_task(task)
            if not agent:
                break  # No agents available

            # Assign and start
            self.scheduler.assign_task(task, agent)

            # Register agent with message bus if not already
            if agent.id not in self.message_bus.queues:
                self.message_bus.register_agent(
                    agent.id,
                    agent.agent_type.value,
                )

            # Create execution tracker
            execution = TaskExecution(task=task, agent=agent)
            self.active_executions[task.id] = execution

            # Start task asynchronously
            execution.future = asyncio.create_task(
                self._run_task(task, agent, project, blackboard)
            )

            # Callback
            if self.on_task_start:
                await self.on_task_start(task, agent)

    async def _run_task(
        self,
        task: Task,
        agent: Agent,
        project: Project,
        blackboard: Blackboard,
    ) -> dict:
        """Run a single task with an agent."""
        base_agent = BaseAgent(
            agent=agent,
            project=project,
            blackboard=blackboard,
            approval_callback=self.approval_callback,
            on_message=self._handle_agent_message,
            on_status=self._handle_agent_status,  # Pass status callback
        )

        result = await base_agent.execute_task(task)
        result["task_id"] = task.id
        result["agent_id"] = agent.id

        return result

    async def _handle_agent_status(self, status_data: dict) -> None:
        """Handle status updates from agents and forward to dashboard."""
        if self.on_agent_status:
            await self.on_agent_status(status_data)

    async def _handle_agent_message(self, message_data: dict) -> None:
        """Handle messages from agents."""
        # Convert to Message and route through bus
        msg = Message(
            message_type=MessageType.NOTIFICATION,
            from_agent_id=message_data.get("from", ""),
            to_agent_type=message_data.get("to", ""),
            subject="Agent Message",
            content=message_data.get("message", ""),
            payload=message_data,
        )
        await self.message_bus.send(msg)

    async def _handle_completed_future(
        self,
        future: asyncio.Future,
        results: dict,
    ) -> None:
        """Handle a completed task future."""
        # Find the execution for this future
        execution = None
        task_id = None

        for tid, ex in self.active_executions.items():
            if ex.future == future:
                execution = ex
                task_id = tid
                break

        if not execution:
            return

        # Remove from active
        del self.active_executions[task_id]

        try:
            result = future.result()
            duration = (datetime.utcnow() - execution.started_at).total_seconds()

            if result.get("success"):
                self.scheduler.complete_task(
                    task_id,
                    result.get("summary", "Completed"),
                    result.get("files_modified", []),
                )
                self.pool.record_task_completion(execution.agent.id, duration, True)
                results["completed"].append({
                    "task_id": task_id,
                    "title": execution.task.title,
                    "duration": duration,
                    **result,
                })

                if self.on_task_complete:
                    await self.on_task_complete(execution.task, result)
            else:
                error = result.get("error", "Unknown error")
                self.scheduler.fail_task(task_id, error)
                self.pool.record_task_completion(execution.agent.id, duration, False)
                results["failed"].append({
                    "task_id": task_id,
                    "title": execution.task.title,
                    "error": error,
                    "duration": duration,
                })

                if self.on_task_error:
                    await self.on_task_error(execution.task, error)

        except Exception as e:
            error = str(e)
            self.scheduler.fail_task(task_id, error)
            results["failed"].append({
                "task_id": task_id,
                "title": execution.task.title,
                "error": error,
            })

            if self.on_task_error:
                await self.on_task_error(execution.task, error)

    async def shutdown(self) -> None:
        """Gracefully shutdown the executor."""
        self.running = False
        self._shutdown_event.set()

        # Cancel all active executions
        for execution in self.active_executions.values():
            if execution.future and not execution.future.done():
                execution.future.cancel()

        # Wait for cancellations
        if self.active_executions:
            await asyncio.gather(
                *[ex.future for ex in self.active_executions.values() if ex.future],
                return_exceptions=True,
            )

        self.active_executions.clear()

    def get_status(self) -> dict:
        """Get executor status."""
        return {
            "running": self.running,
            "active_tasks": len(self.active_executions),
            "active_executions": [
                {
                    "task_id": ex.task.id,
                    "task_title": ex.task.title,
                    "agent_id": ex.agent.id,
                    "started_at": ex.started_at.isoformat(),
                    "duration": (datetime.utcnow() - ex.started_at).total_seconds(),
                }
                for ex in self.active_executions.values()
            ],
            "pool": self.pool.get_pool_status(),
            "scheduler": self.scheduler.get_status(),
            "message_bus": self.message_bus.get_stats(),
        }
