"""Configuration management for the orchestrator."""

import os
from pathlib import Path
from typing import Literal, Optional

from dotenv import load_dotenv  # Explicit .env loading
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load .env file from multiple possible locations
# This ensures .env is found whether running from repo root or elsewhere
_possible_env_paths = [
    Path.cwd() / ".env",                    # Current directory
    Path(__file__).parent.parent.parent.parent / ".env",  # Repo root
    Path.home() / ".orchestrator" / ".env",  # User's home directory
]

for env_path in _possible_env_paths:
    if env_path.exists():
        load_dotenv(env_path)
        print(f"Loaded config from: {env_path}")
        break


class OrchestratorConfig(BaseSettings):
    """Main configuration for the orchestrator system."""

    model_config = SettingsConfigDict(
        env_prefix="ORCHESTRATOR_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # Ignore unknown fields in .env
    )

    # API Configuration
    # Accepts: ANTHROPIC_API_KEY or ORCHESTRATOR_ANTHROPIC_API_KEY
    anthropic_api_key: str = Field(default="", description="Anthropic API key")
    # Default to Haiku for speed and cost efficiency
    # Use claude-sonnet-4-20250514 for complex tasks requiring more reasoning
    model: str = Field(default="claude-3-5-haiku-20241022", description="Claude model to use")

    @field_validator("anthropic_api_key", mode="before")
    @classmethod
    def get_api_key(cls, v):
        """Accept ANTHROPIC_API_KEY env var as fallback (standard name)."""
        if v:
            return v
        # Check standard Anthropic env var name
        return os.environ.get("ANTHROPIC_API_KEY", "")

    # Agent Configuration
    max_agents: int = Field(default=2, ge=1, le=10, description="Maximum concurrent agents")
    agent_timeout_minutes: int = Field(default=30, description="Agent task timeout")
    max_tokens_per_task: int = Field(default=30000, description="Max tokens before trimming conversation")
    max_iterations_per_task: int = Field(default=20, description="Max API calls per task")

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
