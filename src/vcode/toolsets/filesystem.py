from __future__ import annotations as _annotations

from pydantic_ai import AbstractToolset, FunctionToolset, RunContext, ToolDefinition

from vcode.workspace import (
    AgentDeps,
    WorkspacePathError,
    list_workspace_files,
    read_workspace_file,
    resolve_workspace_path,
    write_workspace_file,
)

__all__ = ("build_filesystem_toolset",)


def build_filesystem_toolset() -> AbstractToolset[AgentDeps]:
    """Build the filesystem toolset with deferred approval for writes."""
    toolset = FunctionToolset[AgentDeps]()

    @toolset.tool
    async def list_files(ctx: RunContext[AgentDeps], path: str = ".") -> str:
        """List files relative to the workspace root."""
        return list_workspace_files(ctx.deps.workspace_root, path)

    @toolset.tool
    async def read_file(ctx: RunContext[AgentDeps], path: str) -> str:
        """Read a UTF-8 text file from the workspace."""
        return read_workspace_file(ctx.deps.workspace_root, path)

    @toolset.tool
    async def write_file(ctx: RunContext[AgentDeps], path: str, content: str) -> str:
        """Write a UTF-8 text file inside the workspace."""
        try:
            resolve_workspace_path(ctx.deps.workspace_root, path)
        except WorkspacePathError as exc:
            return str(exc)
        return write_workspace_file(ctx.deps.workspace_root, ctx.deps.mode_id, path, content)

    return toolset.approval_required(_filesystem_approval_required)


def _filesystem_approval_required(
    ctx: RunContext[AgentDeps],
    tool_def: ToolDefinition,
    tool_args: dict[str, object],
) -> bool:
    if tool_def.name != "write_file":
        return False

    path_value = tool_args.get("path")
    content_value = tool_args.get("content")
    if not isinstance(path_value, str) or not isinstance(content_value, str):
        return False

    try:
        target = resolve_workspace_path(ctx.deps.workspace_root, path_value)
    except WorkspacePathError:
        return False

    request = ctx.deps.approval_policy.build_write_request(
        ctx.deps.workspace_root,
        ctx.deps.session_id,
        target,
        content_value,
        tool_call_id=ctx.tool_call_id,
    )
    decision = ctx.deps.approval_policy.evaluate(request)
    return decision.outcome != "allow"
