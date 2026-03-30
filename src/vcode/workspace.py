from __future__ import annotations as _annotations

from dataclasses import dataclass
from fnmatch import fnmatchcase
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vcode.approvals import ApprovalPolicy

__all__ = (
    "AgentDeps",
    "WorkspaceError",
    "WorkspacePathError",
    "can_write_path",
    "is_ignored_path",
    "list_workspace_files",
    "read_workspace_file",
    "resolve_workspace_path",
    "write_workspace_file",
)


@dataclass(frozen=True, slots=True, kw_only=True)
class AgentDeps:
    workspace_root: Path
    mode_id: str
    session_id: str
    approval_policy: ApprovalPolicy


class WorkspaceError(Exception):
    """Base exception for workspace access failures."""


class WorkspacePathError(WorkspaceError):
    """Raised when a requested path escapes the workspace root."""

    def __init__(self, path: str) -> None:
        self.path = path
        super().__init__(f"Path escapes workspace root: {path}")


def resolve_workspace_path(workspace_root: Path, path: str) -> Path:
    candidate = (workspace_root / path).resolve()
    try:
        candidate.relative_to(workspace_root)
    except ValueError as exc:
        raise WorkspacePathError(path) from exc
    return candidate


def can_write_path(mode_id: str, workspace_root: Path, target_path: Path) -> bool:
    relative_path = target_path.relative_to(workspace_root)
    if mode_id == "agent":
        return True
    if mode_id == "plan":
        return relative_path.parts[:2] == (".vcode", "plans")
    return False


def _load_ignore_patterns(workspace_root: Path) -> list[str]:
    ignore_file = workspace_root / ".vcode" / ".vcodeignore"
    if not ignore_file.exists():
        return []
    patterns: list[str] = []
    for raw_line in ignore_file.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith("!"):
            continue
        patterns.append(line)
    return patterns


def _match_ignore_pattern(relative_path: str, pattern: str) -> bool:
    normalized_path = relative_path.strip("/")
    normalized_pattern = pattern.strip()
    anchored = normalized_pattern.startswith("/")
    directory_only = normalized_pattern.endswith("/")
    normalized_pattern = normalized_pattern.strip("/")
    if not normalized_pattern:
        return False

    candidates = [normalized_pattern]
    if not anchored:
        candidates.append(f"**/{normalized_pattern}")

    if directory_only:
        path_prefixes = []
        current = normalized_path
        while current:
            path_prefixes.append(current)
            if "/" not in current:
                break
            current = current.rsplit("/", 1)[0]
        for prefix in path_prefixes:
            if fnmatchcase(prefix, normalized_pattern):
                return True
            if not anchored and fnmatchcase(prefix, f"*/{normalized_pattern}"):
                return True
        return False

    return any(fnmatchcase(normalized_path, candidate) for candidate in candidates)


def is_ignored_path(workspace_root: Path, target_path: Path) -> bool:
    relative_path = str(target_path.relative_to(workspace_root)).replace("\\", "/")
    if not relative_path or relative_path == ".":
        return False
    return any(
        _match_ignore_pattern(relative_path, pattern)
        for pattern in _load_ignore_patterns(workspace_root)
    )


def list_workspace_files(workspace_root: Path, path: str = ".", limit: int = 200) -> str:
    try:
        target = resolve_workspace_path(workspace_root, path)
    except WorkspacePathError as exc:
        return str(exc)
    if is_ignored_path(workspace_root, target):
        return f"Path is ignored by .vcode/.vcodeignore: {path}"
    if target.is_file():
        return str(target.relative_to(workspace_root))
    if not target.exists():
        return f"Path not found: {path}"

    entries: list[str] = []
    for candidate in sorted(target.rglob("*")):
        if candidate.name == "__pycache__":
            continue
        if is_ignored_path(workspace_root, candidate):
            continue
        relative = str(candidate.relative_to(workspace_root))
        if candidate.is_dir():
            relative = f"{relative}/"
        entries.append(relative)
        if len(entries) >= limit:
            entries.append("...")
            break

    if not entries:
        return f"No files under {path}"
    return "\n".join(entries)


def read_workspace_file(workspace_root: Path, path: str, max_chars: int = 20000) -> str:
    try:
        target = resolve_workspace_path(workspace_root, path)
    except WorkspacePathError as exc:
        return str(exc)
    if is_ignored_path(workspace_root, target):
        return f"Read denied by .vcode/.vcodeignore for path: {path}"
    if not target.exists() or not target.is_file():
        return f"File not found: {path}"
    content = target.read_text(encoding="utf-8")
    if len(content) <= max_chars:
        return content
    return f"{content[:max_chars]}\n\n[truncated]"


def write_workspace_file(workspace_root: Path, mode_id: str, path: str, content: str) -> str:
    try:
        target = resolve_workspace_path(workspace_root, path)
    except WorkspacePathError as exc:
        return str(exc)
    if not can_write_path(mode_id, workspace_root, target):
        return f"Write denied in {mode_id} mode for path: {path}"

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return f"Wrote {target.relative_to(workspace_root)}"
