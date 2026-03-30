from __future__ import annotations as _annotations

from pathlib import Path
from typing import Any, TypeAlias
from uuid import uuid4

from acp import PROTOCOL_VERSION, Agent, RequestError, update_agent_message_text
from acp.interfaces import Client
from acp.schema import (
    AgentCapabilities,
    AllowedOutcome,
    AudioContentBlock,
    AuthenticateResponse,
    CloseSessionResponse,
    EmbeddedResourceContentBlock,
    ForkSessionResponse,
    HttpMcpServer,
    ImageContentBlock,
    Implementation,
    InitializeResponse,
    ListSessionsResponse,
    LoadSessionResponse,
    McpServerStdio,
    NewSessionResponse,
    PromptCapabilities,
    PromptResponse,
    ResourceContentBlock,
    ResumeSessionResponse,
    SessionCapabilities,
    SessionForkCapabilities,
    SessionInfo,
    SessionListCapabilities,
    SessionResumeCapabilities,
    SetSessionConfigOptionResponse,
    SetSessionModelResponse,
    SetSessionModeResponse,
    SseMcpServer,
    TextContentBlock,
)

from vcode import __version__
from vcode.acp.permissions import (
    build_permission_options,
    build_permission_tool_call,
    resolve_permission_outcome,
)
from vcode.acp.presentation import AcpConfigOption, build_config_options
from vcode.acp.updates import (
    build_text_prompt,
    emit_config_options_update,
    emit_mode_and_config_updates,
    emit_tool_projections,
    replay_history,
    schedule_available_commands,
)
from vcode.approvals import ApprovalRequest, ApprovalResolution
from vcode.modes import build_mode_state
from vcode.preferences import set_default_model
from vcode.runtime import VCodeRuntime

__all__ = ("VCodeAcpAgent",)

McpServerConfigEntry: TypeAlias = HttpMcpServer | SseMcpServer | McpServerStdio
PromptBlock: TypeAlias = (
    TextContentBlock
    | ImageContentBlock
    | AudioContentBlock
    | ResourceContentBlock
    | EmbeddedResourceContentBlock
)


