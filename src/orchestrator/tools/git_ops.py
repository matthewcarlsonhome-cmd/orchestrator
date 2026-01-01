"""Git operations for agents."""

import subprocess
from pathlib import Path
from typing import Optional

from git import Repo
from git.exc import GitCommandError, InvalidGitRepositoryError

from orchestrator.models.project import Project


class GitTools:
    """Git operations for managing project repositories."""

    def __init__(self, project: Project):
        self.project = project
        self.repo: Optional[Repo] = None

    def clone(self, token: Optional[str] = None) -> bool:
        """Clone the project repository."""
        clone_url = self.project.config.github.get_clone_url()

        # Add token to URL if provided
        if token:
            clone_url = clone_url.replace(
                "https://", f"https://{token}@"
            )

        try:
            self.project.local_path.parent.mkdir(parents=True, exist_ok=True)
            self.repo = Repo.clone_from(
                clone_url,
                self.project.local_path,
                branch=self.project.config.github.default_branch,
            )
            self.project.is_cloned = True
            return True
        except GitCommandError as e:
            raise RuntimeError(f"Failed to clone repository: {e}")

    def open(self) -> bool:
        """Open an existing repository."""
        try:
            self.repo = Repo(self.project.local_path)
            self.project.is_cloned = True
            return True
        except InvalidGitRepositoryError:
            return False

    def ensure_repo(self) -> Repo:
        """Ensure we have a valid repo object."""
        if not self.repo:
            if self.project.local_path.exists():
                self.open()
            else:
                raise RuntimeError("Repository not cloned. Call clone() first.")
        return self.repo

    def pull(self, branch: Optional[str] = None) -> bool:
        """Pull latest changes from remote."""
        repo = self.ensure_repo()
        branch = branch or self.project.config.github.default_branch
        try:
            repo.remotes.origin.pull(branch)
            return True
        except GitCommandError as e:
            raise RuntimeError(f"Failed to pull: {e}")

    def create_branch(self, branch_name: str, from_branch: Optional[str] = None) -> bool:
        """Create a new branch."""
        repo = self.ensure_repo()
        from_branch = from_branch or self.project.config.github.default_branch

        try:
            # Checkout the source branch first
            repo.git.checkout(from_branch)
            # Create and checkout new branch
            repo.git.checkout("-b", branch_name)
            self.project.current_branch = branch_name
            return True
        except GitCommandError as e:
            raise RuntimeError(f"Failed to create branch: {e}")

    def checkout(self, branch_name: str) -> bool:
        """Checkout an existing branch."""
        repo = self.ensure_repo()
        try:
            repo.git.checkout(branch_name)
            self.project.current_branch = branch_name
            return True
        except GitCommandError as e:
            raise RuntimeError(f"Failed to checkout branch: {e}")

    def commit(self, message: str, files: Optional[list[str]] = None) -> str:
        """Commit changes. Returns commit hash."""
        repo = self.ensure_repo()
        try:
            if files:
                repo.index.add(files)
            else:
                repo.git.add("-A")

            # Check if there are changes to commit
            if not repo.index.diff("HEAD") and not repo.untracked_files:
                return ""  # Nothing to commit

            commit = repo.index.commit(message)
            return commit.hexsha
        except GitCommandError as e:
            raise RuntimeError(f"Failed to commit: {e}")

    def push(self, branch: Optional[str] = None, set_upstream: bool = True) -> bool:
        """Push changes to remote."""
        repo = self.ensure_repo()
        branch = branch or self.project.current_branch
        try:
            if set_upstream:
                repo.git.push("-u", "origin", branch)
            else:
                repo.git.push("origin", branch)
            return True
        except GitCommandError as e:
            raise RuntimeError(f"Failed to push: {e}")

    def get_status(self) -> dict:
        """Get repository status."""
        repo = self.ensure_repo()
        return {
            "branch": repo.active_branch.name,
            "is_dirty": repo.is_dirty(),
            "untracked_files": repo.untracked_files,
            "modified_files": [item.a_path for item in repo.index.diff(None)],
            "staged_files": [item.a_path for item in repo.index.diff("HEAD")],
        }

    def get_diff(self, staged: bool = False) -> str:
        """Get diff of changes."""
        repo = self.ensure_repo()
        if staged:
            return repo.git.diff("--cached")
        return repo.git.diff()

    def merge_branch(self, source_branch: str, target_branch: Optional[str] = None) -> bool:
        """Merge source branch into target branch."""
        repo = self.ensure_repo()
        target_branch = target_branch or self.project.config.github.work_branch

        try:
            repo.git.checkout(target_branch)
            repo.git.merge(source_branch)
            return True
        except GitCommandError as e:
            raise RuntimeError(f"Merge conflict or error: {e}")

    def create_pull_request(
        self,
        title: str,
        body: str,
        head_branch: str,
        base_branch: Optional[str] = None,
    ) -> str:
        """Create a pull request using gh CLI. Returns PR URL."""
        base_branch = base_branch or self.project.config.github.default_branch

        try:
            result = subprocess.run(
                [
                    "gh", "pr", "create",
                    "--title", title,
                    "--body", body,
                    "--head", head_branch,
                    "--base", base_branch,
                ],
                cwd=self.project.local_path,
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to create PR: {e.stderr}")
        except FileNotFoundError:
            raise RuntimeError("gh CLI not installed. Install with: brew install gh")

    def get_recent_commits(self, count: int = 10) -> list[dict]:
        """Get recent commit history."""
        repo = self.ensure_repo()
        commits = []
        for commit in list(repo.iter_commits())[:count]:
            commits.append({
                "hash": commit.hexsha[:8],
                "message": commit.message.strip(),
                "author": str(commit.author),
                "date": commit.committed_datetime.isoformat(),
            })
        return commits
