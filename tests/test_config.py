from __future__ import annotations as _annotations

import json
from pathlib import Path

from vcode.config import (
    AgentSpec,
    WorkspacePreferences,
    load_agents_config,
    load_mcp_config,
    load_preferences,
    local_preferences_file,
    resolve_config_path,
    save_preferences,
)


class TestConfig:
    def test_preferences_fall_back_to_global_when_project_missing(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        fake_home = tmp_path / "home"
        monkeypatch.setenv("HOME", str(fake_home))
        global_vcode = fake_home / ".vcode"
        global_vcode.mkdir(parents=True)
        (global_vcode / "preferences.json").write_text(
            json.dumps({"default_mode": "plan", "default_model": "openai:gpt-5-mini"}),
            encoding="utf-8",
        )

        preferences = load_preferences(tmp_path / "workspace")

        assert preferences.default_mode == "plan"
        assert preferences.default_model == "openai:gpt-5-mini"
        assert resolve_config_path(tmp_path / "workspace", "preferences.json") == (
            global_vcode / "preferences.json"
        )

    def test_save_preferences_writes_local_file(self, tmp_path: Path) -> None:
        preferences = WorkspacePreferences(default_model="test:model")

        save_preferences(tmp_path, preferences)

        saved_path = local_preferences_file(tmp_path)
        assert saved_path.exists()
        payload = json.loads(saved_path.read_text(encoding="utf-8"))
        assert payload["default_model"] == "test:model"

    def test_load_agents_config_reads_named_mapping(self, tmp_path: Path) -> None:
        vcode_dir = tmp_path / ".vcode"
        vcode_dir.mkdir(parents=True)
        (vcode_dir / "agents.json").write_text(
            json.dumps(
                {
                    "python": {"model": "openai:gpt-5-mini"},
                    "ignored": "not-a-spec",
                }
            ),
            encoding="utf-8",
        )

        agents = load_agents_config(tmp_path)

        assert agents == {"python": AgentSpec(model="openai:gpt-5-mini")}

    def test_load_mcp_config_interpolates_env(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setenv("TEST_MCP_URL", "https://example.test/mcp")
        vcode_dir = tmp_path / ".vcode"
        vcode_dir.mkdir(parents=True)
        (vcode_dir / "mcp.json").write_text(
            json.dumps(
                {
                    "servers": [
                        {
                            "name": "browser",
                            "transport": "http",
                            "url": "${TEST_MCP_URL}",
                            "env": {"TOKEN": "${TEST_MCP_URL}"},
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )

        config = load_mcp_config(tmp_path)

        assert len(config.servers) == 1
        assert config.servers[0].url == "https://example.test/mcp"
        assert config.servers[0].env["TOKEN"] == "https://example.test/mcp"
