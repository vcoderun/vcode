from __future__ import annotations as _annotations

from dataclasses import dataclass

from acp.schema import SessionMode, SessionModeState

__all__ = (
    "AGENT_MODE",
    "ASK_MODE",
    "DEFAULT_MODE_ID",
    "MODE_BY_ID",
    "MODE_SPECS",
    "ModeSpec",
    "PLAN_MODE",
    "build_mode_state",
    "get_mode",
)


@dataclass(frozen=True, slots=True, kw_only=True)
class ModeSpec:
    id: str
    name: str
    description: str


ASK_MODE = ModeSpec(
    id="ask",
    name="Ask",
    description="Read workspace and plans without changing files or running commands.",
)
PLAN_MODE = ModeSpec(
    id="plan",
    name="Plan",
    description="Read the workspace and write only under .vcode/plans/.",
)
AGENT_MODE = ModeSpec(
    id="agent",
    name="Agent",
    description="Full agent mode with edits and commands gated by approvals.",
)

MODE_SPECS = (ASK_MODE, PLAN_MODE, AGENT_MODE)
MODE_BY_ID = {mode.id: mode for mode in MODE_SPECS}
DEFAULT_MODE_ID = AGENT_MODE.id


def get_mode(mode_id: str) -> ModeSpec | None:
    return MODE_BY_ID.get(mode_id)


def build_mode_state(current_mode_id: str) -> SessionModeState:
    selected_mode_id = current_mode_id if current_mode_id in MODE_BY_ID else DEFAULT_MODE_ID
    return SessionModeState(
        current_mode_id=selected_mode_id,
        available_modes=[
            SessionMode(id=mode.id, name=mode.name, description=mode.description)
            for mode in MODE_SPECS
        ],
    )
