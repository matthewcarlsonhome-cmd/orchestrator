"""
Nexus CLI - Command line interface.

Usage:
    nexus serve        # Start the API server
    nexus add "text"   # Quick add content
    nexus ask "question"  # Ask a question
    nexus search "query"  # Search entries
    nexus briefing     # Get daily briefing
"""

import asyncio
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

app = typer.Typer(help="Nexus - Personal AI Assistant")
console = Console()


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Server host"),
    port: int = typer.Option(8430, "--port", "-p", help="Server port"),
):
    """Start the Nexus API server."""
    from nexus.api.main import run_server

    console.print(Panel.fit(
        f"[bold green]Nexus Server[/bold green]\n\n"
        f"API: http://{host}:{port}\n"
        f"Dashboard: http://{host}:{port}\n\n"
        f"Press Ctrl+C to stop",
        title="Starting Nexus"
    ))

    run_server(host=host, port=port)


@app.command()
def add(
    content: str = typer.Argument(..., help="Content to add"),
    tags: str = typer.Option("", "--tags", "-t", help="Comma-separated tags"),
):
    """Add content to your knowledge base."""
    async def _add():
        from nexus.core.nexus import get_nexus
        nexus = get_nexus()
        await nexus.init()

        tag_list = [t.strip() for t in tags.split(",") if t.strip()]
        entry = await nexus.add(content=content, tags=tag_list)

        console.print(f"[green]Added entry:[/green] {entry.id}")
        if entry.tags:
            console.print(f"[dim]Tags: {', '.join(entry.tags)}[/dim]")

    asyncio.run(_add())


@app.command()
def ask(
    question: str = typer.Argument(..., help="Question to ask"),
):
    """Ask a question about your knowledge base."""
    async def _ask():
        from nexus.core.nexus import get_nexus
        nexus = get_nexus()
        await nexus.init()

        console.print("[dim]Thinking...[/dim]")
        response = await nexus.ask(question)

        console.print(Panel(
            response.answer,
            title="[bold]Answer[/bold]",
            border_style="green"
        ))

        if response.sources:
            console.print("\n[bold]Sources:[/bold]")
            for source in response.sources[:3]:
                console.print(f"  • [{source.type.value}] {source.snippet[:100]}...")

    asyncio.run(_ask())


@app.command()
def search(
    query: str = typer.Argument(..., help="Search query"),
    limit: int = typer.Option(10, "--limit", "-n", help="Number of results"),
):
    """Search your knowledge base."""
    async def _search():
        from nexus.core.nexus import get_nexus
        nexus = get_nexus()
        await nexus.init()

        results = await nexus.search(query, limit=limit)

        if results.total == 0:
            console.print("[yellow]No results found[/yellow]")
            return

        table = Table(title=f"Search Results ({results.total})")
        table.add_column("Type", style="cyan")
        table.add_column("Content", style="white")
        table.add_column("Score", style="green")
        table.add_column("Date", style="dim")

        for entry in results.entries:
            table.add_row(
                entry.type.value,
                entry.snippet[:80] + "..." if len(entry.snippet) > 80 else entry.snippet,
                f"{entry.score:.2f}",
                entry.created_at.strftime("%Y-%m-%d"),
            )

        console.print(table)

    asyncio.run(_search())


@app.command()
def briefing(
    briefing_type: str = typer.Argument("daily", help="Briefing type: daily or weekly"),
):
    """Get a personalized briefing."""
    async def _briefing():
        from nexus.core.nexus import get_nexus
        nexus = get_nexus()
        await nexus.init()

        console.print(f"[dim]Generating {briefing_type} briefing...[/dim]")
        result = await nexus.briefing(briefing_type)

        title = "Daily Briefing" if briefing_type == "daily" else "Weekly Review"
        console.print(Panel(
            result,
            title=f"[bold]{title}[/bold]",
            border_style="blue"
        ))

    asyncio.run(_briefing())


@app.command()
def recent(
    limit: int = typer.Option(10, "--limit", "-n", help="Number of entries"),
):
    """Show recent entries."""
    async def _recent():
        from nexus.core.nexus import get_nexus
        nexus = get_nexus()
        await nexus.init()

        entries = await nexus.recent(limit=limit)

        if not entries:
            console.print("[yellow]No entries yet[/yellow]")
            return

        for entry in entries:
            tags = f" [{', '.join(entry.tags)}]" if entry.tags else ""
            console.print(f"[cyan][{entry.type.value}][/cyan]{tags}")
            console.print(f"  {entry.content[:100]}..." if len(entry.content) > 100 else f"  {entry.content}")
            console.print(f"  [dim]{entry.created_at.strftime('%Y-%m-%d %H:%M')}[/dim]\n")

    asyncio.run(_recent())


@app.command()
def stats():
    """Show knowledge base statistics."""
    async def _stats():
        from nexus.core.nexus import get_nexus
        nexus = get_nexus()
        await nexus.init()

        data = await nexus.stats()

        console.print(Panel.fit(
            f"[bold]Total Entries:[/bold] {data['entries']}\n"
            f"[bold]Vector Store:[/bold] {data['vector_store']['backend']} ({data['vector_store']['count']} vectors)\n\n"
            f"[bold]Top Tags:[/bold]\n" +
            "\n".join([f"  #{tag}: {count}" for tag, count in data['top_tags'][:10]]),
            title="Knowledge Base Stats"
        ))

    asyncio.run(_stats())


@app.command()
def init():
    """Initialize Nexus (create directories and database)."""
    async def _init():
        from nexus.core.nexus import get_nexus
        from nexus.config import config

        nexus = get_nexus()
        await nexus.init()

        console.print("[green]Nexus initialized![/green]")
        console.print(f"Data directory: {config.data_dir}")
        console.print(f"Vector DB: {config.vector_db}")
        console.print(f"LLM: {config.llm_provider}")

    asyncio.run(_init())


if __name__ == "__main__":
    app()
