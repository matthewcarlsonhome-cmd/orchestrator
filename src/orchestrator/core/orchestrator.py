"""Main orchestrator that coordinates everything."""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional, Awaitable

from orchestrator.config import config
from orchestrator.models.project import Project, ProjectConfig
from orchestrator.models.task import Task, TaskStatus
from orchestrator.models.agent import Agent, AgentType, AgentStatus
from orchestrator.models.blackboard import Blackboard
from orchestrator.core.decomposer import TaskDecomposer
from orchestrator.core.scheduler import TaskScheduler, HINT_TO_TYPE
from orchestrator.core.messaging import MessageBus
from orchestrator.core.executor import ParallelExecutor
from orchestrator.tools.git_ops import GitTools
from orchestrator.agents.base import BaseAgent
from orchestrator.agents.pool import AgentPool
from orchestrator.agents.coordinator import AgentCoordinator


class Orchestrator:
    """
    Main orchestrator that coordinates agents, tasks, and projects.

    Usage:
        orchestrator = Orchestrator()
        await orchestrator.run("skillengine", "Add user authentication")
    """

    def __init__(
        self,
        max_agents: int = None,
        approval_callback: Optional[Callable[[str], Awaitable[bool]]] = None,
        on_progress: Optional[Callable[[dict], Awaitable[None]]] = None,
    ):
        self.max_agents = max_agents or config.max_agents
        self.approval_callback = approval_callback
        self.on_progress = on_progress

        # Core components
        self.decomposer = TaskDecomposer()
        self.scheduler = TaskScheduler(max_concurrent=self.max_agents)

        # Phase 2: Enhanced multi-agent components
        self.message_bus = MessageBus()
        self.agent_pool = AgentPool(
            max_agents=self.max_agents,
            on_agent_created=self._on_agent_created,
            on_agent_removed=self._on_agent_removed,
        )

        # Will be initialized per-project
        self.coordinators: dict[str, AgentCoordinator] = {}
        self.executors: dict[str, ParallelExecutor] = {}

        self.projects: dict[str, Project] = {}
        self.blackboards: dict[str, Blackboard] = {}
        self.running = False

        # Checkpoint tracking
        self._last_checkpoint: Optional[datetime] = None
        self._checkpoint_task: Optional[asyncio.Task] = None

        # Ensure directories exist
        config.ensure_dirs()

    async def _on_agent_created(self, agent: Agent) -> None:
        """Callback when an agent is created."""
        # Register with message bus
        self.message_bus.register_agent(agent.id, agent.agent_type.value)
        # Also add to scheduler
        self.scheduler.add_agent(agent)

        await self._emit_progress({
            "type": "agent_created",
            "agent_id": agent.id,
            "agent_type": agent.agent_type.value,
        })

    async def _on_agent_removed(self, agent: Agent) -> None:
        """Callback when an agent is removed."""
        self.message_bus.unregister_agent(agent.id)
        self.scheduler.remove_agent(agent.id)

        await self._emit_progress({
            "type": "agent_removed",
            "agent_id": agent.id,
        })

    def load_project(self, name: str) -> Project:
        """Load a project configuration."""
        config_path = config.config_dir / f"{name}.yaml"
        if not config_path.exists():
            raise FileNotFoundError(f"Project config not found: {config_path}")

        project_config = ProjectConfig.from_yaml(config_path)

        # Set local path if not specified
        local_path = project_config.local_path or config.projects_dir / name

        project = Project(
            config=project_config,
            local_path=local_path,
        )

        self.projects[name] = project
        self.blackboards[name] = Blackboard(project=name)

        return project

    def register_project(self, project_config: ProjectConfig) -> Project:
        """Register a project from config object."""
        local_path = project_config.local_path or config.projects_dir / project_config.name

        project = Project(
            config=project_config,
            local_path=local_path,
        )

        self.projects[project_config.name] = project
        self.blackboards[project_config.name] = Blackboard(project=project_config.name)

        return project

    async def setup_project(self, name: str, github_token: Optional[str] = None) -> Project:
        """Clone/update a project repository."""
        if name not in self.projects:
            self.load_project(name)

        project = self.projects[name]
        git = GitTools(project)

        if project.local_path.exists():
            git.open()
            try:
                git.pull()
            except Exception:
                # Repo might not have remote set up yet (new repo)
                pass
        else:
            git.clone(github_token)

        project.is_cloned = True
        project.last_synced = datetime.utcnow()

        status_msg = "initialized_new" if project.is_new_repo else "ready"
        await self._emit_progress({
            "type": "project_setup",
            "project": name,
            "status": status_msg,
            "is_new_repo": project.is_new_repo,
            "local_path": str(project.local_path),
        })

        return project

    async def create_agents(self, agent_types: list[AgentType] = None) -> list[Agent]:
        """Create the agent pool."""
        if agent_types is None:
            # Default balanced pool
            agent_types = [
                AgentType.ARCHITECT,
                AgentType.FULLSTACK,
                AgentType.FULLSTACK,
            ]

        agents = []
        for agent_type in agent_types[:self.max_agents]:
            agent = await self.agent_pool.create_agent(agent_type)
            if agent:
                agents.append(agent)

        return agents

    def _setup_project_components(self, project_name: str) -> None:
        """Set up coordinator and executor for a project."""
        blackboard = self.blackboards[project_name]

        # Create coordinator
        self.coordinators[project_name] = AgentCoordinator(
            blackboard=blackboard,
            message_bus=self.message_bus,
            on_conflict=self._on_conflict,
        )

        # Create executor
        self.executors[project_name] = ParallelExecutor(
            pool=self.agent_pool,
            scheduler=self.scheduler,
            message_bus=self.message_bus,
            approval_callback=self.approval_callback,
            on_task_start=self._on_task_start,
            on_task_complete=self._on_task_complete,
            on_task_error=self._on_task_error,
        )

    async def _on_conflict(self, conflict) -> None:
        """Handle conflict detection."""
        await self._emit_progress({
            "type": "conflict_detected",
            "conflict_id": conflict.id,
            "conflict_type": conflict.conflict_type.value,
            "agents": conflict.agents_involved,
            "description": conflict.description,
        })

    async def _on_task_start(self, task: Task, agent: Agent) -> None:
        """Handle task start."""
        await self._emit_progress({
            "type": "task_started",
            "task_id": task.id,
            "task_title": task.title,
            "agent_id": agent.id,
            "agent_type": agent.agent_type.value,
        })

    async def _on_task_complete(self, task: Task, result: dict) -> None:
        """Handle task completion."""
        await self._emit_progress({
            "type": "task_completed",
            "task_id": task.id,
            "task_title": task.title,
            "summary": result.get("summary"),
            "files_modified": result.get("files_modified", []),
        })

    async def _on_task_error(self, task: Task, error: str) -> None:
        """Handle task error."""
        await self._emit_progress({
            "type": "task_failed",
            "task_id": task.id,
            "task_title": task.title,
            "error": error,
        })

    async def run(
        self,
        project_name: str,
        instructions: str,
        use_llm_decomposition: bool = True,
        github_token: Optional[str] = None,
        timeout_minutes: int = 240,  # 4 hours default
    ) -> dict:
        """
        Run the orchestrator on a project with given instructions.

        Args:
            project_name: Name of the project to work on
            instructions: High-level instructions
            use_llm_decomposition: Use LLM for task decomposition (vs simple rules)
            github_token: GitHub token for cloning private repos
            timeout_minutes: Maximum run time in minutes (default 4 hours)

        Returns:
            Summary of the run
        """
        self.running = True
        start_time = datetime.utcnow()

        await self._emit_progress({
            "type": "run_start",
            "project": project_name,
            "instructions": instructions,
            "timeout_minutes": timeout_minutes,
        })

        try:
            # Setup project
            project = await self.setup_project(project_name, github_token)
            blackboard = self.blackboards[project_name]

            # Setup Phase 2 components for this project
            self._setup_project_components(project_name)

            # Decompose tasks
            await self._emit_progress({
                "type": "decomposing",
                "project": project_name,
            })

            if use_llm_decomposition:
                tasks = self.decomposer.decompose(instructions, project)
            else:
                tasks = self.decomposer.decompose_simple(instructions, project)

            self.scheduler.add_tasks(tasks)

            await self._emit_progress({
                "type": "tasks_created",
                "project": project_name,
                "count": len(tasks),
                "tasks": [{"id": t.id, "title": t.title} for t in tasks],
            })

            # Create agents if not already created
            if self.agent_pool.size == 0:
                await self.create_agents()

            # Start automatic checkpointing
            self._checkpoint_task = asyncio.create_task(
                self._checkpoint_loop()
            )

            # Use the ParallelExecutor for task execution
            executor = self.executors[project_name]
            results = await executor.execute_all(
                project=project,
                blackboard=blackboard,
                timeout_minutes=timeout_minutes,
            )

        except Exception as e:
            await self._emit_progress({
                "type": "error",
                "error": str(e),
            })
            raise

        finally:
            self.running = False
            if self._checkpoint_task:
                self._checkpoint_task.cancel()
                try:
                    await self._checkpoint_task
                except asyncio.CancelledError:
                    pass

        # Generate summary
        end_time = datetime.utcnow()
        duration = (end_time - start_time).total_seconds()
        status = self.scheduler.get_status()

        summary = {
            "project": project_name,
            "instructions": instructions,
            "duration_seconds": duration,
            "tasks": status["tasks"],
            "completed_tasks": [
                {
                    "id": t.id,
                    "title": t.title,
                    "result": t.result,
                    "files_modified": t.files_modified,
                }
                for t in self.scheduler.tasks.values()
                if t.status == TaskStatus.COMPLETED
            ],
            "failed_tasks": [
                {
                    "id": t.id,
                    "title": t.title,
                    "error": t.error,
                }
                for t in self.scheduler.tasks.values()
                if t.status == TaskStatus.FAILED
            ],
            "agent_pool": self.agent_pool.get_pool_status(),
            "message_bus": self.message_bus.get_stats(),
        }

        await self._emit_progress({
            "type": "run_complete",
            "summary": summary,
        })

        return summary

    async def _checkpoint_loop(self) -> None:
        """Periodically save checkpoints."""
        interval = config.checkpoint_interval_minutes * 60

        while self.running:
            await asyncio.sleep(interval)
            if self.running:
                checkpoint_path = await self.checkpoint()
                await self._emit_progress({
                    "type": "checkpoint_saved",
                    "path": str(checkpoint_path),
                })

    async def _run_agent_task(
        self,
        agent: Agent,
        task: Task,
        project: Project,
        blackboard: Blackboard,
    ) -> dict:
        """Run a single agent on a task."""
        base_agent = BaseAgent(
            agent=agent,
            project=project,
            blackboard=blackboard,
            approval_callback=self.approval_callback,
            on_message=self._handle_agent_message,
        )

        result = await base_agent.execute_task(task)
        result["task_id"] = task.id
        result["agent_id"] = agent.id

        return result

    async def _handle_task_result(self, result: dict) -> None:
        """Handle the result of a completed task."""
        task_id = result.get("task_id")
        if not task_id:
            return

        if result.get("success"):
            self.scheduler.complete_task(
                task_id,
                result.get("summary", "Task completed"),
                result.get("files_modified", []),
            )

            await self._emit_progress({
                "type": "task_completed",
                "task_id": task_id,
                "summary": result.get("summary"),
                "files_modified": result.get("files_modified", []),
            })

            # Handle follow-up tasks if suggested
            follow_ups = result.get("follow_up_tasks", [])
            if follow_ups:
                await self._emit_progress({
                    "type": "follow_up_suggested",
                    "task_id": task_id,
                    "suggestions": follow_ups,
                })
        else:
            self.scheduler.fail_task(
                task_id,
                result.get("error", "Unknown error"),
            )

            await self._emit_progress({
                "type": "task_failed",
                "task_id": task_id,
                "error": result.get("error"),
            })

    async def _handle_agent_message(self, message: dict) -> None:
        """Handle inter-agent messages."""
        await self._emit_progress({
            "type": "agent_message",
            "from": message.get("from"),
            "to": message.get("to"),
            "message": message.get("message"),
        })

    async def _emit_progress(self, event: dict) -> None:
        """Emit a progress event."""
        event["timestamp"] = datetime.utcnow().isoformat()
        if self.on_progress:
            await self.on_progress(event)

    def stop(self) -> None:
        """Stop the orchestrator."""
        self.running = False

    def get_status(self) -> dict:
        """Get current orchestrator status."""
        return {
            "running": self.running,
            "projects": list(self.projects.keys()),
            "scheduler": self.scheduler.get_status(),
            "agent_pool": self.agent_pool.get_pool_status(),
            "message_bus": self.message_bus.get_stats(),
            "blackboards": {
                name: bb.get_summary()
                for name, bb in self.blackboards.items()
            },
            "coordinators": {
                name: coord.get_status()
                for name, coord in self.coordinators.items()
            },
            "executors": {
                name: exec.get_status()
                for name, exec in self.executors.items()
            },
        }

    async def shutdown(self) -> None:
        """Gracefully shutdown the orchestrator."""
        self.running = False

        # Shutdown all executors
        for executor in self.executors.values():
            await executor.shutdown()

        # Shutdown agent pool
        await self.agent_pool.shutdown()

        # Save final checkpoint
        await self.checkpoint()

        await self._emit_progress({
            "type": "shutdown_complete",
        })

    async def checkpoint(self) -> Path:
        """Save current state to a checkpoint file."""
        checkpoint_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "projects": {
                name: project.model_dump(mode="json")
                for name, project in self.projects.items()
            },
            "tasks": {
                task_id: task.model_dump(mode="json")
                for task_id, task in self.scheduler.tasks.items()
            },
            "blackboards": {
                name: bb.model_dump(mode="json")
                for name, bb in self.blackboards.items()
            },
        }

        checkpoint_path = (
            config.data_dir / "checkpoints" /
            f"checkpoint_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        )

        checkpoint_path.parent.mkdir(parents=True, exist_ok=True)

        with open(checkpoint_path, "w") as f:
            json.dump(checkpoint_data, f, indent=2, default=str)

        return checkpoint_path

    @classmethod
    async def from_checkpoint(cls, checkpoint_path: Path) -> "Orchestrator":
        """Restore orchestrator from a checkpoint."""
        with open(checkpoint_path) as f:
            data = json.load(f)

        orchestrator = cls()

        # Restore projects
        for name, project_data in data.get("projects", {}).items():
            project = Project.model_validate(project_data)
            orchestrator.projects[name] = project
            orchestrator.blackboards[name] = Blackboard(project=name)

        # Restore tasks
        for task_id, task_data in data.get("tasks", {}).items():
            task = Task.model_validate(task_data)
            orchestrator.scheduler.tasks[task_id] = task

        # Restore blackboards
        for name, bb_data in data.get("blackboards", {}).items():
            orchestrator.blackboards[name] = Blackboard.model_validate(bb_data)

        return orchestrator
