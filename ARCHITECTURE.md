# Agent Orchestration System - Architecture Plan

## Vision
A multi-agent orchestration system that can autonomously work on any software project for 4+ hours, intelligently delegating tasks to specialized agents that coordinate independently with shared goals.

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         WEB DASHBOARD                                │
│  (Real-time progress, logs, agent status, project overview)         │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         ORCHESTRATOR CORE                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │
│  │   Project   │  │    Task     │  │   Agent     │  │   State     │ │
│  │  Registry   │  │  Decomposer │  │  Scheduler  │  │   Manager   │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
            ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
            │  Agent Pool │ │  Task Queue │ │  Blackboard │
            │  (1-10)     │ │  (Priority) │ │  (Shared)   │
            └─────────────┘ └─────────────┘ └─────────────┘
                    │
    ┌───────┬───────┼───────┬───────┬───────┐
    ▼       ▼       ▼       ▼       ▼       ▼
┌──────┐┌──────┐┌──────┐┌──────┐┌──────┐┌──────┐
│Agent1││Agent2││Agent3││Agent4││Agent5││AgentN│
│Archi-││Front-││Back- ││Tester││Debug-││  ... │
│tect  ││ end  ││ end  ││      ││ger   ││      │
└──────┘└──────┘└──────┘└──────┘└──────┘└──────┘
    │       │       │       │       │       │
    └───────┴───────┴───────┴───────┴───────┘
                        │
                        ▼
            ┌─────────────────────┐
            │   PROJECT SANDBOX   │
            │  (Git worktrees,    │
            │   isolated envs)    │
            └─────────────────────┘
```

---

## Core Components

### 1. Project Registry
Stores metadata about each registered project:
```python
{
    "skillengine": {
        "path": "/path/to/skillengine",
        "type": "website",
        "tech_stack": ["nextjs", "typescript", "tailwind", "supabase"],
        "entry_points": ["package.json", "src/app"],
        "test_command": "npm test",
        "build_command": "npm run build",
        "dev_command": "npm run dev"
    },
    "meta-ad-builder": {
        "path": "/path/to/meta-ad-builder",
        "type": "tool",
        "tech_stack": ["python", "fastapi", "react"],
        ...
    }
}
```

### 2. Task Decomposer
Takes high-level instructions and breaks them into atomic tasks:
```
INPUT: "Add user authentication with OAuth to SkillEngine"

OUTPUT:
├── [ARCHITECT] Analyze current auth state, design OAuth flow
├── [BACKEND] Set up OAuth providers (Google, GitHub)
├── [BACKEND] Create auth API endpoints
├── [FRONTEND] Build login/signup UI components
├── [FRONTEND] Add auth state management
├── [TESTER] Write auth integration tests
├── [DEVOPS] Configure environment variables
└── [DOCS] Update README with auth setup instructions
```

### 3. Agent Scheduler
- Assigns tasks to available agents based on specialization
- Manages agent lifecycle (spawn, monitor, restart)
- Handles task dependencies (DAG execution)
- Load balancing across agents

### 4. State Manager
- Checkpoints agent state every N minutes
- Tracks task completion status
- Manages shared context between agents
- Handles crash recovery

### 5. Blackboard (Shared Knowledge)
Agents read/write to shared knowledge store:
```python
{
    "project_context": { ... },      # What agents learned about the project
    "completed_tasks": [ ... ],       # What's done
    "active_tasks": { ... },          # Who's doing what
    "discoveries": [ ... ],           # Issues found, patterns noticed
    "decisions": [ ... ],             # Architectural decisions made
    "conflicts": [ ... ],             # Merge conflicts, disagreements
    "file_locks": { ... }             # Prevent simultaneous edits
}
```

---

## Agent Specializations

Each agent is a **generalized role** that can work on any project:

| Agent Type | Capabilities | Primary Tools |
|------------|--------------|---------------|
| **Architect** | Analyze codebase, design solutions, create specs, break down work | Read, Grep, planning |
| **Frontend** | UI components, styling, client-side logic, state management | Edit, Write, npm |
| **Backend** | APIs, databases, server logic, integrations | Edit, Write, pip/npm |
| **Full-Stack** | End-to-end features, integration work | All development tools |
| **Tester** | Write tests, run test suites, coverage analysis | Test frameworks |
| **Debugger** | Error analysis, fix bugs, performance issues | Read, logs, debuggers |
| **DevOps** | Build, deploy, CI/CD, infrastructure | Docker, scripts |
| **Reviewer** | Code review, quality checks, security scan | Static analysis |
| **Researcher** | Find docs, solutions, best practices | Web search, docs |
| **Coordinator** | Resolve conflicts, merge work, sync agents | Git, communication |

---

## Agent Implementation

Each agent runs as a separate process using Claude API:

```python
class Agent:
    def __init__(self, agent_type: AgentType, agent_id: str):
        self.type = agent_type
        self.id = agent_id
        self.current_task = None
        self.status = AgentStatus.IDLE

    async def run(self, task: Task, project: Project, blackboard: Blackboard):
        """
        Main agent loop:
        1. Understand task in project context
        2. Read relevant files
        3. Plan approach
        4. Execute changes
        5. Validate results
        6. Report completion
        """

    def get_system_prompt(self, project: Project) -> str:
        """Generate role-specific prompt with project context"""

    async def checkpoint(self):
        """Save current state for recovery"""
