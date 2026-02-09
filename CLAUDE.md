# Claude Development Context

> Upload this file at the start of each development session to maintain continuity and avoid repeated errors.

**Last Updated:** 2026-02-09
**Project:** Orchestrator + Nexus Personal AI Assistant
**Repository:** matthewcarlsonhome-cmd/orchestrator

---

## Project Overview

This repository contains two main components:

1. **Orchestrator** (`/src/orchestrator/`) - Multi-agent coding system with Claude API
2. **Nexus** (`/nexus/`) - Personal AI assistant platform (frontend-agnostic)

---

## Critical Errors Fixed (Do Not Reintroduce)

### 1. Tool Use / Tool Result Mismatch (API Error 400)

**Error:**
```
Error code: 400 - {'type': 'error', 'error': {'type': 'invalid_request_error',
'message': 'messages.0.content.2: unexpected `tool_use_id` found in `tool_result` blocks'}}
```

**Cause:** When trimming conversation history to stay under token limits, `tool_use` blocks were being removed while their corresponding `tool_result` blocks remained (or vice versa).

**Fix Location:** `src/orchestrator/agents/base.py` - `_trim_conversation_history()`

**Solution:** Always keep `tool_use` and `tool_result` pairs together. When trimming:
```python
# Track which tool_use IDs exist
tool_use_ids = set()
for msg in messages:
    if msg.get("role") == "assistant":
        for block in msg.get("content", []):
            if isinstance(block, dict) and block.get("type") == "tool_use":
                tool_use_ids.add(block.get("id"))

# Only include tool_results whose tool_use still exists
for block in content:
    if block.get("type") == "tool_result":
        if block.get("tool_use_id") in tool_use_ids:
            filtered_content.append(block)
```

**Rule:** NEVER trim tool_use without its tool_result, or vice versa.

---

### 2. Agent Task Hallucination (Impossible Tasks)

**Error:** Agent assigned task "Create Visual Assets" attempted to generate images, which Claude cannot do.

**Cause:** Task decomposition created tasks without validating they're achievable by a text-based AI.

**Solution:**
- Filter task descriptions for impossible operations (image generation, video creation, audio synthesis)
- Add validation in task creation
- Include explicit capability constraints in agent prompts

**Rule:** Always validate tasks against Claude's actual capabilities before assignment.

---

### 3. File Path Confusion (Local vs Remote)

**Issue:** Files were being written to `/tmp/orchestrator/projects/` instead of user's local directory.

**Fix Location:** `src/orchestrator/config.py`

**Solution:** Changed `projects_dir` to match user's actual working directory:
```python
projects_dir: str = "C:/Website"  # Direct local editing
```

**Rule:** Always confirm where files will be written before making changes.

---

## Patterns to AVOID

### 1. Parallel Tool Use Without Dependency Checking
**Bad:**
```python
# Calling dependent operations in parallel
asyncio.gather(
    create_file(path),
    write_to_file(path)  # Fails - file doesn't exist yet
)
```

**Good:**
```python
await create_file(path)
await write_to_file(path)
```

### 2. Unbounded Agent Loops
**Bad:** Letting agents retry indefinitely on failure.

**Good:** Use `TaskContract` with `max_iterations` limit:
```python
contract = TaskContract(
    max_iterations=10,
    max_tokens=15000,
    timeout_minutes=10
)
```

### 3. Full File Rewrites for Small Changes
**Bad:** Outputting entire file contents to change one line.

**Good:** Use patch/diff operations:
```python
patch = '''
--- a/src/file.py
+++ b/src/file.py
@@ -10,7 +10,7 @@
-    old_line
+    new_line
'''
patch_tools.apply_patch(patch)
```

### 4. Reading Entire Codebase for Simple Tasks
**Bad:** Loading all files to find one function.

**Good:** Use `RepoIndex` for targeted access:
```python
index = RepoIndex(project)
await index.build()
symbol = index.get_symbol("function_name")  # Returns just that code
```

### 5. Firing All Agents Simultaneously
**Bad:** Starting 10 agents at once, hitting rate limits.

**Good:** Use `RateLimitScheduler` with micro-batches:
```python
scheduler = RateLimitScheduler(
    max_active_agents=3,
    tokens_per_minute=80000
)
```

---

## Architecture Decisions (Frozen)

### Orchestrator
- **API Port:** 8420
- **WebSocket:** Real-time dashboard updates
- **Model Tiering:** Haiku for simple tasks, Sonnet for complex
- **Auto-push:** Enabled (commits push automatically)

### Nexus
- **API Port:** 8430
- **Default Vector DB:** ChromaDB (local)
- **Default Embeddings:** sentence-transformers (local, free)
- **Default LLM:** Claude (Anthropic)
- **Data Directory:** `~/.nexus/`

---

## API Rate Limits Reference

| Tier | Tokens/Min | Requests/Min |
|------|------------|--------------|
| 1    | 40,000     | 50           |
| 2    | 80,000     | 1,000        |
| 3    | 160,000    | 2,000        |
| 4    | 400,000    | 4,000        |

