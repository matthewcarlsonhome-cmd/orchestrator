# Nexus - Personal AI Assistant Platform

A frontend-agnostic personal AI assistant that learns from everything you give it and provides intelligent, personalized recommendations.

## Features

- **Universal Knowledge Base**: Store notes, documents, bookmarks, voice memos, and more
- **Semantic Search**: Find anything by meaning, not just keywords
- **Intelligent Q&A**: Ask questions and get answers with citations from your knowledge
- **Personalized Recommendations**: Workouts, recipes, travel, gifts, work efficiency
- **Autonomous Agents**: Daily briefings, weekly reviews, pattern detection
- **Custom Collections**: Create your own structured data types
- **Multiple Frontends**: Web dashboard, CLI, REST API for custom integrations

---

## Quick Start

### Prerequisites

- Python 3.10 or higher
- An Anthropic API key (for LLM features) - [Get one here](https://console.anthropic.com/)

### Installation

#### Option 1: Automated Setup (Recommended)

**Windows:**
```batch
cd nexus
start.bat
```

**Linux/macOS:**
```bash
cd nexus
chmod +x start.sh
./start.sh
```

#### Option 2: Manual Setup

```bash
# 1. Navigate to nexus directory
cd nexus

# 2. Create virtual environment
python -m venv venv

# 3. Activate it
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# 4. Install Nexus
pip install -e .

# 5. Copy and configure environment
cp .env.example .env
# Edit .env with your API keys

# 6. Initialize and start
nexus init
nexus serve
```

### First Run

1. Open your browser to **http://127.0.0.1:8430**
2. Use the Quick Add box to add your first note
3. Try searching or asking questions
4. Explore the API docs at **http://127.0.0.1:8430/docs**

---

## Configuration Guide

All configuration is done through the `.env` file. Here are the key customization points:

### Vector Database

| Option | Description | Best For |
|--------|-------------|----------|
| `chromadb` (default) | Local, file-based | Personal use, privacy-focused |
| `pinecone` | Cloud-hosted | Scale, team access, backup |

**To switch to Pinecone:**
```env
NEXUS_VECTOR_DB=pinecone
PINECONE_API_KEY=your-api-key
PINECONE_INDEX=nexus
PINECONE_ENVIRONMENT=us-east-1
```

### Embedding Provider

| Option | Description | Cost | Quality |
|--------|-------------|------|---------|
| `local` (default) | sentence-transformers on your machine | Free | Good |
| `openai` | OpenAI's text-embedding-3-small | ~$0.02/1M tokens | Great |
| `voyage` | Voyage AI embeddings | ~$0.10/1M tokens | Best |

**To switch to OpenAI embeddings:**
```env
NEXUS_EMBEDDING_PROVIDER=openai
OPENAI_API_KEY=sk-...
NEXUS_EMBEDDING_MODEL=text-embedding-3-small
```

### LLM Provider

| Option | Description | Best For |
|--------|-------------|----------|
| `claude` (default) | Anthropic Claude | Quality reasoning, longer context |
| `openai` | OpenAI GPT-4o | Speed, existing OpenAI setup |

**To switch to OpenAI:**
```env
NEXUS_LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
NEXUS_LLM_MODEL=gpt-4o
```

### Metadata Database

| Option | Description | Best For |
|--------|-------------|----------|
| `sqlite` (default) | Local SQLite file | Single user, simplicity |
| `postgresql` | PostgreSQL server | Production, multiple users |

**To switch to PostgreSQL:**
```env
NEXUS_METADATA_DB=postgresql
DATABASE_URL=postgresql://user:password@localhost:5432/nexus
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     NEXUS ARCHITECTURE                       │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│   ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐       │
│   │   Web   │  │   CLI   │  │   API   │  │ Mobile  │       │
│   │Dashboard│  │         │  │ Client  │  │  App    │       │
│   └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘       │
│        │            │            │            │              │
│        └────────────┴────────────┴────────────┘              │
│                          │                                   │
│                    ┌─────┴─────┐                            │
│                    │  REST API │ (FastAPI)                  │
│                    └─────┬─────┘                            │
│                          │                                   │
│        ┌─────────────────┼─────────────────┐                │
│        │                 │                 │                 │
│   ┌────┴────┐      ┌─────┴─────┐     ┌────┴────┐           │
│   │Ingestion│      │ Retrieval │     │Response │           │
│   │ Service │      │  Service  │     │ Service │           │
│   └────┬────┘      └─────┬─────┘     └────┬────┘           │
│        │                 │                 │                 │
│   ┌────┴─────────────────┴─────────────────┴────┐           │
│   │                  NEXUS CORE                  │           │
│   └─────────────────────┬───────────────────────┘           │
│                         │                                    │
│    ┌────────────────────┼────────────────────┐              │
│    │                    │                    │               │
│ ┌──┴───┐          ┌─────┴─────┐        ┌────┴────┐         │
│ │Vector│          │ Metadata  │        │Embedding│         │
│ │  DB  │          │    DB     │        │Provider │         │
│ └──────┘          └───────────┘        └─────────┘         │
│ ChromaDB/          SQLite/              Local/              │
│ Pinecone          PostgreSQL        OpenAI/Voyage          │
│                                                              │
│   ┌─────────────────────────────────────────────────────┐   │
│   │                 AGENT SCHEDULER                      │   │
│   │  Daily Briefing │ Weekly Review │ Pattern Detection │   │
│   └─────────────────────────────────────────────────────┘   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## CLI Commands

```bash
# Start the server
nexus serve [--host HOST] [--port PORT]

# Add content
nexus add "Meeting notes: discussed Q1 roadmap" --tags "work,meetings"

# Search your knowledge
nexus search "roadmap planning"

# Ask a question (uses LLM)
nexus ask "What were the key points from my recent meetings?"

# Get briefings
nexus briefing daily
nexus briefing weekly

# Show recent entries
nexus recent --limit 20

# Show statistics
nexus stats

# Initialize/reset
nexus init
```

---

## API Endpoints

### Ingestion

```bash
# Add text
POST /ingest/text
{
  "content": "Your note or content here",
  "tags": ["tag1", "tag2"],
  "type": "note",
  "source": "manual"
}

# Add document (PDF, etc.)
POST /ingest/document
Content-Type: multipart/form-data
file: <your-file>
```

### Search & Query

```bash
# Semantic search
POST /search
{
  "query": "your search query",
  "limit": 10,
  "types": ["note", "document"],
  "tags": ["specific-tag"]
}

# Ask a question (LLM-powered)
POST /ask
{
  "question": "What did I learn about X?",
  "context_limit": 5
}
```

### Management

```bash
# List entries
GET /entries?limit=20&offset=0

# Get stats
GET /stats

# Generate briefing
GET /briefing/daily
GET /briefing/weekly
```

Full API documentation available at **http://127.0.0.1:8430/docs**

---

## Custom Collections

Create structured collections for specific data types:

```python
from nexus.models.collection import Collection, CollectionField, FieldType

# Example: Book tracking collection
BOOKS_COLLECTION = Collection(
    id="books",
    name="Reading List",
    description="Track books I'm reading",
    entry_type="book",
    fields=[
        CollectionField(name="title", type=FieldType.TEXT, required=True),
        CollectionField(name="author", type=FieldType.TEXT, required=True),
        CollectionField(name="rating", type=FieldType.NUMBER),
        CollectionField(name="date_finished", type=FieldType.DATE),
        CollectionField(name="notes", type=FieldType.TEXT),
    ],
    default_tags=["books", "reading"]
)
```

---

## Built-in Agents

| Agent | Schedule | Purpose |
|-------|----------|---------|
| Daily Briefing | 7 AM daily | Summarize recent activity, upcoming tasks |
| Weekly Review | Sunday 6 PM | Patterns, achievements, suggestions |
| Insight Detector | Every 6 hours | Find connections between entries |
| Reminder | Hourly | Check for time-sensitive items |

Enable/disable agents in `.env`:
```env
NEXUS_AGENTS_ENABLED=true
```

---

## Data Storage

Default location: `~/.nexus/`

```
~/.nexus/
├── nexus.db          # SQLite metadata
├── chroma/           # ChromaDB vector store
├── uploads/          # Uploaded documents
└── cache/            # Temporary files
```

To change location:
```env
NEXUS_DATA_DIR=/path/to/your/data
```

---

## Extending Nexus

### Adding a New Embedding Provider

Edit `src/nexus/storage/embeddings.py`:

```python
class MyCustomEmbeddingProvider(EmbeddingProvider):
    def __init__(self, config):
        self.model = load_my_model()

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return self.model.encode(texts)
```

### Adding a New Agent

Edit `src/nexus/models/agent.py`:

```python
MY_AGENT = AgentConfig(
    id="my-agent",
    name="My Custom Agent",
    description="Does something useful",
    schedule=ScheduleConfig(
        type=ScheduleType.CRON,
        cron="0 12 * * *"  # Noon daily
    ),
    prompt_template="Analyze {context} and provide insights..."
)
```

### Adding a New Entry Type

Edit `src/nexus/models/entry.py`:

```python
class EntryType(str, Enum):
    # ... existing types ...
    RECIPE = "recipe"
    WORKOUT = "workout"
```

---

## Troubleshooting

### "No module named 'nexus'"
Make sure you installed with `pip install -e .` from the nexus directory.

### "ANTHROPIC_API_KEY not set"
Edit your `.env` file and add your Anthropic API key.

### Slow first search
Local embeddings download a ~400MB model on first use. Subsequent runs are fast.

### Port already in use
Change the port in `.env`:
```env
NEXUS_PORT=8431
```

### Reset everything
```bash
rm -rf ~/.nexus
nexus init
```

---

## License

MIT License - See LICENSE file for details.

---

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

---

Built with FastAPI, ChromaDB, and Claude.