class VCodeAcpAgent(Agent):
    client: Client | None

    def __init__(self, runtime: VCodeRuntime | None = None) -> None:
        self.runtime = runtime or VCodeRuntime()
        self.client = None
        self.session_roots: dict[str, Path] = {}

    def on_connect(self, conn: Client) -> None:
        self.client = conn
        self.runtime.approval_policy.resolver = self._request_permission

    async def initialize(
        self,
        protocol_version: int,
        client_capabilities=None,
        client_info=None,
        **kwargs: Any,
    ) -> InitializeResponse:
        del protocol_version, client_capabilities, client_info, kwargs
        return InitializeResponse(
            protocol_version=PROTOCOL_VERSION,
            agent_capabilities=AgentCapabilities(
                load_session=True,
                prompt_capabilities=PromptCapabilities(
                    audio=False,
                    embedded_context=False,
                    image=False,
                ),
                session_capabilities=SessionCapabilities(
                    list=SessionListCapabilities(),
                    fork=SessionForkCapabilities(),
                    resume=SessionResumeCapabilities(),
                ),
            ),
            agent_info=Implementation(name="vcode", title="vCode", version=__version__),
        )

    async def authenticate(self, method_id: str, **kwargs: Any) -> AuthenticateResponse | None:
        del method_id, kwargs
        return AuthenticateResponse()

    async def new_session(
        self,
        cwd: str,
        mcp_servers: list[McpServerConfigEntry] | None = None,
        **kwargs: Any,
    ) -> NewSessionResponse:
        del mcp_servers, kwargs
        record = self.runtime.create_session(Path(cwd))
        self.session_roots[record.session_id] = Path(record.cwd)
        schedule_available_commands(self.client, record.session_id)
        return NewSessionResponse(
            session_id=record.session_id,
            config_options=self.config_options(Path(record.cwd), record.mode_id),
            models=self.runtime.build_model_state(Path(record.cwd), record.mode_id),
            modes=build_mode_state(record.mode_id),
        )

    async def fork_session(
        self,
        cwd: str,
        session_id: str,
        mcp_servers: list[McpServerConfigEntry] | None = None,
        **kwargs: Any,
    ) -> ForkSessionResponse:
        del mcp_servers, kwargs
        record = self.runtime.clone_session(Path(cwd), session_id)
        if record is None:
            raise RequestError.invalid_params({"message": "Session not found"})
        self.session_roots[record.session_id] = Path(record.cwd)
        schedule_available_commands(self.client, record.session_id)
        return ForkSessionResponse(
            session_id=record.session_id,
            config_options=self.config_options(Path(record.cwd), record.mode_id),
            models=self.runtime.build_model_state(Path(record.cwd), record.mode_id),
            modes=build_mode_state(record.mode_id),
        )

    async def load_session(
        self,
        cwd: str,
        session_id: str,
        mcp_servers: list[McpServerConfigEntry] | None = None,
        **kwargs: Any,
    ) -> LoadSessionResponse | None:
        del mcp_servers, kwargs
        workspace = Path(cwd)
        record = self.runtime.load_session(workspace, session_id)
        if record is None:
            return None
        self.session_roots[session_id] = Path(record.cwd)
        await replay_history(self.client, self.runtime, Path(record.cwd), session_id)
        schedule_available_commands(self.client, session_id)
        return LoadSessionResponse(
            config_options=self.config_options(Path(record.cwd), record.mode_id),
            models=self.runtime.build_model_state(Path(record.cwd), record.mode_id),
            modes=build_mode_state(record.mode_id),
        )

    async def resume_session(
        self,
        cwd: str,
        session_id: str,
        mcp_servers: list[McpServerConfigEntry] | None = None,
        **kwargs: Any,
    ) -> ResumeSessionResponse:
        response = await self.load_session(cwd, session_id, mcp_servers, **kwargs)
        if response is None:
            raise RequestError.invalid_params({"message": "Session not found"})
        return ResumeSessionResponse(
            config_options=response.config_options,
            models=response.models,
            modes=response.modes,
        )

    async def list_sessions(
        self,
        cursor: str | None = None,
        cwd: str | None = None,
        **kwargs: Any,
    ) -> ListSessionsResponse:
        del cursor, kwargs
        workspace = Path(cwd or Path.cwd()).resolve()
        records = self.runtime.list_sessions(workspace)
        sessions = [
            SessionInfo(
                session_id=record.session_id,
                cwd=record.cwd,
                title=record.title,
                updated_at=record.updated_at,
            )
            for record in records
        ]
        return ListSessionsResponse(sessions=sessions, next_cursor=None)

    async def set_session_mode(
        self,
        mode_id: str,
        session_id: str,
        **kwargs: Any,
    ) -> SetSessionModeResponse | None:
        del kwargs
        workspace = self.session_roots.get(session_id)
        if workspace is None:
            raise RequestError.invalid_params({"message": "Session not found"})
        record = self.runtime.set_mode(workspace, session_id, mode_id)
        if record is None:
            return None
        await emit_mode_and_config_updates(
            self.client,
            session_id,
            record.mode_id,
            self.config_options(workspace, record.mode_id),
        )
        return SetSessionModeResponse()

    async def set_session_model(
        self,
        model_id: str,
        session_id: str,
        **kwargs: Any,
    ) -> SetSessionModelResponse | None:
        del kwargs
        workspace = self.session_roots.get(session_id)
        if workspace is None:
            raise RequestError.invalid_params({"message": "Session not found"})
        if not model_id.strip():
            return None
        set_default_model(workspace, model_id.strip())
        record = self.runtime.load_session(workspace, session_id)
        if record is None:
            raise RequestError.invalid_params({"message": "Session not found"})
        await emit_config_options_update(
            self.client,
            session_id,
            self.config_options(workspace, record.mode_id),
        )
        return SetSessionModelResponse()

    async def set_config_option(
        self,
        config_id: str,
        session_id: str,
        value: str | bool,
        **kwargs: Any,
    ) -> SetSessionConfigOptionResponse | None:
        del kwargs
        workspace = self.session_roots.get(session_id)
        if workspace is None:
            raise RequestError.invalid_params({"message": "Session not found"})
        if not isinstance(value, str):
            return None

        normalized_value = value.strip()
        if not normalized_value:
            return None

        if config_id == "model":
            set_default_model(workspace, normalized_value)
        elif config_id == "mode":
            record = self.runtime.set_mode(workspace, session_id, normalized_value)
            if record is None:
                return None
        else:
            return None

        record = self.runtime.load_session(workspace, session_id)
        if record is None:
            raise RequestError.invalid_params({"message": "Session not found"})
        if config_id == "mode":
            await emit_mode_and_config_updates(
                self.client,
                session_id,
                record.mode_id,
                self.config_options(workspace, record.mode_id),
            )
        else:
            await emit_config_options_update(
                self.client,
                session_id,
                self.config_options(workspace, record.mode_id),
            )
        return SetSessionConfigOptionResponse(
            config_options=self.config_options(workspace, record.mode_id)
        )

    async def prompt(
        self,
        prompt: list[PromptBlock],
        session_id: str,
        message_id: str | None = None,
        **kwargs: Any,
    ) -> PromptResponse:
        del kwargs, message_id
        workspace = self.session_roots.get(session_id)
        if workspace is None:
            raise RequestError.invalid_params({"message": "Session not found"})

        text_prompt = build_text_prompt(prompt)
        result = await self.runtime.run_prompt(workspace, session_id, text_prompt)
        if result is None:
            raise RequestError.invalid_params({"message": "Session not found"})

        if self.client is not None:
            await emit_tool_projections(self.client, session_id, result.tool_projections)
            await self.client.session_update(
                session_id=session_id,
                update=update_agent_message_text(result.response_text),
            )

        return PromptResponse(stop_reason=result.stop_reason)

    async def cancel(self, session_id: str, **kwargs: Any) -> None:
        del session_id, kwargs

    async def close_session(self, session_id: str, **kwargs: Any) -> CloseSessionResponse | None:
        del kwargs
        self.session_roots.pop(session_id, None)
        return CloseSessionResponse()

    async def ext_method(self, method: str, params: dict[str, object]) -> dict[str, object]:
        del params
        raise RequestError.method_not_found(f"_{method}")

    async def ext_notification(self, method: str, params: dict[str, object]) -> None:
        del method, params

    def config_options(self, workspace: Path, mode_id: str) -> list[AcpConfigOption]:
        return build_config_options(workspace, mode_id)

    async def request_permission(self, request: ApprovalRequest) -> ApprovalResolution:
        if self.client is None:
            return ApprovalResolution(kind="reject_once")

        response = await self.client.request_permission(
            session_id=request.session_id,
            tool_call=build_permission_tool_call(
                request,
                request_id=f"{request.tool_call_id}-{uuid4().hex}",
            ),
            options=build_permission_options(),
        )
        if isinstance(response.outcome, AllowedOutcome):
            return ApprovalResolution(kind=resolve_permission_outcome(response.outcome))
        return ApprovalResolution(kind="cancelled")

    async def _request_permission(self, request: ApprovalRequest) -> ApprovalResolution:
        return await self.request_permission(request)