**Current Config:** Tier 2 defaults

---

## Token Optimization Strategies (Implemented)

1. **Repo Index** - Symbol table instead of full file reads
2. **Patch Operations** - Diff-only output (3-10x reduction)
3. **Frozen Contracts** - No architecture re-research per task
4. **Rate Limiter** - Token bucket with micro-batches
5. **Model Tiering** - Cheap models for simple tasks
6. **External Memory** - Decisions stored outside context
7. **Snippet Access** - Line ranges instead of full files

---

## Common Commands

```bash
# Start Orchestrator
cd /home/user/orchestrator
python -m uvicorn src.orchestrator.api:app --port 8420

# Start Nexus
cd /home/user/orchestrator/nexus
nexus serve

# Git operations
git pull origin claude/multi-agent-orchestration-QcyLj
git push -u origin claude/multi-agent-orchestration-QcyLj
```

---

## File Structure Quick Reference

```
orchestrator/
├── src/orchestrator/
│   ├── agents/base.py          # Base agent class (tool_use fix here)
│   ├── core/
│   │   ├── repo_index.py       # Symbol table, snippet access
│   │   ├── task_contract.py    # Frozen task definitions
│   │   ├── rate_limiter.py     # Token bucket scheduler
│   │   └── memory.py           # External memory layer
│   ├── tools/patch_ops.py      # Diff-only file modifications
│   └── config.py               # Central configuration
│
├── nexus/                      # Personal AI Assistant
│   ├── src/nexus/
│   │   ├── api/main.py         # FastAPI + dashboard
│   │   ├── core/               # Ingestion, Retrieval, Response
│   │   ├── storage/            # Vector DB, Metadata, Embeddings
│   │   ├── agents/             # Scheduler, Runner
│   │   └── cli.py              # Command-line interface
│   └── .env.example            # All config options
│
└── CLAUDE.md                   # This file
```

---

## Development Session Checklist

- [ ] Pull latest changes: `git pull origin claude/multi-agent-orchestration-QcyLj`
- [ ] Check for uncommitted work: `git status`
- [ ] Verify ports available: 8420 (Orchestrator), 8430 (Nexus)
- [ ] Confirm API keys set in `.env` files
- [ ] Review this file for recent fixes/patterns

---

## Known Limitations

1. **Claude cannot generate images** - Don't assign visual asset tasks
2. **Claude cannot execute code** - Use Bash tool for execution
3. **Context window limits** - Use trimming with tool_use pair preservation
4. **Rate limits** - Use scheduler, don't fire parallel agents unbounded

---

## Recent Session Notes

### 2026-02-09 (Session 2)
- Fixed Nexus API key loading (now accepts ANTHROPIC_API_KEY without prefix)
- Added proper error handling (503 errors instead of 500 for missing API key)
- Added startup banner showing config status
- Created comprehensive ROADMAP.md with 6 development phases
- Fixed Python 3.14 compatibility issue (use Python 3.13 or lower)

### 2026-02-09 (Session 1)
- Completed Nexus personal AI assistant (6 phases)
- Fixed tool_use/tool_result trimming bug
- Implemented token optimization strategies from LinkedIn recommendations
- Added auto-push and GitHub button to dashboard
- Changed projects_dir to C:/Website for local editing

---

## Debugging Tips

### API Error 400 (Invalid Request)
1. Check tool_use/tool_result pairing
2. Verify message format matches Anthropic spec
3. Look for orphaned tool blocks after trimming

### Agent Stuck/Looping
1. Check `max_iterations` in contract
2. Verify task is actually achievable
3. Look for circular dependencies

### Rate Limit Errors (429)
1. Reduce `max_active_agents`
2. Increase wait times in scheduler
3. Check token bucket consumption

### Files Not Appearing
1. Verify `projects_dir` in config
2. Check file permissions
3. Confirm git branch is correct

### Nexus API Key Not Loading
1. Ensure `.env` file is in `nexus/` directory
2. Use `ANTHROPIC_API_KEY=sk-ant-...` (no NEXUS_ prefix needed)
3. Restart the app after editing `.env`
4. Check startup logs for "Anthropic API: CONFIGURED" message
5. Test with `GET /health` endpoint to verify config status

### Nexus ChromaDB/Pydantic Error
```
pydantic.v1.errors.ConfigError: unable to infer type for attribute "chroma_server_nofile"
```
**Cause:** Python 3.14 incompatibility with ChromaDB
**Fix:** Use Python 3.10, 3.11, 3.12, or 3.13 instead:
```batch
py -3.13 -m venv venv
venv\Scripts\activate
pip install -e .
```

### Nexus "Internal Server Error" on Ask/Briefing
1. Check `/health` endpoint - `llm_configured` should be `true`
2. Verify API key is valid (not expired, has credits)
3. Check console for detailed error message

---

## Contact / Resources

- **GitHub Issues:** https://github.com/anthropics/claude-code/issues
- **Anthropic Docs:** https://docs.anthropic.com
- **Project Repo:** https://github.com/matthewcarlsonhome-cmd/orchestrator
