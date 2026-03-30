from __future__ import annotations as _annotations

from pathlib import Path

__all__ = (
    "agents_file",
    "global_vcode_dir",
    "local_preferences_file",
    "mcp_file",
    "preferences_file",
    "project_vcode_dir",
    "resolve_config_path",
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


def preferences_file(cwd: Path) -> Path:
    return resolve_config_path(cwd.resolve(), "preferences.json")


def local_preferences_file(cwd: Path) -> Path:
    return project_vcode_dir(cwd.resolve()) / "preferences.json"


def agents_file(cwd: Path) -> Path:
    return resolve_config_path(cwd.resolve(), "agents.json")


def mcp_file(cwd: Path) -> Path:
    return resolve_config_path(cwd.resolve(), "mcp.json")
