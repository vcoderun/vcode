from __future__ import annotations as _annotations

from dataclasses import dataclass, field
from typing import Literal, TypeAlias

from vcode.modes import DEFAULT_MODE_ID

__all__ = (
    "AgentSpec",
    "HookCommandConfig",
    "HookConfig",
    "HookEventId",
    "McpConfig",
    "McpServerConfig",
    "WebBrowserPreferences",
    "WebPreferences",
    "WebScrapePreferences",
    "WebSearchPreferences",
    "WorkspacePreferences",
)

HookEventId: TypeAlias = Literal[
    "before_run",
    "after_run",
    "run",
    "run_error",
    "before_node_run",
    "after_node_run",
    "node_run",
    "node_run_error",
    "before_model_request",
    "after_model_request",
    "model_request",
    "model_request_error",
    "before_tool_validate",
    "after_tool_validate",
    "tool_validate",
    "tool_validate_error",
    "before_tool_execute",
    "after_tool_execute",
    "tool_execute",
    "tool_execute_error",
    "prepare_tools",
    "run_event_stream",
    "event",
]


@dataclass(slots=True, kw_only=True)
class AgentSpec:
    model: str = ""


@dataclass(slots=True, kw_only=True)
class WebSearchPreferences:
    provider: str = "searx"
    searx_base_url: str = ""


@dataclass(slots=True, kw_only=True)
class WebScrapePreferences:
    provider: str = "builtin"


@dataclass(slots=True, kw_only=True)
class WebBrowserPreferences:
    provider: str = "browser-use"


@dataclass(slots=True, kw_only=True)
class WebPreferences:
    search: WebSearchPreferences = field(default_factory=WebSearchPreferences)
    scrape: WebScrapePreferences = field(default_factory=WebScrapePreferences)
    browser: WebBrowserPreferences = field(default_factory=WebBrowserPreferences)


@dataclass(slots=True, kw_only=True)
class WorkspacePreferences:
    default_agent: str = ""
    default_mode: str = DEFAULT_MODE_ID
    default_model: str = ""
    mode_models: dict[str, str] = field(default_factory=dict)
    yolo_default: bool = False
    history_compaction: str = "auto"
    external_docs_lookup: bool = False
    skill_discovery: str = "session_start"
    web: WebPreferences = field(default_factory=WebPreferences)


@dataclass(slots=True, kw_only=True)
class McpServerConfig:
    name: str
    transport: str
    command: str | None = None
    args: list[str] = field(default_factory=list)
    url: str | None = None
    env: dict[str, str] = field(default_factory=dict)
    enabled: bool = True
    prefix: str | None = None


@dataclass(slots=True, kw_only=True)
class McpConfig:
    servers: list[McpServerConfig] = field(default_factory=list)


@dataclass(slots=True, kw_only=True)
class HookCommandConfig:
    name: str = ""
    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    tools: list[str] = field(default_factory=list)
    enabled: bool = True
    timeout_seconds: float | None = None


@dataclass(slots=True, kw_only=True)
class HookConfig:
    events: dict[HookEventId, list[HookCommandConfig]] = field(default_factory=dict)
