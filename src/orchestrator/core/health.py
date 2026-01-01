"""Health monitoring for agents and orchestrator."""

import asyncio
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, Callable, Awaitable
from collections import defaultdict

from pydantic import BaseModel, Field

from orchestrator.models.agent import Agent, AgentStatus
from orchestrator.agents.pool import AgentPool


class HealthStatus(str, Enum):
    """Health status levels."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    CRITICAL = "critical"


class AgentHealth(BaseModel):
    """Health status for an agent."""
    agent_id: str
    agent_type: str
    status: HealthStatus
    last_heartbeat: datetime
    seconds_since_heartbeat: float
    current_task: Optional[str] = None
    tasks_completed: int = 0
    errors_count: int = 0
    error_rate: float = 0.0
    avg_task_duration: float = 0.0
    issues: list[str] = Field(default_factory=list)


class SystemHealth(BaseModel):
    """Overall system health status."""
    status: HealthStatus
    timestamp: datetime
    uptime_seconds: float
    agents_healthy: int
    agents_degraded: int
    agents_unhealthy: int
    tasks_in_progress: int
    tasks_queued: int
    memory_usage_mb: float = 0.0
    issues: list[str] = Field(default_factory=list)


class HealthMonitor:
    """
    Monitors health of agents and overall system.

    Features:
    - Agent heartbeat monitoring
    - Error rate tracking
    - Resource usage monitoring
    - Automatic unhealthy agent detection
    - Health status callbacks
    """

    def __init__(
        self,
        agent_pool: AgentPool,
        heartbeat_timeout: int = 120,  # seconds
        error_rate_threshold: float = 0.3,  # 30% error rate = degraded
        on_agent_unhealthy: Optional[Callable[[Agent], Awaitable[None]]] = None,
        on_system_degraded: Optional[Callable[[SystemHealth], Awaitable[None]]] = None,
    ):
        self.agent_pool = agent_pool
        self.heartbeat_timeout = heartbeat_timeout
        self.error_rate_threshold = error_rate_threshold
        self.on_agent_unhealthy = on_agent_unhealthy
        self.on_system_degraded = on_system_degraded

        # Tracking
        self.start_time = datetime.utcnow()
        self.running = False
        self._monitor_task: Optional[asyncio.Task] = None

        # History
        self.health_history: list[SystemHealth] = []
        self.max_history = 100

    async def start(self, check_interval: int = 30) -> None:
        """Start the health monitor."""
        self.running = True
        self._monitor_task = asyncio.create_task(
            self._monitor_loop(check_interval)
        )

    async def stop(self) -> None:
        """Stop the health monitor."""
        self.running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass

    async def _monitor_loop(self, interval: int) -> None:
        """Main monitoring loop."""
        while self.running:
            try:
                health = await self.check_system_health()
                self.health_history.append(health)
                if len(self.health_history) > self.max_history:
                    self.health_history = self.health_history[-self.max_history:]

                # Check for degraded system
                if health.status in (HealthStatus.DEGRADED, HealthStatus.UNHEALTHY):
                    if self.on_system_degraded:
                        await self.on_system_degraded(health)

                # Handle unhealthy agents
                for agent_id, agent in list(self.agent_pool.agents.items()):
                    agent_health = await self.check_agent_health(agent_id)
                    if agent_health.status == HealthStatus.UNHEALTHY:
                        if self.on_agent_unhealthy:
                            await self.on_agent_unhealthy(agent)

            except Exception:
                pass  # Don't let monitor errors stop the monitor

            await asyncio.sleep(interval)

    async def check_agent_health(self, agent_id: str) -> AgentHealth:
        """Check health of a specific agent."""
        agent = self.agent_pool.get_agent(agent_id)
        if not agent:
            return AgentHealth(
                agent_id=agent_id,
                agent_type="unknown",
                status=HealthStatus.UNHEALTHY,
                last_heartbeat=datetime.utcnow(),
                seconds_since_heartbeat=0,
                issues=["Agent not found in pool"],
            )

        now = datetime.utcnow()
        seconds_since_heartbeat = (now - agent.last_heartbeat).total_seconds()

        # Get stats from pool
        stats = self.agent_pool.agent_stats.get(agent_id, {})
        tasks_completed = stats.get("tasks_completed", 0)
        tasks_failed = stats.get("tasks_failed", 0)
        total_tasks = tasks_completed + tasks_failed
        error_rate = tasks_failed / total_tasks if total_tasks > 0 else 0.0

        issues = []
        status = HealthStatus.HEALTHY

        # Check heartbeat
        if seconds_since_heartbeat > self.heartbeat_timeout:
            status = HealthStatus.UNHEALTHY
            issues.append(f"No heartbeat for {seconds_since_heartbeat:.0f}s")
        elif seconds_since_heartbeat > self.heartbeat_timeout / 2:
            status = HealthStatus.DEGRADED
            issues.append(f"Heartbeat delayed: {seconds_since_heartbeat:.0f}s")

        # Check error rate
        if error_rate > self.error_rate_threshold:
            if status != HealthStatus.UNHEALTHY:
                status = HealthStatus.DEGRADED
            issues.append(f"High error rate: {error_rate:.1%}")

        # Check if stuck
        if agent.status == AgentStatus.WORKING and agent.current_task_id:
            # If working for too long, might be stuck
            # This is a simple heuristic
            pass

        return AgentHealth(
            agent_id=agent_id,
            agent_type=agent.agent_type.value,
            status=status,
            last_heartbeat=agent.last_heartbeat,
            seconds_since_heartbeat=seconds_since_heartbeat,
            current_task=agent.current_task_id,
            tasks_completed=tasks_completed,
            errors_count=tasks_failed,
            error_rate=error_rate,
            avg_task_duration=stats.get("avg_task_duration", 0.0),
            issues=issues,
        )

    async def check_system_health(self) -> SystemHealth:
        """Check overall system health."""
        now = datetime.utcnow()
        uptime = (now - self.start_time).total_seconds()

        # Check all agents
        healthy = 0
        degraded = 0
        unhealthy = 0
        issues = []

        for agent_id in self.agent_pool.agents:
            agent_health = await self.check_agent_health(agent_id)
            if agent_health.status == HealthStatus.HEALTHY:
                healthy += 1
            elif agent_health.status == HealthStatus.DEGRADED:
                degraded += 1
            else:
                unhealthy += 1
                issues.extend(
                    f"Agent {agent_id}: {issue}"
                    for issue in agent_health.issues
                )

        # Get task counts
        pool_status = self.agent_pool.get_pool_status()
        working = pool_status["by_status"].get("working", 0)

        # Determine overall status
        total_agents = healthy + degraded + unhealthy
        if total_agents == 0:
            status = HealthStatus.HEALTHY  # No agents yet
        elif unhealthy > total_agents / 2:
            status = HealthStatus.CRITICAL
            issues.append("Majority of agents unhealthy")
        elif unhealthy > 0 or degraded > total_agents / 3:
            status = HealthStatus.DEGRADED
        else:
            status = HealthStatus.HEALTHY

        # Try to get memory usage
        memory_mb = 0.0
        try:
            import psutil
            process = psutil.Process()
            memory_mb = process.memory_info().rss / (1024 * 1024)
        except ImportError:
            pass

        return SystemHealth(
            status=status,
            timestamp=now,
            uptime_seconds=uptime,
            agents_healthy=healthy,
            agents_degraded=degraded,
            agents_unhealthy=unhealthy,
            tasks_in_progress=working,
            tasks_queued=0,  # Would need scheduler access
            memory_usage_mb=memory_mb,
            issues=issues,
        )

    def get_health_summary(self) -> dict:
        """Get a summary of current health."""
        if not self.health_history:
            return {"status": "unknown", "message": "No health checks performed yet"}

        latest = self.health_history[-1]

        return {
            "status": latest.status.value,
            "timestamp": latest.timestamp.isoformat(),
            "uptime_seconds": latest.uptime_seconds,
            "uptime_formatted": str(timedelta(seconds=int(latest.uptime_seconds))),
            "agents": {
                "healthy": latest.agents_healthy,
                "degraded": latest.agents_degraded,
                "unhealthy": latest.agents_unhealthy,
            },
            "tasks": {
                "in_progress": latest.tasks_in_progress,
                "queued": latest.tasks_queued,
            },
            "memory_mb": round(latest.memory_usage_mb, 1),
            "issues": latest.issues,
        }

    def get_health_trend(self, hours: int = 1) -> dict:
        """Get health trend over time."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        recent = [h for h in self.health_history if h.timestamp > cutoff]

        if not recent:
            return {"trend": "unknown", "data_points": 0}

        status_counts = defaultdict(int)
        for h in recent:
            status_counts[h.status.value] += 1

        # Determine trend
        if status_counts.get("critical", 0) > len(recent) / 4:
            trend = "worsening"
        elif status_counts.get("healthy", 0) > len(recent) * 0.8:
            trend = "stable"
        elif status_counts.get("healthy", 0) > status_counts.get("degraded", 0):
            trend = "improving"
        else:
            trend = "fluctuating"

        return {
            "trend": trend,
            "data_points": len(recent),
            "status_distribution": dict(status_counts),
            "period_hours": hours,
        }
