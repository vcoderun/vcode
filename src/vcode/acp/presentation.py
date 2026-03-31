from __future__ import annotations as _annotations

from pathlib import Path
from typing import TypeAlias

from acp.helpers import text_block, tool_content, tool_diff_content
from acp.schema import (
    AvailableCommand,
    AvailableCommandInput,
    ContentToolCallContent,
    FileEditToolCallContent,
    SessionConfigOptionBoolean,
    SessionConfigOptionSelect,
    SessionConfigSelectOption,
    TerminalToolCallContent,
    UnstructuredCommandInput,
)

from vcode.modes import MODE_SPECS
from vcode.preferences import active_model_for_mode, supported_model_ids
from vcode.runtime.types import ToolContent, ToolContentDiff, ToolContentText

__all__ = (
    "AcpConfigOption",
    "build_available_commands",
    "build_config_options",
    "build_projection_content",
)

AcpConfigOption: TypeAlias = SessionConfigOptionSelect | SessionConfigOptionBoolean
AcpToolContent: TypeAlias = (
    ContentToolCallContent | FileEditToolCallContent | TerminalToolCallContent
)


def build_available_commands() -> list[AvailableCommand]:
    return [
        AvailableCommand(
            name="models",
            description="List pydantic-ai supported model ids. Optional filter text is supported.",
            input=build_command_input("models [filter]"),
        ),
        AvailableCommand(
            name="model",
            description="Show current, default and per-mode model configuration.",
            input=build_command_input(
                "model [<provider:model> | <ask|plan|agent> <provider:model>] use /models to browse"
            ),
        ),
        AvailableCommand(
            name="approvals",
            description="Show saved session approvals.",
        ),
        AvailableCommand(
            name="hooks",
            description="Show configured hook events and commands.",
        ),
        AvailableCommand(
            name="mcp",
            description="Show configured MCP servers and transports.",
        ),
        AvailableCommand(
            name="approve",
            description="Allow a tool target for this session.",
            input=build_command_input("approve <write> <path>"),
        ),
        AvailableCommand(
            name="deny",
            description="Deny a tool target for this session.",
            input=build_command_input("deny <write> <path>"),
        ),
        AvailableCommand(
            name="update-preferences",
            description="Import session-scoped approvals from another session.",
            input=build_command_input("update-preferences <session-id>"),
        ),
    ]


def build_command_input(hint: str) -> AvailableCommandInput:
    return AvailableCommandInput(root=UnstructuredCommandInput(hint=hint))


def build_config_options(workspace: Path, mode_id: str) -> list[AcpConfigOption]:
    current_model_id = active_model_for_mode(workspace, mode_id)
    known_model_ids = supported_model_ids()
    model_options = [
        SessionConfigSelectOption(
            value=model_id,
            name=model_id,
            description="pydantic-ai supported model.",
        )
        for model_id in known_model_ids
    ]
    if current_model_id and current_model_id not in known_model_ids:
        model_options.append(
            SessionConfigSelectOption(
                value=current_model_id,
                name=current_model_id,
                description="Custom model.",
            )
        )

    config_options: list[AcpConfigOption] = [
        SessionConfigOptionSelect(
            type="select",
            id="mode",
            category="mode",
            name="Mode",
            description="Current agent mode.",
            current_value=mode_id,
            options=[
                SessionConfigSelectOption(
                    value=mode.id,
                    name=mode.name,
                    description=mode.description,
                )
                for mode in MODE_SPECS
            ],
        )
    ]
    if current_model_id:
        config_options.append(
            SessionConfigOptionSelect(
                type="select",
                id="model",
                category="model",
                name="Model",
                description="Default session model.",
                current_value=current_model_id,
                options=model_options,
            )
        )
    return config_options


def build_projection_content(
    content: tuple[ToolContent, ...],
) -> list[AcpToolContent] | None:
    converted: list[AcpToolContent] = []
    for item in content:
        if isinstance(item, ToolContentDiff):
            converted.append(
                tool_diff_content(
                    path=item.path,
                    new_text=item.new_text,
                    old_text=item.old_text,
                )
            )
            continue
        if isinstance(item, ToolContentText):
            converted.append(tool_content(text_block(item.text)))
    return converted or None
