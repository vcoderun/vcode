from __future__ import annotations as _annotations

import json
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import TypeAlias

import dotenv
from acp.schema import SessionModelState
from pydantic_ai import (
    Agent,
    DeferredToolRequests,
    DeferredToolResults,
    ModelMessagesTypeAdapter,
)
from pydantic_ai.messages import ModelMessage, ToolCallPart
from pydantic_ai.models import Model
from pydantic_ai.tools import ToolDenied

from vcode.approvals import ApprovalPolicy, ApprovalRequest
from vcode.caps import build_runtime_caps
from vcode.hooks import HookEventCollector
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
from vcode.workspace import AgentDeps

dotenv.load_dotenv()

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

    def build_agent(self, workspace: Path) -> Agent[AgentDeps, str]:
        return Agent[AgentDeps, str](
            capabilities=build_runtime_caps(workspace),
            deps_type=AgentDeps,
            instructions=(
                "You are vCode, a coding agent for a local workspace. "
                "Use tools when needed. Respect the active mode. "
                "Ask mode is read-only. Plan mode may only write under .vcode/plans. "
                "Agent mode may edit the workspace."
            ),
        )

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
        hook_event_collector = HookEventCollector()
        deps = AgentDeps(
            workspace_root=workspace,
            mode_id=record.mode_id,
            session_id=session_id,
            approval_policy=self.approval_policy,
            hook_event_collector=hook_event_collector,
        )
        agent = self.build_agent(workspace)
        model = self.model_resolver(active_model)
        prompt_input: str | None = normalized_prompt
        deferred_results: DeferredToolResults | None = None
        projection_messages: list[ModelMessage] = []

        while True:
            try:
                result = await agent.run(
                    prompt_input,
                    deps=deps,
                    deferred_tool_results=deferred_results,
                    model=model,
                    message_history=message_history,
                    output_type=[str, DeferredToolRequests],
                )
            except Exception as exc:
                response_text = f"Model run failed for {active_model}: {exc}"
                tool_projections = ()
                break

            projection_messages.extend(result.new_messages())
            if isinstance(result.output, DeferredToolRequests):
                resolved = await self._resolve_deferred_requests(
                    workspace,
                    session_id,
                    result.output,
                )
                if resolved is None:
                    response_text = self._pending_approval_message(
                        workspace, session_id, result.output
                    )
                    tool_projections = ()
                    break
                deferred_results = resolved
                message_history = result.all_messages()
                prompt_input = None
                continue

            response_text = _render_output(result.output)
            tool_projections = ()
            try:
                self.store.write_model_messages_json(
                    workspace,
                    session_id,
                    result.all_messages_json(),
                )
                tool_projections = (
                    *hook_event_collector.build_projections(),
                    *build_tool_projections(projection_messages),
                )
            except Exception as exc:
                error_type = type(exc).__name__
                response_text = (
                    f"{response_text}\n\n"
                    f"[vCode warning] Post-processing failed after model run "
                    f"({error_type}: {exc})."
                )
            break

        self.store.append_message(workspace, session_id, "user", normalized_prompt)
        self.store.append_message(workspace, session_id, "assistant", response_text)
        return TurnResult(response_text=response_text, tool_projections=tool_projections)

    async def _resolve_deferred_requests(
        self,
        workspace: Path,
        session_id: str,
        requests: DeferredToolRequests,
    ) -> DeferredToolResults | None:
        if requests.calls:
            return None

        results = DeferredToolResults()
        unresolved = False
        for call in requests.approvals:
            request = self._approval_request_from_tool_call(workspace, session_id, call)
            if request is None:
                continue
            decision = await self.approval_policy.resolve(request)
            if decision.outcome == "allow":
                results.approvals[call.tool_call_id] = True
                continue
            if decision.outcome == "deny":
                results.approvals[call.tool_call_id] = ToolDenied(
                    message=decision.message or "The tool call was denied."
                )
                continue
            unresolved = True

        if unresolved or not results.approvals:
            return None
        return results

    def _approval_request_from_tool_call(
        self,
        workspace: Path,
        session_id: str,
        call: ToolCallPart,
    ) -> ApprovalRequest | None:
        if call.tool_name != "write_file":
            return None
        args = call.args_as_dict()
        path_value = args.get("path")
        content_value = args.get("content")
        if not isinstance(path_value, str) or not isinstance(content_value, str):
            return None
        target = workspace / path_value
        return self.approval_policy.build_write_request(
            workspace,
            session_id,
            target.resolve(),
            content_value,
            tool_call_id=call.tool_call_id,
        )

    def _pending_approval_message(
        self,
        workspace: Path,
        session_id: str,
        requests: DeferredToolRequests,
    ) -> str:
        lines: list[str] = []
        for call in requests.approvals:
            request = self._approval_request_from_tool_call(workspace, session_id, call)
            if request is None:
                continue
            decision = self.approval_policy.evaluate(request)
            if decision.outcome == "ask" and decision.message is not None:
                lines.append(decision.message)
        if lines:
            return "\n".join(lines)
        return "Approval is required before the deferred tool call can continue."
