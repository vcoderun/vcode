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

### `mcp.json`

This file is also loadable, including environment variable interpolation for fields such as:

- `command`
- `args`
- `url`
- `env`

The current runtime does not yet instantiate MCP servers from it.

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
