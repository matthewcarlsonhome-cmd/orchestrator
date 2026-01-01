"""FastAPI application for the orchestrator dashboard."""

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from orchestrator.config import config
from orchestrator.core.orchestrator import Orchestrator
from orchestrator.core.checkpoint import CheckpointManager
from orchestrator.core.health import HealthMonitor


# Global orchestrator instance
_orchestrator: Optional[Orchestrator] = None
_checkpoint_manager: Optional[CheckpointManager] = None
_health_monitor: Optional[HealthMonitor] = None
_connected_websockets: list[WebSocket] = []


class RunRequest(BaseModel):
    """Request to start an orchestration run."""
    project: str
    instructions: str
    use_llm_decomposition: bool = True
    timeout_minutes: int = 240


class ProjectConfig(BaseModel):
    """Project configuration."""
    name: str
    repo: str
    tech_stack: list[str] = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global _orchestrator, _checkpoint_manager, _health_monitor

    # Initialize components
    _orchestrator = Orchestrator(
        on_progress=broadcast_progress,
    )
    _checkpoint_manager = CheckpointManager()
    _health_monitor = HealthMonitor(
        agent_pool=_orchestrator.agent_pool,
        on_system_degraded=on_system_degraded,
    )

    # Start health monitor
    await _health_monitor.start()

    yield

    # Cleanup
    if _health_monitor:
        await _health_monitor.stop()
    if _orchestrator and _orchestrator.running:
        await _orchestrator.shutdown()


async def broadcast_progress(event: dict) -> None:
    """Broadcast progress events to all connected WebSocket clients."""
    disconnected = []
    for ws in _connected_websockets:
        try:
            await ws.send_json(event)
        except Exception:
            disconnected.append(ws)

    # Remove disconnected clients
    for ws in disconnected:
        _connected_websockets.remove(ws)


async def on_system_degraded(health) -> None:
    """Handle system degradation."""
    await broadcast_progress({
        "type": "system_health",
        "status": health.status.value,
        "issues": health.issues,
        "timestamp": datetime.utcnow().isoformat(),
    })


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Orchestrator API",
        description="Multi-agent orchestration system API",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS middleware for dashboard
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # In production, restrict this
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routes
    @app.get("/")
    async def root():
        """API root."""
        return {
            "name": "Orchestrator API",
            "version": "0.1.0",
            "status": "running" if _orchestrator and _orchestrator.running else "idle",
        }

    @app.get("/health")
    async def health():
        """Get system health."""
        if not _health_monitor:
            return {"status": "unknown"}
        return _health_monitor.get_health_summary()

    @app.get("/status")
    async def status():
        """Get orchestrator status."""
        if not _orchestrator:
            raise HTTPException(status_code=503, detail="Orchestrator not initialized")
        return _orchestrator.get_status()

    @app.get("/projects")
    async def list_projects():
        """List configured projects."""
        from pathlib import Path
        from orchestrator.models.project import ProjectConfig as PC

        projects = []
        config_dir = Path("projects")

        if config_dir.exists():
            for path in config_dir.glob("*.yaml"):
                try:
                    proj = PC.from_yaml(path)
                    projects.append({
                        "name": proj.name,
                        "repo": proj.github.repo,
                        "tech_stack": proj.tech_stack,
                    })
                except Exception as e:
                    projects.append({
                        "name": path.stem,
                        "error": str(e),
                    })

        return {"projects": projects}

    @app.post("/run")
    async def run(request: RunRequest, background_tasks: BackgroundTasks):
        """Start an orchestration run."""
        if not _orchestrator:
            raise HTTPException(status_code=503, detail="Orchestrator not initialized")

        if _orchestrator.running:
            raise HTTPException(status_code=409, detail="Orchestrator already running")

        # Run in background
        background_tasks.add_task(
            _orchestrator.run,
            project_name=request.project,
            instructions=request.instructions,
            use_llm_decomposition=request.use_llm_decomposition,
            timeout_minutes=request.timeout_minutes,
        )

        return {
            "status": "started",
            "project": request.project,
            "instructions": request.instructions,
        }

    @app.post("/stop")
    async def stop():
        """Stop the current run."""
        if not _orchestrator:
            raise HTTPException(status_code=503, detail="Orchestrator not initialized")

        if not _orchestrator.running:
            raise HTTPException(status_code=409, detail="Orchestrator not running")

        _orchestrator.stop()
        return {"status": "stopping"}

    @app.get("/tasks")
    async def get_tasks():
        """Get all tasks."""
        if not _orchestrator:
            return {"tasks": []}

        tasks = []
        for task_id, task in _orchestrator.scheduler.tasks.items():
            tasks.append({
                "id": task.id,
                "title": task.title,
                "status": task.status.value,
                "agent_type": task.agent_type_hint.value,
                "assigned_agent": task.assigned_agent_id,
                "created_at": task.created_at.isoformat(),
                "started_at": task.started_at.isoformat() if task.started_at else None,
                "completed_at": task.completed_at.isoformat() if task.completed_at else None,
            })

        return {"tasks": tasks}

    @app.get("/agents")
    async def get_agents():
        """Get all agents."""
        if not _orchestrator:
            return {"agents": []}

        agents = []
        for agent_id, agent in _orchestrator.agent_pool.agents.items():
            agents.append({
                "id": agent.id,
                "type": agent.agent_type.value,
                "status": agent.status.value,
                "current_task": agent.current_task_id,
                "tasks_completed": agent.tasks_completed,
                "errors_count": agent.errors_count,
                "last_heartbeat": agent.last_heartbeat.isoformat(),
            })

        return {"agents": agents}

    @app.get("/checkpoints")
    async def get_checkpoints():
        """Get available checkpoints."""
        if not _checkpoint_manager:
            return {"checkpoints": []}

        checkpoints = _checkpoint_manager.list_checkpoints()
        return {
            "checkpoints": [
                {
                    "id": c.id,
                    "timestamp": c.timestamp.isoformat(),
                    "project": c.project,
                    "tasks_total": c.tasks_total,
                    "tasks_completed": c.tasks_completed,
                    "size_mb": round(c.size_bytes / (1024 * 1024), 2),
                }
                for c in checkpoints
            ],
            "stats": _checkpoint_manager.get_stats(),
        }

    @app.post("/checkpoints/{checkpoint_id}/restore")
    async def restore_checkpoint(checkpoint_id: str):
        """Restore from a checkpoint."""
        if not _checkpoint_manager:
            raise HTTPException(status_code=503, detail="Checkpoint manager not initialized")

        if _orchestrator and _orchestrator.running:
            raise HTTPException(status_code=409, detail="Cannot restore while running")

        state = await _checkpoint_manager.load(checkpoint_id)
        if not state:
            raise HTTPException(status_code=404, detail="Checkpoint not found")

        # TODO: Implement state restoration
        return {"status": "restored", "checkpoint_id": checkpoint_id}

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        """WebSocket endpoint for real-time updates."""
        await websocket.accept()
        _connected_websockets.append(websocket)

        try:
            while True:
                # Keep connection alive and receive any commands
                data = await websocket.receive_json()

                # Handle commands
                if data.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
                elif data.get("type") == "get_status":
                    if _orchestrator:
                        await websocket.send_json({
                            "type": "status",
                            "data": _orchestrator.get_status(),
                        })

        except WebSocketDisconnect:
            pass
        finally:
            if websocket in _connected_websockets:
                _connected_websockets.remove(websocket)

    return app


# Create default app instance
app = create_app()


def run_server(host: str = "127.0.0.1", port: int = 8420):
    """Run the API server."""
    import uvicorn
    uvicorn.run(app, host=host, port=port)
