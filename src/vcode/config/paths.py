from __future__ import annotations as _annotations

from pathlib import Path

__all__ = (
    "agents_file",
    "global_vcode_dir",
    "hooks_file",
    "local_preferences_file",
    "local_hooks_file",
    "local_mcp_file",
    "mcp_file",
    "preferences_file",
    "project_vcode_dir",
    "resolve_config_path",
    "resolve_structured_config_path",
)


def project_vcode_dir(cwd: Path) -> Path:
    return cwd.resolve() / ".vcode"


def global_vcode_dir() -> Path:
    return Path.home() / ".vcode"


def resolve_config_path(cwd: Path, name: str) -> Path:
    project_path = project_vcode_dir(cwd) / name
    if project_path.exists():
        return project_path
    return global_vcode_dir() / name


def resolve_structured_config_path(
    cwd: Path,
    stem: str,
    *,
    extensions: tuple[str, ...] = ("yml", "yaml", "json"),
) -> Path:
    workspace = cwd.resolve()
    search_roots = (project_vcode_dir(workspace), global_vcode_dir())
    for root in search_roots:
        for extension in extensions:
            candidate = root / f"{stem}.{extension}"
            if candidate.exists():
                return candidate
    return project_vcode_dir(workspace) / f"{stem}.{extensions[0]}"


def preferences_file(cwd: Path) -> Path:
    return resolve_config_path(cwd.resolve(), "preferences.json")


def local_preferences_file(cwd: Path) -> Path:
    return project_vcode_dir(cwd.resolve()) / "preferences.json"


def agents_file(cwd: Path) -> Path:
    return resolve_config_path(cwd.resolve(), "agents.json")


def mcp_file(cwd: Path) -> Path:
    return resolve_structured_config_path(cwd.resolve(), "mcp")


def local_mcp_file(cwd: Path) -> Path:
    return project_vcode_dir(cwd.resolve()) / "mcp.yml"


def hooks_file(cwd: Path) -> Path:
    return resolve_structured_config_path(cwd.resolve(), "hooks")


def local_hooks_file(cwd: Path) -> Path:
    return project_vcode_dir(cwd.resolve()) / "hooks.yml"
