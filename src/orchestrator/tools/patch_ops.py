"""
Patch Operations - Diff-only file modifications.

Instead of agents outputting full files, they output patches (unified diffs).
This reduces token usage by 3-10x on typical edits.

Usage:
    patch_tool = PatchTools(project)

    # Agent outputs a patch
    patch = '''
    --- a/src/auth.py
    +++ b/src/auth.py
    @@ -10,7 +10,7 @@
     def authenticate(user, password):
    -    return check_password(password)
    +    return check_password(user, password)
    '''

    result = patch_tool.apply_patch(patch)
"""

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from orchestrator.models.project import Project


@dataclass
class PatchResult:
    """Result of applying a patch."""
    success: bool
    file_path: str
    message: str
    lines_added: int = 0
    lines_removed: int = 0
    affected_lines: list[int] = None  # Line numbers that changed


@dataclass
class DiffHunk:
    """A single hunk from a unified diff."""
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    lines: list[str]


class PatchTools:
    """
    Tools for applying patches and generating diffs.

    This dramatically reduces token usage by having agents output
    only the changes, not entire files.
    """

    def __init__(self, project: Project):
        self.project = project
        self.repo_path = Path(project.local_path)

    def apply_patch(self, patch_content: str) -> PatchResult:
        """
        Apply a unified diff patch to a file.

        The patch should be in unified diff format:
        --- a/path/to/file
        +++ b/path/to/file
        @@ -start,count +start,count @@
         context line
        -removed line
        +added line
        """
        # Parse the patch to get file path
        file_match = re.search(r"^\+\+\+ [ab]/(.+)$", patch_content, re.MULTILINE)
        if not file_match:
            return PatchResult(
                success=False,
                file_path="",
                message="Could not parse file path from patch"
            )

        file_path = file_match.group(1)
        full_path = self.repo_path / file_path

        if not full_path.exists():
            return PatchResult(
                success=False,
                file_path=file_path,
                message=f"File not found: {file_path}"
            )

        # Try to apply with git apply first (handles edge cases better)
        try:
            result = subprocess.run(
                ["git", "apply", "--check", "-"],
                input=patch_content,
                capture_output=True,
                text=True,
                cwd=self.repo_path
            )
            if result.returncode == 0:
                # Patch is valid, apply it
                subprocess.run(
                    ["git", "apply", "-"],
                    input=patch_content,
                    capture_output=True,
                    text=True,
                    cwd=self.repo_path
                )
                return self._analyze_patch(patch_content, file_path)
        except FileNotFoundError:
            pass  # git not available, fall back to manual apply

        # Manual patch application
        return self._apply_manual(patch_content, file_path, full_path)

    def _apply_manual(self, patch_content: str, file_path: str, full_path: Path) -> PatchResult:
        """Apply patch manually without git."""
        try:
            original = full_path.read_text()
            lines = original.split("\n")

            hunks = self._parse_hunks(patch_content)
            if not hunks:
                return PatchResult(
                    success=False,
                    file_path=file_path,
                    message="No valid hunks found in patch"
                )

            # Apply hunks in reverse order (so line numbers stay valid)
            lines_added = 0
            lines_removed = 0
            affected = []

            for hunk in reversed(hunks):
                result = self._apply_hunk(lines, hunk)
                if not result["success"]:
                    return PatchResult(
                        success=False,
                        file_path=file_path,
                        message=f"Failed to apply hunk at line {hunk.old_start}: {result['message']}"
                    )
                lines = result["lines"]
                lines_added += result["added"]
                lines_removed += result["removed"]
                affected.extend(result["affected"])

            # Write the result
            full_path.write_text("\n".join(lines))

            return PatchResult(
                success=True,
                file_path=file_path,
                message=f"Applied patch: +{lines_added}/-{lines_removed} lines",
                lines_added=lines_added,
                lines_removed=lines_removed,
                affected_lines=sorted(set(affected))
            )

        except Exception as e:
            return PatchResult(
                success=False,
                file_path=file_path,
                message=f"Error applying patch: {e}"
            )

    def _parse_hunks(self, patch_content: str) -> list[DiffHunk]:
        """Parse unified diff into hunks."""
        hunks = []
        current_hunk = None

        for line in patch_content.split("\n"):
            # Hunk header: @@ -old_start,old_count +new_start,new_count @@
            hunk_match = re.match(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", line)
            if hunk_match:
                if current_hunk:
                    hunks.append(current_hunk)
                current_hunk = DiffHunk(
                    old_start=int(hunk_match.group(1)),
                    old_count=int(hunk_match.group(2) or 1),
                    new_start=int(hunk_match.group(3)),
                    new_count=int(hunk_match.group(4) or 1),
                    lines=[]
                )
            elif current_hunk and (line.startswith(" ") or line.startswith("+") or line.startswith("-")):
                current_hunk.lines.append(line)

        if current_hunk:
            hunks.append(current_hunk)

        return hunks

    def _apply_hunk(self, lines: list[str], hunk: DiffHunk) -> dict:
        """Apply a single hunk to the file lines."""
        result = {"success": False, "lines": lines, "added": 0, "removed": 0, "affected": [], "message": ""}

        # Find the context in the file
        start_idx = hunk.old_start - 1  # Convert to 0-indexed

        # Verify context matches (first non-change line)
        context_lines = [l[1:] for l in hunk.lines if l.startswith(" ")]
        if context_lines:
            # Check if context exists around the expected location
            found = False
            for offset in range(-3, 4):  # Search nearby
                check_idx = start_idx + offset
                if 0 <= check_idx < len(lines):
                    if lines[check_idx] == context_lines[0]:
                        start_idx = check_idx
                        found = True
                        break
            if not found:
                result["message"] = "Context not found"
                return result

        # Apply the changes
        new_lines = lines[:start_idx]
        idx = start_idx
        added = 0
        removed = 0
        affected = []

        for hunk_line in hunk.lines:
            if hunk_line.startswith(" "):
                # Context line - keep it
                if idx < len(lines):
                    new_lines.append(lines[idx])
                    idx += 1
            elif hunk_line.startswith("-"):
                # Remove line
                if idx < len(lines) and lines[idx] == hunk_line[1:]:
                    idx += 1
                    removed += 1
                elif idx < len(lines):
                    # Line doesn't match exactly, try to continue
                    idx += 1
                    removed += 1
            elif hunk_line.startswith("+"):
                # Add line
                new_lines.append(hunk_line[1:])
                added += 1
                affected.append(len(new_lines))

        # Add remaining lines
        new_lines.extend(lines[idx:])

        result["success"] = True
        result["lines"] = new_lines
        result["added"] = added
        result["removed"] = removed
        result["affected"] = affected
        return result

    def _analyze_patch(self, patch_content: str, file_path: str) -> PatchResult:
        """Analyze a patch to count changes."""
        lines_added = patch_content.count("\n+") - 1  # Exclude +++ line
        lines_removed = patch_content.count("\n-") - 1  # Exclude --- line

        return PatchResult(
            success=True,
            file_path=file_path,
            message=f"Applied patch: +{lines_added}/-{lines_removed} lines",
            lines_added=max(0, lines_added),
            lines_removed=max(0, lines_removed)
        )

    def generate_diff(self, file_path: str, old_content: str, new_content: str) -> str:
        """Generate a unified diff between old and new content."""
        import difflib

        old_lines = old_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)

        diff = difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=f"a/{file_path}",
            tofile=f"b/{file_path}",
            lineterm=""
        )

        return "".join(diff)

    def validate_patch(self, patch_content: str) -> dict:
        """
        Validate a patch without applying it.
        Returns info about what would change.
        """
        file_match = re.search(r"^\+\+\+ [ab]/(.+)$", patch_content, re.MULTILINE)
        if not file_match:
            return {"valid": False, "error": "Could not parse file path"}

        file_path = file_match.group(1)
        full_path = self.repo_path / file_path

        if not full_path.exists():
            return {"valid": False, "error": f"File not found: {file_path}"}

        hunks = self._parse_hunks(patch_content)
        if not hunks:
            return {"valid": False, "error": "No valid hunks found"}

        lines_added = sum(1 for h in hunks for l in h.lines if l.startswith("+"))
        lines_removed = sum(1 for h in hunks for l in h.lines if l.startswith("-"))

        return {
            "valid": True,
            "file_path": file_path,
            "hunks": len(hunks),
            "lines_added": lines_added,
            "lines_removed": lines_removed,
        }

    def get_affected_hunks(self, file_path: str, line_numbers: list[int], context: int = 3) -> str:
        """
        Get only the hunks that affect specific line numbers.
        Useful for showing just the relevant part of a file after a change.
        """
        full_path = self.repo_path / file_path
        if not full_path.exists():
            return ""

        lines = full_path.read_text().split("\n")
        result_lines = []

        for line_num in line_numbers:
            start = max(0, line_num - context - 1)
            end = min(len(lines), line_num + context)

            result_lines.append(f"--- {file_path}:{start+1}-{end} ---")
            for i in range(start, end):
                prefix = ">" if i == line_num - 1 else " "
                result_lines.append(f"{prefix} {i+1}: {lines[i]}")
            result_lines.append("")

        return "\n".join(result_lines)


