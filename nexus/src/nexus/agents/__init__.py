"""
Nexus Agents - Proactive intelligence.

Agents run automatically based on schedules or events to:
- Generate daily briefings
- Detect patterns in your data
- Send reminders and follow-ups
- Research topics you're interested in
"""

from nexus.agents.scheduler import AgentScheduler
from nexus.agents.runner import AgentRunner

__all__ = ["AgentScheduler", "AgentRunner"]
