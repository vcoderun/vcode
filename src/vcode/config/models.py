from __future__ import annotations as _annotations

from dataclasses import dataclass, field

from vcode.modes import DEFAULT_MODE_ID

__all__ = (
    "AgentSpec",
    "McpConfig",
    "McpServerConfig",
    "WebBrowserPreferences",
    "WebPreferences",
    "WebScrapePreferences",
    "WebSearchPreferences",
    "WorkspacePreferences",
)


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
