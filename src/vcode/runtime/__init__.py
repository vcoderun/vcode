from __future__ import annotations as _annotations

import json
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import TypeAlias

from acp.schema import SessionModelState
from pydantic_ai import Agent, ModelMessagesTypeAdapter, RunContext
from pydantic_ai.messages import ModelMessage
from pydantic_ai.models import Model

from vcode.approvals import ApprovalPolicy
from vcode.modes import DEFAULT_MODE_ID, get_mode
from vcode.preferences import active_model_for_mode, build_model_state, load_preferences
from vcode.runtime.commands import (
    RuntimeCommandContext,
    handle_runtime_command,
    normalize_prompt_text,
    persist_command_response,
)
from vcode.runtime.projections import build_tool_projections
from vcode.runtime.types import TurnResult
from vcode.sessions import SessionMessage, SessionRecord, SessionStore
from vcode.workspace import (
    AgentDeps,
    WorkspacePathError,
    list_workspace_files,
    read_workspace_file,
    resolve_workspace_path,
    write_workspace_file,
)

__all__ = ("VCodeRuntime",)

ModelReference: TypeAlias = Model | str


def _render_output(output: object) -> str:
    if isinstance(output, str):
        return output
    return json.dumps(output, indent=2, sort_keys=True, ensure_ascii=True)


class VCodeRuntime:
    def __init__(
        self,
        store: SessionStore | None = None,
        model_resolver: Callable[[str], ModelReference] | None = None,
        approval_policy: ApprovalPolicy | None = None,
    ) -> None:
        self.store = store or SessionStore()
        self.model_resolver = model_resolver or (lambda model_id: model_id)
        self.approval_policy = approval_policy or ApprovalPolicy(store=self.store)
        self.agent = self._build_agent()

    def _build_agent(self) -> Agent[AgentDeps, str]:
        agent = Agent[AgentDeps, str](
            output_type=str,
            deps_type=AgentDeps,
            instructions=(
                "You are vCode, a coding agent for a local workspace. "
                "Use tools when needed. Respect the active mode. "
                "Ask mode is read-only. Plan mode may only write under .vcode/plans. "
                "Agent mode may edit the workspace."
            ),
        )

        @agent.tool
        async def list_files(ctx: RunContext[AgentDeps], path: str = ".") -> str:
            """List files relative to the workspace root."""
            return list_workspace_files(ctx.deps.workspace_root, path)

        @agent.tool
        async def read_file(ctx: RunContext[AgentDeps], path: str) -> str:
            """Read a UTF-8 text file from the workspace."""
            return read_workspace_file(ctx.deps.workspace_root, path)

        @agent.tool
        async def write_file(ctx: RunContext[AgentDeps], path: str, content: str) -> str:
            """Write a UTF-8 text file inside the workspace."""
            try:
                target = resolve_workspace_path(ctx.deps.workspace_root, path)
            except WorkspacePathError as exc:
                return str(exc)
            approval_message = await ctx.deps.approval_policy.authorize_write(
                ctx.deps.workspace_root,
                ctx.deps.session_id,
                target,
                content,
            )
            if approval_message is not None:
                return approval_message
            return write_workspace_file(ctx.deps.workspace_root, ctx.deps.mode_id, path, content)

        return agent

    def create_session(self, cwd: Path, mode_id: str | None = None) -> SessionRecord:
        workspace = cwd.resolve()
        if mode_id is None:
            mode_id = load_preferences(workspace).default_mode or DEFAULT_MODE_ID
        return self.store.create(workspace, mode_id)

    def clone_session(self, cwd: Path, session_id: str) -> SessionRecord | None:
        return self.store.clone(cwd.resolve(), session_id)

    def load_session(self, cwd: Path, session_id: str) -> SessionRecord | None:
        return self.store.load(cwd.resolve(), session_id)

    def list_sessions(self, cwd: Path) -> list[SessionRecord]:
        return self.store.list(cwd.resolve())

    def set_mode(self, cwd: Path, session_id: str, mode_id: str) -> SessionRecord | None:
        if get_mode(mode_id) is None:
            return None
        return self.store.set_mode(cwd.resolve(), session_id, mode_id)

    def build_model_state(self, cwd: Path, mode_id: str) -> SessionModelState:
        return build_model_state(cwd.resolve(), mode_id)

    def read_history(self, cwd: Path, session_id: str) -> list[SessionMessage]:
        return self.store.read_history(cwd.resolve(), session_id)

    def read_model_messages(self, cwd: Path, session_id: str) -> Sequence[ModelMessage] | None:
        payload = self.store.read_model_messages_json(cwd.resolve(), session_id)
        if payload is None:
            return None
        return ModelMessagesTypeAdapter.validate_json(payload)

    async def run_prompt(self, cwd: Path, session_id: str, prompt_text: str) -> TurnResult | None:
        workspace = cwd.resolve()
        record = self.store.load(workspace, session_id)
        if record is None:
            return None

        normalized_prompt = normalize_prompt_text(prompt_text)
        if not normalized_prompt:
            return TurnResult(response_text="Prompt was empty.")

        command_context = RuntimeCommandContext(
            workspace=workspace,
            session_id=session_id,
            mode_id=record.mode_id,
            store=self.store,
            approval_policy=self.approval_policy,
        )
        command_response = handle_runtime_command(normalized_prompt, context=command_context)
        if command_response is not None:
            persist_command_response(normalized_prompt, command_response, context=command_context)
            return TurnResult(response_text=command_response)

        active_model = active_model_for_mode(workspace, record.mode_id)
        if not active_model:
            response_text = (
                "No model configured. Set `.vcode/preferences.json` `default_model` "
                "or use `/model provider:model`. Use `/models` to list supported model ids."
            )
            self.store.append_message(workspace, session_id, "user", normalized_prompt)
            self.store.append_message(workspace, session_id, "assistant", response_text)
            return TurnResult(response_text=response_text)

        message_history = self.read_model_messages(workspace, session_id)
        deps = AgentDeps(
            workspace_root=workspace,
            mode_id=record.mode_id,
            session_id=session_id,
            approval_policy=self.approval_policy,
        )
        model = self.model_resolver(active_model)

        try:
            result = await self.agent.run(
                normalized_prompt,
                deps=deps,
                model=model,
                message_history=message_history,
            )
        except Exception as exc:
            response_text = f"Model run failed for {active_model}: {exc}"
            tool_projections = ()
        else:
            response_text = _render_output(result.output)
            tool_projections = ()
            try:
                self.store.write_model_messages_json(
                    workspace,
                    session_id,
                    result.all_messages_json(),
                )
                tool_projections = build_tool_projections(result.new_messages())
            except Exception as exc:
                error_type = type(exc).__name__
                response_text = (
                    f"{response_text}\n\n"
                    f"[vCode warning] Post-processing failed after model run "
                    f"({error_type}: {exc})."
                )

        self.store.append_message(workspace, session_id, "user", normalized_prompt)
        self.store.append_message(workspace, session_id, "assistant", response_text)
        return TurnResult(response_text=response_text, tool_projections=tool_projections)
