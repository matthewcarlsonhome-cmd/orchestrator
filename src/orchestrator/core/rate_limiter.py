"""
Rate Limiter - Token bucket scheduler for API rate limit awareness.

Instead of firing all agents in parallel and hitting rate limits,
this scheduler:
- Tracks tokens per minute (input + output)
- Tracks requests per minute
- Queues work when approaching limits
- Runs micro-batches of 2-4 active agents
- Blocks agents until they have required context

Based on Anthropic rate limits (varies by tier):
- Tier 1: 40k tokens/min, 50 requests/min
- Tier 2: 80k tokens/min, 1000 requests/min
- Tier 3: 160k tokens/min, 2000 requests/min
- Tier 4: 400k tokens/min, 4000 requests/min
"""

import asyncio
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Callable, Awaitable
from threading import Lock


class AgentState(str, Enum):
    IDLE = "idle"
    WAITING_CONTEXT = "waiting_context"  # Blocked until context ready
    WAITING_RATE = "waiting_rate"  # Blocked by rate limit
    ACTIVE = "active"
    COMPLETED = "completed"


@dataclass
class TokenBucket:
    """
    Token bucket for rate limiting.
    Refills over time up to capacity.
    """
    capacity: int  # Max tokens
    tokens: float  # Current tokens
    refill_rate: float  # Tokens per second
    last_refill: float = field(default_factory=time.time)

    def consume(self, amount: int) -> bool:
        """Try to consume tokens. Returns True if successful."""
        self._refill()
        if self.tokens >= amount:
            self.tokens -= amount
            return True
        return False

    def wait_time(self, amount: int) -> float:
        """How long to wait for amount tokens to be available."""
        self._refill()
        if self.tokens >= amount:
            return 0
        needed = amount - self.tokens
        return needed / self.refill_rate

    def _refill(self):
        """Refill tokens based on time passed."""
        now = time.time()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now


@dataclass
class RequestWindow:
    """Sliding window for request counting."""
    window_seconds: int = 60
    max_requests: int = 50
    requests: deque = field(default_factory=deque)
    _lock: Lock = field(default_factory=Lock)

    def can_request(self) -> bool:
        """Check if we can make another request."""
        self._prune()
        return len(self.requests) < self.max_requests

    def record_request(self):
        """Record a request."""
        with self._lock:
            self.requests.append(time.time())

    def wait_time(self) -> float:
        """How long to wait before next request is allowed."""
        self._prune()
        if len(self.requests) < self.max_requests:
            return 0
        oldest = self.requests[0]
        return max(0, self.window_seconds - (time.time() - oldest))

    def _prune(self):
        """Remove requests outside the window."""
        cutoff = time.time() - self.window_seconds
        with self._lock:
            while self.requests and self.requests[0] < cutoff:
                self.requests.popleft()


@dataclass
class QueuedWork:
    """A piece of work waiting to be executed."""
    id: str
    agent_id: str
    estimated_tokens: int
    priority: int = 0
    callback: Optional[Callable[[], Awaitable]] = None
    created_at: float = field(default_factory=time.time)


