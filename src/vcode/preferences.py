from __future__ import annotations as _annotations

from dataclasses import replace
from pathlib import Path
from typing import get_args

from acp.schema import ModelInfo, SessionModelState
from pydantic_ai.models import KnownModelName

from vcode.config import WorkspacePreferences, load_preferences, save_preferences

__all__ = (
    "WorkspacePreferences",
    "active_model_for_mode",
    "build_model_state",
    "load_preferences",
    "save_preferences",
    "set_default_model",
    "set_mode_model",
    "supported_model_ids",
)


def _raw_known_model_ids() -> tuple[str, ...]:
    return tuple(get_args(KnownModelName.__value__))


def supported_model_ids() -> tuple[str, ...]:
    return tuple(sorted(_raw_known_model_ids()))


def active_model_for_mode(cwd: Path, mode_id: str) -> str | None:
    preferences = load_preferences(cwd.resolve())
    return preferences.mode_models.get(mode_id, preferences.default_model)


def set_default_model(cwd: Path, model_id: str) -> WorkspacePreferences:
    workspace = cwd.resolve()
    preferences = load_preferences(workspace)
    updated_preferences = replace(preferences, default_model=model_id.strip())
    save_preferences(workspace, updated_preferences)
    return updated_preferences


def set_mode_model(cwd: Path, mode_id: str, model_id: str) -> WorkspacePreferences:
    workspace = cwd.resolve()
    preferences = load_preferences(workspace)
    updated_mode_models = dict(preferences.mode_models)
    updated_mode_models[mode_id] = model_id.strip()
    updated_preferences = replace(preferences, mode_models=updated_mode_models)
    save_preferences(workspace, updated_preferences)
    return updated_preferences


def build_model_state(cwd: Path, mode_id: str) -> SessionModelState:
    current_model_id = active_model_for_mode(cwd, mode_id) or ""
    supported = supported_model_ids()
    model_ids = list(supported)
    if current_model_id and current_model_id not in model_ids:
        model_ids.append(current_model_id)
    return SessionModelState(
        current_model_id=current_model_id,
        available_models=[
            ModelInfo(
                model_id=model_id,
                name=model_id,
                description=(
                    "pydantic-ai supported model." if model_id in supported else "Custom model."
                ),
            )
            for model_id in model_ids
        ],
    )
