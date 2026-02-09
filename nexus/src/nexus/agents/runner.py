"""
Agent Runner - Executes agent prompts with context.
"""

import asyncio
from datetime import datetime
from uuid import uuid4

from nexus.config import config
from nexus.models.agent import AgentConfig, AgentRun
from nexus.models.entry import EntryCreate, EntryType, EntrySource
from nexus.core.nexus import get_nexus


class AgentRunner:
    """
    Runs individual agents.

    Usage:
        runner = AgentRunner()
        run = await runner.run(agent_config)
        print(run.result)
    """

    def __init__(self):
        self._client = None

    def _get_client(self):
        """Get the LLM client."""
        if self._client is None:
            if config.llm_provider == "claude":
                from anthropic import Anthropic
                self._client = Anthropic(api_key=config.anthropic_api_key)
            else:
                from openai import OpenAI
                self._client = OpenAI(api_key=config.openai_api_key)
        return self._client

    async def run(self, agent: AgentConfig) -> AgentRun:
        """
        Execute an agent.

        1. Gather context based on agent's collection/filters
        2. Run the prompt with LLM
        3. Handle output (notification, entry, etc.)
        """
        run = AgentRun(
            id=str(uuid4()),
            agent_id=agent.id,
            agent_name=agent.name,
            trigger_reason=f"{agent.trigger.type}: {agent.trigger.cron or agent.trigger.event}",
        )

        try:
            nexus = get_nexus()

            # 1. Gather context
            context_entries = []
            if agent.collection_id:
                from nexus.storage import get_metadata_store
                store = get_metadata_store()
                context_entries = await store.search_entries(
                    collection_id=agent.collection_id,
                    limit=20,
                )
            else:
                context_entries = await nexus.recent(limit=20)

            run.context_entries = len(context_entries)

            # 2. Build prompt with context
            context_text = "\n\n---\n\n".join([
                f"[{e.type.value}] {e.created_at.strftime('%Y-%m-%d %H:%M')}\n{e.content[:500]}"
                for e in context_entries
            ])

            full_prompt = f"""You are a personal AI assistant running an automated task.

Current date/time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}

Recent entries from the user's knowledge base:
{context_text}

---

Task: {agent.prompt}

Provide a helpful, personalized response based on the user's actual data above."""

            # 3. Run LLM
            result, tokens = await self._generate(full_prompt)

            run.result = result
            run.tokens_used = tokens
            run.model_used = config.claude_model if config.llm_provider == "claude" else config.openai_model

            # 4. Handle output
            if agent.output_type == "entry":
                # Save result as a new entry
                entry = await nexus.add(
                    content=result,
                    title=f"{agent.name} - {datetime.utcnow().strftime('%Y-%m-%d')}",
                    tags=["agent", agent.name.lower().replace(" ", "_")],
                    entry_type=EntryType.THOUGHT,
                )
                run.entries_created = [entry.id]

            elif agent.output_type == "notification":
                # TODO: Implement notification system
                run.notifications_sent = 1

            run.success = True
            run.completed_at = datetime.utcnow()

        except Exception as e:
            run.error = str(e)
            run.success = False
            run.completed_at = datetime.utcnow()

        return run

    async def _generate(self, prompt: str) -> tuple[str, int]:
        """Generate response from LLM."""
        client = self._get_client()

        if config.llm_provider == "claude":
            response = await asyncio.to_thread(
                client.messages.create,
                model=config.claude_model,
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}],
            )
            result = response.content[0].text
            tokens = response.usage.input_tokens + response.usage.output_tokens
        else:
            response = await asyncio.to_thread(
                client.chat.completions.create,
                model=config.openai_model,
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}],
            )
            result = response.choices[0].message.content
            tokens = response.usage.total_tokens

        return result, tokens