class RateLimitScheduler:
    """
    Rate-limit aware scheduler for multi-agent orchestration.

    Key behaviors:
    - Only 2-4 agents active at once (micro-batches)
    - Queue work when approaching rate limits
    - Prioritize agents that have context ready
    - Track token usage across all agents
    """

    def __init__(
        self,
        max_active_agents: int = 3,
        tokens_per_minute: int = 80000,  # Tier 2 default
        requests_per_minute: int = 1000,
    ):
        self.max_active_agents = max_active_agents

        # Rate limit buckets
        self.input_tokens = TokenBucket(
            capacity=tokens_per_minute,
            tokens=tokens_per_minute,
            refill_rate=tokens_per_minute / 60,
        )
        self.output_tokens = TokenBucket(
            capacity=tokens_per_minute // 2,  # Output usually lower
            tokens=tokens_per_minute // 2,
            refill_rate=tokens_per_minute / 120,
        )
        self.requests = RequestWindow(
            window_seconds=60,
            max_requests=requests_per_minute,
        )

        # Agent tracking
        self.agent_states: dict[str, AgentState] = {}
        self.active_agents: set[str] = set()

        # Work queue
        self.work_queue: list[QueuedWork] = []
        self._queue_lock = Lock()

        # Stats
        self.total_tokens_used = 0
        self.total_requests = 0
        self.rate_limit_waits = 0

    async def acquire(self, agent_id: str, estimated_input_tokens: int = 2000) -> bool:
        """
        Try to acquire a slot for an agent to make an API call.
        Returns True if agent can proceed, False if it should wait.
        """
        # Check if we're at capacity for active agents
        if len(self.active_agents) >= self.max_active_agents:
            if agent_id not in self.active_agents:
                self.agent_states[agent_id] = AgentState.WAITING_RATE
                return False

        # Check token bucket
        if not self.input_tokens.consume(estimated_input_tokens):
            wait_time = self.input_tokens.wait_time(estimated_input_tokens)
            if wait_time > 0:
                self.rate_limit_waits += 1
                self.agent_states[agent_id] = AgentState.WAITING_RATE
                await asyncio.sleep(min(wait_time, 5))  # Wait up to 5s
                return await self.acquire(agent_id, estimated_input_tokens)

        # Check request rate
        if not self.requests.can_request():
            wait_time = self.requests.wait_time()
            if wait_time > 0:
                self.rate_limit_waits += 1
                self.agent_states[agent_id] = AgentState.WAITING_RATE
                await asyncio.sleep(min(wait_time, 5))
                return await self.acquire(agent_id, estimated_input_tokens)

        # Success - record and mark active
        self.requests.record_request()
        self.active_agents.add(agent_id)
        self.agent_states[agent_id] = AgentState.ACTIVE
        self.total_requests += 1

        return True

    def release(self, agent_id: str, tokens_used: int = 0):
        """Release an agent's slot after API call completes."""
        self.active_agents.discard(agent_id)
        self.total_tokens_used += tokens_used

        # Consume output tokens from the bucket for accurate tracking
        if tokens_used > 0:
            self.output_tokens.consume(tokens_used)

    def queue_work(self, work: QueuedWork):
        """Add work to the queue."""
        with self._queue_lock:
            self.work_queue.append(work)
            self.work_queue.sort(key=lambda w: (-w.priority, w.created_at))

    def get_next_work(self) -> Optional[QueuedWork]:
        """Get the next piece of work from the queue."""
        with self._queue_lock:
            if self.work_queue:
                return self.work_queue.pop(0)
        return None

    def set_agent_waiting_context(self, agent_id: str):
        """Mark an agent as waiting for context (file reads, etc.)."""
        self.agent_states[agent_id] = AgentState.WAITING_CONTEXT

    def get_available_slots(self) -> int:
        """How many more agents can be active."""
        return max(0, self.max_active_agents - len(self.active_agents))

    def get_stats(self) -> dict:
        """Get scheduler statistics."""
        return {
            "active_agents": len(self.active_agents),
            "max_active": self.max_active_agents,
            "queued_work": len(self.work_queue),
            "total_tokens": self.total_tokens_used,
            "total_requests": self.total_requests,
            "rate_limit_waits": self.rate_limit_waits,
            "input_tokens_available": int(self.input_tokens.tokens),
            "requests_in_window": len(self.requests.requests),
            "agent_states": {
                agent_id: state.value
                for agent_id, state in self.agent_states.items()
            },
        }

    def estimate_wait_time(self, tokens_needed: int) -> float:
        """Estimate how long until tokens are available."""
        return max(
            self.input_tokens.wait_time(tokens_needed),
            self.requests.wait_time(),
        )

    async def wait_for_slot(self, agent_id: str, timeout: float = 30) -> bool:
        """
        Wait until a slot is available for this agent.
        Returns True if slot acquired, False on timeout.
        """
        start = time.time()
        while time.time() - start < timeout:
            if len(self.active_agents) < self.max_active_agents:
                self.active_agents.add(agent_id)
                self.agent_states[agent_id] = AgentState.ACTIVE
                return True
            await asyncio.sleep(0.5)
        return False


class AdaptiveScheduler(RateLimitScheduler):
    """
    Adaptive scheduler that adjusts based on actual rate limit responses.
    If we get 429s, it backs off. If we're smooth, it speeds up.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.consecutive_429s = 0
        self.consecutive_successes = 0
        self.backoff_factor = 1.0

    def record_success(self, agent_id: str, tokens_used: int):
        """Record a successful API call."""
        self.release(agent_id, tokens_used)
        self.consecutive_successes += 1
        self.consecutive_429s = 0

        # Speed up if we've had many successes
        if self.consecutive_successes > 10:
            self.backoff_factor = max(0.5, self.backoff_factor * 0.9)
            self.consecutive_successes = 0

    def record_rate_limit(self, agent_id: str):
        """Record a 429 rate limit response."""
        self.consecutive_429s += 1
        self.consecutive_successes = 0

        # Back off exponentially
        self.backoff_factor = min(4.0, self.backoff_factor * 1.5)

        # Reduce active capacity temporarily
        if self.consecutive_429s > 2:
            self.max_active_agents = max(1, self.max_active_agents - 1)

    async def acquire_adaptive(self, agent_id: str, estimated_tokens: int = 2000) -> bool:
        """Acquire with adaptive backoff."""
        # Apply backoff factor to wait times
        if self.backoff_factor > 1.0:
            await asyncio.sleep(self.backoff_factor - 1.0)

        return await self.acquire(agent_id, estimated_tokens)
