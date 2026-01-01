"""Shell command execution for agents."""

import asyncio
import subprocess
from pathlib import Path
from typing import Optional, Callable, Awaitable

from orchestrator.models.project import Project
from orchestrator.config import config


class ShellApprovalRequired(Exception):
    """Raised when a shell command requires user approval."""

    def __init__(self, command: str, reason: str):
        self.command = command
        self.reason = reason
        super().__init__(f"Approval required for: {command}")


class ShellTools:
    """Shell command execution with approval workflow."""

    def __init__(
        self,
        project: Project,
        approval_callback: Optional[Callable[[str], Awaitable[bool]]] = None,
    ):
        self.project = project
        self.cwd = project.local_path
        self.approval_callback = approval_callback

        # Commands that are always safe
        self.safe_commands = {
            "ls", "cat", "head", "tail", "grep", "find", "wc",
            "pwd", "echo", "date", "which", "whereis",
        }

    def _is_allowed(self, command: str) -> bool:
        """Check if command is in allowed list."""
        first_word = command.split()[0] if command.split() else ""

        # Check against safe commands
        if first_word in self.safe_commands:
            return True

        # Check against configured allowed commands
        if first_word in config.allowed_shell_commands:
            return True

        return False

    def _needs_approval(self, command: str) -> bool:
        """Check if command needs user approval."""
        if not config.require_shell_approval:
            return False

        return not self._is_allowed(command)

    async def run(
        self,
        command: str,
        timeout: int = 300,
        env: Optional[dict] = None,
    ) -> dict:
        """
        Run a shell command.

        Returns dict with:
            - success: bool
            - stdout: str
            - stderr: str
            - return_code: int
            - approved: bool (whether approval was needed/granted)
        """
        # Check if approval is needed
        if self._needs_approval(command):
            if self.approval_callback:
                approved = await self.approval_callback(command)
                if not approved:
                    return {
                        "success": False,
                        "stdout": "",
                        "stderr": "Command not approved by user",
                        "return_code": -1,
                        "approved": False,
                    }
            else:
                raise ShellApprovalRequired(
                    command,
                    "Command requires user approval but no approval callback provided"
                )

        # Prepare environment
        run_env = dict(subprocess.os.environ)
        if env:
            run_env.update(env)

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.cwd,
                env=run_env,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=timeout
                )
            except asyncio.TimeoutError:
                proc.kill()
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": f"Command timed out after {timeout}s",
                    "return_code": -1,
                    "approved": True,
                }

            return {
                "success": proc.returncode == 0,
                "stdout": stdout.decode() if stdout else "",
                "stderr": stderr.decode() if stderr else "",
                "return_code": proc.returncode,
                "approved": True,
            }

        except Exception as e:
            return {
                "success": False,
                "stdout": "",
                "stderr": str(e),
                "return_code": -1,
                "approved": True,
            }

    def run_sync(
        self,
        command: str,
        timeout: int = 300,
        env: Optional[dict] = None,
    ) -> dict:
        """Synchronous version of run() for non-async contexts."""
        if self._needs_approval(command):
            raise ShellApprovalRequired(
                command,
                "Synchronous execution doesn't support approval workflow"
            )

        run_env = dict(subprocess.os.environ)
        if env:
            run_env.update(env)

        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=self.cwd,
                env=run_env,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "return_code": result.returncode,
                "approved": True,
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Command timed out after {timeout}s",
                "return_code": -1,
                "approved": True,
            }
        except Exception as e:
            return {
                "success": False,
                "stdout": "",
                "stderr": str(e),
                "return_code": -1,
                "approved": True,
            }

    async def run_npm(self, args: str, timeout: int = 300) -> dict:
        """Run an npm command."""
        return await self.run(f"npm {args}", timeout=timeout)

    async def run_python(self, script: str, timeout: int = 300) -> dict:
        """Run a python command."""
        return await self.run(f"python {script}", timeout=timeout)

    async def run_pip(self, args: str, timeout: int = 300) -> dict:
        """Run a pip command."""
        return await self.run(f"pip {args}", timeout=timeout)

    async def install_dependencies(self) -> dict:
        """Install project dependencies based on project type."""
        cmds = self.project.config.commands

        if cmds.install:
            return await self.run(cmds.install)

        # Auto-detect based on files
        if (self.cwd / "package.json").exists():
            return await self.run("npm install")
        elif (self.cwd / "requirements.txt").exists():
            return await self.run("pip install -r requirements.txt")
        elif (self.cwd / "pyproject.toml").exists():
            return await self.run("pip install -e .")

        return {"success": True, "stdout": "No dependencies to install", "stderr": "", "return_code": 0}

    async def run_tests(self) -> dict:
        """Run project tests."""
        cmds = self.project.config.commands

        if cmds.test:
            return await self.run(cmds.test, timeout=600)

        # Auto-detect
        if (self.cwd / "package.json").exists():
            return await self.run("npm test", timeout=600)
        elif (self.cwd / "pytest.ini").exists() or (self.cwd / "tests").exists():
            return await self.run("pytest", timeout=600)

        return {"success": True, "stdout": "No tests configured", "stderr": "", "return_code": 0}

    async def run_build(self) -> dict:
        """Run project build."""
        cmds = self.project.config.commands

        if cmds.build:
            return await self.run(cmds.build, timeout=600)

        # Auto-detect
        if (self.cwd / "package.json").exists():
            return await self.run("npm run build", timeout=600)

        return {"success": True, "stdout": "No build configured", "stderr": "", "return_code": 0}
