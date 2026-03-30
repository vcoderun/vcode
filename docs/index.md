# vCode

vCode is an ACP-first local coding agent built on top of `pydantic-ai`.

The current codebase is intentionally narrow: it focuses on a solid skeleton for local coding sessions before adding more advanced agent patterns. The implemented surface today is centered around:

- ACP server support
- session-backed chat state
- `Ask`, `Plan`, and `Agent` modes
- model selection and persistence
- session-scoped write approvals
- local workspace tools for list, read, and write
- `.vcode/.vcodeignore` filtering for read and list operations

## What vCode can do today

- Run as an ACP agent server over stdio
- Create, resume, fork, and list sessions
- Persist session history under `.vcode/sessions/<session-id>/`
- Read and write local workspace files through tools
- Ask for write approvals with file-aware diff previews
- Store the selected default model in `.vcode/preferences.json`
- Let each mode inherit the default model or override it per mode

## What is not finished yet

These items are planned, but not part of the current working skeleton:

- terminal command execution as a real tool
- workspace text search
- built-in web search and scraping
- Python quality loop (`pytest`, `ruff`, `mypy`/`pyright`) as first-class tools
- subagents, CodeMode, RLM, and multi-agent orchestration
- full MCP runtime integration from `mcp.json`

## Documentation map

- `Getting Started`: how to install and run the ACP server
- `Current Capabilities`: a feature-by-feature inventory
- `ACP Integration`: current ACP methods, updates, and client behavior
- `Configuration`: `.vcode` files and precedence rules
- `Modes and Sessions`: mode semantics and session persistence
- `Approvals`: current approval model and commands
- `Workspace Tools`: read/list/write behavior, diffs, and `.vcodeignore`
