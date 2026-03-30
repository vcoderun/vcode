# Modes and Sessions

vCode is session-centric.

## Session lifecycle

The ACP adapter currently supports:

- create new session
- load existing session
- resume session
- fork session
- list sessions

Each session gets a UUID-based id and its own directory under `.vcode/sessions/`.

## What a session stores

vCode keeps two forms of history:

- human-readable chat history in `history.jsonl`
- serialized model message state in `messages.json`

This split matters because ACP/UI replay and model continuation are related but not identical.

## Session titles

The first user prompt becomes the session title unless the title is still the default placeholder.

## Mode semantics

### Ask

- can read workspace files
- can read plan files
- cannot write workspace files
- does not currently expose terminal execution

### Plan

- can read the workspace
- can write only under `.vcode/plans/`
- intended for planning artifacts, not code changes

### Agent

- can write the workspace
- still goes through approvals
- is the default mode today

## Mode selection

Mode can be changed through ACP and is persisted in the session record.

Default mode comes from:

- `.vcode/preferences.json`
- fallback: `agent`

## Cross-session preference import

Approval rules are session-scoped by default.

If you want to reuse decisions from an older session, use:

```text
/update-preferences <session-id>
```

Current behavior:

- merge import
- if a rule already exists in the current session, the current session wins
