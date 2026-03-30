from __future__ import annotations as _annotations

from pathlib import Path

from vcode.sessions import SessionRecord, SessionStore


def _require_session_record(record: SessionRecord | None) -> SessionRecord:
    assert record is not None, "expected the session store to return a record"
    return record


class TestSessionStore:
    def test_create_append_and_list(self, tmp_path: Path) -> None:
        store = SessionStore()
        session = store.create(tmp_path)

        store.append_message(tmp_path, session.session_id, "user", "first prompt")
        store.append_message(tmp_path, session.session_id, "assistant", "first reply")

        loaded = _require_session_record(store.load(tmp_path, session.session_id))
        history = store.read_history(tmp_path, session.session_id)
        listed = store.list(tmp_path)

        assert loaded.title == "first prompt"
        assert len(history) == 2
        assert listed[0].session_id == session.session_id

    def test_clone_copies_history(self, tmp_path: Path) -> None:
        store = SessionStore()
        session = store.create(tmp_path)
        store.append_message(tmp_path, session.session_id, "user", "hello")
        store.write_model_messages_json(tmp_path, session.session_id, b"[]")

        cloned = _require_session_record(store.clone(tmp_path, session.session_id))

        assert cloned.session_id != session.session_id
        assert len(store.read_history(tmp_path, cloned.session_id)) == 1
        assert store.read_model_messages_json(tmp_path, cloned.session_id) == b"[]"
