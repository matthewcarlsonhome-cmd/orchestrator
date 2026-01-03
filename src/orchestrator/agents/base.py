"""
Base Agent - The core "brain" of each AI coding agent.

This module defines what an agent IS and what it CAN DO. Each agent:
1. Gets assigned a task (like "build the login form")
2. Uses Claude API to think about how to accomplish it
3. Has access to tools (read files, write files, run commands)
4. Works in a loop: think -> act -> observe -> repeat

Think of an agent like a junior developer who:
- Reads the task description
- Looks at the existing code
- Makes changes to files
- Runs tests to verify their work
- Reports back when done

The "tools" are like the developer's IDE - they let the agent
read/write files, search code, run commands, etc.
"""

import asyncio  # For running blocking code without freezing the dashboard
import json
from datetime import datetime
from typing import Any, Callable, Optional, Awaitable

from anthropic import Anthropic  # The Claude API client

from orchestrator.config import config
from orchestrator.models.agent import Agent, AgentType, AgentStatus
from orchestrator.models.task import Task
from orchestrator.models.project import Project
from orchestrator.models.blackboard import Blackboard, EntryType, BlackboardEntry
from orchestrator.tools.file_ops import FileTools     # Read/write/edit files
from orchestrator.tools.git_ops import GitTools       # Git commands (commit, branch, etc.)
from orchestrator.tools.shell import ShellTools, ShellApprovalRequired  # Run shell commands
from orchestrator.agents.prompts import get_agent_system_prompt  # Agent personality prompts


# Tool definitions for Claude API
AGENT_TOOLS = [
    {
        "name": "read_file",
        "description": "Read the contents of a file in the project",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file, relative to project root"
                },
                "max_lines": {
                    "type": "integer",
                    "description": "Maximum number of lines to read (optional)"
                }
            },
            "required": ["path"]
        }
    },
    {
        "name": "write_file",
        "description": "Write content to a file (creates if doesn't exist)",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file, relative to project root"
                },
                "content": {
                    "type": "string",
                    "description": "Content to write to the file"
                }
            },
            "required": ["path", "content"]
        }
    },
    {
        "name": "edit_file",
        "description": "Replace text in a file",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file, relative to project root"
                },
                "old_text": {
                    "type": "string",
                    "description": "Text to find and replace"
                },
                "new_text": {
                    "type": "string",
                    "description": "Replacement text"
                }
            },
            "required": ["path", "old_text", "new_text"]
        }
    },
    {
        "name": "list_directory",
        "description": "List files and directories",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Directory path, relative to project root",
                    "default": "."
                },
                "recursive": {
                    "type": "boolean",
                    "description": "Whether to list recursively",
                    "default": False
                },
                "pattern": {
                    "type": "string",
                    "description": "Glob pattern to filter files (e.g., '*.py')"
                }
            }
        }
    },
    {
        "name": "search_files",
        "description": "Search for a pattern in files",
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Regex pattern to search for"
                },
                "path": {
                    "type": "string",
                    "description": "Directory to search in",
                    "default": "."
                },
                "file_pattern": {
                    "type": "string",
                    "description": "Glob pattern to filter files (e.g., '*.ts')"
                }
            },
            "required": ["pattern"]
        }
    },
    {
        "name": "get_file_tree",
        "description": "Get directory structure as a tree",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Root path for the tree",
                    "default": "."
                },
                "max_depth": {
                    "type": "integer",
                    "description": "Maximum depth to traverse",
                    "default": 3
                }
            }
        }
    },
    {
        "name": "run_shell",
        "description": "Run a shell command. May require user approval.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Shell command to run"
                },
                "timeout": {
                    "type": "integer",
                    "description": "Timeout in seconds",
                    "default": 300
                }
            },
            "required": ["command"]
        }
    },
    {
        "name": "git_commit",
        "description": "Commit changes to git",
        "input_schema": {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "Commit message"
                },
                "files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Specific files to commit (optional, defaults to all)"
                }
            },
            "required": ["message"]
        }
    },
    {
        "name": "git_status",
        "description": "Get git repository status",
        "input_schema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "post_to_blackboard",
        "description": "Post a discovery, decision, or blocker to the shared blackboard",
        "input_schema": {
            "type": "object",
            "properties": {
                "entry_type": {
                    "type": "string",
                    "enum": ["discovery", "decision", "blocker", "progress"],
                    "description": "Type of entry"
                },
                "title": {
                    "type": "string",
                    "description": "Short title"
                },
                "content": {
                    "type": "string",
                    "description": "Full content"
                },
                "metadata": {
                    "type": "object",
                    "description": "Additional metadata"
                }
            },
            "required": ["entry_type", "title", "content"]
        }
    },
    {
        "name": "read_blackboard",
        "description": "Read entries from the shared blackboard",
        "input_schema": {
            "type": "object",
            "properties": {
                "entry_type": {
                    "type": "string",
                    "enum": ["discovery", "decision", "blocker", "all"],
                    "description": "Type of entries to read"
                }
            }
        }
    },
    {
        "name": "send_message",
        "description": "Send a message to another agent",
        "input_schema": {
            "type": "object",
            "properties": {
                "to_agent_type": {
                    "type": "string",
                    "description": "Type of agent to message (e.g., 'frontend', 'backend')"
                },
                "message": {
                    "type": "string",
                    "description": "Message content"
                },
                "context": {
                    "type": "object",
                    "description": "Additional context"
                }
            },
            "required": ["to_agent_type", "message"]
        }
    },
    {
        "name": "complete_task",
        "description": "Mark the current task as complete with a summary",
        "input_schema": {
            "type": "object",
            "properties": {
                "summary": {
                    "type": "string",
                    "description": "Summary of what was accomplished"
                },
                "files_modified": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of files that were modified"
                },
                "follow_up_tasks": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Suggested follow-up tasks"
                }
            },
            "required": ["summary"]
        }
    }
]


