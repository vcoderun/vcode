from __future__ import annotations as _annotations

from pydantic_ai.capabilities import AbstractCapability, PrepareTools, Toolset
from pydantic_ai.tools import RunContext, ToolDefinition

from vcode.toolsets import build_filesystem_toolset
from vcode.workspace import AgentDeps

__all__ = ("build_filesystem_caps",)


def build_filesystem_caps() -> list[AbstractCapability[AgentDeps]]:
    """Build filesystem capabilities for runtime tool exposure."""
    return [
        Toolset[AgentDeps](build_filesystem_toolset()),
        PrepareTools[AgentDeps](prepare_func=prepare_filesystem_tools),
    ]


async def prepare_filesystem_tools(
    ctx: RunContext[AgentDeps],
    tool_defs: list[ToolDefinition],
) -> list[ToolDefinition]:
    if ctx.deps.mode_id != "ask":
        return tool_defs
    return [tool_def for tool_def in tool_defs if tool_def.name != "write_file"]
