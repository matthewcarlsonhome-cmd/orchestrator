"""
Shared Context - A knowledge base that agents can share to avoid duplicate work.

This solves the token explosion problem by:
1. Caching file contents so agents don't re-read the same files
2. Storing discoveries (e.g., "auth is in /lib/auth.ts")
3. Tracking which files are being edited to avoid conflicts
4. Providing summaries instead of full content when possible
"""

from datetime import datetime, timedelta
from typing import Optional, Any
from dataclasses import dataclass, field
from threading import Lock
import hashlib


@dataclass
class CachedFile:
    """A cached file with metadata."""
    path: str
    content: str
    summary: Optional[str] = None  # Short summary of the file
    hash: str = ""
    read_count: int = 0
    first_read: datetime = field(default_factory=datetime.utcnow)
    last_read: datetime = field(default_factory=datetime.utcnow)
    read_by: list[str] = field(default_factory=list)  # Agent IDs who read this

    def __post_init__(self):
        if not self.hash:
            self.hash = hashlib.md5(self.content.encode()).hexdigest()[:8]


@dataclass
class Discovery:
    """A discovery made by an agent that others should know."""
    id: str
    agent_id: str
    category: str  # "architecture", "pattern", "dependency", "issue"
    title: str
    content: str
    related_files: list[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class FileEdit:
    """Tracks a file being edited to prevent conflicts."""
    path: str
    agent_id: str
    started: datetime = field(default_factory=datetime.utcnow)
    description: str = ""


class SharedContext:
    """
    Shared knowledge base for all agents.

    Key features:
    - File cache: Agents share file contents instead of re-reading
    - Discoveries: Share findings like "config is in /src/config.ts"
    - Edit locks: Prevent two agents editing the same file
    - Summaries: Get short summaries instead of full content
    """

    def __init__(self, max_cache_size: int = 100, cache_ttl_minutes: int = 30):
        self.max_cache_size = max_cache_size
        self.cache_ttl = timedelta(minutes=cache_ttl_minutes)

        # File cache
        self._file_cache: dict[str, CachedFile] = {}

        # Discoveries shared between agents
        self._discoveries: list[Discovery] = []

        # Files currently being edited (path -> FileEdit)
        self._active_edits: dict[str, FileEdit] = {}

        # Lock for thread safety
        self._lock = Lock()

        # Statistics
        self.cache_hits = 0
        self.cache_misses = 0

    def cache_file(
        self,
        path: str,
        content: str,
        agent_id: str,
        summary: Optional[str] = None,
    ) -> None:
        """Cache a file's content for other agents to use."""
        with self._lock:
            if path in self._file_cache:
                # Update existing
                cached = self._file_cache[path]
                cached.content = content
                cached.last_read = datetime.utcnow()
                cached.read_count += 1
                if agent_id not in cached.read_by:
                    cached.read_by.append(agent_id)
                if summary:
                    cached.summary = summary
            else:
                # New cache entry
                self._file_cache[path] = CachedFile(
                    path=path,
                    content=content,
                    summary=summary,
                    read_by=[agent_id],
                )

            # Evict old entries if cache too large
            self._evict_if_needed()

    def get_file(self, path: str, agent_id: str) -> Optional[str]:
        """
        Get a file from cache if available.
        Returns None if not cached (agent should read it).
        """
        with self._lock:
            if path in self._file_cache:
                cached = self._file_cache[path]
                # Check if cache is still valid
                if datetime.utcnow() - cached.last_read < self.cache_ttl:
                    cached.read_count += 1
                    cached.last_read = datetime.utcnow()
                    if agent_id not in cached.read_by:
                        cached.read_by.append(agent_id)
                    self.cache_hits += 1
                    return cached.content

            self.cache_misses += 1
            return None

    def get_file_summary(self, path: str) -> Optional[str]:
        """Get a short summary of a file (saves tokens)."""
        with self._lock:
            if path in self._file_cache and self._file_cache[path].summary:
                return self._file_cache[path].summary
            return None

    def get_cached_files_list(self) -> list[dict]:
        """Get list of all cached files with metadata."""
        with self._lock:
            return [
                {
                    "path": cf.path,
                    "hash": cf.hash,
                    "read_count": cf.read_count,
                    "read_by": cf.read_by,
                    "has_summary": cf.summary is not None,
                    "lines": len(cf.content.split("\n")),
                }
                for cf in self._file_cache.values()
            ]

    def add_discovery(
        self,
        agent_id: str,
        category: str,
        title: str,
        content: str,
        related_files: list[str] = None,
    ) -> str:
        """
        Add a discovery for other agents to see.

        Example discoveries:
        - "Authentication uses JWT stored in /lib/auth.ts"
        - "API routes are in /pages/api/"
        - "Found issue: deprecated package in dependencies"
        """
        with self._lock:
            discovery = Discovery(
                id=f"disc-{len(self._discoveries)}",
                agent_id=agent_id,
                category=category,
                title=title,
                content=content,
                related_files=related_files or [],
            )
            self._discoveries.append(discovery)
            return discovery.id

    def get_discoveries(
        self,
        category: Optional[str] = None,
        limit: int = 20,
    ) -> list[Discovery]:
        """Get recent discoveries, optionally filtered by category."""
        with self._lock:
            discoveries = self._discoveries
            if category:
                discoveries = [d for d in discoveries if d.category == category]
            return discoveries[-limit:]

    def get_discoveries_summary(self) -> str:
        """Get a token-efficient summary of all discoveries."""
        with self._lock:
            if not self._discoveries:
                return "No discoveries yet."

            lines = ["Recent discoveries:"]
            for d in self._discoveries[-10:]:  # Last 10
                lines.append(f"- [{d.category}] {d.title}")
            return "\n".join(lines)

    def start_edit(self, path: str, agent_id: str, description: str = "") -> bool:
        """
        Mark a file as being edited by an agent.
        Returns False if another agent is already editing it.
        """
        with self._lock:
            if path in self._active_edits:
                existing = self._active_edits[path]
                # Allow same agent to re-acquire
                if existing.agent_id == agent_id:
                    return True
                # Check if lock is stale (> 5 minutes)
                if datetime.utcnow() - existing.started > timedelta(minutes=5):
                    # Stale lock, allow override
                    pass
                else:
                    return False

            self._active_edits[path] = FileEdit(
                path=path,
                agent_id=agent_id,
                description=description,
            )
            return True

    def end_edit(self, path: str, agent_id: str) -> None:
        """Mark a file as no longer being edited."""
        with self._lock:
            if path in self._active_edits:
                if self._active_edits[path].agent_id == agent_id:
                    del self._active_edits[path]

    def is_being_edited(self, path: str) -> Optional[str]:
        """Check if a file is being edited. Returns agent_id if so."""
        with self._lock:
            if path in self._active_edits:
                return self._active_edits[path].agent_id
            return None

    def get_context_for_agent(self, agent_id: str, max_tokens: int = 2000) -> str:
        """
        Get a token-efficient context summary for an agent.

        This gives the agent awareness of:
        - What files have been read/cached
        - What discoveries have been made
        - What files are being edited by others
        """
        lines = []

        # Discoveries summary
        disc_summary = self.get_discoveries_summary()
        if disc_summary != "No discoveries yet.":
            lines.append("## Shared Knowledge")
            lines.append(disc_summary)
            lines.append("")

        # Cached files summary
        with self._lock:
            if self._file_cache:
                lines.append("## Previously Read Files")
                for path, cf in list(self._file_cache.items())[:10]:
                    readers = ", ".join(cf.read_by[:3])
                    lines.append(f"- {path} (read by: {readers})")
                lines.append("")

            # Active edits
            if self._active_edits:
                lines.append("## Files Being Edited")
                for path, edit in self._active_edits.items():
                    if edit.agent_id != agent_id:
                        lines.append(f"- {path} (by agent {edit.agent_id})")
                lines.append("")

        result = "\n".join(lines)

        # Truncate if too long (rough token estimate: 4 chars per token)
        max_chars = max_tokens * 4
        if len(result) > max_chars:
            result = result[:max_chars] + "\n[...truncated]"

        return result

    def invalidate_file(self, path: str) -> None:
        """Remove a file from cache (e.g., after it's been edited)."""
        with self._lock:
            if path in self._file_cache:
                del self._file_cache[path]

    def _evict_if_needed(self) -> None:
        """Evict oldest entries if cache is too large."""
        while len(self._file_cache) > self.max_cache_size:
            # Find oldest entry
            oldest_path = min(
                self._file_cache.keys(),
                key=lambda p: self._file_cache[p].last_read
            )
            del self._file_cache[oldest_path]

    def get_stats(self) -> dict:
        """Get statistics about the shared context."""
        with self._lock:
            return {
                "cached_files": len(self._file_cache),
                "discoveries": len(self._discoveries),
                "active_edits": len(self._active_edits),
                "cache_hits": self.cache_hits,
                "cache_misses": self.cache_misses,
                "hit_rate": self.cache_hits / max(1, self.cache_hits + self.cache_misses),
            }

    def clear(self) -> None:
        """Clear all cached data."""
        with self._lock:
            self._file_cache.clear()
            self._discoveries.clear()
            self._active_edits.clear()
            self.cache_hits = 0
            self.cache_misses = 0