```

---

## Workflow Example

### Scenario: "Improve the Meta Ad Builder with better analytics dashboard"

```
1. USER INPUT
   └── Project: meta-ad-builder
   └── Instructions: "Add analytics dashboard showing ad performance metrics"

2. TASK DECOMPOSER analyzes and creates:
   ├── Task 1: [ARCHITECT] Design dashboard architecture
   ├── Task 2: [BACKEND] Create analytics API endpoints (depends: 1)
   ├── Task 3: [FRONTEND] Build dashboard components (depends: 1)
   ├── Task 4: [FRONTEND] Add charts/visualizations (depends: 3)
   ├── Task 5: [BACKEND] Aggregate metrics data (depends: 2)
   ├── Task 6: [TESTER] Test analytics endpoints (depends: 2, 5)
   └── Task 7: [FULL-STACK] Integration testing (depends: all)

3. SCHEDULER assigns:
   ├── Agent-1 (Architect) → Task 1
   └── (other agents wait for dependencies)

4. AS TASKS COMPLETE:
   ├── Task 1 done → Agents 2 & 3 can start in parallel
   ├── Task 2 done → Agent for Task 5 starts
   └── ... continues until all complete

5. BLACKBOARD updated throughout:
   ├── discoveries: ["found existing Chart.js setup"]
   ├── decisions: ["use existing API pattern from /api/v1/"]
   └── conflicts: [] (none in this case)

