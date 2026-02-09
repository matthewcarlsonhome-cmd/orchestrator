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
"""

from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional, List

from fastapi import FastAPI, HTTPException, UploadFile, File, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from nexus.config import config
from nexus.models.entry import EntryCreate, EntryType, EntrySource, Entry
from nexus.models.query import SearchQuery, AskQuery
from nexus.core.nexus import get_nexus


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


# ==========================================================================
# DASHBOARD HTML
# ==========================================================================

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Nexus - Personal AI Assistant</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body { background: #0f172a; color: #e2e8f0; }
        .glass { background: rgba(30, 41, 59, 0.8); backdrop-filter: blur(10px); }
        .glow { box-shadow: 0 0 20px rgba(99, 102, 241, 0.3); }
    </style>
</head>
<body class="min-h-screen">
    <div class="max-w-6xl mx-auto p-6">
        <!-- Header -->
        <header class="text-center mb-8">
            <h1 class="text-4xl font-bold bg-gradient-to-r from-indigo-400 to-purple-400 bg-clip-text text-transparent">
                Nexus
            </h1>
            <p class="text-slate-400 mt-2">Your Personal AI Assistant</p>
        </header>

        <!-- Main Input -->
        <div class="glass rounded-2xl p-6 mb-6 glow">
            <div class="flex gap-4">
                <div class="flex-1">
                    <textarea id="main-input" rows="3"
                        class="w-full bg-slate-800 border border-slate-600 rounded-xl px-4 py-3 text-white placeholder-slate-400 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 resize-none"
                        placeholder="Add a thought, ask a question, or search your knowledge..."></textarea>
                </div>
            </div>
            <div class="flex gap-3 mt-4">
                <button onclick="quickAdd()" class="px-6 py-2 bg-indigo-600 hover:bg-indigo-700 rounded-lg font-medium transition">
                    + Add
                </button>
                <button onclick="askQuestion()" class="px-6 py-2 bg-purple-600 hover:bg-purple-700 rounded-lg font-medium transition">
                    ? Ask
                </button>
                <button onclick="searchEntries()" class="px-6 py-2 bg-slate-600 hover:bg-slate-700 rounded-lg font-medium transition">
                    Search
                </button>
                <input type="text" id="tags-input" placeholder="Tags (comma separated)"
                    class="flex-1 bg-slate-800 border border-slate-600 rounded-lg px-4 py-2 text-sm placeholder-slate-500">
            </div>
        </div>

        <!-- Response/Results Area -->
        <div id="response-area" class="glass rounded-2xl p-6 mb-6 hidden">
            <div class="flex justify-between items-start mb-4">
                <h2 id="response-title" class="text-xl font-semibold text-indigo-400">Response</h2>
                <button onclick="hideResponse()" class="text-slate-400 hover:text-white">&times;</button>
            </div>
            <div id="response-content" class="prose prose-invert max-w-none">
                <!-- Response will be inserted here -->
            </div>
            <div id="sources-area" class="mt-4 pt-4 border-t border-slate-700 hidden">
                <h3 class="text-sm font-medium text-slate-400 mb-2">Sources</h3>
                <div id="sources-list" class="space-y-2"></div>
            </div>
        </div>

        <!-- Quick Actions -->
        <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <button onclick="getDailyBriefing()" class="glass rounded-xl p-4 text-left hover:bg-slate-700/50 transition">
                <div class="text-2xl mb-2">☀️</div>
                <div class="font-medium">Daily Briefing</div>
                <div class="text-sm text-slate-400">What to focus on today</div>
            </button>
            <button onclick="getWeeklyReview()" class="glass rounded-xl p-4 text-left hover:bg-slate-700/50 transition">
                <div class="text-2xl mb-2">📊</div>
                <div class="font-medium">Weekly Review</div>
                <div class="text-sm text-slate-400">Your week in summary</div>
            </button>
            <button onclick="getRecentEntries()" class="glass rounded-xl p-4 text-left hover:bg-slate-700/50 transition">
                <div class="text-2xl mb-2">🕐</div>
                <div class="font-medium">Recent</div>
                <div class="text-sm text-slate-400">Latest entries</div>
            </button>
            <button onclick="getStats()" class="glass rounded-xl p-4 text-left hover:bg-slate-700/50 transition">
                <div class="text-2xl mb-2">📈</div>
                <div class="font-medium">Stats</div>
                <div class="text-sm text-slate-400">Your knowledge base</div>
            </button>
        </div>

        <!-- Recent Entries -->
        <div class="glass rounded-2xl p-6">
            <h2 class="text-xl font-semibold mb-4">Recent Entries</h2>
            <div id="recent-entries" class="space-y-3">
                <p class="text-slate-400">Loading...</p>
            </div>
        </div>
    </div>

    <script>
        const API_BASE = '';

        async function quickAdd() {
            const content = document.getElementById('main-input').value.trim();
            const tagsInput = document.getElementById('tags-input').value.trim();
            const tags = tagsInput ? tagsInput.split(',').map(t => t.trim()) : [];

            if (!content) {
                alert('Please enter some content');
                return;
            }

            try {
                const res = await fetch(`${API_BASE}/ingest/text`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ content, tags })
                });
                const data = await res.json();

                showResponse('Added', `Entry saved with ID: ${data.id}`, []);
                document.getElementById('main-input').value = '';
                document.getElementById('tags-input').value = '';
                getRecentEntries();
            } catch (e) {
                alert('Error: ' + e.message);
            }
        }

        async function askQuestion() {
            const question = document.getElementById('main-input').value.trim();
            if (!question) {
                alert('Please enter a question');
                return;
            }

            showResponse('Thinking...', 'Processing your question...', []);

            try {
                const res = await fetch(`${API_BASE}/ask`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ question })
                });
                const data = await res.json();

                showResponse('Answer', data.answer, data.sources || []);
            } catch (e) {
                showResponse('Error', 'Failed to get answer: ' + e.message, []);
            }
        }

        async function searchEntries() {
            const query = document.getElementById('main-input').value.trim();
            if (!query) {
                alert('Please enter a search query');
                return;
            }

            try {
                const res = await fetch(`${API_BASE}/search`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ query, limit: 10 })
                });
                const data = await res.json();

                let content = `Found ${data.total} results:\\n\\n`;
                for (const entry of data.entries) {
                    content += `**[${entry.type}]** ${entry.title || 'Untitled'}\\n`;
                    content += `${entry.snippet}\\n`;
                    content += `_${new Date(entry.created_at).toLocaleDateString()}_\\n\\n`;
                }

                showResponse(`Search Results (${data.total})`, content, []);
            } catch (e) {
                showResponse('Error', 'Search failed: ' + e.message, []);
            }
        }

        async function getDailyBriefing() {
            showResponse('Daily Briefing', 'Generating your briefing...', []);
            try {
                const res = await fetch(`${API_BASE}/briefing/daily`);
                const data = await res.json();
                showResponse('Daily Briefing', data.briefing, []);
            } catch (e) {
                showResponse('Error', 'Failed to generate briefing: ' + e.message, []);
            }
        }

        async function getWeeklyReview() {
            showResponse('Weekly Review', 'Generating your review...', []);
            try {
                const res = await fetch(`${API_BASE}/briefing/weekly`);
                const data = await res.json();
                showResponse('Weekly Review', data.briefing, []);
            } catch (e) {
                showResponse('Error', 'Failed to generate review: ' + e.message, []);
            }
        }

        async function getRecentEntries() {
            try {
                const res = await fetch(`${API_BASE}/entries?limit=10`);
                const data = await res.json();

                const container = document.getElementById('recent-entries');
                if (data.entries.length === 0) {
                    container.innerHTML = '<p class="text-slate-400">No entries yet. Add your first thought above!</p>';
                    return;
                }

                container.innerHTML = data.entries.map(entry => `
                    <div class="bg-slate-800/50 rounded-lg p-4 hover:bg-slate-800 transition cursor-pointer" onclick="showEntry('${entry.id}')">
                        <div class="flex justify-between items-start">
                            <div>
                                <span class="text-xs px-2 py-1 bg-indigo-600/30 text-indigo-300 rounded">${entry.type}</span>
                                <span class="text-sm text-slate-400 ml-2">${new Date(entry.created_at).toLocaleDateString()}</span>
                            </div>
                        </div>
                        <p class="mt-2 text-slate-300">${entry.content.substring(0, 200)}${entry.content.length > 200 ? '...' : ''}</p>
                        ${entry.tags.length > 0 ? `<div class="mt-2 flex gap-2">${entry.tags.map(t => `<span class="text-xs text-slate-400">#${t}</span>`).join('')}</div>` : ''}
                    </div>
                `).join('');
            } catch (e) {
                document.getElementById('recent-entries').innerHTML = '<p class="text-red-400">Failed to load entries</p>';
            }
        }

        async function getStats() {
            try {
                const res = await fetch(`${API_BASE}/stats`);
                const data = await res.json();

                let content = `**Total Entries:** ${data.entries}\\n\\n`;
                content += `**Top Tags:**\\n`;
                for (const [tag, count] of data.top_tags.slice(0, 10)) {
                    content += `- #${tag}: ${count}\\n`;
                }
                content += `\\n**Vector Store:** ${data.vector_store.backend} (${data.vector_store.count} vectors)`;

                showResponse('Statistics', content, []);
            } catch (e) {
                showResponse('Error', 'Failed to load stats: ' + e.message, []);
            }
        }

        async function showEntry(id) {
            try {
                const res = await fetch(`${API_BASE}/entries/${id}`);
                const entry = await res.json();

                let content = entry.content;
                if (entry.tags.length > 0) {
                    content += `\\n\\n**Tags:** ${entry.tags.map(t => '#' + t).join(' ')}`;
                }
                content += `\\n\\n_Created: ${new Date(entry.created_at).toLocaleString()}_`;

                showResponse(entry.title || 'Entry', content, []);
            } catch (e) {
                showResponse('Error', 'Failed to load entry', []);
            }
        }

        function showResponse(title, content, sources) {
            document.getElementById('response-area').classList.remove('hidden');
            document.getElementById('response-title').textContent = title;
            document.getElementById('response-content').innerHTML = content.replace(/\\n/g, '<br>').replace(/\\*\\*(.+?)\\*\\*/g, '<strong>$1</strong>');

            const sourcesArea = document.getElementById('sources-area');
            const sourcesList = document.getElementById('sources-list');

            if (sources && sources.length > 0) {
                sourcesArea.classList.remove('hidden');
                sourcesList.innerHTML = sources.map(s => `
                    <div class="text-sm bg-slate-800/50 rounded p-2">
                        <span class="text-indigo-400">[${s.type}]</span> ${s.snippet}
                    </div>
                `).join('');
            } else {
                sourcesArea.classList.add('hidden');
            }
        }

        function hideResponse() {
            document.getElementById('response-area').classList.add('hidden');
        }

        // Handle Enter key
        document.getElementById('main-input').addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && e.ctrlKey) {
                askQuestion();
            } else if (e.key === 'Enter' && e.shiftKey) {
                quickAdd();
            }
        });

        // Load recent entries on page load
        getRecentEntries();
    </script>
</body>
</html>
"""


