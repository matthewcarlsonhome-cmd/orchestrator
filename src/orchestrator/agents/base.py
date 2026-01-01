"""Base agent class with Claude API integration."""

import json
from datetime import datetime
from typing import Any, Callable, Optional, Awaitable

from anthropic import Anthropic

from orchestrator.config import config
from orchestrator.models.agent import Agent, AgentType, AgentStatus
from orchestrator.models.task import Task
from orchestrator.models.project import Project
from orchestrator.models.blackboard import Blackboard, EntryType, BlackboardEntry
from orchestrator.tools.file_ops import FileTools
from orchestrator.tools.git_ops import GitTools
from orchestrator.tools.shell import ShellTools, ShellApprovalRequired
from orchestrator.agents.prompts import get_agent_system_prompt


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
    """Base class for all agents with Claude API integration."""

    def __init__(
        self,
        agent: Agent,
        project: Project,
        blackboard: Blackboard,
        approval_callback: Optional[Callable[[str], Awaitable[bool]]] = None,
        on_message: Optional[Callable[[dict], Awaitable[None]]] = None,
    ):
        self.agent = agent
        self.project = project
        self.blackboard = blackboard
        self.approval_callback = approval_callback
        self.on_message = on_message

        # Initialize tools
        self.file_tools = FileTools(project)
        self.git_tools = GitTools(project)
        self.shell_tools = ShellTools(project, approval_callback)

        # Claude client
        self.client = Anthropic(api_key=config.anthropic_api_key)

        # Conversation state
        self.messages: list[dict] = []
        self.task_completed = False
        self.task_result: Optional[dict] = None
        self.files_modified: list[str] = []

    async def execute_task(self, task: Task) -> dict:
        """Execute a task and return the result."""
        self.agent.assign_task(task.id, self.project.name)
        self.task_completed = False
        self.task_result = None
        self.files_modified = []
        self.messages = []

        # Build system prompt
        context = self._build_context()
        system_prompt = get_agent_system_prompt(
            agent_type=self.agent.agent_type,
            agent_id=self.agent.id,
            project_name=self.project.name,
            tech_stack=self.project.config.tech_stack,
            local_path=str(self.project.local_path),
            task_description=f"**{task.title}**\n\n{task.description}",
            context=context,
        )

        # Initial user message is the task
        self.messages.append({
            "role": "user",
            "content": f"Please complete this task: {task.title}\n\n{task.description}"
        })

        # Run the agent loop
        max_iterations = 50  # Safety limit
        iteration = 0

        while not self.task_completed and iteration < max_iterations:
            iteration += 1
            self.agent.heartbeat()

            try:
                response = self.client.messages.create(
                    model=config.model,
                    max_tokens=8192,
                    system=system_prompt,
                    tools=AGENT_TOOLS,
                    messages=self.messages,
                )

                # Process response
                await self._process_response(response)

            except Exception as e:
                self.agent.record_error()
                return {
                    "success": False,
                    "error": str(e),
                    "files_modified": self.files_modified,
                }

        self.agent.complete_task()

        if self.task_result:
            return {
                "success": True,
                **self.task_result,
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
