"""Project model and configuration."""

from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field


class GitConfig(BaseModel):
    """Git repository configuration."""

    repo: str = Field(..., description="GitHub repo in format 'owner/repo'")
    default_branch: str = Field(default="main", description="Default branch name")
    work_branch: str = Field(default="dev", description="Branch for agent work")
    clone_url: Optional[str] = Field(default=None, description="Full clone URL (auto-generated)")

    def get_clone_url(self) -> str:
        """Get the HTTPS clone URL."""
        if self.clone_url:
            return self.clone_url
        return f"https://github.com/{self.repo}.git"


class CommandsConfig(BaseModel):
    """Project commands configuration."""

    install: Optional[str] = Field(default=None, description="Install dependencies command")
    dev: Optional[str] = Field(default=None, description="Start dev server command")
    build: Optional[str] = Field(default=None, description="Build command")
    test: Optional[str] = Field(default=None, description="Run tests command")
    lint: Optional[str] = Field(default=None, description="Lint command")
    custom: dict[str, str] = Field(default_factory=dict, description="Custom commands")


class ProjectConfig(BaseModel):
    """Configuration for a project (loaded from YAML)."""

    name: str = Field(..., description="Project identifier")
    description: Optional[str] = Field(default=None, description="Project description")
    github: GitConfig = Field(..., description="GitHub configuration")
    local_path: Optional[Path] = Field(default=None, description="Local clone path")
    tech_stack: list[str] = Field(default_factory=list, description="Technologies used")
    commands: CommandsConfig = Field(default_factory=CommandsConfig)
    entry_points: list[str] = Field(
        default_factory=lambda: ["src", "app", "lib"],
        description="Key directories to explore",
    )
    ignore_patterns: list[str] = Field(
        default_factory=lambda: ["node_modules", ".git", "__pycache__", "dist", "build"],
        description="Patterns to ignore when exploring",
    )

    @classmethod
    def from_yaml(cls, path: Path) -> "ProjectConfig":
        """Load project config from YAML file."""
        with open(path) as f:
            data = yaml.safe_load(f)
        return cls(**data)

    def to_yaml(self, path: Path) -> None:
        """Save project config to YAML file."""
        with open(path, "w") as f:
            yaml.dump(self.model_dump(mode="json"), f, default_flow_style=False)


class Project(BaseModel):
    """Runtime project state."""

    config: ProjectConfig
    local_path: Path = Field(..., description="Local path where project is cloned")
    current_branch: str = Field(default="main", description="Current working branch")
    is_cloned: bool = Field(default=False, description="Whether project is cloned locally")
    last_synced: Optional[datetime] = Field(default=None, description="Last git sync time")

    # Runtime context discovered by agents
    discovered_context: dict = Field(
        default_factory=dict,
        description="Context discovered during analysis (file structure, patterns, etc.)",
    )

    @property
    def name(self) -> str:
        return self.config.name

    def get_agent_branch_name(self, agent_id: str, task_id: str) -> str:
        """Generate a branch name for an agent working on a task."""
        return f"agent/{agent_id}-{task_id[:8]}"

    def model_post_init(self, __context) -> None:
        """Set local_path from config if not provided."""
        if self.config.local_path:
            object.__setattr__(self, "local_path", self.config.local_path)