# ==========================================================================
# APP SETUP
# ==========================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    nexus = get_nexus()
    await nexus.init()
    yield
    # Shutdown
    pass


def create_app() -> FastAPI:
    """Create the FastAPI application."""
    app = FastAPI(
        title="Nexus API",
        description="Personal AI Assistant API",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS
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
        """Serve the dashboard."""
        return DASHBOARD_HTML

    @app.get("/health")
    async def health():
        """Health check."""
        return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}

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

        # Save uploaded file temporarily
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
        """Search entries."""
        nexus = get_nexus()
        results = await nexus.retrieval.search_by_query(query)
        return results

    @app.post("/ask")
    async def ask(query: AskQuery):
        """Ask a question."""
        nexus = get_nexus()
        response = await nexus.response.ask_with_query(query)
        return response

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
        """List entries."""
        nexus = get_nexus()
        types = [EntryType(type)] if type else None
        tags = [tag] if tag else None

        from nexus.storage import get_metadata_store
        store = get_metadata_store()
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
    # BRIEFINGS
    # --------------------------------------------------------------------------

    @app.get("/briefing/{briefing_type}")
    async def get_briefing(briefing_type: str):
        """Get a briefing."""
        if briefing_type not in ("daily", "weekly"):
            raise HTTPException(status_code=400, detail="Invalid briefing type")

        nexus = get_nexus()
        briefing = await nexus.briefing(briefing_type)
        return {"briefing": briefing, "type": briefing_type}

    # --------------------------------------------------------------------------
    # STATS
    # --------------------------------------------------------------------------

    @app.get("/stats")
    async def get_stats():
        """Get statistics."""
        nexus = get_nexus()
        return await nexus.stats()

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
