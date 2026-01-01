"""Message bus for direct agent-to-agent communication."""

import asyncio
from datetime import datetime
from enum import Enum
from typing import Optional, Callable, Awaitable, Any
from uuid import uuid4
from collections import defaultdict

from pydantic import BaseModel, Field


class MessagePriority(int, Enum):
    """Priority levels for messages."""
    URGENT = 1
    HIGH = 2
    NORMAL = 3
    LOW = 4


class MessageType(str, Enum):
    """Types of inter-agent messages."""
    REQUEST = "request"          # Request information or action
    RESPONSE = "response"        # Response to a request
    NOTIFICATION = "notification"  # One-way notification
    BROADCAST = "broadcast"      # Message to all agents
    HANDOFF = "handoff"          # Task handoff between agents
    SYNC = "sync"                # Synchronization message


class Message(BaseModel):
    """A message between agents."""
    id: str = Field(default_factory=lambda: uuid4().hex[:12])
    message_type: MessageType
    priority: MessagePriority = Field(default=MessagePriority.NORMAL)

    from_agent_id: str
    to_agent_id: Optional[str] = None  # None for broadcasts
    to_agent_type: Optional[str] = None  # For routing by type

    subject: str
    content: str
    payload: dict = Field(default_factory=dict)

    # For request/response tracking
    correlation_id: Optional[str] = None  # Links response to request
    expects_response: bool = False
    response_timeout: int = 60  # seconds

    # Metadata
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    delivered: bool = False
    read: bool = False


