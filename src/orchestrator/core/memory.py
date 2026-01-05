"""
External Memory Layer - Persistent storage for agent knowledge.

Agents should NOT "remember" by re-reading entire files or conversations.
Instead, they query this memory layer for:
- Decisions made
- API contracts
- File summaries
- Task status
- Known constraints
- Prior errors and fixes

Only the 3-10 most relevant memory items are fed back per task.
"""

import json
import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, Any
from threading import Lock


class MemoryType(str, Enum):
    DECISION = "decision"           # Architectural or implementation decision
    CONTRACT = "contract"           # API contract, interface definition
    FILE_SUMMARY = "file_summary"   # Summary of what a file does
    CONSTRAINT = "constraint"       # Known constraint (stack, auth, etc.)
    ERROR = "error"                 # Error encountered and fix
    DISCOVERY = "discovery"         # Something learned about the codebase
    TASK_STATUS = "task_status"     # Status of a task
    DEPENDENCY = "dependency"       # Dependency between files/modules


@dataclass
class MemoryEntry:
    """A single memory entry."""
    id: str
    type: MemoryType
    key: str  # Unique key for this memory (e.g., "auth_strategy", "db_schema")
    content: str
    tags: list[str] = field(default_factory=list)  # For searching
    related_files: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    created_by: str = ""  # Agent ID that created this
    importance: int = 5  # 1-10, higher = more important
    ttl_minutes: Optional[int] = None  # Auto-expire after this time


@dataclass
class MemoryQuery:
    """Query parameters for searching memory."""
    types: list[MemoryType] = None
    tags: list[str] = None
    files: list[str] = None
    keys: list[str] = None
    min_importance: int = 0
    limit: int = 10


