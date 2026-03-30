# Approvals

The current approval system is intentionally narrow and explicit.

## What is implemented

Today, approvals are enforced for:

- `write_file`

That is the only tool family with a real approval gate in the current runtime.

## Scope

Approval decisions are session-scoped.

This means:

- a saved approval applies only to the current session
- opening a new session starts from a clean approval state
- old approvals can be imported manually from another session

## Storage

Rules are saved in:

```text
.vcode/sessions/<session-id>/approvals.json
```

## Manual commands

Supported commands:

- `/approvals`
- `/approve write <path>`
- `/deny write <path>`
- `/update-preferences <session-id>`

## ACP approval flow

When a write is not already approved, the ACP adapter sends a permission request with:

- title
- tool kind
- file location
- raw input
- diff content

This lets ACP clients render a meaningful approval dialog instead of a blind allow/deny prompt.

## Write diff behavior

For write approvals, vCode compares:

- the current file contents, if the file exists
- the proposed new contents

That diff is sent through ACP as structured diff content.

## YOLO behavior

There is a `yolo_default` preference in `preferences.json`.

Current meaning:

- if enabled, write approval checks are bypassed

This is intentionally off by default.

## Current limitation

Approvals are not yet wired into:

- terminal commands
- network access
- browser automation
- MCP tools
