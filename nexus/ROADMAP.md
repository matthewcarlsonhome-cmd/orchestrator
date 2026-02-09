# Nexus Development Roadmap

> Comprehensive plan to transform Nexus from prototype to production-ready personal AI assistant.

**Created:** 2026-02-09
**Status:** Active Development

---

## Competitor Analysis

| App | Strengths | Key Feature to Adopt |
|-----|-----------|---------------------|
| **Mem.ai** | Auto-organization, knowledge graph | Smart collections, automatic tagging |
| **Notion AI** | Templates, databases, views | Structured data, templates |
| **Obsidian** | Graph view, backlinks, plugins | Connection visualization, daily notes |
| **Reflect** | Quick capture, AI summaries | Frictionless input, instant sync |
| **Readwise** | Import highlights, spaced repetition | Daily review emails, import integrations |
| **Rewind** | Timeline, automatic capture | Chronological view, search history |
| **Personal.ai** | Memory stacking, AI personas | Contextual personas, draft generation |

---

## Phase 0: Stabilization (IMMEDIATE - Week 1)

**Goal:** Make the app reliably usable day-to-day.

### 0.1 Fix Core Functionality
- [x] Fix API key loading (support both ANTHROPIC_API_KEY and NEXUS_ANTHROPIC_API_KEY)
- [x] Add proper error messages instead of 500 errors
- [x] Add startup health check logging
- [ ] Fix /stats endpoint to handle empty database
- [ ] Ensure entries persist across restarts
- [ ] Add entry count to dashboard
- [ ] Show success/failure feedback on Add button

### 0.2 Improve Dashboard UX
- [ ] Show list of recent entries below input
- [ ] Add delete button for entries
- [ ] Add edit functionality for entries
- [ ] Show tags on entries
- [ ] Add loading spinners for async operations
- [ ] Add toast notifications for success/error

### 0.3 Data Reliability
- [ ] Add database backup command
- [ ] Add export to JSON functionality
- [ ] Add import from JSON functionality
- [ ] Verify ChromaDB persistence path works on Windows

---

## Phase 1: Daily Driver Features (Weeks 2-3)

**Goal:** Features that make you want to use it every day.

### 1.1 Daily Notes
```
GET /daily - Get or create today's note
POST /daily - Append to today's note
GET /daily/{date} - Get note for specific date
```
- [ ] Automatic daily note creation
- [ ] Append-only mode for quick capture
- [ ] Calendar view of daily notes
- [ ] Daily note template system

### 1.2 Quick Capture Improvements
- [ ] Keyboard shortcut (global hotkey via companion app)
- [ ] Browser extension for web clipping
- [ ] Email-to-Nexus (receive emails at a unique address)
- [ ] Telegram/Discord bot integration
- [ ] Mobile-responsive PWA

### 1.3 Smart Tagging
- [ ] Auto-suggest tags based on content
- [ ] Auto-categorize entry types (note vs task vs idea)
- [ ] Extract entities (people, places, dates)
- [ ] Link detection and metadata fetching

### 1.4 Search Improvements
- [ ] Search history
- [ ] Saved searches / filters
- [ ] Full-text search (not just semantic)
- [ ] Search within date range
- [ ] Search by multiple tags (AND/OR)

---

## Phase 2: Intelligence Layer (Weeks 4-5)

**Goal:** AI that provides genuine value.

### 2.1 Daily Digest Email
```
POST /settings/digest
{
  "enabled": true,
  "time": "07:00",
  "email": "user@example.com",
  "include": ["summary", "tasks", "insights"]
}
```
- [ ] Morning briefing email at configured time
- [ ] Weekly review email on Sundays
- [ ] Configurable sections (summary, tasks, insights, random memory)
- [ ] SMTP configuration for sending

### 2.2 Smarter Responses
- [ ] Remember conversation context within session
- [ ] Learn user preferences over time
- [ ] Cite specific entries with links
- [ ] Ask clarifying questions when needed
- [ ] Suggest related entries after answering

### 2.3 Proactive Insights
- [ ] "This reminds me of X you noted last month"
- [ ] Pattern detection ("You often write about X on Mondays")
- [ ] Forgotten follow-ups ("You said you'd check on X")
- [ ] Anniversary reminders ("One year ago you...")

### 2.4 Task Extraction
- [ ] Auto-extract action items from notes
- [ ] Task list view
- [ ] Due date parsing ("by Friday" → actual date)
- [ ] Task completion tracking
- [ ] Overdue task notifications

---

## Phase 3: Connections & Visualization (Weeks 6-7)

**Goal:** See relationships between your knowledge.

### 3.1 Backlinks
- [ ] [[wiki-style]] linking syntax
- [ ] Auto-link detection based on content similarity
- [ ] "Entries that reference this" panel
- [ ] Bidirectional link creation

### 3.2 Knowledge Graph
- [ ] D3.js graph visualization
- [ ] Cluster by tags/topics
- [ ] Click to navigate
- [ ] Filter by date range
- [ ] Zoom and pan

### 3.3 Timeline View
- [ ] Chronological entry browser
- [ ] Filter by type/tag
- [ ] Infinite scroll
- [ ] Jump to date