class MemoryStore:
    """
    Persistent memory store for agent knowledge.

    Usage:
        memory = MemoryStore(project_path)

        # Store a decision
        memory.remember(
            type=MemoryType.DECISION,
            key="auth_strategy",
            content="Using JWT tokens with refresh, stored in httpOnly cookies",
            tags=["auth", "security"],
            related_files=["src/auth.py", "src/middleware.py"],
            importance=8
        )

        # Query relevant memories for a task
        memories = memory.query(MemoryQuery(
            tags=["auth"],
            files=["src/auth.py"],
            limit=5
        ))

        # Get formatted context for an agent
        context = memory.get_context_for_task(
            task_description="Fix login bug",
            relevant_files=["src/auth.py"],
            max_tokens=2000
        )
    """

    def __init__(self, project_path: str, persist: bool = True):
        self.project_path = Path(project_path)
        self.persist = persist
        self.memory_file = self.project_path / ".orchestrator" / "memory.json"

        self.entries: dict[str, MemoryEntry] = {}
        self._lock = Lock()

        if persist:
            self._load()

    def _load(self):
        """Load memory from disk."""
        if self.memory_file.exists():
            try:
                data = json.loads(self.memory_file.read_text())
                for entry_data in data.get("entries", []):
                    entry = MemoryEntry(
                        id=entry_data["id"],
                        type=MemoryType(entry_data["type"]),
                        key=entry_data["key"],
                        content=entry_data["content"],
                        tags=entry_data.get("tags", []),
                        related_files=entry_data.get("related_files", []),
                        created_at=datetime.fromisoformat(entry_data["created_at"]),
                        importance=entry_data.get("importance", 5),
                    )
                    self.entries[entry.id] = entry
            except Exception:
                pass  # Start fresh if corrupted

    def _save(self):
        """Save memory to disk."""
        if not self.persist:
            return

        self.memory_file.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "entries": [
                {
                    "id": e.id,
                    "type": e.type.value,
                    "key": e.key,
                    "content": e.content,
                    "tags": e.tags,
                    "related_files": e.related_files,
                    "created_at": e.created_at.isoformat(),
                    "importance": e.importance,
                }
                for e in self.entries.values()
            ]
        }
        self.memory_file.write_text(json.dumps(data, indent=2))

    def remember(
        self,
        type: MemoryType,
        key: str,
        content: str,
        tags: list[str] = None,
        related_files: list[str] = None,
        created_by: str = "",
        importance: int = 5,
        ttl_minutes: int = None,
    ) -> str:
        """
        Store a memory. Returns the memory ID.
        If a memory with the same key exists, it's updated.
        """
        entry_id = hashlib.md5(f"{type.value}:{key}".encode()).hexdigest()[:12]

        with self._lock:
            if entry_id in self.entries:
                # Update existing
                entry = self.entries[entry_id]
                entry.content = content
                entry.updated_at = datetime.utcnow()
                if tags:
                    entry.tags = list(set(entry.tags + tags))
                if related_files:
                    entry.related_files = list(set(entry.related_files + related_files))
            else:
                # Create new
                entry = MemoryEntry(
                    id=entry_id,
                    type=type,
                    key=key,
                    content=content,
                    tags=tags or [],
                    related_files=related_files or [],
                    created_by=created_by,
                    importance=importance,
                    ttl_minutes=ttl_minutes,
                )
                self.entries[entry_id] = entry

            self._save()
            return entry_id

    def forget(self, key: str = None, entry_id: str = None) -> bool:
        """Remove a memory by key or ID."""
        with self._lock:
            if entry_id and entry_id in self.entries:
                del self.entries[entry_id]
                self._save()
                return True

            if key:
                to_remove = [
                    eid for eid, e in self.entries.items()
                    if e.key == key
                ]
                for eid in to_remove:
                    del self.entries[eid]
                if to_remove:
                    self._save()
                    return True

            return False

    def query(self, q: MemoryQuery) -> list[MemoryEntry]:
        """Query memories matching criteria."""
        results = []

        with self._lock:
            for entry in self.entries.values():
                # Filter by type
                if q.types and entry.type not in q.types:
                    continue

                # Filter by importance
                if entry.importance < q.min_importance:
                    continue

                # Filter by tags
                if q.tags and not any(t in entry.tags for t in q.tags):
                    continue

                # Filter by files
                if q.files and not any(
                    any(f in rf for rf in entry.related_files)
                    for f in q.files
                ):
                    continue

                # Filter by keys
                if q.keys and entry.key not in q.keys:
                    continue

                results.append(entry)

        # Sort by importance, then recency
        results.sort(key=lambda e: (-e.importance, e.updated_at), reverse=True)

        return results[:q.limit]

    def get(self, key: str) -> Optional[MemoryEntry]:
        """Get a specific memory by key."""
        for entry in self.entries.values():
            if entry.key == key:
                return entry
        return None

    def get_context_for_task(
        self,
        task_description: str,
        relevant_files: list[str] = None,
        tags: list[str] = None,
        max_tokens: int = 2000,
    ) -> str:
        """
        Get formatted memory context for a task.
        Returns only the most relevant memories, within token budget.
        """
        # Extract keywords from task description
        keywords = self._extract_keywords(task_description)

        # Query memories
        query = MemoryQuery(
            files=relevant_files,
            tags=tags or keywords,
            min_importance=3,
            limit=20,
        )
        memories = self.query(query)

        if not memories:
            return ""

        # Format and truncate to token budget
        lines = ["## Relevant Context from Memory\n"]
        char_budget = max_tokens * 4  # ~4 chars per token

        for entry in memories:
            entry_text = self._format_entry(entry)
            if len("\n".join(lines)) + len(entry_text) > char_budget:
                break
            lines.append(entry_text)

        return "\n".join(lines)

    def _format_entry(self, entry: MemoryEntry) -> str:
        """Format a memory entry for context."""
        type_emoji = {
            MemoryType.DECISION: "DECISION",
            MemoryType.CONTRACT: "CONTRACT",
            MemoryType.CONSTRAINT: "CONSTRAINT",
            MemoryType.ERROR: "ERROR",
            MemoryType.DISCOVERY: "DISCOVERY",
            MemoryType.FILE_SUMMARY: "FILE",
        }.get(entry.type, "INFO")

        files = f" [{', '.join(entry.related_files[:3])}]" if entry.related_files else ""
        return f"[{type_emoji}] {entry.key}{files}\n{entry.content}\n"

    def _extract_keywords(self, text: str) -> list[str]:
        """Extract keywords from text for searching."""
        import re
        # Simple keyword extraction
        words = re.findall(r'\b\w+\b', text.lower())
        # Filter out common words
        stop_words = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been",
            "being", "have", "has", "had", "do", "does", "did", "will",
            "would", "could", "should", "may", "might", "must", "shall",
            "to", "of", "in", "for", "on", "with", "at", "by", "from",
            "as", "into", "through", "during", "before", "after", "above",
            "below", "between", "under", "again", "further", "then", "once",
            "here", "there", "when", "where", "why", "how", "all", "each",
            "every", "both", "few", "more", "most", "other", "some", "such",
            "no", "nor", "not", "only", "own", "same", "so", "than", "too",
            "very", "can", "just", "should", "now", "and", "but", "or", "if",
            "this", "that", "these", "those", "it", "its",
        }
        keywords = [w for w in words if len(w) > 2 and w not in stop_words]
        return list(set(keywords))[:10]

    def get_decisions(self) -> list[MemoryEntry]:
        """Get all decisions."""
        return self.query(MemoryQuery(types=[MemoryType.DECISION], limit=50))

    def get_constraints(self) -> list[MemoryEntry]:
        """Get all constraints."""
        return self.query(MemoryQuery(types=[MemoryType.CONSTRAINT], limit=50))

    def get_errors(self) -> list[MemoryEntry]:
        """Get recent errors."""
        return self.query(MemoryQuery(types=[MemoryType.ERROR], limit=20))

    def summarize_for_new_task(self, max_tokens: int = 1000) -> str:
        """
        Get a summary of key information for starting a new task.
        Includes high-importance decisions and constraints.
        """
        lines = ["## Project Context\n"]

        # High importance decisions
        decisions = self.query(MemoryQuery(
            types=[MemoryType.DECISION],
            min_importance=7,
            limit=5
        ))
        if decisions:
            lines.append("### Key Decisions")
            for d in decisions:
                lines.append(f"- **{d.key}**: {d.content[:200]}")
            lines.append("")

        # Constraints
        constraints = self.query(MemoryQuery(
            types=[MemoryType.CONSTRAINT],
            limit=5
        ))
        if constraints:
            lines.append("### Constraints")
            for c in constraints:
                lines.append(f"- {c.content}")
            lines.append("")

        # Recent errors (to avoid repeating)
        errors = self.query(MemoryQuery(
            types=[MemoryType.ERROR],
            limit=3
        ))
        if errors:
            lines.append("### Known Issues")
            for e in errors:
                lines.append(f"- {e.key}: {e.content[:100]}")

        result = "\n".join(lines)

        # Truncate if too long
        char_budget = max_tokens * 4
        if len(result) > char_budget:
            result = result[:char_budget] + "\n... (truncated)"

        return result

    def clear_expired(self):
        """Remove expired entries."""
        now = datetime.utcnow()
        with self._lock:
            to_remove = []
            for eid, entry in self.entries.items():
                if entry.ttl_minutes:
                    age = (now - entry.created_at).total_seconds() / 60
                    if age > entry.ttl_minutes:
                        to_remove.append(eid)
            for eid in to_remove:
                del self.entries[eid]
            if to_remove:
                self._save()

    def get_stats(self) -> dict:
        """Get memory statistics."""
        type_counts = {}
        for entry in self.entries.values():
            type_counts[entry.type.value] = type_counts.get(entry.type.value, 0) + 1

        return {
            "total_entries": len(self.entries),
            "by_type": type_counts,
            "avg_importance": sum(e.importance for e in self.entries.values()) / max(1, len(self.entries)),
        }
