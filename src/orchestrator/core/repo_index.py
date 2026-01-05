"""
Repo Index - Smart codebase indexing for token-efficient agent access.

Instead of agents reading entire files, they query this index for:
- File summaries (what's in each file)
- Symbol table (functions, classes, their locations)
- Dependency graph (imports/exports)
- Targeted snippets (specific line ranges or symbols)

This dramatically reduces token usage by giving agents only what they need.
"""

import ast
import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class Symbol:
    """A code symbol (function, class, variable)."""
    name: str
    kind: str  # function, class, method, variable, const
    file_path: str
    start_line: int
    end_line: int
    signature: str = ""  # e.g., "def foo(a: int, b: str) -> bool"
    docstring: str = ""
    parent: Optional[str] = None  # For methods, the class name


@dataclass
class FileSummary:
    """Summary of a file without full content."""
    path: str
    language: str
    size_bytes: int
    line_count: int
    last_modified: datetime
    content_hash: str
    summary: str  # 1-2 sentence description
    symbols: list[str] = field(default_factory=list)  # Symbol names in this file
    imports: list[str] = field(default_factory=list)  # What this file imports
    exports: list[str] = field(default_factory=list)  # What this file exports


@dataclass
class Snippet:
    """A targeted code snippet."""
    file_path: str
    start_line: int
    end_line: int
    content: str
    context: str = ""  # Brief description of what this snippet is