### 3.4 Collections 2.0
- [ ] Custom field types (date, number, URL, rating)
- [ ] Collection templates (Book, Recipe, Workout, etc.)
- [ ] Collection-specific views (table, kanban, gallery)
- [ ] Collection statistics

---

## Phase 4: Import & Export (Week 8)

**Goal:** Get data in and out easily.

### 4.1 Import Sources
- [ ] Notion export (markdown + CSV)
- [ ] Obsidian vault (markdown files)
- [ ] Apple Notes (via export)
- [ ] Readwise highlights (API)
- [ ] Pocket bookmarks (API)
- [ ] Twitter/X bookmarks
- [ ] Browser bookmarks (Chrome, Firefox)
- [ ] CSV/JSON bulk import

### 4.2 Export Options
- [ ] Full backup to JSON
- [ ] Export to Markdown files
- [ ] Export to Obsidian-compatible vault
- [ ] Export specific date range
- [ ] Export specific tags/collections

### 4.3 Sync
- [ ] Optional cloud sync (user provides storage)
- [ ] Conflict resolution
- [ ] Multi-device support

---

## Phase 5: Personalization (Weeks 9-10)

**Goal:** Make it feel like YOUR assistant.

### 5.1 User Profiles
- [ ] Name, preferences, communication style
- [ ] Timezone handling
- [ ] Theme selection (dark/light/custom)
- [ ] Dashboard layout customization

### 5.2 AI Personas
- [ ] Default assistant persona
- [ ] "Coach" mode for motivation
- [ ] "Editor" mode for writing help
- [ ] "Analyst" mode for data insights
- [ ] Custom persona creation

### 5.3 Templates
- [ ] Daily note template
- [ ] Meeting notes template
- [ ] Weekly review template
- [ ] Custom template creation
- [ ] Template variables (date, random entry, etc.)

### 5.4 Automations
- [ ] "When I add entry with tag X, also add tag Y"
- [ ] "Every Monday at 9am, create weekly planning note"
- [ ] "When entry contains 'TODO', extract task"
- [ ] Webhook triggers for external integrations

---

## Phase 6: Platform Expansion (Weeks 11-12)

**Goal:** Use Nexus everywhere.

### 6.1 Mobile PWA
- [ ] Responsive design optimization
- [ ] Offline support with sync
- [ ] Add to home screen
- [ ] Push notifications

### 6.2 Desktop App (Electron)
- [ ] Global hotkey for quick capture
- [ ] Menu bar/system tray
- [ ] Auto-start on boot
- [ ] Local file watching

### 6.3 Browser Extension
- [ ] One-click save current page
- [ ] Highlight and save selection
- [ ] Auto-capture reading history (optional)
- [ ] Quick search popup

### 6.4 API Expansion
- [ ] Webhooks for entry events
- [ ] OAuth for third-party apps
- [ ] Rate limiting
- [ ] API key management

---

## Technical Debt & Infrastructure

### Performance
- [ ] Implement caching layer (Redis)
- [ ] Optimize embedding generation (batch processing)
- [ ] Add database indexing
- [ ] Implement pagination everywhere

### Reliability
- [ ] Add comprehensive error logging
- [ ] Implement retry logic for API calls
- [ ] Add health monitoring
- [ ] Set up automated backups

### Security
- [ ] Add authentication (optional)
- [ ] Encrypt sensitive data at rest
- [ ] Audit logging
- [ ] Rate limiting

### Testing
- [ ] Unit tests for core functions
- [ ] Integration tests for API
- [ ] End-to-end tests for dashboard
- [ ] Load testing

---

## Quick Wins (Can Do Anytime)

These are small improvements that provide immediate value:

1. **Add favicon** - Stop the 404 error
2. **Remember last search** - Persist in localStorage
3. **Keyboard shortcuts** - Ctrl+Enter to submit
4. **Entry timestamps** - Show "2 hours ago" not full date
5. **Tag autocomplete** - Suggest existing tags
6. **Dark/light toggle** - Quick theme switch
7. **Entry count badge** - Show total in header
8. **Random memory** - "Show me something from my past"
9. **Copy entry button** - Easy clipboard access
10. **Markdown preview** - Render markdown in entries

---

## Metrics to Track

1. **Daily active usage** - Are you using it every day?
2. **Entries per day** - Are you capturing enough?
3. **Search usage** - Are you finding things?
4. **Ask usage** - Is the AI helpful?
5. **Entry retention** - Are old entries still valuable?

---

## Recommended Priority Order

```
Phase 0 (Stabilization) → immediately, before anything else
Phase 1.1 (Daily Notes) → highest value daily driver
Phase 2.1 (Daily Digest) → passive value delivery
Phase 1.2 (Quick Capture) → reduce friction
Phase 1.4 (Search) → make data retrievable
Phase 2.4 (Tasks) → actionable productivity
Phase 3.1 (Backlinks) → knowledge connections
Phase 4.1 (Import) → bootstrap with existing data
```

---

## Getting Started Today

1. Pull the latest code: `git pull origin claude/multi-agent-orchestration-QcyLj`
2. Restart the app: `nexus serve`
3. Check the startup logs for API key status
4. Test /health endpoint: `http://127.0.0.1:8430/health`
5. Add a few test entries
6. Try searching and asking questions

**Focus for this week:** Complete Phase 0 (Stabilization) so the app is reliably usable.
