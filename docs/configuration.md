# Configuration

vCode currently reads configuration from `.vcode/` and optionally from `~/.vcode/`.

## Precedence

Configuration resolution is file-by-file:

- use `project/.vcode/<file>` if it exists
- otherwise fall back to `~/.vcode/<file>`

This means local project config wins over global config.

## Current files

### `preferences.json`

This is the only config file actively used by the current runtime.

Example:

```json
{
  "default_mode": "agent",
  "default_model": "groq:openai/gpt-oss-120b",
  "mode_models": {
    "ask": "openai:gpt-5-mini",
    "plan": "anthropic:claude-sonnet-4-5"
  },
  "yolo_default": false,
  "history_compaction": "auto",
  "external_docs_lookup": false,
  "skill_discovery": "session_start",
  "web": {
    "search": {
      "provider": "searx",
      "searx_base_url": ""
    },
    "scrape": {
      "provider": "builtin"
    },
    "browser": {
      "provider": "browser-use"
    }
  }
}
```

Important current fields:

- `default_mode`
- `default_model`
- `mode_models`
- `yolo_default`

### `.vcodeignore`

This file is checked by workspace read/list tools.

Current behavior:

- ignored paths do not appear in `list_files`
- ignored files cannot be read by `read_file`

Current implementation supports simple gitignore-like glob patterns, but not full gitignore semantics. In particular, negation patterns beginning with `!` are not active yet.

### `agents.json`

This file is loadable and schema-checked, but not yet actively consumed by the runtime.

Current typed shape:

```json
{
  "python": {
    "model": "openai:gpt-5-mini"
  }
}
```

Only the `model` field is currently validated.

### `mcp.yml`

MCP config is YAML-first.

Resolution order:

- `.vcode/mcp.yml`
- `.vcode/mcp.yaml`
- `.vcode/mcp.json`
- `~/.vcode/mcp.yml`
- `~/.vcode/mcp.yaml`
- `~/.vcode/mcp.json`

JSON remains supported, but `mcp.yml` is the native format.

Environment variable interpolation is supported for fields such as:

- `command`
- `args`
- `url`
- `env`

The current runtime reads this file and builds native `pydantic-ai` MCP capabilities from it.

Example:

```yaml
servers:
  - name: demo-local
    transport: stdio
    command: python3.11
    args:
      - scripts/demo_mcp_server.py
    prefix: demo

  - name: searx-local
    transport: http
    url: ${SEARX_MCP_URL}
    prefix: searx
    enabled: false
```

Tracked local demo server:

- `scripts/demo_mcp_server.py`

### `hooks.yml`

Hooks config is also YAML-first.

Resolution order:

- `.vcode/hooks.yml`
- `.vcode/hooks.yaml`
- `.vcode/hooks.json`
- `~/.vcode/hooks.yml`
- `~/.vcode/hooks.yaml`
- `~/.vcode/hooks.json`

Current scope:

- the file is loadable and typed
- configured commands are bridged into native `pydantic-ai` `Hooks`
- event ids match `pydantic-ai` hook lifecycle names

Example:

```yaml
events:
  before_tool_execute:
    - name: audit-write
      command: python3.11
      args:
        - scripts/mock_hook_audit.py
      tools:
        - write_file

  after_model_request:
    - name: snapshot-model-response
      command: python3.11
      args:
        - scripts/mock_hook_snapshot.py
```

Current behavior:

- commands run with the workspace root as `cwd`
- configured `env` entries are merged into the process environment
- optional `name` gives a stable display label for `/hooks` and ACP hook projections
- optional `tools` filters a hook command to matching tool names or glob patterns
- `VCODE_HOOK_EVENT`
- `VCODE_HOOK_WORKSPACE_ROOT`
- `VCODE_HOOK_SESSION_ID`
- `VCODE_HOOK_MODE_ID`
- `VCODE_HOOK_PAYLOAD_JSON`
  are injected for each hook command

Inspection commands:

- `/hooks` shows the resolved hook configuration for the current workspace
- `/mcp` shows the resolved MCP server configuration for the current workspace

Tracked local demo scripts:

- `scripts/mock_hook_audit.py`
- `scripts/mock_hook_snapshot.py`

## Session storage

Session state lives under:

```text
.vcode/sessions/<session-id>/
```

Per-session files currently include:

- `session.json`
- `history.jsonl`
- `messages.json`
- `approvals.json`
