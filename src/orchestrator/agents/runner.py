"""Enhanced agent runner with message handling and coordination."""

import asyncio
from datetime import datetime
from typing import Optional, Callable, Awaitable

from orchestrator.models.agent import Agent, AgentStatus
from orchestrator.models.task import Task
from orchestrator.models.project import Project
from orchestrator.models.blackboard import Blackboard
from orchestrator.agents.base import BaseAgent
from orchestrator.core.messaging import MessageBus, Message, MessageType
from orchestrator.agents.coordinator import AgentCoordinator


class AgentRunner:
    """
    Enhanced agent runner with messaging and coordination support.

    Features:
    - Message handling during task execution
    - Coordination with other agents
    - File locking
    - Heartbeat monitoring
    """

    def __init__(
        self,
        agent: Agent,
        project: Project,
        blackboard: Blackboard,
        message_bus: MessageBus,
        coordinator: AgentCoordinator,
        approval_callback: Optional[Callable[[str], Awaitable[bool]]] = None,
    ):
        self.agent = agent
        self.project = project
        self.blackboard = blackboard
        self.message_bus = message_bus
        self.coordinator = coordinator
        self.approval_callback = approval_callback

        # Base agent for Claude API interaction
        self.base_agent = BaseAgent(
            agent=agent,
            project=project,
            blackboard=blackboard,
            approval_callback=approval_callback,
            on_message=self._handle_outgoing_message,
        )

        # State
        self.running = False
        self.current_task: Optional[Task] = None

        # Register with message bus
        self.message_bus.register_agent(
            agent.id,
            agent.agent_type.value,
            self._handle_incoming_message,
        )

    async def execute_task(self, task: Task) -> dict:
        """Execute a task with full messaging and coordination support."""
        self.running = True
        self.current_task = task
        self.agent.assign_task(task.id, self.project.name)

        start_time = datetime.utcnow()

        try:
            # Start heartbeat
            heartbeat_task = asyncio.create_task(self._heartbeat_loop())

            # Start message processing
            message_task = asyncio.create_task(self._message_loop())

            # Execute the actual task
            result = await self.base_agent.execute_task(task)

            # Stop background tasks
            self.running = False
            heartbeat_task.cancel()
            message_task.cancel()

            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass

            try:
                await message_task
            except asyncio.CancelledError:
                pass

            # Release any locks
            await self.coordinator.release_all_locks(self.agent.id)

            # Calculate duration
            duration = (datetime.utcnow() - start_time).total_seconds()
            result["duration"] = duration

            return result

        except Exception as e:
            self.running = False
            await self.coordinator.release_all_locks(self.agent.id)
            return {
                "success": False,
                "error": str(e),
                "duration": (datetime.utcnow() - start_time).total_seconds(),
            }

        finally:
            self.current_task = None
            self.agent.complete_task()

    async def _heartbeat_loop(self) -> None:
        """Send periodic heartbeats."""
        while self.running:
            self.agent.heartbeat()
            await asyncio.sleep(30)

    async def _message_loop(self) -> None:
        """Process incoming messages during task execution."""
        while self.running:
            message = await self.message_bus.receive(self.agent.id, timeout=1.0)
            if message:
                await self._process_message(message)

    async def _handle_incoming_message(self, message: Message) -> None:
        """Handle incoming message (called by message bus)."""
        # This is called immediately when a message is enqueued
        # Actual processing happens in _message_loop
        pass

    async def _process_message(self, message: Message) -> None:
        """Process a received message."""
        if message.message_type == MessageType.REQUEST:
            # Handle request from another agent
            response = await self._handle_request(message)
            if message.expects_response:
                await self.message_bus.respond(message, response)

        elif message.message_type == MessageType.NOTIFICATION:
            # Handle notification
            await self._handle_notification(message)

        elif message.message_type == MessageType.SYNC:
            # Handle sync request
            await self.message_bus.respond(message, "acknowledged")

        elif message.message_type == MessageType.HANDOFF:
            # Handle task handoff
            await self._handle_handoff(message)

    async def _handle_request(self, message: Message) -> str:
        """Handle a request message from another agent."""
        subject = message.subject.lower()

        if "status" in subject:
            return f"Working on: {self.current_task.title if self.current_task else 'idle'}"

        elif "file" in subject:
            # File-related request
            file_path = message.payload.get("file_path")
            if file_path:
                return f"File {file_path}: locked={self.coordinator.file_locks.get(file_path) == self.agent.id}"

        elif "help" in subject or "assist" in subject:
            # Request for help
            return "I'll try to help. What do you need?"

        return "Request received"

    async def _handle_notification(self, message: Message) -> None:
        """Handle a notification message."""
        # Log to blackboard
        self.blackboard.add_entry(
            self.blackboard.entries[-1].__class__(
                entry_type=self.blackboard.entries[-1].entry_type.PROGRESS
                if self.blackboard.entries else "progress",
                agent_id=self.agent.id,
                project=self.project.name,
                title=f"Received: {message.subject}",
                content=message.content,
            )
        )

    async def _handle_handoff(self, message: Message) -> None:
        """Handle a task handoff from another agent."""
        task_context = message.payload.get("task_context", {})

        # Post to blackboard that we received the handoff
        self.blackboard.post_discovery(
            agent_id=self.agent.id,
            title=f"Received handoff from {message.from_agent_id}",
            content=f"Context: {task_context}",
        )

    async def _handle_outgoing_message(self, message_data: dict) -> None:
        """Handle outgoing messages from the base agent."""
        to_agent_type = message_data.get("to", "")
        content = message_data.get("message", "")

        await self.message_bus.notify(
            from_agent_id=self.agent.id,
            to_agent_type=to_agent_type,
            subject="Agent Communication",
            content=content,
            payload=message_data,
        )

    async def request_file_lock(self, file_path: str) -> bool:
        """Request a file lock through the coordinator."""
        return await self.coordinator.request_file_lock(self.agent.id, file_path)

    async def release_file_lock(self, file_path: str) -> bool:
        """Release a file lock through the coordinator."""
        return await self.coordinator.release_file_lock(self.agent.id, file_path)

    async def send_to_agent(
        self,
        to_agent_type: str,
        message: str,
        expect_response: bool = False,
    ) -> Optional[str]:
        """Send a message to another agent."""
        if expect_response:
            response = await self.message_bus.request(
                from_agent_id=self.agent.id,
                to_agent_id=to_agent_type,  # Will be routed by type
                subject="Agent Request",
                content=message,
            )
            return response.content if response else None
        else:
            await self.message_bus.notify(
                from_agent_id=self.agent.id,
                to_agent_type=to_agent_type,
                subject="Agent Message",
                content=message,
            )
            return None

    async def broadcast(self, message: str) -> None:
        """Broadcast a message to all agents."""
        await self.message_bus.broadcast(
            from_agent_id=self.agent.id,
            subject="Broadcast",
            content=message,
        )

    async def handoff_to(
        self,
        to_agent_id: str,
        context: dict,
        reason: str,
    ) -> None:
        """Hand off current work to another agent."""
        await self.message_bus.handoff(
            from_agent_id=self.agent.id,
            to_agent_id=to_agent_id,
            task_context=context,
            reason=reason,
        )

    def shutdown(self) -> None:
        """Shutdown the runner."""
        self.running = False
        self.message_bus.unregister_agent(self.agent.id)
