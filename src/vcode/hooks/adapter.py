from __future__ import annotations as _annotations

import asyncio
import json
import os
from collections.abc import AsyncIterable
from dataclasses import dataclass
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Any

from pydantic_ai.capabilities import (
    AgentNode,
    Hooks,
    NodeResult,
    RawToolArgs,
    ValidatedToolArgs,
    WrapModelRequestHandler,
    WrapNodeRunHandler,
    WrapRunHandler,
    WrapToolExecuteHandler,
    WrapToolValidateHandler,
)
from pydantic_ai.messages import AgentStreamEvent, ModelResponse, ToolCallPart
from pydantic_ai.models import ModelRequestContext
from pydantic_ai.run import AgentRunResult
from pydantic_ai.tools import RunContext, ToolDefinition

from vcode.config import HookCommandConfig, HookConfig, HookEventId, load_hooks_config
from vcode.hooks.errors import HookCommandError, HookCommandTimeoutError
from vcode.hooks.events import HookEventCollector
from vcode.workspace import AgentDeps

__all__ = ("build_hooks_capability",)


def build_hooks_capability(workspace_root: Path) -> Hooks[AgentDeps] | None:
    config = load_hooks_config(workspace_root.resolve())
    if not config.events:
        return None
    adapter = HookCapabilityAdapter(workspace_root=workspace_root.resolve(), config=config)
    hooks: Hooks[AgentDeps] = Hooks(
        before_run=adapter.before_run if adapter.has_commands("before_run") else None,
        after_run=adapter.after_run if adapter.has_commands("after_run") else None,
        run=adapter.run if adapter.has_commands("run") else None,
        run_error=adapter.run_error if adapter.has_commands("run_error") else None,
        before_node_run=(
            adapter.before_node_run if adapter.has_commands("before_node_run") else None
        ),
        after_node_run=(adapter.after_node_run if adapter.has_commands("after_node_run") else None),
        node_run=adapter.node_run if adapter.has_commands("node_run") else None,
        node_run_error=(adapter.node_run_error if adapter.has_commands("node_run_error") else None),
        before_model_request=(
            adapter.before_model_request if adapter.has_commands("before_model_request") else None
        ),
        after_model_request=(
            adapter.after_model_request if adapter.has_commands("after_model_request") else None
        ),
        model_request=(adapter.model_request if adapter.has_commands("model_request") else None),
        model_request_error=(
            adapter.model_request_error if adapter.has_commands("model_request_error") else None
        ),
        before_tool_validate=(
            adapter.before_tool_validate if adapter.has_commands("before_tool_validate") else None
        ),
        after_tool_validate=(
            adapter.after_tool_validate if adapter.has_commands("after_tool_validate") else None
        ),
        tool_validate=(adapter.tool_validate if adapter.has_commands("tool_validate") else None),
        tool_validate_error=(
            adapter.tool_validate_error if adapter.has_commands("tool_validate_error") else None
        ),
        before_tool_execute=(
            adapter.before_tool_execute if adapter.has_commands("before_tool_execute") else None
        ),
        after_tool_execute=(
            adapter.after_tool_execute if adapter.has_commands("after_tool_execute") else None
        ),
        tool_execute=(adapter.tool_execute if adapter.has_commands("tool_execute") else None),
        tool_execute_error=(
            adapter.tool_execute_error if adapter.has_commands("tool_execute_error") else None
        ),
        prepare_tools=(adapter.prepare_tools if adapter.has_commands("prepare_tools") else None),
        run_event_stream=(
            adapter.run_event_stream if adapter.has_commands("run_event_stream") else None
        ),
        event=adapter.event if adapter.has_commands("event") else None,
    )
    return hooks


