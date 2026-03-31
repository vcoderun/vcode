from __future__ import annotations as _annotations

from pathlib import Path

from pydantic_ai.capabilities import AbstractCapability

from vcode.caps.filesystem import build_filesystem_caps
from vcode.caps.hooks import build_hooks_cap
from vcode.caps.mcp import build_mcp_caps
from vcode.workspace import AgentDeps

__all__ = ("build_runtime_caps",)


def build_runtime_caps(workspace_root: Path) -> list[AbstractCapability[AgentDeps]]:
    """Build the runtime capability stack for a workspace."""
    workspace = workspace_root.resolve()
    caps: list[AbstractCapability[AgentDeps]] = []

    hooks_cap = build_hooks_cap(workspace)
    if hooks_cap is not None:
        caps.append(hooks_cap)

    caps.extend(build_filesystem_caps())
    caps.extend(build_mcp_caps(workspace))
    return caps