class BaseAgent:
    """
    The main class that controls an AI coding agent.

    Each agent has:
    - A type (architect, frontend, backend, etc.) - defines personality
    - Access to tools (file operations, git, shell commands)
    - A connection to Claude API for thinking/reasoning
    - A conversation history (messages) with Claude

    The agent works in a loop:
    1. Send task + context to Claude
    2. Claude responds with text and/or tool calls
    3. Execute any tool calls (read file, write file, etc.)
    4. Send tool results back to Claude
    5. Repeat until Claude calls "complete_task"
    """

    def __init__(
        self,
        agent: Agent,                # The agent's identity (type, id, status)
        project: Project,            # The project being worked on
        blackboard: Blackboard,      # Shared notepad for agents to communicate
        approval_callback: Optional[Callable[[str], Awaitable[bool]]] = None,  # For approving shell commands
        on_message: Optional[Callable[[dict], Awaitable[None]]] = None,        # For inter-agent messages
        on_status: Optional[Callable[[dict], Awaitable[None]]] = None,         # For status updates
    ):
        self.agent = agent
        self.project = project
        self.blackboard = blackboard
        self.approval_callback = approval_callback
        self.on_message = on_message
        self.on_status = on_status  # Callback for status updates

        # Initialize the tools this agent can use
        # These are like the agent's "hands" - how it interacts with the codebase
        self.file_tools = FileTools(project)      # Read, write, edit, search files
        self.git_tools = GitTools(project)        # Git operations (commit, branch)
        self.shell_tools = ShellTools(project, approval_callback)  # Run npm, python, etc.

        # Create connection to Claude API
        # This is the agent's "brain" - it makes decisions using Claude
        self.client = Anthropic(api_key=config.anthropic_api_key)

        # Conversation state - keeps track of the back-and-forth with Claude
        self.messages: list[dict] = []      # Full conversation history
        self.task_completed = False          # Has the agent finished its task?
        self.task_result: Optional[dict] = None  # The final result/summary
        self.files_modified: list[str] = []  # List of files the agent changed

        # Status tracking for progress updates
        self._current_status = "idle"
        self._last_status_time = datetime.now()
        self._api_call_count = 0

    async def _emit_status(self, status: str, details: str = ""):
        """Emit a status update to the dashboard."""
        self._current_status = status
        if self.on_status:
            await self.on_status({
                "agent_id": self.agent.id,
                "agent_type": self.agent.agent_type.value,
                "status": status,
                "details": details,
                "api_calls": self._api_call_count,
                "files_modified": len(self.files_modified),
            })

    async def execute_task(self, task: Task) -> dict:
        """
        Execute a task and return the result.

        This is the main method that runs the agent. It:
        1. Sets up the task context
        2. Runs a loop where it talks to Claude
        3. Claude can use tools (read/write files, etc.)
        4. Continues until Claude marks the task complete

        Args:
            task: The Task object containing title and description

        Returns:
            A dictionary with 'success', 'summary', 'files_modified', etc.
        """
        # Mark this agent as working on this task
        self.agent.assign_task(task.id, self.project.name)

        # Reset state for new task
        self.task_completed = False
        self.task_result = None
        self.files_modified = []
        self.messages = []

        # Build the "system prompt" - this tells Claude what kind of agent it is
        # and gives it context about the project (like tech stack, file structure)
        context = self._build_context()
        system_prompt = get_agent_system_prompt(
            agent_type=self.agent.agent_type,    # architect, frontend, backend, etc.
            agent_id=self.agent.id,
            project_name=self.project.name,
            tech_stack=self.project.config.tech_stack,
            local_path=str(self.project.local_path),
            task_description=f"**{task.title}**\n\n{task.description}",
            context=context,
        )

        # Start the conversation with Claude by giving it the task
        self.messages.append({
            "role": "user",
            "content": f"Please complete this task: {task.title}\n\n{task.description}"
        })

        # ========== THE MAIN AGENT LOOP ==========
        # This loop continues until Claude calls "complete_task" or we hit the limit
        max_iterations = 50  # Safety limit to prevent infinite loops
        iteration = 0
        self._api_call_count = 0

        while not self.task_completed and iteration < max_iterations:
            iteration += 1
            self._api_call_count += 1
            self.agent.heartbeat()  # Let the system know we're still alive

            try:
                # Emit status: waiting for API response
                await self._emit_status(
                    "calling_api",
                    f"API call #{self._api_call_count} - waiting for Claude response..."
                )

                # Call Claude API in a background thread
                # This is important! Without asyncio.to_thread(), this call
                # would freeze the dashboard for 5-30 seconds while waiting
                api_start = datetime.now()
                response = await asyncio.to_thread(
                    self.client.messages.create,
                    model=config.model,      # Which Claude model to use
                    max_tokens=8192,         # Max response length
                    system=system_prompt,    # Agent's personality/instructions
                    tools=AGENT_TOOLS,       # What tools Claude can use
                    messages=self.messages,  # Full conversation history
                )
                api_duration = (datetime.now() - api_start).total_seconds()

                # Emit status: got response, processing
                await self._emit_status(
                    "processing",
                    f"Got response in {api_duration:.1f}s - processing tools..."
                )

                # Process Claude's response (execute any tools it wants to use)
                await self._process_response(response)

            except Exception as e:
                # Something went wrong - log it and return failure
                self.agent.record_error()
                await self._emit_status("error", str(e))
                return {
                    "success": False,
                    "error": str(e),
                    "files_modified": self.files_modified,
                }

        # Mark the agent as done with this task
        self.agent.complete_task()

        # Return the results
        if self.task_result:
            return {
                "success": True,
                **self.task_result,  # Includes summary, follow_up_tasks, etc.
                "files_modified": self.files_modified,
            }

        return {
            "success": False,
            "error": "Task did not complete properly",
            "files_modified": self.files_modified,
        }

    async def _process_response(self, response) -> None:
        """Process a Claude API response."""
        assistant_content = []

        for block in response.content:
            if block.type == "text":
                assistant_content.append({
                    "type": "text",
                    "text": block.text
                })
            elif block.type == "tool_use":
                assistant_content.append({
                    "type": "tool_use",
                    "id": block.id,
                    "name": block.name,
                    "input": block.input,
                })

        # Add assistant message
        self.messages.append({
            "role": "assistant",
            "content": assistant_content
        })

        # Process tool calls
        if response.stop_reason == "tool_use":
            tool_results = []

            for block in response.content:
                if block.type == "tool_use":
                    result = await self._execute_tool(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result) if isinstance(result, dict) else str(result),
                    })

            # Add tool results
            self.messages.append({
                "role": "user",
                "content": tool_results
            })

    async def _execute_tool(self, name: str, inputs: dict) -> Any:
        """Execute a tool and return the result."""
        try:
            if name == "read_file":
                return self.file_tools.read(
                    inputs["path"],
                    inputs.get("max_lines")
                )

            elif name == "write_file":
                self.file_tools.write(inputs["path"], inputs["content"])
                self.files_modified.append(inputs["path"])
                return {"success": True}

            elif name == "edit_file":
                self.file_tools.edit(
                    inputs["path"],
                    inputs["old_text"],
                    inputs["new_text"]
                )
                self.files_modified.append(inputs["path"])
                return {"success": True}

            elif name == "list_directory":
                return self.file_tools.list_dir(
                    inputs.get("path", "."),
                    inputs.get("recursive", False),
                    inputs.get("pattern")
                )

            elif name == "search_files":
                return self.file_tools.search(
                    inputs["pattern"],
                    inputs.get("path", "."),
                    inputs.get("file_pattern")
                )

            elif name == "get_file_tree":
                return self.file_tools.get_tree(
                    inputs.get("path", "."),
                    inputs.get("max_depth", 3)
                )

            elif name == "run_shell":
                result = await self.shell_tools.run(
                    inputs["command"],
                    inputs.get("timeout", 300)
                )
                return result

            elif name == "git_commit":
                commit_hash = self.git_tools.commit(
                    inputs["message"],
                    inputs.get("files")
                )
                return {"success": True, "commit": commit_hash}

            elif name == "git_status":
                return self.git_tools.get_status()

            elif name == "post_to_blackboard":
                entry_type = inputs["entry_type"]
                if entry_type == "discovery":
                    entry = self.blackboard.post_discovery(
                        self.agent.id, inputs["title"], inputs["content"]
                    )
                elif entry_type == "decision":
                    entry = self.blackboard.post_decision(
                        self.agent.id, inputs["title"], inputs["content"]
                    )
                elif entry_type == "blocker":
                    entry = self.blackboard.post_blocker(
                        self.agent.id, inputs["title"], inputs["content"]
                    )
                else:
                    entry = BlackboardEntry(
                        entry_type=EntryType.PROGRESS,
                        agent_id=self.agent.id,
                        project=self.project.name,
                        title=inputs["title"],
                        content=inputs["content"],
                        metadata=inputs.get("metadata", {}),
                    )
                    self.blackboard.add_entry(entry)
                return {"success": True, "entry_id": entry.id}

            elif name == "read_blackboard":
                entry_type = inputs.get("entry_type", "all")
                if entry_type == "discovery":
                    entries = self.blackboard.get_discoveries()
                elif entry_type == "decision":
                    entries = self.blackboard.get_decisions()
                elif entry_type == "blocker":
                    entries = self.blackboard.get_blockers()
                else:
                    entries = self.blackboard.entries

                return [
                    {
                        "id": e.id,
                        "type": e.entry_type.value,
                        "title": e.title,
                        "content": e.content,
                        "agent": e.agent_id,
                    }
                    for e in entries
                ]

            elif name == "send_message":
                entry = self.blackboard.send_message(
                    from_agent_id=self.agent.id,
                    to_agent_id=inputs["to_agent_type"],  # Will be resolved by orchestrator
                    message=inputs["message"],
                    context=inputs.get("context"),
                )
                if self.on_message:
                    await self.on_message({
                        "from": self.agent.id,
                        "to": inputs["to_agent_type"],
                        "message": inputs["message"],
                        "entry_id": entry.id,
                    })
                return {"success": True, "entry_id": entry.id}

            elif name == "complete_task":
                self.task_completed = True
                self.task_result = {
                    "summary": inputs["summary"],
                    "files_modified": inputs.get("files_modified", self.files_modified),
                    "follow_up_tasks": inputs.get("follow_up_tasks", []),
                }
                return {"success": True}

            else:
                return {"error": f"Unknown tool: {name}"}

        except Exception as e:
            return {"error": str(e)}

    def _build_context(self) -> str:
        """Build context string from blackboard and project."""
        parts = []

        # Recent discoveries
        discoveries = self.blackboard.get_discoveries()[-5:]
        if discoveries:
            parts.append("## Recent Discoveries")
            for d in discoveries:
                parts.append(f"- [{d.agent_id}] {d.title}: {d.content[:200]}")

        # Recent decisions
        decisions = self.blackboard.get_decisions()[-5:]
        if decisions:
            parts.append("\n## Decisions Made")
            for d in decisions:
                parts.append(f"- {d.title}: {d.content[:200]}")

        # Active blockers
        blockers = self.blackboard.get_blockers()
        if blockers:
            parts.append("\n## Current Blockers")
            for b in blockers:
                parts.append(f"- {b.title}: {b.content[:200]}")

        # Messages for this agent
        messages = self.blackboard.get_messages_for_agent(self.agent.id)
        if messages:
            parts.append("\n## Messages for You")
            for m in messages:
                parts.append(f"- From {m.agent_id}: {m.content}")

        return "\n".join(parts) if parts else "No additional context."
