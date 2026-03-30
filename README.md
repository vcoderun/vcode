# vCode

vCode is an ACP-first local coding agent built on `pydantic-ai`.

The current repository is intentionally focused on a narrow but working skeleton:

- ACP session lifecycle
- local session persistence under `.vcode/`
- `Ask`, `Plan`, and `Agent` modes
- per-session approvals for file writes
- model selection and ACP model/config surfaces
- local workspace tools for list, read, and write

## Quick Start

Requirements:

- Python 3.11+
- `uv` preferred

Local install:

```bash
uv pip install -e .
```

`pip` fallback:

```bash
pip install -e .
```

Run the ACP server:

```bash
vcode acp
```

## Contributor Setup

Development install:

```bash
uv sync --extra dev --extra docs
```

`pip` fallback:

```bash
pip install -e ".[dev,docs]"
```

Common validation commands:

```bash
uv run ruff check
uv run ty check
uv run basedpyright
python3.11 -m pytest
```

## Documentation

The detailed docs live under `docs/`.

Start with:

- `docs/getting-started.md`
- `docs/current-capabilities.md`
- `docs/acp.md`
- `docs/configuration.md`
- `docs/sessions-and-modes.md`
- `docs/approvals.md`
- `docs/workspace-tools.md`
- `docs/limitations.md`

To preview the docs locally:

```bash
uv run mkdocs serve --dev-addr 127.0.0.1:8080
```

## Current Scope

Implemented today:

- ACP server support
- session create/load/resume/fork/list
- mode switching
- model selection
- write approvals with diff previews
- `.vcode/.vcodeignore` filtering for reads and file listing

Not implemented yet:

- terminal tool execution
- workspace search
- web search and scraping
- Python quality tools as runtime tools
- subagents, CodeMode, and RLM workflows
