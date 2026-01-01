"""Command-line interface for the orchestrator."""

import asyncio
import os
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.tree import Tree

from orchestrator.config import config, OrchestratorConfig
from orchestrator.core.orchestrator import Orchestrator
from orchestrator.models.project import ProjectConfig, GitConfig, CommandsConfig
from orchestrator.models.agent import AgentType

app = typer.Typer(
    name="orchestrate",
    help="Multi-agent orchestration system for autonomous software development",
    add_completion=False,
)
console = Console()


def get_approval(command: str) -> bool:
    """Prompt user for shell command approval."""
    console.print(f"\n[yellow]Shell command requires approval:[/yellow]")
    console.print(f"  [cyan]{command}[/cyan]")
    response = typer.prompt("Allow this command? [y/N]", default="n")
    return response.lower() in ("y", "yes")


async def async_approval(command: str) -> bool:
    """Async wrapper for approval."""
    return get_approval(command)


async def print_progress(event: dict) -> None:
    """Print progress events to console."""
    event_type = event.get("type", "")

    if event_type == "run_start":
        console.print(Panel(
            f"[bold green]Starting orchestration[/bold green]\n"
            f"Project: {event.get('project')}\n"
            f"Instructions: {event.get('instructions')}",
            title="Orchestrator",
        ))

    elif event_type == "decomposing":
        console.print("[cyan]Decomposing instructions into tasks...[/cyan]")

    elif event_type == "tasks_created":
        console.print(f"[green]Created {event.get('count')} tasks:[/green]")
        for task in event.get("tasks", []):
            console.print(f"  - {task['title']}")

    elif event_type == "task_started":
        console.print(
            f"[blue]▶ Starting:[/blue] {event.get('task_title')} "
            f"[dim]({event.get('agent_type')})[/dim]"
        )

    elif event_type == "task_completed":
        console.print(
            f"[green]✓ Completed:[/green] {event.get('summary', 'Task completed')}"
        )
        files = event.get("files_modified", [])
        if files:
            console.print(f"  Files modified: {', '.join(files)}")

    elif event_type == "task_failed":
        console.print(
            f"[red]✗ Failed:[/red] {event.get('error')}"
        )

    elif event_type == "agent_message":
        console.print(
            f"[dim]💬 {event.get('from')} → {event.get('to')}: {event.get('message')}[/dim]"
        )

    elif event_type == "run_complete":
        summary = event.get("summary", {})
        console.print(Panel(
            f"[bold green]Orchestration Complete[/bold green]\n"
            f"Duration: {summary.get('duration_seconds', 0):.1f}s\n"
            f"Tasks: {summary.get('tasks', {})}",
            title="Summary",
        ))

    elif event_type == "error":
        console.print(f"[red]Error: {event.get('error')}[/red]")


