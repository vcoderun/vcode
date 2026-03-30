from __future__ import annotations as _annotations

from collections.abc import Sequence

from pydantic_ai.messages import ModelMessage, ToolCallPart, ToolReturnPart

from vcode.runtime.types import (
    ToolContentDiff,
    ToolContentText,
    ToolKind,
    ToolProjection,
)

__all__ = ("build_tool_projections",)

kind_by_tool: dict[str, ToolKind] = {
    "list_files": "search",
    "read_file": "read",
    "write_file": "edit",
}
title_by_tool: dict[str, str] = {
    "list_files": "List Files",
    "read_file": "Read File",
    "write_file": "Write File",
}


def build_tool_projections(
    messages: Sequence[ModelMessage],
) -> tuple[ToolProjection, ...]:
    starts: dict[str, ToolProjection] = {}
    projections: list[ToolProjection] = []

    for message in messages:
        for part in message.parts:
            if isinstance(part, ToolCallPart):
                projection = build_start_projection(part)
                starts[part.tool_call_id] = projection
            elif isinstance(part, ToolReturnPart):
                start = starts.get(part.tool_call_id)
                if start is None:
                    continue
                projections.append(
                    build_complete_projection(start, str(part.content), part.outcome)
                )

    return tuple(projections)


def build_start_projection(part: ToolCallPart) -> ToolProjection:
    args = {str(key): str(value) for key, value in part.args_as_dict().items()}
    locations = projection_locations(part.tool_name, args)
    content = projection_start_content(part.tool_name, args)
    return ToolProjection(
        tool_call_id=part.tool_call_id,
        title=projection_title(part.tool_name, args),
        kind=kind_by_tool.get(part.tool_name, "other"),
        raw_input=args,
        raw_output="",
        locations=locations,
        content=content,
        status="pending",
    )


def build_complete_projection(
    start: ToolProjection,
    raw_output: str,
    outcome: str,
) -> ToolProjection:
    content = start.content
    if start.kind in {"read", "search"}:
        content = (tool_text_content(raw_output[:4000]),)

    return ToolProjection(
        tool_call_id=start.tool_call_id,
        title=start.title,
        kind=start.kind,
        raw_input=start.raw_input,
        raw_output=raw_output,
        locations=start.locations,
        content=content,
        status="completed" if outcome == "success" else "failed",
    )


def projection_title(tool_name: str, args: dict[str, str]) -> str:
    base_title = title_by_tool.get(tool_name, tool_name)
    path = args.get("path")
    if path:
        return f"{base_title} {path}"
    return base_title


def projection_locations(tool_name: str, args: dict[str, str]) -> tuple[str, ...]:
    if tool_name not in {"list_files", "read_file", "write_file"}:
        return ()
    path = args.get("path")
    if path:
        return (path,)
    return ()


def projection_start_content(tool_name: str, args: dict[str, str]) -> tuple[ToolContentDiff, ...]:
    if tool_name != "write_file":
        return ()
    path = args.get("path")
    content = args.get("content")
    if not path or content is None:
        return ()
    return (
        ToolContentDiff(
            path=path,
            new_text=content,
        ),
    )


def tool_text_content(text: str) -> ToolContentText:
    return ToolContentText(text=text)
