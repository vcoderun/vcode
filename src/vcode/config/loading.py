from __future__ import annotations as _annotations

import json
import os
import re
from collections.abc import Mapping
from pathlib import Path
from typing import TypeAlias

import yaml

from vcode.config.models import (
    AgentSpec,
    HookCommandConfig,
    HookConfig,
    HookEventId,
    McpConfig,
    McpServerConfig,
    WebBrowserPreferences,
    WebPreferences,
    WebScrapePreferences,
    WebSearchPreferences,
    WorkspacePreferences,
)
from vcode.config.paths import (
    agents_file,
    hooks_file,
    local_preferences_file,
    mcp_file,
    preferences_file,
)
from vcode.modes import DEFAULT_MODE_ID, MODE_BY_ID

__all__ = (
    "load_agents_config",
    "load_hooks_config",
    "load_mcp_config",
    "load_preferences",
    "save_preferences",
)

JsonObject: TypeAlias = dict[str, object]

ENV_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


def load_preferences(cwd: Path) -> WorkspacePreferences:
    payload = load_data_file(preferences_file(cwd.resolve()))

    mode_models_value = payload.get("mode_models", {})
    mode_models = mode_models_value if isinstance(mode_models_value, dict) else {}
    normalized_mode_models = {
        str(mode_id): str(model_id).strip()
        for mode_id, model_id in mode_models.items()
        if str(mode_id) in MODE_BY_ID and str(model_id).strip()
    }

    web_payload = nested_mapping(payload, "web")
    search_payload = nested_mapping(web_payload, "search")
    scrape_payload = nested_mapping(web_payload, "scrape")
    browser_payload = nested_mapping(web_payload, "browser")

    default_mode = str(payload.get("default_mode", DEFAULT_MODE_ID)).strip() or DEFAULT_MODE_ID
    if default_mode not in MODE_BY_ID:
        default_mode = DEFAULT_MODE_ID

    return WorkspacePreferences(
        default_agent=str(payload.get("default_agent", "")).strip(),
        default_mode=default_mode,
        default_model=str(payload.get("default_model", "")).strip(),
        mode_models=normalized_mode_models,
        yolo_default=bool(payload.get("yolo_default", False)),
        history_compaction=str(payload.get("history_compaction", "auto")).strip() or "auto",
        external_docs_lookup=bool(payload.get("external_docs_lookup", False)),
        skill_discovery=str(payload.get("skill_discovery", "session_start")).strip()
        or "session_start",
        web=WebPreferences(
            search=WebSearchPreferences(
                provider=str(search_payload.get("provider", "searx")).strip() or "searx",
                searx_base_url=str(search_payload.get("searx_base_url", "")).strip(),
            ),
            scrape=WebScrapePreferences(
                provider=str(scrape_payload.get("provider", "builtin")).strip() or "builtin"
            ),
            browser=WebBrowserPreferences(
                provider=str(browser_payload.get("provider", "browser-use")).strip()
                or "browser-use"
            ),
        ),
    )


