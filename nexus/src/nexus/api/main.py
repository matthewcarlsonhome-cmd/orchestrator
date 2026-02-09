"""
Nexus API - FastAPI application.

Endpoints:
- POST /ingest - Add content
- POST /search - Search entries
- POST /ask - Ask a question
- GET /entries - List entries
- GET /entries/{id} - Get entry
- DELETE /entries/{id} - Delete entry
- GET /briefing/{type} - Get briefing
- GET /stats - Get statistics
- GET /daily/{date} - Get daily note
- PUT /daily/{date} - Update daily note
- GET /graph - Get knowledge graph data
"""

from contextlib import asynccontextmanager
from datetime import datetime, date, timedelta
from typing import Optional, List

from fastapi import FastAPI, HTTPException, UploadFile, File, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from nexus.config import config
from nexus.models.entry import EntryCreate, EntryType, EntrySource, Entry
from nexus.models.query import SearchQuery, AskQuery
from nexus.core.nexus import get_nexus
from nexus.api.dashboard import DASHBOARD_HTML


# ==========================================================================
# REQUEST/RESPONSE MODELS
# ==========================================================================

class IngestTextRequest(BaseModel):
    content: str
    title: Optional[str] = None
    tags: List[str] = []
    type: EntryType = EntryType.THOUGHT
    event_date: Optional[datetime] = None
    collection_id: Optional[str] = None
    custom_fields: dict = {}


class IngestWebRequest(BaseModel):
    url: str
    title: Optional[str] = None
    content: Optional[str] = None
    tags: List[str] = []


class QuickAddRequest(BaseModel):
    content: str
    tags: List[str] = []


class DailyNoteRequest(BaseModel):
    content: str


class AdvancedSearchRequest(BaseModel):
    query: str
    mode: str = "hybrid"
    types: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    limit: int = 20
    sort: str = "relevance"


# ==========================================================================
# APP SETUP
# ==========================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    print("\n" + "="*60)
    print("  NEXUS - Personal AI Assistant")
    print("="*60)
    print(f"  LLM Provider:     {config.llm_provider}")
    if config.llm_provider == "claude":
        key_status = "CONFIGURED" if config.anthropic_api_key else "NOT SET - Ask/Briefing will fail"
        print(f"  Anthropic API:    {key_status}")
    else:
        key_status = "CONFIGURED" if config.openai_api_key else "NOT SET - Ask/Briefing will fail"
        print(f"  OpenAI API:       {key_status}")
    print(f"  Vector DB:        {config.vector_db}")
    print(f"  Embeddings:       {config.embedding_provider}")
    print(f"  Data Directory:   {config.data_dir}")
    print("="*60 + "\n")

    nexus = get_nexus()
    await nexus.init()
    yield


