from __future__ import annotations as _annotations

from pathlib import Path

import pytest
from fakes import build_test_runtime, configure_test_model
from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from vcode.runtime import VCodeRuntime
from vcode.runtime.types import ToolContentDiff, TurnResult
from vcode.sessions import SessionRecord

pytestmark = pytest.mark.asyncio


def _require_turn_result(result: TurnResult | None) -> TurnResult:
    assert result is not None, "expected a prompt result for an existing session"
    return result


def _require_session_record(record: SessionRecord | None) -> SessionRecord:
    assert record is not None, "expected a persisted session record"
    return record


class TestVCodeRuntime:
    async def test_demo_model_can_write_and_read_file(self, tmp_path: Path) -> None:
        runtime = build_test_runtime(auto_approve=True)
        configure_test_model(tmp_path)
        session = runtime.create_session(tmp_path)

        write_result = _require_turn_result(
            await runtime.run_prompt(
                tmp_path,
                session.session_id,
                "write notes.txt: hello from runtime",
            )
        )
        read_result = _require_turn_result(
            await runtime.run_prompt(tmp_path, session.session_id, "read notes.txt")
        )

        assert (tmp_path / "notes.txt").read_text(encoding="utf-8") == "hello from runtime"
        assert "Wrote notes.txt" in write_result.response_text
        assert "hello from runtime" in read_result.response_text
        assert write_result.tool_projections

    async def test_plan_mode_blocks_non_plan_writes(self, tmp_path: Path) -> None:
        runtime = build_test_runtime(auto_approve=True)
        configure_test_model(tmp_path)
        session = runtime.create_session(tmp_path)
        runtime.set_mode(tmp_path, session.session_id, "plan")

        result = _require_turn_result(
            await runtime.run_prompt(
                tmp_path,
                session.session_id,
                "write app.py: blocked in plan mode",
            )
        )

        assert "Write denied in plan mode" in result.response_text
        assert not (tmp_path / "app.py").exists()

    async def test_manual_model_command_updates_session(self, tmp_path: Path) -> None:
        runtime = VCodeRuntime()
        session = runtime.create_session(tmp_path)

        result = _require_turn_result(
            await runtime.run_prompt(tmp_path, session.session_id, "/model openai:gpt-5-mini")
        )
        loaded = _require_session_record(runtime.load_session(tmp_path, session.session_id))

        assert result.response_text == "Default model set to openai:gpt-5-mini."
        assert loaded.session_id == session.session_id

    async def test_manual_mode_model_command_updates_preferences(self, tmp_path: Path) -> None:
        runtime = VCodeRuntime()
        session = runtime.create_session(tmp_path)

        await runtime.run_prompt(
            tmp_path,
            session.session_id,
            "/model plan anthropic:claude-sonnet-4-5",
        )
        status = _require_turn_result(
            await runtime.run_prompt(tmp_path, session.session_id, "/model")
        )

        assert "Model Configuration" in status.response_text
        assert "Active Mode" in status.response_text
        assert "Agent" in status.response_text
        assert "Plan          anthropic:claude-sonnet-4-5" in status.response_text

    async def test_duplicate_plain_text_is_normalized(self, tmp_path: Path) -> None:
        runtime = build_test_runtime(auto_approve=True)
        configure_test_model(tmp_path)
        session = runtime.create_session(tmp_path)

        result = _require_turn_result(
            await runtime.run_prompt(tmp_path, session.session_id, "hellohello")
        )

        assert result.response_text == "echo: hello"

    async def test_duplicate_model_command_is_normalized(self, tmp_path: Path) -> None:
        runtime = VCodeRuntime()
        session = runtime.create_session(tmp_path)

        result = _require_turn_result(
            await runtime.run_prompt(
                tmp_path,
                session.session_id,
                "//model openai:gpt-5-mini//model openai:gpt-5-mini",
            )
        )

        assert result.response_text == "Default model set to openai:gpt-5-mini."

    async def test_write_requires_local_approval_without_resolver(self, tmp_path: Path) -> None:
        runtime = build_test_runtime(auto_approve=False)
        configure_test_model(tmp_path)
        session = runtime.create_session(tmp_path)

        result = _require_turn_result(
            await runtime.run_prompt(
                tmp_path,
                session.session_id,
                "write notes.txt: blocked until approved",
            )
        )

        assert "Approval required for write_file notes.txt" in result.response_text
        assert not (tmp_path / "notes.txt").exists()

    async def test_manual_approve_command_allows_followup_write(self, tmp_path: Path) -> None:
        runtime = build_test_runtime(auto_approve=False)
        configure_test_model(tmp_path)
        session = runtime.create_session(tmp_path)

        await runtime.run_prompt(tmp_path, session.session_id, "/approve write notes.txt")
        result = _require_turn_result(
            await runtime.run_prompt(
                tmp_path,
                session.session_id,
                "write notes.txt: approved now",
            )
        )

        assert "Wrote notes.txt" in result.response_text
        assert (tmp_path / "notes.txt").read_text(encoding="utf-8") == "approved now"

    async def test_update_preferences_imports_session_approvals(self, tmp_path: Path) -> None:
        runtime = build_test_runtime(auto_approve=False)
        configure_test_model(tmp_path)
        source_session = runtime.create_session(tmp_path)
        target_session = runtime.create_session(tmp_path)

        await runtime.run_prompt(tmp_path, source_session.session_id, "/approve write imported.txt")
        result = _require_turn_result(
            await runtime.run_prompt(
                tmp_path,
                target_session.session_id,
                f"/update-preferences {source_session.session_id}",
            )
        )

        assert (
            f"Imported 1 approval rule(s) from session {source_session.session_id}."
            == result.response_text
        )

        write_result = _require_turn_result(
            await runtime.run_prompt(
                tmp_path,
                target_session.session_id,
                "write imported.txt: imported approval works",
            )
        )

        assert "Wrote imported.txt" in write_result.response_text

    async def test_tool_projection_handles_json_string_args(self, tmp_path: Path) -> None:
        async def string_args_model(messages, agent_info: AgentInfo) -> ModelResponse:
            del agent_info
            latest_message = messages[-1] if messages else None
            if latest_message is not None:
                tool_returns = [
                    part
                    for part in getattr(latest_message, "parts", ())
                    if getattr(part, "part_kind", None) == "tool-return"
                ]
                if tool_returns:
                    return ModelResponse(
                        parts=[TextPart(content="write complete")],
                        model_name="test:json",
                    )
            return ModelResponse(
                parts=[
                    ToolCallPart(
                        tool_name="write_file",
                        args='{"path":"json.txt","content":"from json args"}',
                        tool_call_id="json-write",
                    )
                ],
                model_name="test:json",
            )

        runtime = VCodeRuntime(
            approval_policy=build_test_runtime(auto_approve=True).approval_policy,
            model_resolver=lambda model_id: FunctionModel(
                function=string_args_model,
                model_name=model_id,
            ),
        )
        session = runtime.create_session(tmp_path)
        configure_test_model(tmp_path)

        result = _require_turn_result(
            await runtime.run_prompt(tmp_path, session.session_id, "write json.txt")
        )

        assert result.tool_projections
        assert result.tool_projections[0].raw_input == {
            "path": "json.txt",
            "content": "from json args",
        }
        assert isinstance(result.tool_projections[0].content[0], ToolContentDiff)

    async def test_read_denied_by_vcodeignore(self, tmp_path: Path) -> None:
        runtime = build_test_runtime(auto_approve=True)
        configure_test_model(tmp_path)
        session = runtime.create_session(tmp_path)
        (tmp_path / ".vcode").mkdir(exist_ok=True)
        (tmp_path / ".vcode" / ".vcodeignore").write_text("secret.txt\n", encoding="utf-8")
        (tmp_path / "secret.txt").write_text("hidden", encoding="utf-8")

        result = _require_turn_result(
            await runtime.run_prompt(tmp_path, session.session_id, "read secret.txt")
        )

        assert (
            result.response_text
            == "read_file: Read denied by .vcode/.vcodeignore for path: secret.txt"
        )

    async def test_workspace_escape_is_rejected(self, tmp_path: Path) -> None:
        runtime = build_test_runtime(auto_approve=True)
        configure_test_model(tmp_path)
        session = runtime.create_session(tmp_path)

        result = _require_turn_result(
            await runtime.run_prompt(tmp_path, session.session_id, "read ../../etc/passwd")
        )

        assert result.response_text == "read_file: Path escapes workspace root: ../../etc/passwd"

    async def test_list_hides_vcodeignored_paths(self, tmp_path: Path) -> None:
        runtime = build_test_runtime(auto_approve=True)
        configure_test_model(tmp_path)
        session = runtime.create_session(tmp_path)
        (tmp_path / ".vcode").mkdir(exist_ok=True)
        (tmp_path / ".vcode" / ".vcodeignore").write_text("private/\n*.secret\n", encoding="utf-8")
        (tmp_path / "visible.txt").write_text("ok", encoding="utf-8")
        (tmp_path / "hidden.secret").write_text("nope", encoding="utf-8")
        (tmp_path / "private").mkdir()
        (tmp_path / "private" / "nested.txt").write_text("nope", encoding="utf-8")

        result = _require_turn_result(
            await runtime.run_prompt(tmp_path, session.session_id, "list")
        )

        assert "visible.txt" in result.response_text
        assert "hidden.secret" not in result.response_text
        assert "private/" not in result.response_text
