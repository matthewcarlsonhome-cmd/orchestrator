"""
Response Service - Generate intelligent responses using LLM.

Handles:
- Context-aware question answering
- Personalized response generation
- Source citation
- Follow-up suggestions
"""

import time
import asyncio
from datetime import datetime
from typing import Optional

from nexus.config import config
from nexus.models.entry import Entry, EntryType
from nexus.models.query import AskQuery, AskResponse, SourceCitation
from nexus.core.retrieval import RetrievalService


class ResponseService:
    """
    Service for generating intelligent responses.

    Usage:
        service = ResponseService()

        response = await service.ask(
            "What should I focus on today based on my recent notes?"
        )

        print(response.answer)
        for source in response.sources:
            print(f"- {source.snippet}")
    """

    def __init__(self, retrieval_service: RetrievalService = None):
        self.retrieval = retrieval_service or RetrievalService()
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

    async def ask(
        self,
        question: str,
        context_types: list[EntryType] = None,
        context_tags: list[str] = None,
        context_collection: str = None,
        max_context_entries: int = 10,
        include_sources: bool = True,
    ) -> AskResponse:
        """
        Ask a question and get an intelligent response.

        The response is generated using relevant context from your
        knowledge base, with source citations.
        """
        start_time = time.time()

        # 1. Retrieve relevant context
        context, entries_used = await self.retrieval.get_context_for_query(
            query=question,
            types=context_types,
            tags=context_tags,
            collection_id=context_collection,
            max_entries=max_context_entries,
            max_tokens=config.context_token_budget,
        )

        # 2. Build the prompt
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(question, context)

        # 3. Generate response
        answer, tokens_used, model_used = await self._generate_response(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )

        # 4. Build source citations
        sources = []
        if include_sources and entries_used:
            for entry in entries_used[:5]:  # Top 5 sources
                sources.append(SourceCitation(
                    entry_id=entry.id,
                    type=entry.type,
                    title=entry.title,
                    snippet=entry.content[:200] + "..." if len(entry.content) > 200 else entry.content,
                    date=entry.created_at,
                    relevance=0.8,  # TODO: Calculate actual relevance
                ))

        # 5. Generate follow-up questions
        follow_ups = self._suggest_follow_ups(question, answer, entries_used)

        response_time = (time.time() - start_time) * 1000

        return AskResponse(
            question=question,
            answer=answer,
            confidence=self._estimate_confidence(entries_used, answer),
            sources=sources,
            context_used=len(entries_used),
            tokens_used=tokens_used,
            follow_up_questions=follow_ups,
            model_used=model_used,
            response_time_ms=response_time,
        )

    async def ask_with_query(self, query: AskQuery) -> AskResponse:
        """Ask using an AskQuery object."""
        return await self.ask(
            question=query.question,
            context_types=query.context_types,
            context_tags=query.context_tags,
            context_collection=query.context_collection,
            max_context_entries=query.max_context_entries,
            include_sources=query.include_sources,
        )

    async def summarize_entries(
        self,
        entries: list[Entry],
        focus: str = None,
    ) -> str:
        """Summarize a list of entries."""
        if not entries:
            return "No entries to summarize."

        context = "\n\n---\n\n".join([
            f"[{e.type.value}] {e.created_at.strftime('%Y-%m-%d')}\n{e.content}"
            for e in entries[:20]
        ])

        prompt = f"""Summarize the following entries concisely:

{context}

"""
        if focus:
            prompt += f"\nFocus on: {focus}"
        else:
            prompt += "\nHighlight key themes, decisions, and action items."

        summary, _, _ = await self._generate_response(
            system_prompt="You are a helpful assistant that creates concise summaries.",
            user_prompt=prompt,
        )

        return summary

    async def generate_briefing(
        self,
        briefing_type: str = "daily",
    ) -> str:
        """
        Generate a personalized briefing.

        Types:
        - daily: Morning briefing for the day
        - weekly: Week in review
        - custom: Based on specific criteria
        """
        today = datetime.utcnow()

        if briefing_type == "daily":
            # Get recent entries and any tasks
            recent = await self.retrieval.get_recent_entries(limit=20)

            context = "\n\n".join([
                f"[{e.type.value}] {e.created_at.strftime('%Y-%m-%d %H:%M')}\n{e.content[:500]}"
                for e in recent
            ])

            prompt = f"""Based on my recent notes and entries, create a morning briefing for {today.strftime('%A, %B %d, %Y')}.

Recent entries:
{context}

Include:
1. Key things to focus on today
2. Any follow-ups or commitments mentioned
3. One insight from recent notes that might be useful today

Keep it concise and actionable."""

        elif briefing_type == "weekly":
            # Get entries from the past week
            from datetime import timedelta
            week_ago = today - timedelta(days=7)

            entries = await self.retrieval.metadata_store.search_entries(
                date_from=week_ago,
                limit=50,
            )

            context = "\n\n".join([
                f"[{e.type.value}] {e.created_at.strftime('%Y-%m-%d')}\n{e.content[:300]}"
                for e in entries
            ])

            prompt = f"""Create a weekly review based on my entries from the past week.

Entries:
{context}

Include:
1. What I accomplished
2. Key decisions made
3. Patterns or themes noticed
4. Suggestions for next week

Be specific and reference actual entries."""

        else:
            prompt = f"Create a {briefing_type} briefing based on my recent entries."

        briefing, _, _ = await self._generate_response(
            system_prompt=self._build_system_prompt(),
            user_prompt=prompt,
        )

        return briefing

    # ==========================================================================
    # INTERNAL METHODS
    # ==========================================================================

    def _build_system_prompt(self) -> str:
        """Build the system prompt based on user preferences."""
        style = config.communication_style
        length = config.response_length
        name = config.user_name or "the user"

        style_instructions = {
            "casual": "Be friendly and conversational. Use simple language.",
            "professional": "Be clear, professional, and well-organized.",
            "technical": "Be precise and technical. Include specific details.",
        }

        length_instructions = {
            "brief": "Keep responses short and to the point. Use bullet points.",
            "moderate": "Provide balanced responses with key details.",
            "detailed": "Provide comprehensive responses with full explanations.",
        }

        return f"""You are a personal AI assistant for {name}. You have access to their personal knowledge base including notes, documents, conversations, and other information they've stored.

Style: {style_instructions.get(style, style_instructions['professional'])}
Length: {length_instructions.get(length, length_instructions['moderate'])}

Guidelines:
- Always base your answers on the provided context from the knowledge base
- If you don't have enough information, say so clearly
- Reference specific entries when relevant (by date or topic)
- Be helpful and proactive in suggesting related information
- Respect privacy - this is personal information"""

    def _build_user_prompt(self, question: str, context: str) -> str:
        """Build the user prompt with context."""
        if context:
            return f"""Based on the following information from my knowledge base:

{context}

---

Question: {question}

Please provide a helpful response based on the context above."""
        else:
            return f"""Question: {question}

Note: I don't have specific context from your knowledge base for this question. I'll do my best to help based on general knowledge."""

    async def _generate_response(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> tuple[str, int, str]:
        """Generate a response using the configured LLM."""
        client = self._get_client()

        if config.llm_provider == "claude":
            response = await asyncio.to_thread(
                client.messages.create,
                model=config.claude_model,
                max_tokens=2000,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )

            answer = response.content[0].text
            tokens = response.usage.input_tokens + response.usage.output_tokens
            model = config.claude_model

        else:  # OpenAI
            response = await asyncio.to_thread(
                client.chat.completions.create,
                model=config.openai_model,
                max_tokens=2000,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )

            answer = response.choices[0].message.content
            tokens = response.usage.total_tokens
            model = config.openai_model

        return answer, tokens, model

    def _estimate_confidence(self, entries_used: list[Entry], answer: str) -> float:
        """Estimate confidence in the answer."""
        if not entries_used:
            return 0.3  # Low confidence without context

        # More entries = higher confidence (up to a point)
        entry_factor = min(len(entries_used) / 5, 1.0)

        # Longer, more detailed answers tend to be more confident
        length_factor = min(len(answer) / 500, 1.0)

        # Combine factors
        confidence = 0.3 + (entry_factor * 0.4) + (length_factor * 0.3)
        return min(confidence, 0.95)  # Never claim 100% confidence

    def _suggest_follow_ups(
        self,
        question: str,
        answer: str,
        entries_used: list[Entry],
    ) -> list[str]:
        """Suggest follow-up questions."""
        # Simple rule-based suggestions
        suggestions = []

        # If answer mentions specific topics, suggest exploring them
        topics = set()
        for entry in entries_used[:5]:
            topics.update(entry.tags)

        for topic in list(topics)[:2]:
            suggestions.append(f"Tell me more about {topic}")

        # Time-based follow-ups
        if "last week" in question.lower() or "recently" in question.lower():
            suggestions.append("What should I focus on next?")

        if "decision" in question.lower():
            suggestions.append("What were the alternatives I considered?")

        if len(suggestions) < 3:
            suggestions.append("What else should I know about this?")

        return suggestions[:3]
