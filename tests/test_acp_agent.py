from __future__ import annotations as _annotations

import asyncio
from pathlib import Path
from typing import TypeAlias

import pytest
from acp import PROTOCOL_VERSION
from acp.interfaces import Client
from acp.schema import (
    AgentMessageChunk,
    AgentPlanUpdate,
    AgentThoughtChunk,
    AllowedOutcome,
    AvailableCommandsUpdate,
    ConfigOptionUpdate,
    CreateTerminalResponse,
    CurrentModeUpdate,
    EnvVariable,
    KillTerminalResponse,
    PermissionOption,
    ReadTextFileResponse,
    ReleaseTerminalResponse,
    RequestPermissionResponse,
    SessionInfoUpdate,
    TerminalOutputResponse,
    TextContentBlock,
    ToolCallProgress,
    ToolCallStart,
    ToolCallUpdate,
    UsageUpdate,
    UserMessageChunk,
    WaitForTerminalExitResponse,
    WriteTextFileResponse,
)
from fakes import build_test_runtime, configure_test_model

from vcode.acp.agent import VCodeAcpAgent
from vcode.modes import DEFAULT_MODE_ID

pytestmark = pytest.mark.asyncio

SessionUpdate: TypeAlias = (
    UserMessageChunk
    | AgentMessageChunk
    | AgentThoughtChunk
    | AgentPlanUpdate
    | AvailableCommandsUpdate
    | CurrentModeUpdate
    | ConfigOptionUpdate
    | SessionInfoUpdate
    | UsageUpdate
    | ToolCallProgress
    | ToolCallStart
)
JsonObject: TypeAlias = dict[str, object]


class FakeClient(Client):
    def __init__(self) -> None:
        self.updates: list[tuple[str, SessionUpdate]] = []
        self.permission_requests: list[tuple[str, ToolCallUpdate, list[PermissionOption]]] = []

    async def session_update(
        self,
        session_id: str,
        update: SessionUpdate,
        **kwargs: object,
    ) -> None:
        del kwargs
        self.updates.append((session_id, update))

    async def request_permission(
        self,
        options: list[PermissionOption],
        session_id: str,
        tool_call: ToolCallUpdate,
        **kwargs: object,
    ) -> RequestPermissionResponse:
        del kwargs
        self.permission_requests.append((session_id, tool_call, options))
        return RequestPermissionResponse(
            outcome=AllowedOutcome(outcome="selected", option_id="allow_once")
        )

    async def write_text_file(
        self, content: str, path: str, session_id: str, **kwargs: object
    ) -> WriteTextFileResponse | None:
        del content, path, session_id, kwargs
        raise AssertionError("write_text_file should not be called in ACP agent tests")

    async def read_text_file(
        self,
        path: str,
        session_id: str,
        limit: int | None = None,
        line: int | None = None,
        **kwargs: object,
    ) -> ReadTextFileResponse:
        del path, session_id, limit, line, kwargs
        raise AssertionError("read_text_file should not be called in ACP agent tests")

    async def create_terminal(
        self,
        command: str,
        session_id: str,
        args: list[str] | None = None,
        cwd: str | None = None,
        env: list[EnvVariable] | None = None,
        output_byte_limit: int | None = None,
        **kwargs: object,
    ) -> CreateTerminalResponse:
        del command, session_id, args, cwd, env, output_byte_limit, kwargs
        raise AssertionError("create_terminal should not be called in ACP agent tests")

    async def terminal_output(
        self, session_id: str, terminal_id: str, **kwargs: object
    ) -> TerminalOutputResponse:
        del session_id, terminal_id, kwargs
        raise AssertionError("terminal_output should not be called in ACP agent tests")

    async def release_terminal(
        self, session_id: str, terminal_id: str, **kwargs: object
    ) -> ReleaseTerminalResponse | None:
        del session_id, terminal_id, kwargs
        raise AssertionError("release_terminal should not be called in ACP agent tests")

    async def wait_for_terminal_exit(
        self, session_id: str, terminal_id: str, **kwargs: object
    ) -> WaitForTerminalExitResponse:
        del session_id, terminal_id, kwargs
        raise AssertionError("wait_for_terminal_exit should not be called in ACP agent tests")

    async def kill_terminal(
        self, session_id: str, terminal_id: str, **kwargs: object
    ) -> KillTerminalResponse | None:
        del session_id, terminal_id, kwargs
        raise AssertionError("kill_terminal should not be called in ACP agent tests")

    async def ext_method(self, method: str, params: JsonObject) -> JsonObject:
        del method, params
        raise AssertionError("ext_method should not be called in ACP agent tests")

    async def ext_notification(self, method: str, params: JsonObject) -> None:
        del method, params
        raise AssertionError("ext_notification should not be called in ACP agent tests")

    def on_connect(self, conn: object) -> None:
        del conn


