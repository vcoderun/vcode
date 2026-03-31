# ACP Integration

vCode is designed to be ACP-first from the beginning.

## Runtime shape

The ACP entrypoint is a thin adapter around the local runtime:

- `src/vcode/acp/server.py`
- `src/vcode/acp/agent.py`

The adapter:

- creates sessions
- forwards prompt turns to the runtime
- maps runtime state into ACP updates
- handles permission requests for write approvals

## Session bootstrap

On session creation or load, vCode returns ACP session state that includes:

- modes
- models
- config options

This lets ACP clients render:

- mode pickers
- model pickers
- session state

## Config options

The current ACP config option surface includes:

- `mode`
- `model`

The selected values are synchronized back into local state.

## Tool call updates

Tool activity is emitted through ACP tool updates.

Current mapping:

- `list_files` -> `search`
- `read_file` -> `read`
- `write_file` -> `edit`

Write operations send structured diff content so ACP clients that understand diffs can render them cleanly.

Read and list operations send structured text content previews.

## Permission requests

Write approvals are implemented through `session/request_permission`.

The current permission request includes:

- a title
- structured `raw_input`
- file locations
- diff content for writes

This is especially important for ACP clients such as `toad`, which can render file diffs in approval dialogs.

## Hook and MCP visibility

ACP clients now also receive projections for:

- hook command executions as generic `execute` tool updates
- non-filesystem tools, including MCP-backed tools, as generic execute-style tool updates

This means MCP and hook activity is no longer invisible in ACP sessions, even when the tool family does not map to a specialized ACP kind such as `read` or `edit`.

## Known current limits

The ACP surface is already useful, but still incomplete.

Missing or partial areas:

- terminal capability integration
- filesystem client-backed fallback behavior
- richer session metadata
- search and browser tools
- richer MCP approval and policy routing
