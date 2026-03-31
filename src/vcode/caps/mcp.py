from __future__ import annotations as _annotations

from pathlib import Path

from pydantic_ai.capabilities import MCP, AbstractCapability, Toolset
from pydantic_ai.mcp import MCPServerSSE, MCPServerStdio, MCPServerStreamableHTTP

from vcode.config import McpServerConfig, load_mcp_config
from vcode.workspace import AgentDeps

__all__ = ("build_mcp_caps",)


def build_mcp_caps(workspace_root: Path) -> list[AbstractCapability[AgentDeps]]:
    """Build MCP-backed capabilities from workspace configuration."""
    config = load_mcp_config(workspace_root.resolve())
    caps: list[AbstractCapability[AgentDeps]] = []
    for server in config.servers:
        if not server.enabled:
            continue
        cap = build_mcp_cap(server)
        if cap is not None:
            caps.append(cap)
    return caps


def build_mcp_cap(server: McpServerConfig) -> AbstractCapability[AgentDeps] | None:
    transport = normalize_transport(server.transport)
    if transport == "stdio":
        if server.command is None:
            return None
        return Toolset[AgentDeps](
            MCPServerStdio(
                command=server.command,
                args=tuple(server.args),
                env=server.env or None,
                id=server.name,
                tool_prefix=server.prefix,
            )
        )

    if server.url is None:
        return None

    local_server = build_local_http_server(server, transport=transport)
    cap: AbstractCapability[AgentDeps] = MCP[AgentDeps](
        url=server.url,
        id=server.name,
        local=local_server,
    )
    if server.prefix:
        cap = cap.prefix_tools(server.prefix)
    return cap


def build_local_http_server(
    server: McpServerConfig,
    *,
    transport: str,
) -> MCPServerSSE | MCPServerStreamableHTTP:
    if server.url is None:
        raise ValueError("URL transport requires a server URL.")
    if transport == "sse":
        return MCPServerSSE(
            server.url,
            id=server.name,
        )
    return MCPServerStreamableHTTP(
        server.url,
        id=server.name,
    )


def normalize_transport(value: str) -> str:
    normalized = value.strip().lower().replace("_", "-")
    if normalized in {"http", "https", "streamable-http", "streamablehttp"}:
        return "streamable-http"
    if normalized == "sse":
        return "sse"
    if normalized == "stdio":
        return "stdio"
    return normalized