@app.command()
def run(
    project: str = typer.Argument(..., help="Project name to work on"),
    instructions: str = typer.Argument(..., help="Instructions for what to build"),
    simple: bool = typer.Option(False, "--simple", "-s", help="Use simple task decomposition"),
    max_agents: int = typer.Option(3, "--max-agents", "-m", help="Maximum concurrent agents"),
    github_token: Optional[str] = typer.Option(None, "--token", "-t", envvar="GITHUB_TOKEN"),
    no_approval: bool = typer.Option(False, "--no-approval", help="Skip shell command approval"),
):
    """Run the orchestrator on a project with given instructions."""
    console.print(f"[bold]Orchestrator[/bold] - Project: {project}")

    # Set up approval callback
    approval_cb = None if no_approval else async_approval

    orchestrator = Orchestrator(
        max_agents=max_agents,
        approval_callback=approval_cb,
        on_progress=print_progress,
    )

    try:
        summary = asyncio.run(orchestrator.run(
            project_name=project,
            instructions=instructions,
            use_llm_decomposition=not simple,
            github_token=github_token,
        ))

        # Print final summary
        if summary.get("failed_tasks"):
            console.print("\n[red]Some tasks failed:[/red]")
            for task in summary["failed_tasks"]:
                console.print(f"  - {task['title']}: {task['error']}")

    except FileNotFoundError as e:
        console.print(f"[red]Error: {e}[/red]")
        console.print(f"Create a project config at: projects/{project}.yaml")
        raise typer.Exit(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
        orchestrator.stop()


@app.command()
def init(
    name: str = typer.Argument(..., help="Project name"),
    repo: str = typer.Option(..., "--repo", "-r", help="GitHub repo (owner/repo)"),
    tech_stack: str = typer.Option("", "--tech", "-t", help="Comma-separated tech stack"),
):
    """Initialize a new project configuration."""
    config_dir = Path("projects")
    config_dir.mkdir(exist_ok=True)

    config_path = config_dir / f"{name}.yaml"
    if config_path.exists():
        console.print(f"[yellow]Project config already exists: {config_path}[/yellow]")
        if not typer.confirm("Overwrite?"):
            raise typer.Exit(0)

    # Create project config
    project_config = ProjectConfig(
        name=name,
        description=f"Configuration for {name}",
        github=GitConfig(repo=repo),
        tech_stack=tech_stack.split(",") if tech_stack else [],
        commands=CommandsConfig(),
    )

    project_config.to_yaml(config_path)
    console.print(f"[green]Created project config: {config_path}[/green]")
    console.print("\nEdit the file to customize commands and settings.")


@app.command()
def list_projects():
    """List all configured projects."""
    config_dir = Path("projects")
    if not config_dir.exists():
        console.print("[yellow]No projects directory found[/yellow]")
        return

    table = Table(title="Configured Projects")
    table.add_column("Name", style="cyan")
    table.add_column("Repository", style="green")
    table.add_column("Tech Stack")

    for config_path in config_dir.glob("*.yaml"):
        try:
            project_config = ProjectConfig.from_yaml(config_path)
            table.add_row(
                project_config.name,
                project_config.github.repo,
                ", ".join(project_config.tech_stack[:3]),
            )
        except Exception as e:
            table.add_row(config_path.stem, f"[red]Error: {e}[/red]", "")

    console.print(table)


@app.command()
def agents():
    """List available agent types."""
    from orchestrator.models.agent import AGENT_CAPABILITIES

    table = Table(title="Agent Types")
    table.add_column("Type", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Skills")
    table.add_column("Primary For")

    for agent_type, caps in AGENT_CAPABILITIES.items():
        table.add_row(
            agent_type.value,
            caps["name"],
            ", ".join(caps["skills"][:3]),
            ", ".join(caps["primary_for"][:3]),
        )

    console.print(table)


@app.command()
def status(
    project: str = typer.Argument(..., help="Project name"),
):
    """Show status of an orchestration run."""
    # Load from latest checkpoint
    checkpoint_dir = config.data_dir / "checkpoints"
    if not checkpoint_dir.exists():
        console.print("[yellow]No checkpoints found[/yellow]")
        return

    checkpoints = sorted(checkpoint_dir.glob("*.json"), reverse=True)
    if not checkpoints:
        console.print("[yellow]No checkpoints found[/yellow]")
        return

    import json
    with open(checkpoints[0]) as f:
        data = json.load(f)

    # Show tasks
    tasks = data.get("tasks", {})
    if not tasks:
        console.print("[yellow]No tasks found[/yellow]")
        return

    table = Table(title=f"Tasks for {project}")
    table.add_column("ID", style="dim")
    table.add_column("Title")
    table.add_column("Status")
    table.add_column("Agent")

    for task_id, task in tasks.items():
        if task.get("project_name") != project:
            continue

        status_style = {
            "completed": "green",
            "in_progress": "blue",
            "failed": "red",
            "queued": "yellow",
        }.get(task.get("status"), "white")

        table.add_row(
            task_id[:8],
            task.get("title", ""),
            f"[{status_style}]{task.get('status')}[/{status_style}]",
            task.get("assigned_agent_id", "-"),
        )

    console.print(table)


@app.command()
def config_show():
    """Show current configuration."""
    tree = Tree("[bold]Orchestrator Configuration[/bold]")

    tree.add(f"API Model: {config.model}")
    tree.add(f"Max Agents: {config.max_agents}")
    tree.add(f"Projects Dir: {config.projects_dir}")
    tree.add(f"Data Dir: {config.data_dir}")
    tree.add(f"Checkpoint Interval: {config.checkpoint_interval_minutes} min")
    tree.add(f"Git Strategy: {config.git_strategy}")
    tree.add(f"Require Shell Approval: {config.require_shell_approval}")

    console.print(tree)


if __name__ == "__main__":
    app()
