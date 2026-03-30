from __future__ import annotations as _annotations

import asyncio
from pathlib import Path

from acp import update_agent_message_text, update_user_message_text
from acp.interfaces import Client
from acp.schema import (
    AvailableCommandsUpdate,
    ConfigOptionUpdate,
    CurrentModeUpdate,
    TextContentBlock,
    ToolCallLocation,
    ToolCallProgress,
    ToolCallStart,
)

from vcode.acp.presentation import (
    AcpConfigOption,
    build_available_commands,
    build_projection_content,
)
from vcode.runtime import VCodeRuntime
from vcode.runtime.types import ToolProjection

__all__ = (
    "build_text_prompt",
    "emit_available_commands",
    "emit_config_options_update",
    "emit_mode_and_config_updates",
    "emit_tool_projections",
    "replay_history",
    "schedule_available_commands",
)


def build_text_prompt(prompt: list[object]) -> str:
    parts: list[str] = []
    for block in prompt:
        if isinstance(block, TextContentBlock) and block.text:
            parts.append(block.text)
    return "\n\n".join(parts)


async def replay_history(
    client: Client | None,
    runtime: VCodeRuntime,
    cwd: Path,
    session_id: str,
) -> None:
    if client is None:
        return
    for message in runtime.read_history(cwd, session_id):
        if message.role == "user":
            update = update_user_message_text(message.content)
        else:
            update = update_agent_message_text(message.content)
        await client.session_update(session_id=session_id, update=update)


async def emit_available_commands(client: Client | None, session_id: str) -> None:
    if client is None:
        return
    await client.session_update(
        session_id=session_id,
        update=AvailableCommandsUpdate(
            session_update="available_commands_update",
            available_commands=build_available_commands(),
        ),
    )


def schedule_available_commands(client: Client | None, session_id: str) -> None:
    if client is None:
        return
    asyncio.get_running_loop().call_soon(
        asyncio.create_task,
        emit_available_commands(client, session_id),
    )


async def emit_tool_projections(
    client: Client | None,
    session_id: str,
    projections: tuple[ToolProjection, ...],
) -> None:
    if client is None:
        return
    for projection in projections:
        locations = [ToolCallLocation(path=path) for path in projection.locations] or None
        content = build_projection_content(projection.content)
        await client.session_update(
            session_id=session_id,
            update=ToolCallStart(
                session_update="tool_call",
                tool_call_id=projection.tool_call_id,
                title=projection.title,
                kind=projection.kind,
                content=content,
                locations=locations,
                raw_input=projection.raw_input,
                status="in_progress",
            ),
        )
        await client.session_update(
            session_id=session_id,
            update=ToolCallProgress(
                session_update="tool_call_update",
                tool_call_id=projection.tool_call_id,
                title=projection.title,
                kind=projection.kind,
                content=content,
                locations=locations,
                raw_input=projection.raw_input,
                raw_output=projection.raw_output,
                status=projection.status,
            ),
        )


async def emit_mode_and_config_updates(
    client: Client | None,
    session_id: str,
    mode_id: str,
    config_options: list[AcpConfigOption],
) -> None:
    if client is None:
        return
    await client.session_update(
        session_id=session_id,
        update=CurrentModeUpdate(
            session_update="current_mode_update",
            current_mode_id=mode_id,
        ),
    )
    await emit_config_options_update(client, session_id, config_options)


async def emit_config_options_update(
    client: Client | None,
    session_id: str,
    config_options: list[AcpConfigOption],
) -> None:
    if client is None:
        return
    await client.session_update(
        session_id=session_id,
        update=ConfigOptionUpdate(
            session_update="config_option_update",
            config_options=config_options,
        ),
    )
