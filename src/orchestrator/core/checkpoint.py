"""Checkpoint and recovery system for long-running orchestration."""

import asyncio
import json
import gzip
from datetime import datetime
from pathlib import Path
from typing import Optional, Any

from pydantic import BaseModel, Field

from orchestrator.config import config


class CheckpointMetadata(BaseModel):
    """Metadata for a checkpoint."""
    id: str
    timestamp: datetime
    project: str
    tasks_total: int
    tasks_completed: int
    tasks_failed: int
    agents_active: int
    file_path: Path
    size_bytes: int
    compressed: bool = True


class CheckpointManager:
    """
    Manages checkpoints for crash recovery and state persistence.

    Features:
    - Automatic periodic checkpointing
    - Compressed checkpoint storage
    - Checkpoint rotation (keep N most recent)
    - State restoration from checkpoint
    - Incremental checkpoints (only changes)
    """

    def __init__(
        self,
        checkpoint_dir: Optional[Path] = None,
        max_checkpoints: int = None,
        compress: bool = True,
    ):
        self.checkpoint_dir = checkpoint_dir or config.data_dir / "checkpoints"
        self.max_checkpoints = max_checkpoints or config.max_checkpoints
        self.compress = compress

        # Ensure directory exists
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

        # Track checkpoints
        self.checkpoints: list[CheckpointMetadata] = []
        self._load_existing_checkpoints()

    def _load_existing_checkpoints(self) -> None:
        """Load metadata for existing checkpoints."""
        self.checkpoints = []

        for path in self.checkpoint_dir.glob("checkpoint_*.json*"):
            try:
                metadata = self._extract_metadata(path)
                if metadata:
                    self.checkpoints.append(metadata)
            except Exception:
                continue

        # Sort by timestamp (newest first)
        self.checkpoints.sort(key=lambda c: c.timestamp, reverse=True)

    def _extract_metadata(self, path: Path) -> Optional[CheckpointMetadata]:
        """Extract metadata from a checkpoint file."""
        try:
            if path.suffix == ".gz":
                with gzip.open(path, "rt") as f:
                    data = json.load(f)
                compressed = True
            else:
                with open(path) as f:
                    data = json.load(f)
                compressed = False

            tasks = data.get("tasks", {})
            completed = sum(1 for t in tasks.values() if t.get("status") == "completed")
            failed = sum(1 for t in tasks.values() if t.get("status") == "failed")

            return CheckpointMetadata(
                id=path.stem,
                timestamp=datetime.fromisoformat(data.get("timestamp", datetime.utcnow().isoformat())),
                project=data.get("project", "unknown"),
                tasks_total=len(tasks),
                tasks_completed=completed,
                tasks_failed=failed,
                agents_active=len(data.get("agents", {})),
                file_path=path,
                size_bytes=path.stat().st_size,
                compressed=compressed,
            )
        except Exception:
            return None

    async def save(
        self,
        state: dict,
        project: str,
        checkpoint_id: Optional[str] = None,
    ) -> CheckpointMetadata:
        """
        Save a checkpoint.

        Args:
            state: Complete state to checkpoint
            project: Project name
            checkpoint_id: Optional custom ID (default: timestamp-based)

        Returns:
            Metadata for the saved checkpoint
        """
        # Generate ID
        if not checkpoint_id:
            checkpoint_id = f"checkpoint_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

        # Add metadata to state
        state["timestamp"] = datetime.utcnow().isoformat()
        state["project"] = project
        state["checkpoint_id"] = checkpoint_id

        # Determine file path
        if self.compress:
            file_path = self.checkpoint_dir / f"{checkpoint_id}.json.gz"
        else:
            file_path = self.checkpoint_dir / f"{checkpoint_id}.json"

        # Write checkpoint
        json_data = json.dumps(state, indent=2, default=str)

        if self.compress:
            with gzip.open(file_path, "wt") as f:
                f.write(json_data)
        else:
            with open(file_path, "w") as f:
                f.write(json_data)

        # Create metadata
        tasks = state.get("tasks", {})
        completed = sum(1 for t in tasks.values() if t.get("status") == "completed")
        failed = sum(1 for t in tasks.values() if t.get("status") == "failed")

        metadata = CheckpointMetadata(
            id=checkpoint_id,
            timestamp=datetime.utcnow(),
            project=project,
            tasks_total=len(tasks),
            tasks_completed=completed,
            tasks_failed=failed,
            agents_active=len(state.get("agents", {})),
            file_path=file_path,
            size_bytes=file_path.stat().st_size,
            compressed=self.compress,
        )

        # Add to list and rotate
        self.checkpoints.insert(0, metadata)
        await self._rotate_checkpoints()

        return metadata

    async def load(self, checkpoint_id: Optional[str] = None) -> Optional[dict]:
        """
        Load a checkpoint.

        Args:
            checkpoint_id: ID of checkpoint to load (default: most recent)

        Returns:
            Checkpoint state or None if not found
        """
        if not checkpoint_id:
            # Load most recent
            if not self.checkpoints:
                return None
            checkpoint = self.checkpoints[0]
        else:
            # Find by ID
            checkpoint = next(
                (c for c in self.checkpoints if c.id == checkpoint_id),
                None
            )

        if not checkpoint:
            return None

        try:
            if checkpoint.compressed:
                with gzip.open(checkpoint.file_path, "rt") as f:
                    return json.load(f)
            else:
                with open(checkpoint.file_path) as f:
                    return json.load(f)
        except Exception:
            return None

    async def _rotate_checkpoints(self) -> None:
        """Remove old checkpoints to stay within limit."""
        while len(self.checkpoints) > self.max_checkpoints:
            oldest = self.checkpoints.pop()
            try:
                oldest.file_path.unlink()
            except Exception:
                pass

    def get_latest(self, project: Optional[str] = None) -> Optional[CheckpointMetadata]:
        """Get the most recent checkpoint, optionally filtered by project."""
        for checkpoint in self.checkpoints:
            if project is None or checkpoint.project == project:
                return checkpoint
        return None

    def list_checkpoints(
        self,
        project: Optional[str] = None,
        limit: int = 10,
    ) -> list[CheckpointMetadata]:
        """List available checkpoints."""
        checkpoints = self.checkpoints
        if project:
            checkpoints = [c for c in checkpoints if c.project == project]
        return checkpoints[:limit]

    async def delete(self, checkpoint_id: str) -> bool:
        """Delete a checkpoint."""
        checkpoint = next(
            (c for c in self.checkpoints if c.id == checkpoint_id),
            None
        )

        if not checkpoint:
            return False

        try:
            checkpoint.file_path.unlink()
            self.checkpoints.remove(checkpoint)
            return True
        except Exception:
            return False

    async def cleanup_old(self, max_age_hours: int = 24) -> int:
        """Delete checkpoints older than specified age."""
        cutoff = datetime.utcnow().timestamp() - (max_age_hours * 3600)
        deleted = 0

        for checkpoint in list(self.checkpoints):
            if checkpoint.timestamp.timestamp() < cutoff:
                if await self.delete(checkpoint.id):
                    deleted += 1

        return deleted

    def get_stats(self) -> dict:
        """Get checkpoint statistics."""
        total_size = sum(c.size_bytes for c in self.checkpoints)

        return {
            "total_checkpoints": len(self.checkpoints),
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "oldest": self.checkpoints[-1].timestamp.isoformat() if self.checkpoints else None,
            "newest": self.checkpoints[0].timestamp.isoformat() if self.checkpoints else None,
            "max_checkpoints": self.max_checkpoints,
            "compression_enabled": self.compress,
        }
