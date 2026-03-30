from __future__ import annotations as _annotations

from pathlib import Path

from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
)
from pydantic_ai.models.function import AgentInfo, FunctionModel

from vcode.approvals import ApprovalPolicy, ApprovalRequest, ApprovalResolution
from vcode.preferences import set_default_model
from vcode.runtime import VCodeRuntime


def _latest_user_prompt(messages: list[ModelMessage]) -> str:
    for message in reversed(messages):
        if not isinstance(message, ModelRequest):
            continue
        for part in reversed(message.parts):
            content = getattr(part, "content", None)
            if isinstance(content, str):
                return content.strip()
    return ""


def _tool_call_for_prompt(prompt: str) -> tuple[str, dict[str, str]] | None:
    lowered = prompt.lower()
    if lowered.startswith("read "):
        return "read_file", {"path": prompt[5:].strip()}
    if lowered.startswith("list"):
        path = prompt[4:].strip() or "."
        return "list_files", {"path": path}
    if lowered.startswith("write "):
        raw = prompt[6:].strip()
        if ":" in raw:
            path, content = raw.split(":", 1)
        else:
            path, _, content = raw.partition(" ")
        if path.strip() and content.strip():
            return "write_file", {"path": path.strip(), "content": content.lstrip()}
    return None


async def _test_model_response(
    messages: list[ModelMessage], agent_info: AgentInfo
) -> ModelResponse:
    del agent_info
    latest_message = messages[-1] if messages else None
    if isinstance(latest_message, ModelRequest):
        tool_returns = [
            part
            for part in latest_message.parts
            if getattr(part, "part_kind", None) == "tool-return"
        ]
        if tool_returns:
            content = "\n".join(f"{part.tool_name}: {part.content}" for part in tool_returns)
            return ModelResponse(parts=[TextPart(content=content)], model_name="test:demo")

    prompt = _latest_user_prompt(messages)
    tool_call = _tool_call_for_prompt(prompt)
    if tool_call is not None:
        tool_name, args = tool_call
        return ModelResponse(
            parts=[
                ToolCallPart(
                    tool_name=tool_name,
                    args=args,
                    tool_call_id=f"test-demo-{tool_name}",
                )
            ],
            model_name="test:demo",
        )

    return ModelResponse(parts=[TextPart(content=f"echo: {prompt}")], model_name="test:demo")


async def _allow_all_approvals(request: ApprovalRequest) -> ApprovalResolution:
    del request
    return ApprovalResolution(kind="allow_once")


def build_test_runtime(*, auto_approve: bool = True) -> VCodeRuntime:
    approval_policy = ApprovalPolicy(
        resolver=_allow_all_approvals if auto_approve else None,
    )
    runtime = VCodeRuntime(
        approval_policy=approval_policy,
        model_resolver=lambda model_id: FunctionModel(
            function=_test_model_response, model_name=model_id
        ),
    )
    return runtime


def configure_test_model(cwd: Path) -> None:
    set_default_model(cwd, "test:demo")