class MessageBus:
    """
    Central message bus for agent communication.

    Features:
    - Direct agent-to-agent messaging
    - Broadcast to all agents
    - Message routing by agent type
    - Request/response pattern with correlation
    - Priority queuing
    - Message persistence for recovery
    """

    def __init__(self):
        # Message queues per agent
        self.queues: dict[str, asyncio.PriorityQueue] = {}

        # Pending responses (correlation_id -> Future)
        self.pending_responses: dict[str, asyncio.Future] = {}

        # Message handlers by agent
        self.handlers: dict[str, Callable[[Message], Awaitable[None]]] = {}

        # Agent type registry (agent_id -> agent_type)
        self.agent_types: dict[str, str] = {}

        # Message history for debugging/recovery
        self.message_history: list[Message] = []
        self.max_history = 1000

        # Subscribers for broadcasts
        self.broadcast_subscribers: set[str] = set()

        # Running flag
        self.running = False

    def register_agent(
        self,
        agent_id: str,
        agent_type: str,
        handler: Optional[Callable[[Message], Awaitable[None]]] = None,
    ) -> None:
        """Register an agent with the message bus."""
        self.queues[agent_id] = asyncio.PriorityQueue()
        self.agent_types[agent_id] = agent_type
        self.broadcast_subscribers.add(agent_id)

        if handler:
            self.handlers[agent_id] = handler

    def unregister_agent(self, agent_id: str) -> None:
        """Unregister an agent from the message bus."""
        if agent_id in self.queues:
            del self.queues[agent_id]
        if agent_id in self.agent_types:
            del self.agent_types[agent_id]
        if agent_id in self.handlers:
            del self.handlers[agent_id]
        self.broadcast_subscribers.discard(agent_id)

    def get_agents_by_type(self, agent_type: str) -> list[str]:
        """Get all agent IDs of a specific type."""
        return [
            aid for aid, atype in self.agent_types.items()
            if atype == agent_type
        ]

    async def send(self, message: Message) -> Optional[str]:
        """
        Send a message. Returns message ID on success.

        For broadcasts, sends to all registered agents.
        For type-targeted messages, sends to first available agent of that type.
        """
        # Store in history
        self.message_history.append(message)
        if len(self.message_history) > self.max_history:
            self.message_history = self.message_history[-self.max_history:]

        if message.message_type == MessageType.BROADCAST:
            # Send to all subscribers
            for agent_id in self.broadcast_subscribers:
                if agent_id != message.from_agent_id:
                    await self._enqueue(agent_id, message)
            return message.id

        elif message.to_agent_id:
            # Direct message
            await self._enqueue(message.to_agent_id, message)
            return message.id

        elif message.to_agent_type:
            # Route to agent by type
            agents = self.get_agents_by_type(message.to_agent_type)
            if agents:
                # Send to first available
                await self._enqueue(agents[0], message)
                return message.id

        return None

    async def _enqueue(self, agent_id: str, message: Message) -> None:
        """Enqueue a message for an agent."""
        if agent_id not in self.queues:
            return

        # Priority queue item: (priority, timestamp, message)
        item = (message.priority.value, message.timestamp.timestamp(), message)
        await self.queues[agent_id].put(item)
        message.delivered = True

        # Notify handler if registered
        if agent_id in self.handlers:
            try:
                await self.handlers[agent_id](message)
            except Exception:
                pass  # Don't let handler errors stop message delivery

    async def receive(
        self,
        agent_id: str,
        timeout: Optional[float] = None,
    ) -> Optional[Message]:
        """Receive the next message for an agent."""
        if agent_id not in self.queues:
            return None

        try:
            if timeout:
                item = await asyncio.wait_for(
                    self.queues[agent_id].get(),
                    timeout=timeout,
                )
            else:
                item = await self.queues[agent_id].get()

            message = item[2]  # Extract message from priority tuple
            message.read = True
            return message

        except asyncio.TimeoutError:
            return None

    def peek(self, agent_id: str) -> Optional[Message]:
        """Peek at the next message without removing it."""
        if agent_id not in self.queues or self.queues[agent_id].empty():
            return None

        # This is a bit hacky but works for peeking
        queue = self.queues[agent_id]
        if queue._queue:  # Access internal queue
            return queue._queue[0][2]
        return None

    def get_pending_count(self, agent_id: str) -> int:
        """Get count of pending messages for an agent."""
        if agent_id not in self.queues:
            return 0
        return self.queues[agent_id].qsize()

    async def request(
        self,
        from_agent_id: str,
        to_agent_id: str,
        subject: str,
        content: str,
        payload: dict = None,
        timeout: int = 60,
    ) -> Optional[Message]:
        """
        Send a request and wait for response.

        Returns the response message or None on timeout.
        """
        correlation_id = uuid4().hex[:12]

        message = Message(
            message_type=MessageType.REQUEST,
            from_agent_id=from_agent_id,
            to_agent_id=to_agent_id,
            subject=subject,
            content=content,
            payload=payload or {},
            correlation_id=correlation_id,
            expects_response=True,
            response_timeout=timeout,
        )

        # Create future for response
        future = asyncio.get_event_loop().create_future()
        self.pending_responses[correlation_id] = future

        try:
            await self.send(message)
            response = await asyncio.wait_for(future, timeout=timeout)
            return response
        except asyncio.TimeoutError:
            return None
        finally:
            self.pending_responses.pop(correlation_id, None)

    async def respond(
        self,
        original_message: Message,
        content: str,
        payload: dict = None,
    ) -> Optional[str]:
        """Send a response to a request message."""
        if not original_message.correlation_id:
            return None

        response = Message(
            message_type=MessageType.RESPONSE,
            from_agent_id=original_message.to_agent_id or "",
            to_agent_id=original_message.from_agent_id,
            subject=f"Re: {original_message.subject}",
            content=content,
            payload=payload or {},
            correlation_id=original_message.correlation_id,
        )

        # Complete the pending future if exists
        if original_message.correlation_id in self.pending_responses:
            future = self.pending_responses[original_message.correlation_id]
            if not future.done():
                future.set_result(response)

        return await self.send(response)

    async def broadcast(
        self,
        from_agent_id: str,
        subject: str,
        content: str,
        payload: dict = None,
        priority: MessagePriority = MessagePriority.NORMAL,
    ) -> str:
        """Broadcast a message to all agents."""
        message = Message(
            message_type=MessageType.BROADCAST,
            priority=priority,
            from_agent_id=from_agent_id,
            subject=subject,
            content=content,
            payload=payload or {},
        )
        return await self.send(message)

    async def notify(
        self,
        from_agent_id: str,
        to_agent_type: str,
        subject: str,
        content: str,
        payload: dict = None,
    ) -> Optional[str]:
        """Send a notification to agents of a specific type."""
        message = Message(
            message_type=MessageType.NOTIFICATION,
            from_agent_id=from_agent_id,
            to_agent_type=to_agent_type,
            subject=subject,
            content=content,
            payload=payload or {},
        )
        return await self.send(message)

    async def handoff(
        self,
        from_agent_id: str,
        to_agent_id: str,
        task_context: dict,
        reason: str,
    ) -> Optional[str]:
        """Hand off a task from one agent to another."""
        message = Message(
            message_type=MessageType.HANDOFF,
            priority=MessagePriority.HIGH,
            from_agent_id=from_agent_id,
            to_agent_id=to_agent_id,
            subject="Task Handoff",
            content=reason,
            payload={"task_context": task_context},
        )
        return await self.send(message)

    def get_message_history(
        self,
        agent_id: Optional[str] = None,
        message_type: Optional[MessageType] = None,
        limit: int = 100,
    ) -> list[Message]:
        """Get message history with optional filters."""
        messages = self.message_history

        if agent_id:
            messages = [
                m for m in messages
                if m.from_agent_id == agent_id or m.to_agent_id == agent_id
            ]

        if message_type:
            messages = [m for m in messages if m.message_type == message_type]

        return messages[-limit:]

    def get_stats(self) -> dict:
        """Get message bus statistics."""
        total_pending = sum(q.qsize() for q in self.queues.values())
        total_messages = len(self.message_history)

        type_counts = defaultdict(int)
        for msg in self.message_history:
            type_counts[msg.message_type.value] += 1

        return {
            "registered_agents": len(self.queues),
            "total_pending": total_pending,
            "total_messages": total_messages,
            "pending_responses": len(self.pending_responses),
            "by_type": dict(type_counts),
        }
