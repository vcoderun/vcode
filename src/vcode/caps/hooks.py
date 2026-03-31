from __future__ import annotations as _annotations

from pathlib import Path

from pydantic_ai.capabilities import Hooks

from vcode.hooks import build_hooks_capability
from vcode.workspace import AgentDeps

__all__ = ("build_hooks_cap",)


def build_hooks_cap(workspace_root: Path) -> Hooks[AgentDeps] | None:
    """Build the configured hooks capability for a workspace."""
    return build_hooks_capability(workspace_root.resolve())
