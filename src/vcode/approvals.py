from __future__ import annotations as _annotations

import json
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Literal

from vcode.config import load_preferences
from vcode.sessions import SessionStore, utc_now

__all__ = (
    "ApprovalPolicy",
    "ApprovalRequest",
    "ApprovalResolution",
    "ApprovalRule",
)

ApprovalOutcome = Literal["allow", "deny", "ask"]
ApprovalToolKind = Literal[
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
ApprovalResolverKind = Literal[
    "allow_once",
    "allow_always",
    "reject_once",
    "reject_always",
    "cancelled",
]
ApprovalResolver = Callable[["ApprovalRequest"], Awaitable["ApprovalResolution"]]


@dataclass(frozen=True, slots=True, kw_only=True)
class ApprovalRule:
    tool_name: str
    target: str
    outcome: ApprovalOutcome
    created_at: str
    source: str = "manual"
    imported_from_session_id: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class ApprovalRequest:
    session_id: str
    workspace_root: Path
    tool_name: str
    target: str
    kind: ApprovalToolKind
    reason: str
    tool_call_id: str
    title: str | None = None
    raw_input: dict[str, object] | None = None
    old_text: str | None = None
    new_text: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class ApprovalResolution:
    kind: ApprovalResolverKind


class ApprovalPolicy:
    def __init__(
        self,
        store: SessionStore | None = None,
        resolver: ApprovalResolver | None = None,
    ) -> None:
        self.store = store or SessionStore()
        self.resolver = resolver

    def approvals_file(self, cwd: Path, session_id: str) -> Path:
        return self.store.session_dir(cwd.resolve(), session_id) / "approvals.json"

    def load_rules(self, cwd: Path, session_id: str) -> list[ApprovalRule]:
        path = self.approvals_file(cwd, session_id)
        if not path.exists():
            return []
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            return []
        rules: list[ApprovalRule] = []
        for raw_rule in payload:
            if not isinstance(raw_rule, dict):
                continue
            tool_name = str(raw_rule.get("tool_name", "")).strip()
            target = str(raw_rule.get("target", "")).strip()
            outcome = _parse_approval_outcome(raw_rule.get("outcome"))
            if not tool_name or not target or outcome is None:
                continue
            rules.append(
                ApprovalRule(
                    tool_name=tool_name,
                    target=target,
                    outcome=outcome,
                    created_at=str(raw_rule.get("created_at", utc_now())),
                    source=str(raw_rule.get("source", "manual")),
                    imported_from_session_id=(
                        str(raw_rule["imported_from_session_id"])
                        if raw_rule.get("imported_from_session_id") is not None
                        else None
                    ),
                )
            )
        return rules

    def save_rules(self, cwd: Path, session_id: str, rules: list[ApprovalRule]) -> None:
        path = self.approvals_file(cwd, session_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps([asdict(rule) for rule in rules], indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def find_rule(
        self, cwd: Path, session_id: str, tool_name: str, target: str
    ) -> ApprovalRule | None:
        for rule in self.load_rules(cwd, session_id):
            if rule.tool_name == tool_name and rule.target == target:
                return rule
        return None

    def set_rule(
        self,
        cwd: Path,
        session_id: str,
        tool_name: str,
        target: str,
        outcome: ApprovalOutcome,
        *,
        source: str = "manual",
        imported_from_session_id: str | None = None,
    ) -> ApprovalRule:
        rules = [
            rule
            for rule in self.load_rules(cwd, session_id)
            if not (rule.tool_name == tool_name and rule.target == target)
        ]
        rule = ApprovalRule(
            tool_name=tool_name,
            target=target,
            outcome=outcome,
            created_at=utc_now(),
            source=source,
            imported_from_session_id=imported_from_session_id,
        )
        rules.append(rule)
        self.save_rules(cwd, session_id, rules)
        return rule

    def import_rules(self, cwd: Path, session_id: str, source_session_id: str) -> int:
        destination_record = self.store.load(cwd, session_id)
        source_record = self.store.load(cwd, source_session_id)
        if destination_record is None or source_record is None:
            return 0

        existing = {
            (rule.tool_name, rule.target): rule for rule in self.load_rules(cwd, session_id)
        }
        merged = list(existing.values())
        imported_count = 0
        for rule in self.load_rules(cwd, source_session_id):
            key = (rule.tool_name, rule.target)
            if key in existing:
                continue
            merged.append(
                ApprovalRule(
                    tool_name=rule.tool_name,
                    target=rule.target,
                    outcome=rule.outcome,
                    created_at=utc_now(),
                    source="imported",
                    imported_from_session_id=source_session_id,
                )
            )
            imported_count += 1
        self.save_rules(cwd, session_id, merged)
        updated_record = replace(
            destination_record,
            imported_approval_session_ids=sorted(
                set(destination_record.imported_approval_session_ids + [source_session_id])
            ),
            updated_at=utc_now(),
        )
        self.store.save(updated_record)
        return imported_count

    async def authorize_write(
        self,
        workspace_root: Path,
        session_id: str,
        target: Path,
        content: str,
    ) -> str | None:
        relative_target = str(target.relative_to(workspace_root))
        if relative_target.split("/")[:2] == [".vcode", "plans"]:
            return None

        preferences = load_preferences(workspace_root)
        if preferences.yolo_default:
            return None

        existing_rule = self.find_rule(workspace_root, session_id, "write_file", relative_target)
        if existing_rule is not None:
            if existing_rule.outcome == "allow":
                return None
            return f"Approval denied for write_file {relative_target}."

        if self.resolver is None:
            return (
                f"Approval required for write_file {relative_target}. "
                f"Run `/approve write {relative_target}` to allow it for this session."
            )

        old_text: str | None = None
        if target.exists() and target.is_file():
            old_text = target.read_text(encoding="utf-8", errors="replace")

        request = ApprovalRequest(
            session_id=session_id,
            workspace_root=workspace_root,
            tool_name="write_file",
            target=relative_target,
            kind="edit",
            reason=f"Write {relative_target}",
            tool_call_id=f"approval-write-{session_id}-{relative_target}",
            title=f"Write {relative_target}",
            raw_input={"path": relative_target, "content": content},
            old_text=old_text,
            new_text=content,
        )
        resolution = await self.resolver(request)
        if resolution.kind == "allow_always":
            self.set_rule(
                workspace_root,
                session_id,
                "write_file",
                relative_target,
                "allow",
                source="approval_prompt",
            )
            return None
        if resolution.kind == "reject_always":
            self.set_rule(
                workspace_root,
                session_id,
                "write_file",
                relative_target,
                "deny",
                source="approval_prompt",
            )
            return f"Approval denied for write_file {relative_target}."
        if resolution.kind == "allow_once":
            return None
        return f"Approval denied for write_file {relative_target}."


def _parse_approval_outcome(value: object) -> ApprovalOutcome | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    if normalized == "allow":
        return "allow"
    if normalized == "deny":
        return "deny"
    if normalized == "ask":
        return "ask"
    return None