def save_preferences(cwd: Path, preferences: WorkspacePreferences) -> None:
    path = local_preferences_file(cwd.resolve())
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: JsonObject = {
        "default_agent": preferences.default_agent,
        "default_mode": preferences.default_mode,
        "default_model": preferences.default_model,
        "mode_models": preferences.mode_models,
        "yolo_default": preferences.yolo_default,
        "history_compaction": preferences.history_compaction,
        "external_docs_lookup": preferences.external_docs_lookup,
        "skill_discovery": preferences.skill_discovery,
        "web": {
            "search": {
                "provider": preferences.web.search.provider,
                "searx_base_url": preferences.web.search.searx_base_url,
            },
            "scrape": {
                "provider": preferences.web.scrape.provider,
            },
            "browser": {
                "provider": preferences.web.browser.provider,
            },
        },
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def load_agents_config(cwd: Path) -> dict[str, AgentSpec]:
    payload = load_data_file(agents_file(cwd.resolve()))
    agents: dict[str, AgentSpec] = {}
    for name, value in payload.items():
        agent_payload = mapping_from_object(value)
        if agent_payload is None:
            continue
        agents[str(name)] = AgentSpec(model=string_value(agent_payload, "model").strip())
    return agents


def load_mcp_config(cwd: Path) -> McpConfig:
    payload = load_data_file(mcp_file(cwd.resolve()))
    raw_servers = list_from_object(payload.get("servers"))

    servers: list[McpServerConfig] = []
    for raw_server in raw_servers:
        server_payload = mapping_from_object(raw_server)
        if server_payload is None:
            continue
        name = string_value(server_payload, "name").strip()
        transport = string_value(server_payload, "transport").strip()
        if not name or not transport:
            continue
        env_payload = nested_mapping(server_payload, "env")
        args_payload = list_from_object(server_payload.get("args"))
        command = optional_string_value(server_payload, "command")
        url = optional_string_value(server_payload, "url")
        prefix = optional_string_value(server_payload, "prefix")
        servers.append(
            McpServerConfig(
                name=name,
                transport=transport,
                command=interpolate_env(command) if command is not None else None,
                args=[interpolate_env(str(arg)) for arg in args_payload],
                url=interpolate_env(url) if url is not None else None,
                env=interpolate_mapping(env_payload),
                enabled=bool_value(server_payload, "enabled", default=True),
                prefix=prefix,
            )
        )
    return McpConfig(servers=servers)


def load_hooks_config(cwd: Path) -> HookConfig:
    payload = load_data_file(hooks_file(cwd.resolve()))
    events_payload = nested_mapping(payload, "events") if "events" in payload else payload
    events: dict[HookEventId, list[HookCommandConfig]] = {}
    for event_name, raw_commands in events_payload.items():
        normalized_event = normalize_hook_event_id(event_name)
        if normalized_event is None:
            continue
        commands_payload = list_from_object(raw_commands)
        commands: list[HookCommandConfig] = []
        for raw_command in commands_payload:
            command_payload = mapping_from_object(raw_command)
            if command_payload is None:
                continue
            command = optional_string_value(command_payload, "command")
            if command is None:
                continue
            timeout_value = optional_float_value(command_payload, "timeout_seconds")
            if timeout_value is None:
                timeout_value = optional_float_value(command_payload, "timeout")
            commands.append(
                HookCommandConfig(
                    name=string_value(command_payload, "name").strip(),
                    command=interpolate_env(command),
                    args=[
                        interpolate_env(str(arg))
                        for arg in list_from_object(command_payload.get("args"))
                    ],
                    env=interpolate_mapping(nested_mapping(command_payload, "env")),
                    tools=[
                        str(tool_name).strip()
                        for tool_name in list_from_object(command_payload.get("tools"))
                        if str(tool_name).strip()
                    ],
                    enabled=bool_value(command_payload, "enabled", default=True),
                    timeout_seconds=timeout_value,
                )
            )
        if commands:
            events[normalized_event] = commands
    return HookConfig(events=events)


def load_data_file(path: Path) -> JsonObject:
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".json":
        payload = json.loads(text)
    elif path.suffix in {".yml", ".yaml"}:
        payload = yaml.safe_load(text)
    else:
        return {}
    if isinstance(payload, dict):
        return payload
    return {}


def nested_mapping(payload: Mapping[str, object], key: str) -> JsonObject:
    value = payload.get(key, {})
    nested_payload = mapping_from_object(value)
    if nested_payload is not None:
        return nested_payload
    return {}


def interpolate_env(value: str) -> str:
    return ENV_PATTERN.sub(lambda match: os.getenv(match.group(1), ""), value)


def interpolate_mapping(mapping: Mapping[str, object]) -> dict[str, str]:
    return {str(key): interpolate_env(str(value)) for key, value in mapping.items()}


def mapping_from_object(value: object) -> JsonObject | None:
    if not isinstance(value, dict):
        return None
    return {str(key): item for key, item in value.items()}


def list_from_object(value: object) -> list[object]:
    if isinstance(value, list):
        return list(value)
    return []


def string_value(payload: Mapping[str, object], key: str) -> str:
    value = payload.get(key)
    if value is None:
        return ""
    return str(value)


def optional_string_value(payload: Mapping[str, object], key: str) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def bool_value(payload: Mapping[str, object], key: str, *, default: bool) -> bool:
    value = payload.get(key)
    if value is None:
        return default
    return bool(value)


def optional_float_value(payload: Mapping[str, object], key: str) -> float | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str | int | float):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_hook_event_id(value: object) -> HookEventId | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    if normalized == "before_run":
        return "before_run"
    if normalized == "after_run":
        return "after_run"
    if normalized == "run":
        return "run"
    if normalized == "run_error":
        return "run_error"
    if normalized == "before_node_run":
        return "before_node_run"
    if normalized == "after_node_run":
        return "after_node_run"
    if normalized == "node_run":
        return "node_run"
    if normalized == "node_run_error":
        return "node_run_error"
    if normalized == "before_model_request":
        return "before_model_request"
    if normalized == "after_model_request":
        return "after_model_request"
    if normalized == "model_request":
        return "model_request"
    if normalized == "model_request_error":
        return "model_request_error"
    if normalized == "before_tool_validate":
        return "before_tool_validate"
    if normalized == "after_tool_validate":
        return "after_tool_validate"
    if normalized == "tool_validate":
        return "tool_validate"
    if normalized == "tool_validate_error":
        return "tool_validate_error"
    if normalized == "before_tool_execute":
        return "before_tool_execute"
    if normalized == "after_tool_execute":
        return "after_tool_execute"
    if normalized == "tool_execute":
        return "tool_execute"
    if normalized == "tool_execute_error":
        return "tool_execute_error"
    if normalized == "prepare_tools":
        return "prepare_tools"
    if normalized == "run_event_stream":
        return "run_event_stream"
    if normalized == "event":
        return "event"
    return None