def create_app() -> FastAPI:
    """Create the FastAPI application."""
    app = FastAPI(
        title="Nexus API",
        description="Personal AI Assistant API",
        version="0.2.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ==========================================================================
    # ROUTES
    # ==========================================================================

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        """Serve the premium dashboard."""
        return DASHBOARD_HTML

    @app.get("/health")
    async def health():
        """Health check - shows configuration status."""
        return {
            "status": "ok",
            "timestamp": datetime.utcnow().isoformat(),
            "version": "0.2.0",
            "config": {
                "llm_provider": config.llm_provider,
                "llm_configured": bool(config.anthropic_api_key) if config.llm_provider == "claude" else bool(config.openai_api_key),
                "vector_db": config.vector_db,
                "embedding_provider": config.embedding_provider,
            }
        }

    # --------------------------------------------------------------------------
    # DAILY NOTES
    # --------------------------------------------------------------------------

    @app.get("/daily/{date_str}")
    async def get_daily_note(date_str: str):
        """Get daily note for a specific date."""
        try:
            target_date = date.fromisoformat(date_str)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

        from nexus.storage import get_metadata_store
        store = get_metadata_store()

        entries = await store.search_entries(
            types=[EntryType.NOTE],
            tags=["daily", date_str],
            limit=1
        )

        if entries:
            return {
                "date": date_str,
                "content": entries[0].content,
                "word_count": len(entries[0].content.split()),
                "entry_id": entries[0].id
            }
        return {"date": date_str, "content": "", "word_count": 0}

    @app.put("/daily/{date_str}")
    async def update_daily_note(date_str: str, request: DailyNoteRequest):
        """Update or create a daily note."""
        try:
            target_date = date.fromisoformat(date_str)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

        from nexus.storage import get_metadata_store
        store = get_metadata_store()

        # Check for existing
        entries = await store.search_entries(
            types=[EntryType.NOTE],
            tags=["daily", date_str],
            limit=1
        )

        if entries:
            # Update existing
            entry = entries[0]
            entry.content = request.content
            entry.updated_at = datetime.utcnow()
            await store.update_entry(entry)
            return {"success": True, "entry_id": entry.id, "action": "updated"}
        else:
            # Create new
            nexus = get_nexus()
            entry = await nexus.ingestion.ingest_text(
                content=request.content,
                title=f"Daily Note - {target_date.strftime('%B %d, %Y')}",
                tags=["daily", date_str],
                entry_type=EntryType.NOTE
            )
            return {"success": True, "entry_id": entry.id, "action": "created"}

    @app.get("/daily/calendar/{year}/{month}")
    async def get_calendar(year: int, month: int):
        """Get calendar data for a month."""
        from nexus.storage import get_metadata_store
        store = get_metadata_store()

        first_day = date(year, month, 1)
        if month == 12:
            last_day = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            last_day = date(year, month + 1, 1) - timedelta(days=1)

        entries = await store.search_entries(
            types=[EntryType.NOTE],
            tags=["daily"],
            date_from=datetime.combine(first_day, datetime.min.time()),
            date_to=datetime.combine(last_day, datetime.max.time()),
            limit=31
        )

        dates_with_entries = []
        for entry in entries:
            for tag in entry.tags:
                if tag.startswith(str(year)):
                    try:
                        date.fromisoformat(tag)
                        dates_with_entries.append(tag)
                    except ValueError:
                        pass

        return {
            "year": year,
            "month": month,
            "days_with_entries": dates_with_entries
        }

    # --------------------------------------------------------------------------
    # INGESTION
    # --------------------------------------------------------------------------

    @app.post("/ingest/text")
    async def ingest_text(request: IngestTextRequest):
        """Ingest text content."""
        nexus = get_nexus()
        entry = await nexus.ingestion.ingest_text(
            content=request.content,
            title=request.title,
            tags=request.tags,
            entry_type=request.type,
            event_date=request.event_date,
            collection_id=request.collection_id,
            custom_fields=request.custom_fields,
        )
        return {"id": entry.id, "type": entry.type.value, "created_at": entry.created_at}

    @app.post("/ingest/quick")
    async def ingest_quick(request: QuickAddRequest):
        """Quick add content."""
        nexus = get_nexus()
        entry = await nexus.add(content=request.content, tags=request.tags)
        return {"id": entry.id, "type": entry.type.value}

    @app.post("/ingest/document")
    async def ingest_document(
        file: UploadFile = File(...),
        tags: str = Query(default=""),
    ):
        """Ingest a document file."""
        import tempfile
        from pathlib import Path

        suffix = Path(file.filename).suffix
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        try:
            nexus = get_nexus()
            tag_list = [t.strip() for t in tags.split(",") if t.strip()]
            entries = await nexus.add_document(tmp_path, tags=tag_list)
            return {"entries": [{"id": e.id} for e in entries], "count": len(entries)}
        finally:
            Path(tmp_path).unlink()

    @app.post("/ingest/web")
    async def ingest_web(request: IngestWebRequest):
        """Ingest a web page."""
        nexus = get_nexus()
        entry = await nexus.add_web_clip(
            url=request.url,
            tags=request.tags,
        )
        return {"id": entry.id, "title": entry.title}

    # --------------------------------------------------------------------------
    # SEARCH & ASK
    # --------------------------------------------------------------------------

    @app.post("/search")
    async def search(query: SearchQuery):
        """Search entries with semantic search."""
        nexus = get_nexus()
        results = await nexus.retrieval.search_by_query(query)
        return results

    @app.post("/search/advanced")
    async def advanced_search(request: AdvancedSearchRequest):
        """Advanced search with filters."""
        from nexus.storage import get_metadata_store
        store = get_metadata_store()

        types = [EntryType(t) for t in request.types] if request.types else None

        entries = await store.search_entries(
            types=types,
            tags=request.tags,
            date_from=request.date_from,
            date_to=request.date_to,
            limit=request.limit,
        )

        # If semantic search requested, also do vector search and merge
        if request.mode in ("semantic", "hybrid"):
            nexus = get_nexus()
            semantic_results = await nexus.retrieval.search(
                query=request.query,
                types=types,
                tags=request.tags,
                limit=request.limit
            )

            if request.mode == "hybrid":
                # Merge results (simple deduplication)
                seen_ids = {e.id for e in entries}
                for result in semantic_results.entries:
                    if result.id not in seen_ids:
                        entries.append(result)

        return {
            "entries": [e.model_dump() for e in entries[:request.limit]],
            "total": len(entries),
            "mode": request.mode
        }

    @app.post("/ask")
    async def ask(query: AskQuery):
        """Ask a question using AI."""
        if not config.anthropic_api_key and config.llm_provider == "claude":
            raise HTTPException(
                status_code=503,
                detail="Anthropic API key not configured. Add ANTHROPIC_API_KEY to your .env file."
            )
        if not config.openai_api_key and config.llm_provider == "openai":
            raise HTTPException(
                status_code=503,
                detail="OpenAI API key not configured. Add OPENAI_API_KEY to your .env file."
            )

        try:
            nexus = get_nexus()
            response = await nexus.response.ask_with_query(query)
            return response
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error generating response: {str(e)}")

    # --------------------------------------------------------------------------
    # ENTRIES
    # --------------------------------------------------------------------------

    @app.get("/entries")
    async def list_entries(
        limit: int = Query(default=20, le=100),
        offset: int = Query(default=0),
        type: Optional[str] = Query(default=None),
        tag: Optional[str] = Query(default=None),
    ):
        """List entries with optional filters."""
        from nexus.storage import get_metadata_store
        store = get_metadata_store()

        types = [EntryType(type)] if type else None
        tags = [tag] if tag else None

        entries = await store.search_entries(
            types=types,
            tags=tags,
            limit=limit,
            offset=offset,
        )
        return {"entries": [e.model_dump() for e in entries], "count": len(entries)}

    @app.get("/entries/{entry_id}")
    async def get_entry(entry_id: str):
        """Get an entry by ID."""
        nexus = get_nexus()
        entry = await nexus.get(entry_id)
        if not entry:
            raise HTTPException(status_code=404, detail="Entry not found")
        return entry.model_dump()

    @app.delete("/entries/{entry_id}")
    async def delete_entry(entry_id: str):
        """Delete an entry."""
        nexus = get_nexus()
        success = await nexus.delete(entry_id)
        if not success:
            raise HTTPException(status_code=404, detail="Entry not found")
        return {"deleted": True}

    # --------------------------------------------------------------------------
    # KNOWLEDGE GRAPH
    # --------------------------------------------------------------------------

    @app.get("/graph")
    async def get_graph(limit: int = Query(default=100, le=500)):
        """Get knowledge graph data for visualization."""
        from nexus.storage import get_metadata_store
        store = get_metadata_store()

        entries = await store.search_entries(limit=limit)

        nodes = []
        links = []
        tag_to_entries = {}

        for entry in entries:
            nodes.append({
                "id": entry.id,
                "title": entry.title or entry.content[:40] + "...",
                "type": entry.type.value,
                "tags": entry.tags,
                "created_at": entry.created_at.isoformat()
            })

            for tag in entry.tags:
                if tag not in tag_to_entries:
                    tag_to_entries[tag] = []
                tag_to_entries[tag].append(entry.id)

        # Create links between entries with shared tags
        for tag, entry_ids in tag_to_entries.items():
            for i, source_id in enumerate(entry_ids):
                for target_id in entry_ids[i + 1:]:
                    links.append({
                        "source": source_id,
                        "target": target_id,
                        "tag": tag
                    })

        return {"nodes": nodes, "links": links}

    # --------------------------------------------------------------------------
    # BRIEFINGS
    # --------------------------------------------------------------------------

    @app.get("/briefing/{briefing_type}")
    async def get_briefing(briefing_type: str):
        """Get AI-generated briefing."""
        if briefing_type not in ("daily", "weekly"):
            raise HTTPException(status_code=400, detail="Invalid briefing type")

        if not config.anthropic_api_key and config.llm_provider == "claude":
            raise HTTPException(
                status_code=503,
                detail="Anthropic API key not configured. Add ANTHROPIC_API_KEY to your .env file."
            )

        try:
            nexus = get_nexus()
            briefing = await nexus.briefing(briefing_type)
            return {"briefing": briefing, "type": briefing_type}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error generating briefing: {str(e)}")

    # --------------------------------------------------------------------------
    # STATS
    # --------------------------------------------------------------------------

    @app.get("/stats")
    async def get_stats():
        """Get comprehensive statistics."""
        from nexus.storage import get_metadata_store
        store = get_metadata_store()

        try:
            # Get all entries for stats
            all_entries = await store.search_entries(limit=1000)

            # Calculate stats
            total = len(all_entries)

            # This week
            week_ago = datetime.utcnow() - timedelta(days=7)
            this_week = sum(1 for e in all_entries if e.created_at > week_ago)

            # Top tags
            tag_counts = {}
            for entry in all_entries:
                for tag in entry.tags:
                    if tag not in ["daily"] and not tag.startswith("202"):
                        tag_counts[tag] = tag_counts.get(tag, 0) + 1

            top_tags = sorted(tag_counts.items(), key=lambda x: -x[1])[:10]

            # Entry types
            type_counts = {}
            for entry in all_entries:
                t = entry.type.value
                type_counts[t] = type_counts.get(t, 0) + 1

            # Streak calculation (simplified)
            streak = 0
            check_date = date.today()
            daily_dates = {tag for e in all_entries for tag in e.tags if tag.startswith("202")}
            while check_date.isoformat() in daily_dates:
                streak += 1
                check_date -= timedelta(days=1)

            return {
                "entries": total,
                "week": this_week,
                "streak": streak,
                "top_tags": top_tags,
                "types": type_counts,
                "vector_store": {
                    "backend": config.vector_db,
                    "count": total
                }
            }
        except Exception as e:
            return {
                "entries": 0,
                "week": 0,
                "streak": 0,
                "top_tags": [],
                "types": {},
                "vector_store": {"backend": config.vector_db, "count": 0},
                "error": str(e)
            }

    return app


# Create app instance
app = create_app()


def run_server(host: str = None, port: int = None):
    """Run the server."""
    import uvicorn
    uvicorn.run(
        app,
        host=host or config.api_host,
        port=port or config.api_port,
    )
