"""
Task Decomposer - Breaks down high-level instructions into specific tasks.

This module uses the Claude API to intelligently analyze user instructions
and split them into smaller, actionable tasks that can be assigned to
specialized agents (like frontend dev, backend dev, etc.).

Example: If user says "Add a login page", this might create tasks like:
  1. "Design authentication flow" (for architect agent)
  2. "Build login form UI" (for frontend agent)
  3. "Create auth API endpoint" (for backend agent)
  4. "Write login tests" (for tester agent)
"""

import asyncio  # For running blocking code without freezing the UI
import json
from typing import Optional

from anthropic import Anthropic  # Claude API client

from orchestrator.config import config
from orchestrator.models.task import Task, AgentTypeHint, TaskPriority
from orchestrator.models.project import Project


DECOMPOSER_SYSTEM_PROMPT = """You are a task decomposition expert for software development projects.

Your job is to take a high-level task description and break it down into specific, actionable subtasks that can be assigned to specialized agents.

## Available Agent Types
- architect: Analyzes codebase, designs solutions, creates implementation plans
- frontend: UI components, styling, client-side logic, state management
- backend: APIs, databases, server logic, integrations
- fullstack: End-to-end features connecting frontend and backend
- tester: Writes and runs tests, ensures code quality
- debugger: Investigates bugs, fixes issues
- devops: Build systems, deployment, CI/CD
- reviewer: Code review, security checks
- researcher: Documentation, finding solutions
- coordinator: Merges work, resolves conflicts

## Guidelines
1. Break tasks into atomic, independently completable units
2. Each task should be doable by ONE agent
3. Identify dependencies between tasks
4. Prioritize tasks (critical > high > medium > low)
5. Include enough detail for the agent to understand what to do
6. Consider the project's tech stack when assigning agent types

## Output Format
Return a JSON array of tasks, each with:
- title: Short task title
- description: Detailed description with acceptance criteria
- agent_type_hint: Which agent type should do this
- priority: critical, high, medium, or low
- depends_on: List of task indices this depends on (0-indexed)
"""


DECOMPOSE_TOOL = {
    "name": "create_tasks",
    "description": "Create the decomposed task list",
    "input_schema": {
        "type": "object",
        "properties": {
            "tasks": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "description": {"type": "string"},
                        "agent_type_hint": {
                            "type": "string",
                            "enum": ["architect", "frontend", "backend", "fullstack",
                                     "tester", "debugger", "devops", "reviewer",
                                     "researcher", "coordinator"]
                        },
                        "priority": {
                            "type": "string",
                            "enum": ["critical", "high", "medium", "low"]
                        },
                        "depends_on": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "description": "Indices of tasks this depends on"
                        }
                    },
                    "required": ["title", "description", "agent_type_hint", "priority"]
                }
            }
        },
        "required": ["tasks"]
    }
}


