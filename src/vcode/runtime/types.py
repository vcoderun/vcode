from __future__ import annotations as _annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal, TypeAlias

__all__ = (
    "RawToolInput",
    "ToolContent",
    "ToolContentDiff",
    "ToolContentText",
    "ToolKind",
    "ToolProjection",
    "ToolStatus",
    "TurnStopReason",
    "TurnResult",
)

RawToolInput: TypeAlias = Mapping[str, object]
ToolKind: TypeAlias = Literal[
    "read",
    "edit",
    "delete",
    "move",
    "search",
    "execute",
    "think",
    "fetch",
    "switch_mode",
    "other",
]
ToolStatus: TypeAlias = Literal["pending", "completed", "failed"]
TurnStopReason: TypeAlias = Literal[
    "end_turn",
    "max_tokens",
    "max_turn_requests",
    "refusal",
    "cancelled",
]


@dataclass(frozen=True, slots=True, kw_only=True)
class ToolContentText:
    text: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ToolContentDiff:
    path: str
    new_text: str
    old_text: str | None = None


ToolContent: TypeAlias = ToolContentText | ToolContentDiff


@dataclass(frozen=True, slots=True, kw_only=True)
class ToolProjection:
    tool_call_id: str
    title: str
    kind: ToolKind
    raw_input: RawToolInput
    raw_output: str
    locations: tuple[str, ...] = ()
    content: tuple[ToolContent, ...] = ()
    status: ToolStatus = "completed"


@dataclass(frozen=True, slots=True, kw_only=True)
class TurnResult:
    response_text: str
    stop_reason: TurnStopReason = "end_turn"
    tool_projections: tuple[ToolProjection, ...] = ()
