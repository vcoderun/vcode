# Current Limitations

This page is intentionally blunt. It lists what the current implementation does not do yet.

## Tooling gaps

Not implemented as first-class tools yet:

- terminal execution
- text search
- regex search
- web search
- scraping
- browser automation

## Quality loop gaps

Not implemented yet:

- `pytest` as a tool
- `ruff` as a tool
- `mypy` or `pyright` as a tool
- automatic repair loops around lint or test failures

## Config gaps

These surfaces still exist, but are not yet full runtime bootstrap surfaces:

- `agents.json`

`mcp.yml` / `mcp.json` is active and builds native MCP capabilities, but still has current limits:

- approval policy is not yet wired into MCP tool calls
- collision strategy still relies on explicit prefixes when needed
- there is no richer agent-level MCP orchestration yet

`hooks.yml` / `hooks.json` is active for command hooks, but still limited:

- no approval layer for hook commands yet
- no richer hook action types beyond command execution

## Approval gaps

Approval enforcement currently applies only to file writes.

Missing:

- command approvals
- network approvals
- browser approvals
- tool family policy matching

## Ignore semantics

`.vcode/.vcodeignore` is useful now, but still limited.

Not implemented:

- negation patterns with `!`
- full gitignore parity
- ignore-aware search tooling

## Advanced agent features

Explicitly not part of the current bare skeleton:

- subagents
- deep agent orchestration
- CodeMode
- recursive language model loops
- durable multi-agent workflows
