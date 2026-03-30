# Getting Started

This page documents the current working way to run vCode.

## Requirements

- Python 3.11+
- the project installed in an environment with:
  - `agent-client-protocol`
  - `pydantic-ai`

## Install

Preferred local install:

```bash
uv pip install -e .
```

`pip` fallback:

```bash
pip install -e .
```

If you want docs support too:

```bash
uv pip install -e .[docs]
```

`pip` fallback:

```bash
pip install -e .[docs]
```

## Run the ACP server

vCode currently exposes a single runtime mode: ACP over stdio.

```bash
vcode
```

or explicitly:

```bash
vcode acp
```

Internally this calls `run_agent(VCodeAcpAgent())`.

## First-run local state

vCode writes project-local state under `.vcode/`.

Important files and directories:

- `.vcode/preferences.json`
- `.vcode/.vcodeignore`
- `.vcode/sessions/<session-id>/session.json`
- `.vcode/sessions/<session-id>/history.jsonl`
- `.vcode/sessions/<session-id>/messages.json`
- `.vcode/sessions/<session-id>/approvals.json`

## Select a model

The agent needs a configured model before a normal prompt turn can run.

Supported models come from `pydantic_ai.models.KnownModelName`.

Commands:

- `/models`
- `/models groq`
- `/model`
- `/model groq:openai/gpt-oss-120b`
- `/model ask openai:gpt-5-mini`
- `/model plan anthropic:claude-sonnet-4-5`

When you set a model, vCode writes it to `.vcode/preferences.json`.

## Current ACP clients

The current implementation is built for ACP clients such as:

- terminal/TUI ACP clients
- editor ACP clients such as Zed

Behavior can differ slightly by client, especially around:

- command autocomplete
- model picker UI
- permission dialog rendering
- diff rendering
