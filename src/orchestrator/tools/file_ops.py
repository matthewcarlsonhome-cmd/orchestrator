"""File operations for agents."""

import os
from pathlib import Path
from typing import Optional

from orchestrator.models.project import Project


class FileTools:
    """File operations within a project context."""

    def __init__(self, project: Project):
        self.project = project
        self.base_path = project.local_path

    def _resolve_path(self, path: str) -> Path:
        """Resolve a path relative to project root."""
        full_path = self.base_path / path
        # Security: ensure path doesn't escape project directory
        try:
            full_path.resolve().relative_to(self.base_path.resolve())
        except ValueError:
            raise ValueError(f"Path {path} escapes project directory")
        return full_path

    def read(self, path: str, max_lines: Optional[int] = None) -> str:
        """Read a file's contents."""
        full_path = self._resolve_path(path)
        if not full_path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        if not full_path.is_file():
            raise ValueError(f"Path is not a file: {path}")

        content = full_path.read_text()
        if max_lines:
            lines = content.splitlines()[:max_lines]
            content = "\n".join(lines)
        return content

    def write(self, path: str, content: str) -> bool:
        """Write content to a file."""
        full_path = self._resolve_path(path)
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content)
        return True

    def edit(self, path: str, old_text: str, new_text: str) -> bool:
        """Replace old_text with new_text in a file."""
        content = self.read(path)
        if old_text not in content:
            raise ValueError(f"Text not found in file: {old_text[:50]}...")
        new_content = content.replace(old_text, new_text, 1)
        return self.write(path, new_content)

    def append(self, path: str, content: str) -> bool:
        """Append content to a file."""
        full_path = self._resolve_path(path)
        with open(full_path, "a") as f:
            f.write(content)
        return True

    def delete(self, path: str) -> bool:
        """Delete a file."""
        full_path = self._resolve_path(path)
        if full_path.exists():
            full_path.unlink()
        return True

    def exists(self, path: str) -> bool:
        """Check if a file/directory exists."""
        return self._resolve_path(path).exists()

    def is_file(self, path: str) -> bool:
        """Check if path is a file."""
        return self._resolve_path(path).is_file()

    def is_dir(self, path: str) -> bool:
        """Check if path is a directory."""
        return self._resolve_path(path).is_dir()

    def mkdir(self, path: str) -> bool:
        """Create a directory."""
        full_path = self._resolve_path(path)
        full_path.mkdir(parents=True, exist_ok=True)
        return True

    def list_dir(
        self,
        path: str = ".",
        recursive: bool = False,
        pattern: Optional[str] = None,
    ) -> list[str]:
        """List directory contents."""
        full_path = self._resolve_path(path)
        if not full_path.is_dir():
            raise ValueError(f"Path is not a directory: {path}")

        if recursive:
            if pattern:
                files = list(full_path.rglob(pattern))
            else:
                files = list(full_path.rglob("*"))
        else:
            if pattern:
                files = list(full_path.glob(pattern))
            else:
                files = list(full_path.iterdir())

        # Filter out ignored patterns
        ignore = set(self.project.config.ignore_patterns)
        result = []
        for f in files:
            rel_path = f.relative_to(self.base_path)
            # Check if any part of the path matches ignore patterns
            if not any(part in ignore for part in rel_path.parts):
                result.append(str(rel_path))

        return sorted(result)

    def search(
        self,
        pattern: str,
        path: str = ".",
        file_pattern: Optional[str] = None,
    ) -> list[dict]:
        """Search for pattern in files. Returns list of matches."""
        import re

        full_path = self._resolve_path(path)
        results = []

        files = self.list_dir(path, recursive=True, pattern=file_pattern)
        for file_path in files:
            full_file = self._resolve_path(file_path)
            if not full_file.is_file():
                continue

            try:
                content = full_file.read_text()
                for i, line in enumerate(content.splitlines(), 1):
                    if re.search(pattern, line):
                        results.append({
                            "file": file_path,
                            "line": i,
                            "content": line.strip(),
                        })
            except (UnicodeDecodeError, PermissionError):
                continue  # Skip binary/unreadable files

        return results

    def get_file_info(self, path: str) -> dict:
        """Get file metadata."""
        full_path = self._resolve_path(path)
        stat = full_path.stat()
        return {
            "path": path,
            "size": stat.st_size,
            "modified": stat.st_mtime,
            "is_file": full_path.is_file(),
            "is_dir": full_path.is_dir(),
        }

    def get_tree(self, path: str = ".", max_depth: int = 3) -> str:
        """Get directory tree as string."""
        lines = []
        self._build_tree(self._resolve_path(path), "", max_depth, lines)
        return "\n".join(lines)

    def _build_tree(
        self, path: Path, prefix: str, max_depth: int, lines: list, depth: int = 0
    ) -> None:
        """Recursively build directory tree."""
        if depth > max_depth:
            return

        ignore = set(self.project.config.ignore_patterns)
        items = sorted(path.iterdir(), key=lambda x: (x.is_file(), x.name))

        for i, item in enumerate(items):
            if item.name in ignore:
                continue

            is_last = i == len(items) - 1
            connector = "└── " if is_last else "├── "
            lines.append(f"{prefix}{connector}{item.name}")

            if item.is_dir() and depth < max_depth:
                extension = "    " if is_last else "│   "
                self._build_tree(item, prefix + extension, max_depth, lines, depth + 1)
