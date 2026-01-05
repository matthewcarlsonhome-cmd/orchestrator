"""
Task Contracts - Frozen task definitions with verifiable completion criteria.

Prevents agents from "wandering" by defining exactly:
- What files can be touched
- What the done criteria are
- Maximum iterations allowed
- Tests that must pass

Once a contract is created, agents cannot deviate from it.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import uuid4


class ContractStatus(str, Enum):
    DRAFT = "draft"        # Being created
    FROZEN = "frozen"      # Locked, ready for execution
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


@dataclass
class DoneCriteria:
    """Verifiable criteria for task completion."""
    tests_pass: list[str] = field(default_factory=list)  # Test commands that must pass
    lint_pass: bool = False  # Linting must pass
    files_exist: list[str] = field(default_factory=list)  # Files that must exist
    files_modified: list[str] = field(default_factory=list)  # Files that must be changed
    contains_strings: dict[str, list[str]] = field(default_factory=dict)  # file -> strings it must contain
    build_pass: bool = False  # Build must succeed


@dataclass
class TaskContract:
    """
    A frozen contract defining exactly what a task should accomplish.

    Once frozen, agents CANNOT:
    - Touch files not in allowed_files
    - Make more than max_iterations API calls
    - Revisit architecture decisions
    - Do "research" unless explicitly allowed

    The contract is verified programmatically - no agent judgment needed.
    """

    id: str = field(default_factory=lambda: str(uuid4())[:8])
    task_id: str = ""
    title: str = ""
    description: str = ""

    # Constraints
    allowed_files: list[str] = field(default_factory=list)  # Files agent can read/write
    forbidden_files: list[str] = field(default_factory=list)  # Files agent must NOT touch
    max_iterations: int = 10  # Max API calls
    max_tokens: int = 15000  # Token budget for this task
    timeout_minutes: int = 10

    # Completion criteria
    done_criteria: DoneCriteria = field(default_factory=DoneCriteria)

    # Execution tracking
    status: ContractStatus = ContractStatus.DRAFT
    iterations_used: int = 0
    tokens_used: int = 0
    files_touched: list[str] = field(default_factory=list)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # Decisions (frozen after planning)
    decisions: dict[str, str] = field(default_factory=dict)  # key -> decision
    constraints: list[str] = field(default_factory=list)  # e.g., "use TypeScript", "no new deps"

    # Model to use
    model: str = "claude-3-5-haiku-20241022"  # Default to cheap model
    use_expensive_model: bool = False  # Flag for complex tasks

    def freeze(self) -> bool:
        """
        Freeze the contract. After this, constraints cannot be changed.
        Returns False if contract is invalid.
        """
        if not self.title or not self.description:
            return False

        if not self.allowed_files and not self.done_criteria.files_modified:
            return False  # Must specify what files are in scope

        self.status = ContractStatus.FROZEN
        return True

    def start(self):
        """Mark contract as in progress."""
        if self.status != ContractStatus.FROZEN:
            raise ValueError("Cannot start unfrozen contract")
        self.status = ContractStatus.IN_PROGRESS
        self.started_at = datetime.utcnow()

    def can_touch_file(self, path: str) -> bool:
        """Check if agent is allowed to touch this file."""
        if self.status == ContractStatus.DRAFT:
            return True  # No restrictions during planning

        # Check forbidden first
        for pattern in self.forbidden_files:
            if pattern in path:
                return False

        # If allowed_files is empty, allow all (except forbidden)
        if not self.allowed_files:
            return True

        # Check against allowed patterns
        for pattern in self.allowed_files:
            if pattern in path or path.endswith(pattern):
                return True

        return False

    def record_file_touch(self, path: str):
        """Record that a file was touched."""
        if path not in self.files_touched:
            self.files_touched.append(path)

    def record_iteration(self, tokens: int = 0):
        """Record an API call iteration."""
        self.iterations_used += 1
        self.tokens_used += tokens

    def is_over_budget(self) -> bool:
        """Check if contract has exceeded its budget."""
        if self.iterations_used >= self.max_iterations:
            return True
        if self.tokens_used >= self.max_tokens:
            return True
        return False

    def check_done(self, runner: "LocalRunner") -> dict:
        """
        Check if done criteria are met.
        Returns {"done": bool, "failures": [...]}
        """
        failures = []
        criteria = self.done_criteria

        # Check tests
        for test_cmd in criteria.tests_pass:
            result = runner.run_command(test_cmd)
            if not result["success"]:
                failures.append(f"Test failed: {test_cmd}")

        # Check lint
        if criteria.lint_pass:
            result = runner.run_lint()
            if not result["success"]:
                failures.append("Lint failed")

        # Check files exist
        for file_path in criteria.files_exist:
            if not runner.file_exists(file_path):
                failures.append(f"File missing: {file_path}")

        # Check files modified
        for file_path in criteria.files_modified:
            if file_path not in self.files_touched:
                failures.append(f"File not modified: {file_path}")

        # Check build
        if criteria.build_pass:
            result = runner.run_build()
            if not result["success"]:
                failures.append("Build failed")

        return {
            "done": len(failures) == 0,
            "failures": failures
        }

    def complete(self, success: bool = True):
        """Mark contract as completed."""
        self.status = ContractStatus.COMPLETED if success else ContractStatus.FAILED
        self.completed_at = datetime.utcnow()

    def to_prompt(self) -> str:
        """Generate the contract as a prompt section for the agent."""
        lines = [
            "## Task Contract (FROZEN - Do not deviate)",
            f"**Task:** {self.title}",
            f"**Description:** {self.description}",
            "",
            "### Constraints",
            f"- Max iterations: {self.max_iterations} (used: {self.iterations_used})",
            f"- Token budget: {self.max_tokens} (used: {self.tokens_used})",
        ]

        if self.allowed_files:
            lines.append(f"- Allowed files: {', '.join(self.allowed_files)}")

        if self.forbidden_files:
            lines.append(f"- FORBIDDEN files: {', '.join(self.forbidden_files)}")

        if self.constraints:
            lines.append("")
            lines.append("### Decisions (Do not revisit)")
            for c in self.constraints:
                lines.append(f"- {c}")

        if self.decisions:
            for key, value in self.decisions.items():
                lines.append(f"- {key}: {value}")

        lines.append("")
        lines.append("### Done Criteria")
        criteria = self.done_criteria

        if criteria.tests_pass:
            lines.append(f"- Tests must pass: {', '.join(criteria.tests_pass)}")
        if criteria.lint_pass:
            lines.append("- Linting must pass")
        if criteria.build_pass:
            lines.append("- Build must succeed")
        if criteria.files_modified:
            lines.append(f"- Must modify: {', '.join(criteria.files_modified)}")
        if criteria.files_exist:
            lines.append(f"- Must create: {', '.join(criteria.files_exist)}")

        lines.append("")
        lines.append("**IMPORTANT: Do not research or explore beyond this scope.**")
        lines.append("**If blocked, report the blocker immediately.**")

        return "\n".join(lines)

    def to_dict(self) -> dict:
        """Serialize for storage."""
        return {
            "id": self.id,
            "task_id": self.task_id,
            "title": self.title,
            "description": self.description,
            "allowed_files": self.allowed_files,
            "forbidden_files": self.forbidden_files,
            "max_iterations": self.max_iterations,
            "max_tokens": self.max_tokens,
            "status": self.status.value,
            "iterations_used": self.iterations_used,
            "tokens_used": self.tokens_used,
            "files_touched": self.files_touched,
            "decisions": self.decisions,
            "constraints": self.constraints,
            "model": self.model,
        }


class ContractBuilder:
    """
    Builds task contracts from decomposed tasks.
    Uses a cheap model to create the initial contract.
    """

    @staticmethod
    def from_task(task: "Task", repo_index: "RepoIndex" = None) -> TaskContract:
        """
        Create a contract from a Task object.
        Infers allowed files from the task description.
        """
        contract = TaskContract(
            task_id=task.id,
            title=task.title,
            description=task.description,
        )

        # Infer allowed files from task metadata
        if hasattr(task, "files") and task.files:
            contract.allowed_files = task.files

        # Set model based on task complexity
        if hasattr(task, "priority"):
            from orchestrator.models.task import TaskPriority
            if task.priority == TaskPriority.CRITICAL:
                contract.use_expensive_model = True
                contract.model = "claude-sonnet-4-20250514"

        # Default done criteria
        contract.done_criteria.lint_pass = True

        return contract

    @staticmethod
    def create_simple(
        title: str,
        description: str,
        files: list[str],
        tests: list[str] = None,
        max_iterations: int = 10,
    ) -> TaskContract:
        """Create a simple contract with common defaults."""
        contract = TaskContract(
            title=title,
            description=description,
            allowed_files=files,
            max_iterations=max_iterations,
        )

        if tests:
            contract.done_criteria.tests_pass = tests

        contract.done_criteria.lint_pass = True
        contract.freeze()

        return contract


class LocalRunner:
    """
    Runs local commands for contract verification.
    These are deterministic steps that don't need AI.
    """

    def __init__(self, repo_path: str):
        self.repo_path = repo_path

    def run_command(self, cmd: str) -> dict:
        """Run a shell command and return result."""
        import subprocess
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                cwd=self.repo_path,
                timeout=60
            )
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def run_lint(self) -> dict:
        """Run linting based on project type."""
        # Try common linters
        for cmd in ["npm run lint", "ruff check .", "eslint .", "pylint ."]:
            result = self.run_command(cmd)
            if "command not found" not in result.get("stderr", ""):
                return result
        return {"success": True, "message": "No linter configured"}

    def run_build(self) -> dict:
        """Run build command."""
        for cmd in ["npm run build", "python setup.py build", "cargo build"]:
            result = self.run_command(cmd)
            if "command not found" not in result.get("stderr", ""):
                return result
        return {"success": True, "message": "No build configured"}

    def run_tests(self, test_cmd: str = None) -> dict:
        """Run tests."""
        if test_cmd:
            return self.run_command(test_cmd)

        for cmd in ["npm test", "pytest", "cargo test", "go test ./..."]:
            result = self.run_command(cmd)
            if "command not found" not in result.get("stderr", ""):
                return result
        return {"success": True, "message": "No tests configured"}

    def file_exists(self, path: str) -> bool:
        """Check if file exists."""
        from pathlib import Path
        return (Path(self.repo_path) / path).exists()

    def get_file_hash(self, path: str) -> str:
        """Get hash of file contents for change detection."""
        import hashlib
        from pathlib import Path
        full_path = Path(self.repo_path) / path
        if not full_path.exists():
            return ""
        content = full_path.read_bytes()
        return hashlib.md5(content).hexdigest()