class RepoIndex:
    """
    Smart repository index for token-efficient code access.

    Usage:
        index = RepoIndex(repo_path)
        index.build()  # Scan and index the repo

        # Agents query the index instead of reading files
        summary = index.get_file_summary("src/app.py")
        symbols = index.find_symbols("handleLogin")
        snippet = index.get_snippet("src/auth.py", 50, 80)
        deps = index.get_dependencies("src/routes.py")
    """

    def __init__(self, repo_path: str | Path, ignore_patterns: list[str] = None):
        self.repo_path = Path(repo_path)
        self.ignore_patterns = ignore_patterns or [
            "node_modules", ".git", "__pycache__", ".venv",
            "dist", "build", ".next", "*.pyc", "*.min.js"
        ]

        # Index storage
        self.files: dict[str, FileSummary] = {}
        self.symbols: dict[str, list[Symbol]] = {}  # name -> list of symbols
        self.dependencies: dict[str, list[str]] = {}  # file -> imports

        # Cache for snippets
        self._snippet_cache: dict[str, str] = {}

        # Language detection
        self._lang_map = {
            ".py": "python",
            ".js": "javascript",
            ".jsx": "javascript",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".go": "go",
            ".rs": "rust",
            ".java": "java",
            ".rb": "ruby",
            ".php": "php",
            ".css": "css",
            ".html": "html",
            ".json": "json",
            ".yaml": "yaml",
            ".yml": "yaml",
            ".md": "markdown",
        }

    def build(self) -> dict:
        """
        Build the complete index. Returns stats about what was indexed.
        """
        stats = {"files": 0, "symbols": 0, "errors": []}

        for file_path in self._iter_files():
            try:
                self._index_file(file_path)
                stats["files"] += 1
            except Exception as e:
                stats["errors"].append(f"{file_path}: {e}")

        stats["symbols"] = sum(len(syms) for syms in self.symbols.values())
        return stats

    def _iter_files(self):
        """Iterate over all files, respecting ignore patterns."""
        for path in self.repo_path.rglob("*"):
            if path.is_file() and not self._should_ignore(path):
                yield path

    def _should_ignore(self, path: Path) -> bool:
        """Check if path matches any ignore pattern."""
        path_str = str(path)
        for pattern in self.ignore_patterns:
            if pattern.startswith("*"):
                if path_str.endswith(pattern[1:]):
                    return True
            elif pattern in path_str:
                return True
        return False

    def _index_file(self, path: Path):
        """Index a single file."""
        rel_path = str(path.relative_to(self.repo_path))
        lang = self._detect_language(path)

        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return

        lines = content.split("\n")

        # Create file summary
        summary = FileSummary(
            path=rel_path,
            language=lang,
            size_bytes=path.stat().st_size,
            line_count=len(lines),
            last_modified=datetime.fromtimestamp(path.stat().st_mtime),
            content_hash=hashlib.md5(content.encode()).hexdigest()[:12],
            summary=self._generate_summary(content, lang),
            imports=self._extract_imports(content, lang),
            exports=self._extract_exports(content, lang),
        )

        # Extract symbols
        symbols = self._extract_symbols(content, lang, rel_path)
        summary.symbols = [s.name for s in symbols]

        self.files[rel_path] = summary
        self.dependencies[rel_path] = summary.imports

        for sym in symbols:
            if sym.name not in self.symbols:
                self.symbols[sym.name] = []
            self.symbols[sym.name].append(sym)

    def _detect_language(self, path: Path) -> str:
        """Detect language from file extension."""
        return self._lang_map.get(path.suffix.lower(), "unknown")

    def _generate_summary(self, content: str, lang: str) -> str:
        """Generate a 1-2 sentence summary of the file."""
        lines = content.split("\n")[:50]  # First 50 lines

        # Look for docstrings, comments, or class/function names
        if lang == "python":
            # Check for module docstring
            if lines and lines[0].startswith('"""') or lines[0].startswith("'''"):
                end = 1
                quote = lines[0][:3]
                while end < len(lines) and quote not in lines[end]:
                    end += 1
                docstring = " ".join(lines[:end+1]).replace(quote, "").strip()
                if len(docstring) > 200:
                    docstring = docstring[:200] + "..."
                return docstring

        # Look for main exports
        classes = re.findall(r"class\s+(\w+)", content[:2000])
        functions = re.findall(r"(?:def|function|const|export)\s+(\w+)", content[:2000])

        if classes:
            return f"Defines: {', '.join(classes[:5])}"
        if functions:
            return f"Contains: {', '.join(functions[:5])}"

        return "Code file"

    def _extract_imports(self, content: str, lang: str) -> list[str]:
        """Extract import statements."""
        imports = []

        if lang == "python":
            # import x, from x import y
            imports.extend(re.findall(r"^import\s+([\w.]+)", content, re.MULTILINE))
            imports.extend(re.findall(r"^from\s+([\w.]+)\s+import", content, re.MULTILINE))

        elif lang in ("javascript", "typescript"):
            # import x from 'y', require('y')
            imports.extend(re.findall(r"from\s+['\"]([^'\"]+)['\"]", content))
            imports.extend(re.findall(r"require\(['\"]([^'\"]+)['\"]\)", content))

        return list(set(imports))

    def _extract_exports(self, content: str, lang: str) -> list[str]:
        """Extract exported symbols."""
        exports = []

        if lang in ("javascript", "typescript"):
            exports.extend(re.findall(r"export\s+(?:default\s+)?(?:class|function|const|let|var)\s+(\w+)", content))
            exports.extend(re.findall(r"export\s*\{([^}]+)\}", content))

        elif lang == "python":
            # __all__ = [...]
            all_match = re.search(r"__all__\s*=\s*\[([^\]]+)\]", content)
            if all_match:
                exports = re.findall(r"['\"](\w+)['\"]", all_match.group(1))

        return exports

    def _extract_symbols(self, content: str, lang: str, file_path: str) -> list[Symbol]:
        """Extract function and class definitions."""
        symbols = []
        lines = content.split("\n")

        if lang == "python":
            try:
                tree = ast.parse(content)
                symbols.extend(self._extract_python_symbols(tree, file_path, lines))
            except SyntaxError:
                pass

        elif lang in ("javascript", "typescript"):
            symbols.extend(self._extract_js_symbols(content, file_path, lines))

        return symbols

    def _extract_python_symbols(self, tree: ast.AST, file_path: str, lines: list[str]) -> list[Symbol]:
        """Extract symbols from Python AST."""
        symbols = []

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                symbols.append(Symbol(
                    name=node.name,
                    kind="function",
                    file_path=file_path,
                    start_line=node.lineno,
                    end_line=node.end_lineno or node.lineno,
                    signature=self._get_python_signature(node, lines),
                    docstring=ast.get_docstring(node) or "",
                ))

            elif isinstance(node, ast.ClassDef):
                symbols.append(Symbol(
                    name=node.name,
                    kind="class",
                    file_path=file_path,
                    start_line=node.lineno,
                    end_line=node.end_lineno or node.lineno,
                    signature=f"class {node.name}",
                    docstring=ast.get_docstring(node) or "",
                ))

                # Also extract methods
                for item in node.body:
                    if isinstance(item, ast.FunctionDef):
                        symbols.append(Symbol(
                            name=item.name,
                            kind="method",
                            file_path=file_path,
                            start_line=item.lineno,
                            end_line=item.end_lineno or item.lineno,
                            signature=self._get_python_signature(item, lines),
                            docstring=ast.get_docstring(item) or "",
                            parent=node.name,
                        ))

        return symbols

    def _get_python_signature(self, node: ast.FunctionDef, lines: list[str]) -> str:
        """Get function signature from source."""
        start = node.lineno - 1
        sig_lines = []
        for i in range(start, min(start + 5, len(lines))):
            sig_lines.append(lines[i])
            if ":" in lines[i] and not lines[i].strip().endswith(","):
                break
        return " ".join(sig_lines).strip()

    def _extract_js_symbols(self, content: str, file_path: str, lines: list[str]) -> list[Symbol]:
        """Extract symbols from JavaScript/TypeScript using regex."""
        symbols = []

        # Functions: function name(), const name = () =>, async function name()
        for match in re.finditer(
            r"(?:export\s+)?(?:async\s+)?(?:function\s+(\w+)|(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>)",
            content
        ):
            name = match.group(1) or match.group(2)
            line_num = content[:match.start()].count("\n") + 1
            symbols.append(Symbol(
                name=name,
                kind="function",
                file_path=file_path,
                start_line=line_num,
                end_line=line_num,  # Would need proper parsing for accurate end
                signature=match.group(0)[:100],
            ))

        # Classes: class Name
        for match in re.finditer(r"(?:export\s+)?class\s+(\w+)", content):
            name = match.group(1)
            line_num = content[:match.start()].count("\n") + 1
            symbols.append(Symbol(
                name=name,
                kind="class",
                file_path=file_path,
                start_line=line_num,
                end_line=line_num,
                signature=f"class {name}",
            ))

        return symbols

    # === Query Methods (what agents use) ===

    def get_file_summary(self, path: str) -> Optional[FileSummary]:
        """Get summary of a file without its content."""
        return self.files.get(path)

    def find_symbols(self, name: str, exact: bool = False) -> list[Symbol]:
        """Find symbols by name. Returns all matches if name appears in multiple files."""
        if exact:
            return self.symbols.get(name, [])

        # Fuzzy match
        results = []
        name_lower = name.lower()
        for sym_name, syms in self.symbols.items():
            if name_lower in sym_name.lower():
                results.extend(syms)
        return results

    def get_symbol(self, name: str, file_path: str = None) -> Optional[Symbol]:
        """Get a specific symbol, optionally filtering by file."""
        symbols = self.symbols.get(name, [])
        if file_path:
            symbols = [s for s in symbols if s.file_path == file_path]
        return symbols[0] if symbols else None

    def get_snippet(self, file_path: str, start_line: int, end_line: int) -> Optional[Snippet]:
        """Get a specific line range from a file."""
        full_path = self.repo_path / file_path
        if not full_path.exists():
            return None

        try:
            lines = full_path.read_text().split("\n")
            # Adjust to 0-indexed, clamp to valid range
            start = max(0, start_line - 1)
            end = min(len(lines), end_line)

            content = "\n".join(lines[start:end])
            return Snippet(
                file_path=file_path,
                start_line=start_line,
                end_line=end_line,
                content=content,
            )
        except Exception:
            return None

    def get_symbol_snippet(self, symbol_name: str, file_path: str = None) -> Optional[Snippet]:
        """Get the code for a specific symbol (function, class, etc.)."""
        symbol = self.get_symbol(symbol_name, file_path)
        if not symbol:
            return None

        snippet = self.get_snippet(symbol.file_path, symbol.start_line, symbol.end_line)
        if snippet:
            snippet.context = f"{symbol.kind} {symbol.name}"
        return snippet

    def get_dependencies(self, file_path: str) -> list[str]:
        """Get what a file imports."""
        return self.dependencies.get(file_path, [])

    def get_dependents(self, file_path: str) -> list[str]:
        """Get files that import this file."""
        dependents = []
        for path, deps in self.dependencies.items():
            # Check if any import matches this file
            file_name = Path(file_path).stem
            if any(file_name in dep for dep in deps):
                dependents.append(path)
        return dependents

    def search_symbols(self, query: str, kind: str = None) -> list[Symbol]:
        """Search for symbols matching a query."""
        results = []
        query_lower = query.lower()

        for name, symbols in self.symbols.items():
            if query_lower in name.lower():
                for sym in symbols:
                    if kind is None or sym.kind == kind:
                        results.append(sym)

        return results[:50]  # Limit results

    def list_files(self, pattern: str = None, language: str = None) -> list[str]:
        """List files, optionally filtered by pattern or language."""
        results = []
        for path, summary in self.files.items():
            if pattern and pattern not in path:
                continue
            if language and summary.language != language:
                continue
            results.append(path)
        return results

    def get_context_budget(self, max_tokens: int = 8000) -> str:
        """
        Get a token-budgeted overview of the repo.
        Returns a summary that fits within the token limit.
        """
        # Rough estimate: 4 chars per token
        char_budget = max_tokens * 4

        lines = ["# Repository Overview\n"]

        # File tree (compact)
        lines.append("## Files\n")
        for path in sorted(self.files.keys())[:100]:  # Limit files
            summary = self.files[path]
            lines.append(f"- {path} ({summary.language}, {summary.line_count} lines)")

        # Key symbols
        lines.append("\n## Key Symbols\n")
        for name, symbols in list(self.symbols.items())[:50]:
            sym = symbols[0]
            lines.append(f"- {sym.kind} `{name}` in {sym.file_path}:{sym.start_line}")

        result = "\n".join(lines)
        if len(result) > char_budget:
            result = result[:char_budget] + "\n... (truncated)"

        return result

    def get_stats(self) -> dict:
        """Get index statistics."""
        return {
            "files_indexed": len(self.files),
            "total_symbols": sum(len(s) for s in self.symbols.values()),
            "languages": list(set(f.language for f in self.files.values())),
            "total_lines": sum(f.line_count for f in self.files.values()),
        }

    def to_json(self) -> str:
        """Serialize index to JSON for persistence."""
        data = {
            "files": {k: {
                "path": v.path,
                "language": v.language,
                "size_bytes": v.size_bytes,
                "line_count": v.line_count,
                "summary": v.summary,
                "symbols": v.symbols,
                "imports": v.imports,
            } for k, v in self.files.items()},
            "symbols": {k: [{
                "name": s.name,
                "kind": s.kind,
                "file_path": s.file_path,
                "start_line": s.start_line,
                "end_line": s.end_line,
                "signature": s.signature,
            } for s in v] for k, v in self.symbols.items()},
        }
        return json.dumps(data, indent=2)

    @classmethod
    def from_json(cls, json_str: str, repo_path: str) -> "RepoIndex":
        """Load index from JSON."""
        data = json.loads(json_str)
        index = cls(repo_path)

        for path, fdata in data.get("files", {}).items():
            index.files[path] = FileSummary(
                path=fdata["path"],
                language=fdata["language"],
                size_bytes=fdata["size_bytes"],
                line_count=fdata["line_count"],
                last_modified=datetime.now(),
                content_hash="",
                summary=fdata["summary"],
                symbols=fdata.get("symbols", []),
                imports=fdata.get("imports", []),
            )

        for name, syms in data.get("symbols", {}).items():
            index.symbols[name] = [
                Symbol(
                    name=s["name"],
                    kind=s["kind"],
                    file_path=s["file_path"],
                    start_line=s["start_line"],
                    end_line=s["end_line"],
                    signature=s.get("signature", ""),
                )
                for s in syms
            ]

        return index