6. DASHBOARD shows real-time progress
```

---

## Technology Stack

### Backend (Orchestrator)
- **Python 3.11+** with asyncio
- **FastAPI** for API + WebSocket support
- **SQLite/PostgreSQL** for state persistence
- **Redis** for task queue (or in-memory for single machine)
- **Anthropic SDK** for Claude API

### Frontend (Dashboard)
- **React + TypeScript**
- **Tailwind CSS**
- **WebSocket** for real-time updates
- **Recharts** for progress visualization

### Agent Runtime
- **Multiprocessing** for true parallelism
- **Claude API** with tool use for each agent
- **Git worktrees** for isolated project work

---

## Directory Structure

```
orchestrator/
├── src/
│   ├── core/
│   │   ├── __init__.py
│   │   ├── orchestrator.py      # Main orchestration engine
│   │   ├── scheduler.py         # Task scheduling & assignment
│   │   ├── decomposer.py        # Task breakdown logic
│   │   └── state.py             # State management & checkpoints
│   │
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── base.py              # Base agent class
│   │   ├── architect.py         # Architect agent
│   │   ├── frontend.py          # Frontend developer agent
│   │   ├── backend.py           # Backend developer agent
│   │   ├── tester.py            # Testing agent
│   │   ├── debugger.py          # Debugging agent
│   │   ├── devops.py            # DevOps agent
│   │   ├── reviewer.py          # Code review agent
│   │   └── prompts/             # Agent system prompts
│   │       ├── architect.md
│   │       ├── frontend.md
│   │       └── ...
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── project.py           # Project model
│   │   ├── task.py              # Task model
│   │   ├── agent.py             # Agent model
│   │   └── blackboard.py        # Shared state model
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI app
│   │   ├── routes/
│   │   │   ├── projects.py      # Project management
│   │   │   ├── tasks.py         # Task management
│   │   │   ├── agents.py        # Agent control
│   │   │   └── ws.py            # WebSocket for dashboard
│   │   └── schemas.py           # Pydantic schemas
│   │
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── file_ops.py          # File read/write/edit
│   │   ├── git_ops.py           # Git operations
│   │   ├── shell.py             # Shell command execution
│   │   └── web.py               # Web search/fetch
│   │
│   └── utils/
│       ├── __init__.py
│       ├── logging.py           # Structured logging
│       ├── config.py            # Configuration
│       └── recovery.py          # Crash recovery
│
├── dashboard/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── components/
│   │   │   ├── ProjectList.tsx
│   │   │   ├── AgentStatus.tsx
│   │   │   ├── TaskBoard.tsx
│   │   │   ├── LogViewer.tsx
│   │   │   └── ProgressChart.tsx
│   │   └── hooks/
│   │       └── useWebSocket.ts
│   ├── package.json
│   └── tailwind.config.js
│
├── projects/                    # Project registry configs
│   ├── skillengine.yaml
│   ├── mcc-site.yaml
│   ├── meta-ad-builder.yaml
│   ├── media-mix-model.yaml
│   └── rag-system.yaml
│
├── config/
│   ├── orchestrator.yaml        # Main configuration
│   └── agents.yaml              # Agent configurations
│
├── tests/
│   ├── test_orchestrator.py
│   ├── test_agents.py
│   └── test_decomposer.py
│
├── requirements.txt
├── pyproject.toml
├── docker-compose.yml           # Optional containerization
└── README.md
```

---

## Key Features for 4+ Hour Autonomy

### 1. Checkpointing System
```python
# Every 5 minutes, save:
- Current task state for each agent
- Blackboard contents
- File change history
- Git commit hashes

# On crash recovery:
- Detect last checkpoint
- Restore agent states
- Resume from last known good state
```

### 2. Health Monitoring
```python
# Heartbeat every 30 seconds from each agent
# If no heartbeat for 2 minutes:
- Mark agent as unhealthy
- Attempt restart
- Reassign tasks if restart fails
```

### 3. Resource Management
```python
# Memory limits per agent
# Automatic garbage collection
# Log rotation
# Temp file cleanup
```

### 4. Conflict Resolution
```python
# File locking to prevent simultaneous edits
# If conflict detected:
- Pause conflicting agents
- Run coordinator agent to merge
- Resume with merged state
```

---

## Implementation Phases

### Phase 1: Core Foundation (MVP)
- [ ] Project model and registry
- [ ] Basic task queue
- [ ] Single agent runner with Claude API
- [ ] Simple CLI interface
- [ ] File operations tools

### Phase 2: Multi-Agent
- [ ] Agent pool management
- [ ] Task decomposer
- [ ] Parallel execution
- [ ] Basic blackboard
- [ ] Agent specializations

### Phase 3: Stability
- [ ] Checkpointing system
- [ ] Health monitoring
- [ ] Crash recovery
- [ ] Conflict resolution
- [ ] Logging infrastructure

### Phase 4: Dashboard
- [ ] FastAPI backend
- [ ] WebSocket real-time updates
- [ ] React dashboard UI
- [ ] Progress visualization
- [ ] Log viewer

### Phase 5: Polish
- [ ] Advanced task decomposition
- [ ] Learning from past runs
- [ ] Performance optimization
- [ ] Documentation
- [ ] Production hardening

---

## Next Steps

1. **Validate this architecture** - Does this match your vision?
2. **Prioritize features** - What's most critical for MVP?
3. **Start Phase 1** - Build core foundation

---

## Questions to Resolve

1. Should agents work in git branches and merge, or directly on main?
2. How should we handle API rate limits for Claude?
3. Do you want agents to be able to run shell commands (npm, python, etc.)?
4. Should the dashboard allow starting/stopping agents manually?
5. How much should agents communicate with each other vs. through blackboard?