class TaskDecomposer:
    """
    Breaks down high-level instructions into atomic (small, specific) tasks.

    Think of this like a project manager who takes a big request like
    "build a shopping cart" and splits it into specific tickets that
    individual developers can work on.
    """

    def __init__(self):
        # Create a connection to Claude API using your API key
        self.client = Anthropic(api_key=config.anthropic_api_key)

    def _call_claude(self, project_context: str):
        """
        Make an API call to Claude to analyze and decompose the task.

        This is a "synchronous" call - it waits for Claude to respond
        before continuing. We wrap it in asyncio.to_thread() elsewhere
        so it doesn't freeze the dashboard while waiting.
        """
        return self.client.messages.create(
            model=config.model,          # Which Claude model to use (e.g., claude-sonnet)
            max_tokens=4096,             # Max length of Claude's response
            system=DECOMPOSER_SYSTEM_PROMPT,  # Instructions telling Claude how to behave
            tools=[DECOMPOSE_TOOL],      # Give Claude a structured way to return tasks
            messages=[{
                "role": "user",
                "content": f"Please decompose this task into subtasks:\n\n{project_context}"
            }]
        )

    def decompose(
        self,
        instructions: str,
        project: Project,
        context: Optional[str] = None,
    ) -> list[Task]:
        """
        Break down instructions into tasks (synchronous/blocking version).

        Args:
            instructions: What the user wants done (e.g., "Add user login")
            project: The project we're working on (has tech stack info, etc.)
            context: Optional extra context about the codebase

        Returns:
            A list of Task objects ready to be assigned to agents
        """
        project_context = self._build_context(instructions, project, context)
        response = self._call_claude(project_context)
        return self._parse_response(response, project)

    async def decompose_async(
        self,
        instructions: str,
        project: Project,
        context: Optional[str] = None,
    ) -> list[Task]:
        """
        Break down instructions into tasks (async/non-blocking version).

        This version runs the Claude API call in a separate thread so the
        dashboard stays responsive while waiting for Claude's response.
        This is important because Claude can take 5-30 seconds to respond!

        The 'await asyncio.to_thread()' magic moves the blocking call to
        a background thread, letting other things (like the dashboard)
        keep running.
        """
        project_context = self._build_context(instructions, project, context)
        # Run the blocking API call in a thread pool - this is the key fix!
        response = await asyncio.to_thread(self._call_claude, project_context)
        return self._parse_response(response, project)

    def _build_context(self, instructions: str, project: Project, context: Optional[str] = None) -> str:
        """
        Build a context string that gives Claude all the info it needs.

        This includes:
        - Project name
        - Tech stack (React, Python, etc.)
        - The user's instructions
        - Any extra context we've discovered about the codebase
        """
        project_context = f"""
## Project: {project.name}
- Tech Stack: {', '.join(project.config.tech_stack)}
- Type: {project.config.github.repo}

## Instructions
{instructions}
"""
        if context:
            project_context += f"\n## Additional Context\n{context}"
        return project_context

    def _parse_response(self, response, project: Project) -> list[Task]:
        """
        Parse Claude's response and convert it into Task objects.

        Claude returns its response in a structured format using "tool use".
        This method extracts the task data from that response and converts
        each task into a proper Task object that our system can work with.
        """
        # Extract tasks from Claude's tool use response
        # Claude uses "tools" to return structured data (like JSON)
        tasks = []
        task_data = []

        # Loop through Claude's response blocks looking for the task data
        for block in response.content:
            # Check if this block is Claude using our "create_tasks" tool
            if block.type == "tool_use" and block.name == "create_tasks":
                task_data = block.input.get("tasks", [])
                break  # Found it, stop looking

        # Convert to Task objects
        priority_map = {
            "critical": TaskPriority.CRITICAL,
            "high": TaskPriority.HIGH,
            "medium": TaskPriority.MEDIUM,
            "low": TaskPriority.LOW,
        }

        agent_type_map = {
            "architect": AgentTypeHint.ARCHITECT,
            "frontend": AgentTypeHint.FRONTEND,
            "backend": AgentTypeHint.BACKEND,
            "fullstack": AgentTypeHint.FULLSTACK,
            "tester": AgentTypeHint.TESTER,
            "debugger": AgentTypeHint.DEBUGGER,
            "devops": AgentTypeHint.DEVOPS,
            "reviewer": AgentTypeHint.REVIEWER,
            "researcher": AgentTypeHint.RESEARCHER,
            "coordinator": AgentTypeHint.COORDINATOR,
        }

        for data in task_data:
            task = Task(
                project_name=project.name,
                title=data["title"],
                description=data["description"],
                agent_type_hint=agent_type_map.get(
                    data["agent_type_hint"], AgentTypeHint.FULLSTACK
                ),
                priority=priority_map.get(data.get("priority", "medium"), TaskPriority.MEDIUM),
            )
            tasks.append(task)

        # Set up dependencies using task IDs
        for i, data in enumerate(task_data):
            depends_on_indices = data.get("depends_on", [])
            for dep_idx in depends_on_indices:
                if 0 <= dep_idx < len(tasks):
                    tasks[i].depends_on.append(tasks[dep_idx].id)
                    tasks[dep_idx].blocks.append(tasks[i].id)

        return tasks

    def decompose_simple(self, instructions: str, project: Project) -> list[Task]:
        """
        Simple rule-based decomposition for common patterns.
        Faster than LLM-based decomposition for simple cases.
        """
        tasks = []
        instructions_lower = instructions.lower()

        # Always start with architect for analysis
        tasks.append(Task(
            project_name=project.name,
            title="Analyze requirements and design approach",
            description=f"Analyze the codebase and create an implementation plan for: {instructions}",
            agent_type_hint=AgentTypeHint.ARCHITECT,
            priority=TaskPriority.HIGH,
        ))

        # Detect frontend work
        frontend_keywords = ["ui", "component", "page", "style", "css", "tailwind", "react", "view", "button", "form"]
        if any(kw in instructions_lower for kw in frontend_keywords):
            tasks.append(Task(
                project_name=project.name,
                title="Implement frontend changes",
                description=f"Build the UI components for: {instructions}",
                agent_type_hint=AgentTypeHint.FRONTEND,
                priority=TaskPriority.MEDIUM,
                depends_on=[tasks[0].id],
            ))

        # Detect backend work
        backend_keywords = ["api", "endpoint", "database", "server", "backend", "auth", "data"]
        if any(kw in instructions_lower for kw in backend_keywords):
            tasks.append(Task(
                project_name=project.name,
                title="Implement backend changes",
                description=f"Build the backend logic for: {instructions}",
                agent_type_hint=AgentTypeHint.BACKEND,
                priority=TaskPriority.MEDIUM,
                depends_on=[tasks[0].id],
            ))

        # Detect testing needs
        test_keywords = ["test", "testing", "coverage", "spec"]
        if any(kw in instructions_lower for kw in test_keywords):
            tasks.append(Task(
                project_name=project.name,
                title="Write tests",
                description=f"Write tests for the implemented changes",
                agent_type_hint=AgentTypeHint.TESTER,
                priority=TaskPriority.LOW,
                depends_on=[t.id for t in tasks[1:]],  # Depends on all implementation tasks
            ))

        # If neither frontend nor backend detected, add fullstack
        if len(tasks) == 1:
            tasks.append(Task(
                project_name=project.name,
                title="Implement feature",
                description=f"Implement: {instructions}",
                agent_type_hint=AgentTypeHint.FULLSTACK,
                priority=TaskPriority.MEDIUM,
                depends_on=[tasks[0].id],
            ))

        return tasks
