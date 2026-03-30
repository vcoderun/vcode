from __future__ import annotations as _annotations

from acp.helpers import text_block, tool_content, tool_diff_content
from acp.schema import (
    AllowedOutcome,
    ContentToolCallContent,
    FileEditToolCallContent,
    PermissionOption,
    TerminalToolCallContent,
    ToolCallLocation,
    ToolCallProgress,
)

from vcode.approvals import ApprovalRequest, ApprovalResolverKind

__all__ = (
    "build_permission_options",
    "build_permission_tool_call",
    "resolve_permission_outcome",
)


def build_permission_tool_call(request: ApprovalRequest, request_id: str) -> ToolCallProgress:
    raw_input: dict[str, object] = request.raw_input or {
        "target": request.target,
        "reason": request.reason,
    }
    locations: list[ToolCallLocation] | None = None
    title = request.title or request.tool_name
    content: list[ContentToolCallContent | FileEditToolCallContent | TerminalToolCallContent]

    if request.tool_name == "write_file":
        raw_input = request.raw_input or {"path": request.target}
        locations = [ToolCallLocation(path=request.target)]
        content = [
            tool_diff_content(
                path=request.target,
                new_text=request.new_text or "",
                old_text=request.old_text,
            )
        ]
    else:
        content = [tool_content(text_block(f"{request.reason}\nTarget: {request.target}"))]

    return ToolCallProgress(
        session_update="tool_call_update",
        tool_call_id=request_id,
        title=title,
        kind=request.kind,
        content=content,
        locations=locations,
        raw_input=raw_input,
        status="pending",
    )


def build_permission_options() -> list[PermissionOption]:
    return [
        PermissionOption(
            option_id="allow_once",
            kind="allow_once",
            name="Allow Once",
        ),
        PermissionOption(
            option_id="allow_always",
            kind="allow_always",
            name="Allow For Session",
        ),
        PermissionOption(
            option_id="reject_once",
            kind="reject_once",
            name="Reject Once",
        ),
        PermissionOption(
            option_id="reject_always",
            kind="reject_always",
            name="Reject For Session",
        ),
    ]


def resolve_permission_outcome(outcome: AllowedOutcome) -> ApprovalResolverKind:
    option_id = outcome.option_id
    if option_id == "allow_once":
        return "allow_once"
    if option_id == "allow_always":
        return "allow_always"
    if option_id == "reject_once":
        return "reject_once"
    if option_id == "reject_always":
        return "reject_always"
    return "cancelled"
