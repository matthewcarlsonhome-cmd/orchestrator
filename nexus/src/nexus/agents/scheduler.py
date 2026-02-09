"""
Agent Scheduler - Manages when agents run.

Handles:
- Cron-based scheduling
- Event-based triggers
- Agent execution queue
"""

import asyncio
from datetime import datetime
from typing import Optional, Callable, Awaitable
from threading import Thread
import time

from nexus.config import config
from nexus.models.agent import (
    AgentConfig, AgentRun, AgentTrigger,
    DAILY_BRIEFING_AGENT, WEEKLY_REVIEW_AGENT,
    FOLLOW_UP_REMINDER_AGENT, PATTERN_DETECTOR_AGENT,
)


class AgentScheduler:
    """
    Scheduler for running agents.

    Usage:
        scheduler = AgentScheduler()

        # Add built-in agents
        scheduler.add_agent(DAILY_BRIEFING_AGENT)

        # Start the scheduler
        await scheduler.start()

        # Manually trigger an agent
        await scheduler.run_agent("daily_briefing")
    """

    def __init__(self):
        self.agents: dict[str, AgentConfig] = {}
        self.running = False
        self._task: Optional[asyncio.Task] = None
        self._on_run: Optional[Callable[[AgentRun], Awaitable[None]]] = None

    def add_agent(self, agent: AgentConfig):
        """Add an agent to the scheduler."""
        self.agents[agent.id] = agent

    def remove_agent(self, agent_id: str):
        """Remove an agent."""
        self.agents.pop(agent_id, None)

    def set_callback(self, callback: Callable[[AgentRun], Awaitable[None]]):
        """Set callback for when agents complete."""
        self._on_run = callback

    async def start(self):
        """Start the scheduler."""
        if self.running:
            return

        self.running = True

        # Add default agents if none configured
        if not self.agents:
            self.add_agent(DAILY_BRIEFING_AGENT)
            self.add_agent(WEEKLY_REVIEW_AGENT)
            self.add_agent(FOLLOW_UP_REMINDER_AGENT)
            self.add_agent(PATTERN_DETECTOR_AGENT)

        self._task = asyncio.create_task(self._run_loop())

    async def stop(self):
        """Stop the scheduler."""
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _run_loop(self):
        """Main scheduler loop."""
        while self.running:
            try:
                now = datetime.utcnow()

                for agent_id, agent in self.agents.items():
                    if not agent.enabled:
                        continue

                    if agent.trigger.type == "schedule" and agent.trigger.cron:
                        if self._should_run(agent.trigger.cron, now, agent.last_run):
                            await self.run_agent(agent_id)

                # Sleep until next check
                await asyncio.sleep(config.agent_check_interval_minutes * 60)

            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Scheduler error: {e}")
                await asyncio.sleep(60)

    def _should_run(
        self,
        cron: str,
        now: datetime,
        last_run: Optional[datetime]
    ) -> bool:
        """Check if a cron schedule should run now."""
        try:
            from croniter import croniter
            cron_iter = croniter(cron, last_run or now)
            next_run = cron_iter.get_next(datetime)
            return now >= next_run
        except ImportError:
            # Simple fallback without croniter
            # Just check if enough time has passed
            if not last_run:
                return True
            # Assume daily for simplicity
            hours_passed = (now - last_run).total_seconds() / 3600
            return hours_passed >= 20  # Run once per day-ish
        except Exception:
            return False

    async def run_agent(self, agent_id: str) -> Optional[AgentRun]:
        """Manually run an agent."""
        agent = self.agents.get(agent_id)
        if not agent:
            return None

        from nexus.agents.runner import AgentRunner

        runner = AgentRunner()
        run = await runner.run(agent)

        # Update last run time
        agent.last_run = datetime.utcnow()
        agent.run_count += 1

        # Callback
        if self._on_run:
            await self._on_run(run)

        return run

    async def trigger_event(self, event: str, context: dict = None):
        """Trigger all agents listening for an event."""
        for agent_id, agent in self.agents.items():
            if not agent.enabled:
                continue

            if agent.trigger.type == "event" and agent.trigger.event == event:
                # Check filter if present
                if agent.trigger.filter:
                    # Simple tag filter
                    if context and "tags" in context:
                        filter_tags = agent.trigger.filter.replace("tags:", "").split()
                        if not any(t in context["tags"] for t in filter_tags):
                            continue

                await self.run_agent(agent_id)

    def get_status(self) -> dict:
        """Get scheduler status."""
        return {
            "running": self.running,
            "agents": [
                {
                    "id": a.id,
                    "name": a.name,
                    "enabled": a.enabled,
                    "trigger": a.trigger.type,
                    "last_run": a.last_run.isoformat() if a.last_run else None,
                    "run_count": a.run_count,
                }
                for a in self.agents.values()
            ]
        }