class TestVCodeAcpAgent:
    async def test_initialize_advertises_load_and_list(self) -> None:
        agent = VCodeAcpAgent(runtime=build_test_runtime())

        response = await agent.initialize(protocol_version=PROTOCOL_VERSION)

        assert response.protocol_version == PROTOCOL_VERSION
        assert response.agent_capabilities is not None
        assert response.agent_capabilities.load_session is True
        assert response.agent_capabilities.session_capabilities is not None
        assert response.agent_capabilities.session_capabilities.list is not None

    async def test_new_session_returns_modes(self, tmp_path: Path) -> None:
        agent = VCodeAcpAgent(runtime=build_test_runtime())
        configure_test_model(tmp_path)

        response = await agent.new_session(cwd=str(tmp_path), mcp_servers=[])

        assert response.session_id
        assert response.config_options is not None
        assert {option.id for option in response.config_options} == {"mode", "model"}
        assert response.models is not None
        assert response.models.current_model_id == "test:demo"
        assert response.modes is not None
        assert response.modes.current_mode_id == DEFAULT_MODE_ID
        assert {mode.id for mode in response.modes.available_modes} == {
            "ask",
            "plan",
            "agent",
        }

    async def test_prompt_streams_user_and_agent_messages(self, tmp_path: Path) -> None:
        agent = VCodeAcpAgent(runtime=build_test_runtime())
        configure_test_model(tmp_path)
        client = FakeClient()
        agent.on_connect(client)

        response = await agent.new_session(cwd=str(tmp_path), mcp_servers=[])
        prompt_response = await agent.prompt(
            session_id=response.session_id,
            prompt=[TextContentBlock(type="text", text="hello world")],
        )

        assert prompt_response.stop_reason == "end_turn"
        assert client.updates[0][0] == response.session_id
        visible_updates = [
            type(update).__name__
            for _, update in client.updates
            if type(update).__name__ != "AvailableCommandsUpdate"
        ]
        assert visible_updates[-1:] == ["AgentMessageChunk"]

    async def test_new_session_emits_available_commands(self, tmp_path: Path) -> None:
        agent = VCodeAcpAgent(runtime=build_test_runtime())
        configure_test_model(tmp_path)
        client = FakeClient()
        agent.on_connect(client)

        response = await agent.new_session(cwd=str(tmp_path), mcp_servers=[])
        await asyncio.sleep(0.01)

        assert response.session_id
        assert [type(update).__name__ for _, update in client.updates] == [
            "AvailableCommandsUpdate"
        ]
        commands_update = client.updates[0][1]
        assert isinstance(commands_update, AvailableCommandsUpdate)
        assert [command.name for command in commands_update.available_commands] == [
            "models",
            "model",
            "approvals",
            "hooks",
            "mcp",
            "approve",
            "deny",
            "update-preferences",
        ]

    async def test_prompt_projects_tool_calls_and_writes_file(self, tmp_path: Path) -> None:
        agent = VCodeAcpAgent(runtime=build_test_runtime(auto_approve=False))
        configure_test_model(tmp_path)
        client = FakeClient()
        agent.on_connect(client)

        response = await agent.new_session(cwd=str(tmp_path), mcp_servers=[])
        await agent.prompt(
            session_id=response.session_id,
            prompt=[TextContentBlock(type="text", text="write demo.txt: hello acp")],
        )

        assert (tmp_path / "demo.txt").read_text(encoding="utf-8") == "hello acp"
        assert client.permission_requests
        _, tool_call, _ = client.permission_requests[0]
        assert tool_call.title == "Write demo.txt"
        assert tool_call.raw_input == {"path": "demo.txt", "content": "hello acp"}
        assert tool_call.locations is not None
        assert tool_call.locations[0].path == "demo.txt"
        assert tool_call.content is not None
        assert len(tool_call.content) == 1
        assert tool_call.content[0].type == "diff"
        assert tool_call.content[0].path == "demo.txt"
        assert tool_call.content[0].new_text == "hello acp"
        visible_updates = [
            update
            for _, update in client.updates
            if type(update).__name__ != "AvailableCommandsUpdate"
        ]
        assert [type(update).__name__ for update in visible_updates[-3:]] == [
            "ToolCallStart",
            "ToolCallProgress",
            "AgentMessageChunk",
        ]

    async def test_prompt_projects_hook_commands_to_acp(self, tmp_path: Path) -> None:
        agent = VCodeAcpAgent(runtime=build_test_runtime(auto_approve=True))
        configure_test_model(tmp_path)
        client = FakeClient()
        agent.on_connect(client)
        (tmp_path / ".vcode").mkdir(parents=True, exist_ok=True)
        (tmp_path / ".vcode" / "hooks.yml").write_text(
            "\n".join(
                [
                    "events:",
                    "  before_tool_execute:",
                    "    - name: audit-write",
                    "      command: python3.11",
                    "      args:",
                    "        - -c",
                    "        - print('hook ran')",
                    "      tools:",
                    "        - write_file",
                ]
            ),
            encoding="utf-8",
        )

        response = await agent.new_session(cwd=str(tmp_path), mcp_servers=[])
        await agent.prompt(
            session_id=response.session_id,
            prompt=[TextContentBlock(type="text", text="write demo.txt: hello acp")],
        )

        hook_updates = [
            update
            for _, update in client.updates
            if isinstance(update, ToolCallProgress)
            and isinstance(update.raw_input, dict)
            and update.raw_input.get("event") == "before_tool_execute"
        ]
        assert hook_updates
        assert hook_updates[0].kind == "execute"
        assert hook_updates[0].title == "Hook audit-write"

    async def test_prompt_projects_read_file_with_visible_tool_content(
        self, tmp_path: Path
    ) -> None:
        agent = VCodeAcpAgent(runtime=build_test_runtime())
        configure_test_model(tmp_path)
        (tmp_path / "notes.txt").write_text("hello from file", encoding="utf-8")
        client = FakeClient()
        agent.on_connect(client)

        response = await agent.new_session(cwd=str(tmp_path), mcp_servers=[])
        await agent.prompt(
            session_id=response.session_id,
            prompt=[TextContentBlock(type="text", text="read notes.txt")],
        )

        visible_updates = [
            update
            for _, update in client.updates
            if type(update).__name__ != "AvailableCommandsUpdate"
        ]
        assert [type(update).__name__ for update in visible_updates[-3:]] == [
            "ToolCallStart",
            "ToolCallProgress",
            "AgentMessageChunk",
        ]
        tool_start = visible_updates[-3]
        tool_progress = visible_updates[-2]
        assert isinstance(tool_start, ToolCallStart)
        assert isinstance(tool_progress, ToolCallProgress)
        assert tool_start.title == "Read File notes.txt"
        assert tool_start.locations is not None
        assert tool_start.locations[0].path == "notes.txt"
        assert tool_progress.content is not None
        assert tool_progress.content[0].type == "content"
        assert tool_progress.content[0].content.text == "hello from file"

    async def test_set_session_mode_persists(self, tmp_path: Path) -> None:
        agent = VCodeAcpAgent(runtime=build_test_runtime())
        configure_test_model(tmp_path)

        response = await agent.new_session(cwd=str(tmp_path), mcp_servers=[])
        mode_response = await agent.set_session_mode("plan", response.session_id)
        loaded = await agent.load_session(str(tmp_path), response.session_id, mcp_servers=[])

        assert mode_response is not None
        assert loaded is not None
        assert loaded.modes is not None
        assert loaded.modes.current_mode_id == "plan"

    async def test_set_session_model_persists(self, tmp_path: Path) -> None:
        agent = VCodeAcpAgent(runtime=build_test_runtime())

        response = await agent.new_session(cwd=str(tmp_path), mcp_servers=[])
        model_response = await agent.set_session_model("test:test", response.session_id)
        loaded = await agent.load_session(str(tmp_path), response.session_id, mcp_servers=[])

        assert model_response is not None
        assert loaded is not None
        assert loaded.models is not None
        assert loaded.models.current_model_id == "test:test"

    async def test_set_session_model_enables_followup_prompt(self, tmp_path: Path) -> None:
        agent = VCodeAcpAgent(runtime=build_test_runtime())

        response = await agent.new_session(cwd=str(tmp_path), mcp_servers=[])
        await agent.set_session_model("test:test", response.session_id)
        prompt_response = await agent.prompt(
            session_id=response.session_id,
            prompt=[TextContentBlock(type="text", text="hello after set_session_model")],
        )

        assert prompt_response.stop_reason == "end_turn"

    async def test_set_config_option_model_persists(self, tmp_path: Path) -> None:
        agent = VCodeAcpAgent(runtime=build_test_runtime())

        response = await agent.new_session(cwd=str(tmp_path), mcp_servers=[])
        config_response = await agent.set_config_option(
            session_id=response.session_id,
            config_id="model",
            value="test:test",
        )
        loaded = await agent.load_session(str(tmp_path), response.session_id, mcp_servers=[])

        assert config_response is not None
        assert {option.id for option in config_response.config_options} == {
            "mode",
            "model",
        }
        assert loaded is not None
        assert loaded.models is not None
        assert loaded.models.current_model_id == "test:test"

    async def test_set_config_option_model_enables_followup_prompt(self, tmp_path: Path) -> None:
        agent = VCodeAcpAgent(runtime=build_test_runtime())

        response = await agent.new_session(cwd=str(tmp_path), mcp_servers=[])
        await agent.set_config_option(
            session_id=response.session_id,
            config_id="model",
            value="test:test",
        )
        prompt_response = await agent.prompt(
            session_id=response.session_id,
            prompt=[TextContentBlock(type="text", text="hello after set_config_option")],
        )

        assert prompt_response.stop_reason == "end_turn"

    async def test_set_config_option_emits_config_option_update(self, tmp_path: Path) -> None:
        agent = VCodeAcpAgent(runtime=build_test_runtime())
        configure_test_model(tmp_path)
        client = FakeClient()
        agent.on_connect(client)

        response = await agent.new_session(cwd=str(tmp_path), mcp_servers=[])
        await asyncio.sleep(0.01)
        await agent.set_config_option(
            session_id=response.session_id,
            config_id="model",
            value="test:test",
        )

        assert any(type(update).__name__ == "ConfigOptionUpdate" for _, update in client.updates)
