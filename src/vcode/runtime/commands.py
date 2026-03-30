from __future__ import annotations as _annotations

from dataclasses import dataclass
from pathlib import Path

from vcode.approvals import ApprovalPolicy
from vcode.preferences import (
    active_model_for_mode,
    load_preferences,
    set_default_model,
    set_mode_model,
    supported_model_ids,
)
from vcode.sessions import SessionStore

__all__ = (
    "RuntimeCommandContext",
    "handle_runtime_command",
    "normalize_prompt_text",
    "persist_command_response",
)


@dataclass(frozen=True, slots=True, kw_only=True)
class RuntimeCommandContext:
    workspace: Path
    session_id: str
    mode_id: str
    store: SessionStore
    approval_policy: ApprovalPolicy


def normalize_prompt_text(prompt_text: str) -> str:
    normalized = prompt_text.strip()
    while normalized.startswith("//"):
        normalized = normalized[1:]

    if (
        not any(char.isspace() for char in normalized)
        and len(normalized) >= 6
        and len(normalized) % 2 == 0
    ):
        half = len(normalized) // 2
        if normalized[:half] == normalized[half:]:
            normalized = normalized[:half]

    normalized = normalized.replace("//models", "/models").replace("//model", "/model")

    if normalized.startswith("/models "):
        suffix = normalized.split(None, 1)[1].strip()
        if "/models" in suffix:
            suffix = suffix.split("/models", 1)[0].strip()
        return f"/models {suffix}" if suffix else "/models"

    if normalized.startswith("/model "):
        suffix = normalized.split(None, 1)[1].strip()
        if suffix in {"/model", "model"}:
            return "/model"
        if "/model " in suffix:
            suffix = suffix.split("/model ", 1)[0].strip()
        return f"/model {suffix}" if suffix else "/model"

    return normalized


def handle_runtime_command(
    normalized_prompt: str,
    *,
    context: RuntimeCommandContext,
) -> str | None:
    if normalized_prompt.startswith("/models"):
        _, _, filter_text = normalized_prompt.partition(" ")
        filtered_models = [
            model_id
            for model_id in supported_model_ids()
            if filter_text.strip().lower() in model_id.lower()
        ]
        return "\n".join(filtered_models) if filtered_models else "No supported models matched."

    if normalized_prompt == "/approvals":
        return format_approval_status(
            context.approval_policy, context.workspace, context.session_id
        )

    if normalized_prompt.startswith("/approve "):
        parts = normalized_prompt.split(maxsplit=2)
        if len(parts) != 3 or not parts[2].strip():
            return "Approval command requires a tool and target."
        tool_name = approval_tool_name(parts[1])
        target = parts[2].strip()
        context.approval_policy.set_rule(
            context.workspace,
            context.session_id,
            tool_name,
            target,
            "allow",
        )
        return f"Saved session approval: {tool_name} {target}"

    if normalized_prompt.startswith("/deny "):
        parts = normalized_prompt.split(maxsplit=2)
        if len(parts) != 3 or not parts[2].strip():
            return "Deny command requires a tool and target."
        tool_name = approval_tool_name(parts[1])
        target = parts[2].strip()
        context.approval_policy.set_rule(
            context.workspace,
            context.session_id,
            tool_name,
            target,
            "deny",
        )
        return f"Saved session denial: {tool_name} {target}"

    if normalized_prompt.startswith("/update-preferences "):
        source_session_id = normalized_prompt.split(None, 1)[1].strip()
        imported_count = context.approval_policy.import_rules(
            context.workspace,
            context.session_id,
            source_session_id,
        )
        if imported_count:
            return f"Imported {imported_count} approval rule(s) from session {source_session_id}."
        return f"No approval rules imported from session {source_session_id}."

    if normalized_prompt == "/model":
        return format_model_status(context.workspace, context.mode_id)

    if normalized_prompt.startswith("/model "):
        parts = normalized_prompt.split()
        if len(parts) >= 3 and parts[1] in {"ask", "plan", "agent"}:
            mode_id = parts[1]
            model_id = normalized_prompt.split(None, 2)[2].strip()
            if not model_id:
                return "Model id was empty."
            set_mode_model(context.workspace, mode_id, model_id)
            return f"Model for {mode_id} mode set to {model_id}."

        model_id = normalized_prompt.split(None, 1)[1].strip()
        if not model_id:
            return "Model id was empty."
        set_default_model(context.workspace, model_id)
        return f"Default model set to {model_id}."

    return None


def persist_command_response(
    prompt_text: str,
    response_text: str,
    *,
    context: RuntimeCommandContext,
) -> None:
    context.store.append_message(context.workspace, context.session_id, "user", prompt_text)
    context.store.append_message(context.workspace, context.session_id, "assistant", response_text)


def format_model_status(workspace: Path, mode_id: str) -> str:
    preferences = load_preferences(workspace)
    current_model = active_model_for_mode(workspace, mode_id) or "-"
    default_model = preferences.default_model or "-"
    lines = [
        "Model Configuration",
        "",
        f"{'Active Mode':<13} {mode_id.title()}",
        f"{'Current Model':<13} {current_model}",
        f"{'Default Model':<13} {default_model}",
        "",
        "Mode Assignments",
        f"{'Ask':<13} {preferences.mode_models.get('ask') or default_model}",
        f"{'Plan':<13} {preferences.mode_models.get('plan') or default_model}",
        f"{'Agent':<13} {preferences.mode_models.get('agent') or default_model}",
    ]
    return "\n".join(lines)


def format_approval_status(policy: ApprovalPolicy, workspace: Path, session_id: str) -> str:
    rules = policy.load_rules(workspace, session_id)
    if not rules:
        return "Session Approvals\n\nNo saved approvals."

    lines = ["Session Approvals", ""]
    for rule in rules:
        imported_suffix = (
            f" [from {rule.imported_from_session_id}]"
            if rule.imported_from_session_id is not None
            else ""
        )
        lines.append(f"- {rule.tool_name} {rule.target}: {rule.outcome}{imported_suffix}")
    return "\n".join(lines)


def approval_tool_name(alias: str) -> str:
    normalized = alias.strip().lower()
    if normalized in {"write", "write_file"}:
        return "write_file"
    if normalized in {"read", "read_file"}:
        return "read_file"
    if normalized in {"list", "list_files"}:
        return "list_files"
    return normalized
