from __future__ import annotations as _annotations

from dataclasses import dataclass, field

from vcode.runtime.types import ToolContentText, ToolProjection

__all__ = (
    "HookEventCollector",
    "HookExecutionEvent",
)


@dataclass(frozen=True, slots=True, kw_only=True)
class HookExecutionEvent:
    sequence_id: int
    event_id: str
    command: str
    hook_name: str = ""
    tool_name: str = ""
    tool_filters: tuple[str, ...] = ()
    raw_output: str = ""
    status: str = "completed"


@dataclass(slots=True, kw_only=True)
class HookEventCollector:
    events: list[HookExecutionEvent] = field(default_factory=list)
    next_sequence_id: int = 1

    def record(
        self,
        *,
        event_id: str,
        command: str,
        hook_name: str = "",
        tool_name: str = "",
        tool_filters: tuple[str, ...] = (),
        raw_output: str = "",
        status: str = "completed",
    ) -> None:
        self.events.append(
            HookExecutionEvent(
                sequence_id=self.next_sequence_id,
                event_id=event_id,
                command=command,
                hook_name=hook_name,
                tool_name=tool_name,
                tool_filters=tool_filters,
                raw_output=raw_output,
                status=status,
            )
        )
        self.next_sequence_id += 1

    def build_projections(self) -> tuple[ToolProjection, ...]:
        return tuple(self._build_projection(event) for event in self.events)

    def _build_projection(self, event: HookExecutionEvent) -> ToolProjection:
        title_suffix = event.hook_name or event.command
        summary_lines = [
            f"Event: {event.event_id}",
            f"Command: {event.command}",
        ]
        if event.tool_name:
            summary_lines.append(f"Tool: {event.tool_name}")
        if event.tool_filters:
            summary_lines.append(f"Filters: {', '.join(event.tool_filters)}")
        if event.raw_output:
            summary_lines.extend(["", event.raw_output[:4000]])
        content = (ToolContentText(text="\n".join(summary_lines)),)
        return ToolProjection(
            tool_call_id=f"hook-{event.sequence_id}",
            title=f"Hook {title_suffix}",
            kind="execute",
            raw_input={
                "event": event.event_id,
                "command": event.command,
                "name": event.hook_name,
                "tool_name": event.tool_name,
                "tools": list(event.tool_filters),
            },
            raw_output=event.raw_output,
            content=content,
            status="completed" if event.status == "completed" else "failed",
        )
