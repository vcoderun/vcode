from __future__ import annotations as _annotations

from pathlib import Path

from pydantic_ai.capabilities import MCP, PrefixTools, PrepareTools, Toolset

from vcode.caps import build_runtime_caps


class TestRuntimeCaps:
    def test_runtime_caps_include_filesystem_caps(self, tmp_path: Path) -> None:
        caps = build_runtime_caps(tmp_path)

        assert any(isinstance(cap, Toolset) for cap in caps)
        assert any(isinstance(cap, PrepareTools) for cap in caps)

    def test_runtime_caps_include_mcp_cap_for_streamable_http(self, tmp_path: Path) -> None:
        vcode_dir = tmp_path / ".vcode"
        vcode_dir.mkdir(parents=True)
        (vcode_dir / "mcp.yml").write_text(
            "\n".join(
                [
                    "servers:",
                    "  - name: remote",
                    "    transport: http",
                    "    url: https://example.test/mcp",
                ]
            ),
            encoding="utf-8",
        )

        caps = build_runtime_caps(tmp_path)

        assert any(isinstance(cap, MCP) for cap in caps)

    def test_runtime_caps_prefix_wrapped_mcp_when_prefix_is_set(self, tmp_path: Path) -> None:
        vcode_dir = tmp_path / ".vcode"
        vcode_dir.mkdir(parents=True)
        (vcode_dir / "mcp.yml").write_text(
            "\n".join(
                [
                    "servers:",
                    "  - name: remote",
                    "    transport: sse",
                    "    url: https://example.test/sse",
                    "    prefix: remote",
                ]
            ),
            encoding="utf-8",
        )

        caps = build_runtime_caps(tmp_path)

        assert any(isinstance(cap, PrefixTools) for cap in caps)

    def test_runtime_caps_include_stdio_toolset_cap(self, tmp_path: Path) -> None:
        vcode_dir = tmp_path / ".vcode"
        vcode_dir.mkdir(parents=True)
        (vcode_dir / "mcp.yml").write_text(
            "\n".join(
                [
                    "servers:",
                    "  - name: local",
                    "    transport: stdio",
                    "    command: python3.11",
                    "    args:",
                    "      - server.py",
                ]
            ),
            encoding="utf-8",
        )

        caps = build_runtime_caps(tmp_path)

        toolset_caps = [cap for cap in caps if isinstance(cap, Toolset)]
        assert len(toolset_caps) >= 2
