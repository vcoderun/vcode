# Current Capabilities

This page lists what the current codebase actually implements.

## ACP runtime

Implemented ACP-facing behavior:

- `initialize`
- `authenticate`
- `new_session`
- `fork_session`
- `load_session`
- `resume_session`
- `list_sessions`
- `prompt`
- `set_session_mode`
- `set_session_model`
- `set_config_option`

The ACP adapter also emits:

- available commands updates
- current mode updates
- config option updates
- tool call start/progress updates
- permission requests for write approvals

## Session model

Sessions are first-class and stored on disk.

Each session currently persists:

- session id
- workspace path
- active mode
- title
- human-readable chat history
- serialized model message history
- imported approval source sessions

## Modes

Three modes exist:

- `Ask`: read-only
- `Plan`: read workspace, write only under `.vcode/plans/`
- `Agent`: full edit mode, still gated by approvals

Mode state is represented both in the runtime and through ACP mode/config surfaces.

## Model management

vCode currently supports:

- listing known model ids from `pydantic-ai`
- selecting a default model
- selecting per-mode model overrides
- exposing model state to ACP clients

Current storage:

- `.vcode/preferences.json`

## Workspace tools

Implemented local tools:

- `list_files`
- `read_file`
- `write_file`

Current behavior:

- reads are plain text reads
- writes are mode-gated
- writes require approval unless already allowed for the session
- `.vcode/.vcodeignore` hides matching files from read/list

## Approval system

Implemented today:

- session-scoped write approvals
- manual allow/deny commands
- importing approval preferences from another session
- ACP permission prompts with diff previews for writes

Not implemented yet:

- terminal approvals
- network approvals
- browser approvals
- multi-tool approval policies

## Slash commands

Currently handled in the runtime:

- `/models`
- `/model`
- `/model <model-id>`
- `/model <ask|plan|agent> <model-id>`
- `/approvals`
- `/approve <tool> <target>`
- `/deny <tool> <target>`
- `/update-preferences <session-id>`

## Test coverage

The repository currently has tests for:

- session behavior
- ACP adapter behavior
- config loading
- approval persistence
- model command flows
- workspace read/write flows
- `.vcodeignore` read/list filtering
