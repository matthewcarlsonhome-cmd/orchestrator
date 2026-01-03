"""Configuration management for the orchestrator."""

import os
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class OrchestratorConfig(BaseSettings):
    """Main configuration for the orchestrator system."""

    model_config = SettingsConfigDict(
        env_prefix="ORCHESTRATOR_",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    # API Configuration - also accepts ANTHROPIC_API_KEY without prefix
    anthropic_api_key: str = Field(default="", description="Anthropic API key")
    model: str = Field(default="claude-sonnet-4-20250514", description="Claude model to use")

    @field_validator("anthropic_api_key", mode="before")
    @classmethod
    def get_api_key(cls, v):
        """Accept ANTHROPIC_API_KEY env var as fallback."""
        if v:
            return v
        return os.environ.get("ANTHROPIC_API_KEY", "")

    # Agent Configuration
    max_agents: int = Field(default=3, ge=1, le=10, description="Maximum concurrent agents")
    agent_timeout_minutes: int = Field(default=30, description="Agent task timeout")

    # Paths
    projects_dir: Path = Field(
        default=Path("/tmp/orchestrator/projects"),
        description="Directory for cloned projects",
    )
    data_dir: Path = Field(
        default=Path.home() / ".orchestrator",
        description="Directory for orchestrator data",
    )
    config_dir: Path = Field(
        default=Path.cwd() / "projects",
        description="Directory for project configurations",
    )

    # Checkpointing
    checkpoint_interval_minutes: int = Field(
        default=5, description="How often to save checkpoints"
    )
    max_checkpoints: int = Field(default=10, description="Maximum checkpoints to keep")

    # Server
    api_host: str = Field(default="127.0.0.1", description="API server host")
    api_port: int = Field(default=8420, description="API server port")

    # Git
    git_strategy: Literal["branch_per_agent", "shared_branch"] = Field(
        default="branch_per_agent", description="Git branching strategy"
    )
    auto_push: bool = Field(
        default=False, description="Automatically push changes to remote"
    )
    create_pull_requests: bool = Field(
        default=True, description="Create PRs instead of pushing to main"
    )

    # Shell Commands
    require_shell_approval: bool = Field(
        default=True, description="Require user approval for shell commands"
    )
    allowed_shell_commands: list[str] = Field(
        default=["npm", "yarn", "pnpm", "pip", "python", "pytest", "node"],
        description="Commands allowed without approval",
    )

    def ensure_dirs(self) -> None:
        """Create necessary directories."""
        self.projects_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        (self.data_dir / "checkpoints").mkdir(exist_ok=True)
        (self.data_dir / "logs").mkdir(exist_ok=True)


# Global config instance
config = OrchestratorConfig()