@dataclass(slots=True, kw_only=True)
class HookCapabilityAdapter:
    workspace_root: Path
    config: HookConfig

    def has_commands(self, event_id: HookEventId) -> bool:
        return bool(self.config.events.get(event_id))

    async def before_run(self, ctx: RunContext[AgentDeps]) -> None:
        await self.run_commands("before_run", ctx, payload={})

    async def after_run(
        self,
        ctx: RunContext[AgentDeps],
        *,
        result: AgentRunResult[Any],
    ) -> AgentRunResult[Any]:
        await self.run_commands("after_run", ctx, payload={"result": repr(result)})
        return result

    async def run(
        self,
        ctx: RunContext[AgentDeps],
        *,
        handler: WrapRunHandler,
    ) -> AgentRunResult[Any]:
        await self.run_commands("run", ctx, payload={})
        return await handler()

    async def run_error(
        self,
        ctx: RunContext[AgentDeps],
        *,
        error: BaseException,
    ) -> AgentRunResult[Any]:
        await self.run_commands("run_error", ctx, payload={"error": repr(error)})
        raise error

    async def before_node_run(
        self,
        ctx: RunContext[AgentDeps],
        *,
        node: AgentNode[AgentDeps],
    ) -> AgentNode[AgentDeps]:
        await self.run_commands("before_node_run", ctx, payload={"node": repr(node)})
        return node

    async def after_node_run(
        self,
        ctx: RunContext[AgentDeps],
        *,
        node: AgentNode[AgentDeps],
        result: NodeResult[AgentDeps],
    ) -> NodeResult[AgentDeps]:
        await self.run_commands(
            "after_node_run",
            ctx,
            payload={"node": repr(node), "result": repr(result)},
        )
        return result

    async def node_run(
        self,
        ctx: RunContext[AgentDeps],
        *,
        node: AgentNode[AgentDeps],
        handler: WrapNodeRunHandler[AgentDeps],
    ) -> NodeResult[AgentDeps]:
        await self.run_commands("node_run", ctx, payload={"node": repr(node)})
        return await handler(node)

    async def node_run_error(
        self,
        ctx: RunContext[AgentDeps],
        *,
        node: AgentNode[AgentDeps],
        error: Exception,
    ) -> NodeResult[AgentDeps]:
        await self.run_commands(
            "node_run_error",
            ctx,
            payload={"node": repr(node), "error": repr(error)},
        )
        raise error

    async def before_model_request(
        self,
        ctx: RunContext[AgentDeps],
        request_context: ModelRequestContext,
    ) -> ModelRequestContext:
        await self.run_commands(
            "before_model_request",
            ctx,
            payload={"message_count": len(request_context.messages)},
        )
        return request_context

    async def after_model_request(
        self,
        ctx: RunContext[AgentDeps],
        *,
        request_context: ModelRequestContext,
        response: ModelResponse,
    ) -> ModelResponse:
        await self.run_commands(
            "after_model_request",
            ctx,
            payload={
                "message_count": len(request_context.messages),
                "model_name": response.model_name,
            },
        )
        return response

    async def model_request(
        self,
        ctx: RunContext[AgentDeps],
        *,
        request_context: ModelRequestContext,
        handler: WrapModelRequestHandler,
    ) -> ModelResponse:
        await self.run_commands(
            "model_request",
            ctx,
            payload={"message_count": len(request_context.messages)},
        )
        return await handler(request_context)

    async def model_request_error(
        self,
        ctx: RunContext[AgentDeps],
        *,
        request_context: ModelRequestContext,
        error: Exception,
    ) -> ModelResponse:
        await self.run_commands(
            "model_request_error",
            ctx,
            payload={
                "message_count": len(request_context.messages),
                "error": repr(error),
            },
        )
        raise error

    async def before_tool_validate(
        self,
        ctx: RunContext[AgentDeps],
        *,
        call: ToolCallPart,
        tool_def: ToolDefinition,
        args: RawToolArgs,
    ) -> RawToolArgs:
        await self.run_commands(
            "before_tool_validate",
            ctx,
            payload=self.tool_payload(call=call, tool_def=tool_def, args=args),
            tool_name=call.tool_name,
        )
        return args

    async def after_tool_validate(
        self,
        ctx: RunContext[AgentDeps],
        *,
        call: ToolCallPart,
        tool_def: ToolDefinition,
        args: ValidatedToolArgs,
    ) -> ValidatedToolArgs:
        await self.run_commands(
            "after_tool_validate",
            ctx,
            payload=self.tool_payload(call=call, tool_def=tool_def, args=args),
            tool_name=call.tool_name,
        )
        return args

    async def tool_validate(
        self,
        ctx: RunContext[AgentDeps],
        *,
        call: ToolCallPart,
        tool_def: ToolDefinition,
        args: RawToolArgs,
        handler: WrapToolValidateHandler,
    ) -> ValidatedToolArgs:
        await self.run_commands(
            "tool_validate",
            ctx,
            payload=self.tool_payload(call=call, tool_def=tool_def, args=args),
            tool_name=call.tool_name,
        )
        return await handler(args)

    async def tool_validate_error(
        self,
        ctx: RunContext[AgentDeps],
        *,
        call: ToolCallPart,
        tool_def: ToolDefinition,
        args: RawToolArgs,
        error: Exception,
    ) -> ValidatedToolArgs:
        await self.run_commands(
            "tool_validate_error",
            ctx,
            payload={
                **self.tool_payload(call=call, tool_def=tool_def, args=args),
                "error": repr(error),
            },
            tool_name=call.tool_name,
        )
        raise error

    async def before_tool_execute(
        self,
        ctx: RunContext[AgentDeps],
        *,
        call: ToolCallPart,
        tool_def: ToolDefinition,
        args: ValidatedToolArgs,
    ) -> ValidatedToolArgs:
        await self.run_commands(
            "before_tool_execute",
            ctx,
            payload=self.tool_payload(call=call, tool_def=tool_def, args=args),
            tool_name=call.tool_name,
        )
        return args

    async def after_tool_execute(
        self,
        ctx: RunContext[AgentDeps],
        *,
        call: ToolCallPart,
        tool_def: ToolDefinition,
        args: ValidatedToolArgs,
        result: Any,
    ) -> Any:
        await self.run_commands(
            "after_tool_execute",
            ctx,
            payload={
                **self.tool_payload(call=call, tool_def=tool_def, args=args),
                "result": serialize_value(result),
            },
            tool_name=call.tool_name,
        )
        return result

    async def tool_execute(
        self,
        ctx: RunContext[AgentDeps],
        *,
        call: ToolCallPart,
        tool_def: ToolDefinition,
        args: ValidatedToolArgs,
        handler: WrapToolExecuteHandler,
    ) -> Any:
        await self.run_commands(
            "tool_execute",
            ctx,
            payload=self.tool_payload(call=call, tool_def=tool_def, args=args),
            tool_name=call.tool_name,
        )
        return await handler(args)

    async def tool_execute_error(
        self,
        ctx: RunContext[AgentDeps],
        *,
        call: ToolCallPart,
        tool_def: ToolDefinition,
        args: ValidatedToolArgs,
        error: Exception,
    ) -> Any:
        await self.run_commands(
            "tool_execute_error",
            ctx,
            payload={
                **self.tool_payload(call=call, tool_def=tool_def, args=args),
                "error": repr(error),
            },
            tool_name=call.tool_name,
        )
        raise error

    async def prepare_tools(
        self,
        ctx: RunContext[AgentDeps],
        tool_defs: list[ToolDefinition],
    ) -> list[ToolDefinition]:
        await self.run_commands(
            "prepare_tools",
            ctx,
            payload={"tool_names": [tool_def.name for tool_def in tool_defs]},
        )
        return tool_defs

    def run_event_stream(
        self,
        ctx: RunContext[AgentDeps],
        *,
        stream: AsyncIterable[AgentStreamEvent],
    ) -> AsyncIterable[AgentStreamEvent]:
        async def wrapped_stream() -> AsyncIterable[AgentStreamEvent]:
            await self.run_commands("run_event_stream", ctx, payload={})
            async for event in stream:
                yield event

        return wrapped_stream()

    async def event(
        self,
        ctx: RunContext[AgentDeps],
        event: AgentStreamEvent,
    ) -> AgentStreamEvent:
        await self.run_commands("event", ctx, payload={"event": repr(event)})
        return event

    async def run_commands(
        self,
        event_id: HookEventId,
        ctx: RunContext[AgentDeps],
        *,
        payload: dict[str, object],
        tool_name: str = "",
    ) -> None:
        commands = self.config.events.get(event_id, [])
        if not commands:
            return
        for command_config in commands:
            if not command_config.enabled:
                continue
            if not matches_tool_filters(command_config, tool_name):
                continue
            await self.run_command(
                command_config,
                event_id=event_id,
                ctx=ctx,
                payload=payload,
                tool_name=tool_name,
            )

    async def run_command(
        self,
        command_config: HookCommandConfig,
        *,
        event_id: HookEventId,
        ctx: RunContext[AgentDeps],
        payload: dict[str, object],
        tool_name: str,
    ) -> None:
        env = os.environ.copy()
        env.update(command_config.env)
        env.update(
            {
                "VCODE_HOOK_EVENT": event_id,
                "VCODE_HOOK_MODE_ID": ctx.deps.mode_id,
                "VCODE_HOOK_PAYLOAD_JSON": json.dumps(payload, sort_keys=True, ensure_ascii=True),
                "VCODE_HOOK_SESSION_ID": ctx.deps.session_id,
                "VCODE_HOOK_WORKSPACE_ROOT": str(self.workspace_root),
            }
        )
        process = await asyncio.create_subprocess_exec(
            command_config.command,
            *command_config.args,
            cwd=str(self.workspace_root),
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        command_display = " ".join([command_config.command, *command_config.args]).strip()
        collector = ctx.deps.hook_event_collector
        try:
            if command_config.timeout_seconds is None:
                stdout_bytes, stderr_bytes = await process.communicate()
            else:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    process.communicate(),
                    timeout=command_config.timeout_seconds,
                )
        except TimeoutError:
            process.kill()
            await process.wait()
            record_hook_event(
                collector,
                event_id=event_id,
                command_display=command_display,
                command_config=command_config,
                tool_name=tool_name,
                raw_output=(f"Timed out after {command_config.timeout_seconds or 0.0} seconds."),
                status="failed",
            )
            raise HookCommandTimeoutError(
                event_id=event_id,
                command=command_display,
                timeout_seconds=command_config.timeout_seconds or 0.0,
            ) from None

        stdout_text = stdout_bytes.decode("utf-8", errors="replace").strip()
        stderr_text = stderr_bytes.decode("utf-8", errors="replace").strip()
        raw_output = "\n".join(part for part in (stdout_text, stderr_text) if part).strip()
        if process.returncode == 0:
            record_hook_event(
                collector,
                event_id=event_id,
                command_display=command_display,
                command_config=command_config,
                tool_name=tool_name,
                raw_output=raw_output,
                status="completed",
            )
            return
        returncode = process.returncode
        if returncode is None:
            returncode = -1
        record_hook_event(
            collector,
            event_id=event_id,
            command_display=command_display,
            command_config=command_config,
            tool_name=tool_name,
            raw_output=raw_output,
            status="failed",
        )
        raise HookCommandError(
            event_id=event_id,
            command=command_display,
            returncode=returncode,
            stderr=raw_output,
        )

    def tool_payload(
        self,
        *,
        call: ToolCallPart,
        tool_def: ToolDefinition,
        args: RawToolArgs | ValidatedToolArgs,
    ) -> dict[str, object]:
        return {
            "args": serialize_value(args),
            "tool_call_id": call.tool_call_id,
            "tool_description": tool_def.description or "",
            "tool_name": call.tool_name,
        }


def serialize_value(value: object) -> object:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): serialize_value(item) for key, item in value.items()}
    if isinstance(value, list | tuple | set | frozenset):
        return [serialize_value(item) for item in value]
    return repr(value)


def matches_tool_filters(command_config: HookCommandConfig, tool_name: str) -> bool:
    if not command_config.tools:
        return True
    if not tool_name:
        return False
    return any(fnmatchcase(tool_name, pattern) for pattern in command_config.tools)


def record_hook_event(
    collector: HookEventCollector | None,
    *,
    event_id: HookEventId,
    command_display: str,
    command_config: HookCommandConfig,
    tool_name: str,
    raw_output: str,
    status: str,
) -> None:
    if collector is None:
        return
    collector.record(
        event_id=event_id,
        command=command_display,
        hook_name=command_config.name,
        tool_name=tool_name,
        tool_filters=tuple(command_config.tools),
        raw_output=raw_output,
        status=status,
    )
