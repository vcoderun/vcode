from __future__ import annotations as _annotations

import json
from pathlib import Path

from vcode.config import (
    AgentSpec,
    HookConfig,
    WorkspacePreferences,
    load_agents_config,
    load_hooks_config,
    load_mcp_config,
    load_preferences,
    local_hooks_file,
    local_mcp_file,
    local_preferences_file,
    mcp_file,
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
        local_mcp_file(tmp_path).write_text(
            "\n".join(
                [
                    "servers:",
                    "  - name: browser",
                    "    transport: http",
                    "    url: ${TEST_MCP_URL}",
                    "    env:",
                    "      TOKEN: ${TEST_MCP_URL}",
                ]
            ),
            encoding="utf-8",
        )

        config = load_mcp_config(tmp_path)

        assert len(config.servers) == 1
        assert config.servers[0].url == "https://example.test/mcp"
        assert config.servers[0].env["TOKEN"] == "https://example.test/mcp"

    def test_load_mcp_config_prefers_yaml_over_json(self, tmp_path: Path) -> None:
        vcode_dir = tmp_path / ".vcode"
        vcode_dir.mkdir(parents=True)
        local_mcp_file(tmp_path).write_text(
            "\n".join(
                [
                    "servers:",
                    "  - name: yaml-server",
                    "    transport: http",
                    "    url: https://yaml.test/mcp",
                ]
            ),
            encoding="utf-8",
        )
        (vcode_dir / "mcp.json").write_text(
            json.dumps(
                {
                    "servers": [
                        {
                            "name": "json-server",
                            "transport": "http",
                            "url": "https://json.test/mcp",
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )

        config = load_mcp_config(tmp_path)

        assert len(config.servers) == 1
        assert config.servers[0].name == "yaml-server"
        assert mcp_file(tmp_path).name == "mcp.yml"

    def test_load_mcp_config_supports_demo_shape(self, tmp_path: Path) -> None:
        vcode_dir = tmp_path / ".vcode"
        vcode_dir.mkdir(parents=True)
        local_mcp_file(tmp_path).write_text(
            "\n".join(
                [
                    "servers:",
                    "  - name: demo-local",
                    "    transport: stdio",
                    "    command: python3.11",
                    "    args:",
                    "      - scripts/demo_mcp_server.py",
                    "    prefix: demo",
                    "  - name: searx-local",
                    "    transport: http",
                    "    url: https://example.test/mcp",
                    "    prefix: searx",
                    "    enabled: false",
                ]
            ),
            encoding="utf-8",
        )

        config = load_mcp_config(tmp_path)

        assert len(config.servers) == 2
        assert config.servers[0].name == "demo-local"
        assert config.servers[0].transport == "stdio"
        assert config.servers[0].prefix == "demo"
        assert config.servers[1].name == "searx-local"
        assert config.servers[1].enabled is False

    def test_load_hooks_config_reads_yaml_events(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setenv("HOOK_TOKEN", "secret-token")
        (tmp_path / ".vcode").mkdir(parents=True)
        local_hooks_file(tmp_path).write_text(
            "\n".join(
                [
                    "events:",
                    "  before_tool_execute:",
                    "    - name: audit-write",
                    "      command: python3.11",
                    "      args:",
                    "        - hooks.py",
                    "        - audit",
                    "      tools:",
                    "        - write_file",
                    "      env:",
                    "        TOKEN: ${HOOK_TOKEN}",
                    "      timeout_seconds: 2.5",
                ]
            ),
            encoding="utf-8",
        )

        config = load_hooks_config(tmp_path)

        assert isinstance(config, HookConfig)
        assert "before_tool_execute" in config.events
        command = config.events["before_tool_execute"][0]
        assert command.name == "audit-write"
        assert command.command == "python3.11"
        assert command.args == ["hooks.py", "audit"]
        assert command.tools == ["write_file"]
        assert command.env["TOKEN"] == "secret-token"
        assert command.timeout_seconds == 2.5

    def test_load_hooks_config_supports_demo_shape(self, tmp_path: Path) -> None:
        (tmp_path / ".vcode").mkdir(parents=True)
        local_hooks_file(tmp_path).write_text(
            "\n".join(
                [
                    "events:",
                    "  before_tool_execute:",
                    "    - name: audit-write",
                    "      command: python3.11",
                    "      args:",
                    "        - scripts/mock_hook_audit.py",
                    "      tools:",
                    "        - write_file",
                    "    - name: audit-demo-mcp",
                    "      command: python3.11",
                    "      args:",
                    "        - scripts/mock_hook_audit.py",
                    "      tools:",
                    "        - demo*",
                    "  after_model_request:",
                    "    - name: snapshot-model-response",
                    "      command: python3.11",
                    "      args:",
                    "        - scripts/mock_hook_snapshot.py",
                ]
            ),
            encoding="utf-8",
        )

        config = load_hooks_config(tmp_path)

        assert sorted(config.events) == ["after_model_request", "before_tool_execute"]
        before_tool_execute = config.events["before_tool_execute"]
        assert [command.name for command in before_tool_execute] == [
            "audit-write",
            "audit-demo-mcp",
        ]
        assert before_tool_execute[1].tools == ["demo*"]
