from __future__ import annotations as _annotations

import builtins
import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from shutil import copyfile
from uuid import uuid4

from vcode.modes import DEFAULT_MODE_ID

__all__ = (
    "SessionMessage",
    "SessionRecord",
    "SessionStore",
    "utc_now",
)


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _session_title(text: str) -> str:
    normalized = " ".join(text.split()).strip()
    if not normalized:
        return "New Session"
    if len(normalized) <= 80:
        return normalized
    return f"{normalized[:77]}..."


@dataclass(slots=True, kw_only=True)
class SessionMessage:
    role: str
    content: str
    created_at: str
    message_id: str | None = None


@dataclass(slots=True, kw_only=True)
class SessionRecord:
    session_id: str
    cwd: str
    mode_id: str
    created_at: str
    updated_at: str
    title: str = "New Session"
    imported_approval_session_ids: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> SessionRecord:
        imported_value = data.get("imported_approval_session_ids", [])
        imported_session_ids = (
            [str(session_id) for session_id in imported_value]
            if isinstance(imported_value, list)
            else []
        )
        return cls(
            session_id=str(data["session_id"]),
            cwd=str(data["cwd"]),
            mode_id=str(data["mode_id"]),
            created_at=str(data["created_at"]),
            updated_at=str(data["updated_at"]),
            title=str(data.get("title", "New Session")),
            imported_approval_session_ids=imported_session_ids,
        )


class SessionStore:
    def sessions_dir(self, cwd: Path) -> Path:
        return cwd / ".vcode" / "sessions"

    def session_dir(self, cwd: Path, session_id: str) -> Path:
        return self.sessions_dir(cwd) / session_id

    def session_file(self, cwd: Path, session_id: str) -> Path:
        return self.session_dir(cwd, session_id) / "session.json"

    def history_file(self, cwd: Path, session_id: str) -> Path:
        return self.session_dir(cwd, session_id) / "history.jsonl"

    def messages_file(self, cwd: Path, session_id: str) -> Path:
        return self.session_dir(cwd, session_id) / "messages.json"

    def create(
        self,
        cwd: Path,
        mode_id: str = DEFAULT_MODE_ID,
    ) -> SessionRecord:
        session_id = uuid4().hex
        now = utc_now()
        record = SessionRecord(
            session_id=session_id,
            cwd=str(cwd),
            mode_id=mode_id,
            created_at=now,
            updated_at=now,
        )
        self.save(record)
        self.history_file(cwd, session_id).touch(exist_ok=True)
        return record

    def clone(self, cwd: Path, session_id: str) -> SessionRecord | None:
        record = self.load(cwd, session_id)
        if record is None:
            return None
        cloned = replace(
            self.create(cwd, record.mode_id),
            title=record.title,
            updated_at=utc_now(),
        )
        self.save(cloned)
        source_history = self.history_file(cwd, session_id)
        target_history = self.history_file(cwd, cloned.session_id)
        if source_history.exists():
            copyfile(source_history, target_history)
        source_messages = self.messages_file(cwd, session_id)
        target_messages = self.messages_file(cwd, cloned.session_id)
        if source_messages.exists():
            copyfile(source_messages, target_messages)
        return cloned

    def load(self, cwd: Path, session_id: str) -> SessionRecord | None:
        session_file = self.session_file(cwd, session_id)
        if not session_file.exists():
            return None
        data = json.loads(session_file.read_text(encoding="utf-8"))
        return SessionRecord.from_dict(data)

    def save(self, record: SessionRecord) -> None:
        cwd = Path(record.cwd)
        session_dir = self.session_dir(cwd, record.session_id)
        session_dir.mkdir(parents=True, exist_ok=True)
        self.session_file(cwd, record.session_id).write_text(
            json.dumps(asdict(record), indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def list(self, cwd: Path) -> builtins.list[SessionRecord]:
        sessions_dir = self.sessions_dir(cwd)
        if not sessions_dir.exists():
            return []
        records: list[SessionRecord] = []
        for session_file in sorted(sessions_dir.glob("*/session.json")):
            data = json.loads(session_file.read_text(encoding="utf-8"))
            records.append(SessionRecord.from_dict(data))
        return sorted(records, key=lambda record: record.updated_at, reverse=True)

    def set_mode(self, cwd: Path, session_id: str, mode_id: str) -> SessionRecord | None:
        record = self.load(cwd, session_id)
        if record is None:
            return None
        updated_record = replace(record, mode_id=mode_id, updated_at=utc_now())
        self.save(updated_record)
        return updated_record

    def append_message(
        self,
        cwd: Path,
        session_id: str,
        role: str,
        content: str,
        message_id: str | None = None,
    ) -> SessionRecord | None:
        record = self.load(cwd, session_id)
        if record is None:
            return None

        message = SessionMessage(
            role=role,
            content=content,
            created_at=utc_now(),
            message_id=message_id,
        )
        history_file = self.history_file(cwd, session_id)
        history_file.parent.mkdir(parents=True, exist_ok=True)
        with history_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(message), sort_keys=True))
            handle.write("\n")

        next_title = record.title
        if role == "user" and record.title == "New Session":
            next_title = _session_title(content)
        updated_record = replace(
            record,
            title=next_title,
            updated_at=message.created_at,
        )
        self.save(updated_record)
        return updated_record

    def read_history(self, cwd: Path, session_id: str) -> builtins.list[SessionMessage]:
        history_file = self.history_file(cwd, session_id)
        if not history_file.exists():
            return []
        messages: list[SessionMessage] = []
        for line in history_file.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            payload = json.loads(line)
            messages.append(
                SessionMessage(
                    role=payload["role"],
                    content=payload["content"],
                    created_at=payload["created_at"],
                    message_id=payload.get("message_id"),
                )
            )
        return messages

    def read_model_messages_json(self, cwd: Path, session_id: str) -> bytes | None:
        messages_file = self.messages_file(cwd, session_id)
        if not messages_file.exists():
            return None
        return messages_file.read_bytes()

    def write_model_messages_json(self, cwd: Path, session_id: str, payload: bytes) -> None:
        messages_file = self.messages_file(cwd, session_id)
        messages_file.parent.mkdir(parents=True, exist_ok=True)
        messages_file.write_bytes(payload)