# === Tool definitions for agents ===

PATCH_TOOLS = [
    {
        "name": "apply_patch",
        "description": "Apply a unified diff patch to modify a file. Use this instead of write_file for most edits. The patch should be in unified diff format with --- and +++ headers.",
        "input_schema": {
            "type": "object",
            "properties": {
                "patch": {
                    "type": "string",
                    "description": "The unified diff patch to apply"
                }
            },
            "required": ["patch"]
        }
    },
    {
        "name": "get_snippet",
        "description": "Get a specific line range from a file. Use this instead of read_file when you only need part of a file.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file"
                },
                "start_line": {
                    "type": "integer",
                    "description": "Starting line number (1-indexed)"
                },
                "end_line": {
                    "type": "integer",
                    "description": "Ending line number (inclusive)"
                }
            },
            "required": ["path", "start_line", "end_line"]
        }
    },
    {
        "name": "get_symbol",
        "description": "Get the code for a specific function, class, or method by name. More efficient than reading whole files.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Name of the function, class, or method"
                },
                "file_path": {
                    "type": "string",
                    "description": "Optional: specific file to look in"
                }
            },
            "required": ["name"]
        }
    },
    {
        "name": "search_symbols",
        "description": "Search for functions, classes, or methods by name pattern. Returns locations without full code.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query (partial name match)"
                },
                "kind": {
                    "type": "string",
                    "description": "Optional: filter by symbol type (function, class, method)",
                    "enum": ["function", "class", "method"]
                }
            },
            "required": ["query"]
        }
    },
]
