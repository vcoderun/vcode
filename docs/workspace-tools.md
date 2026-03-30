# Workspace Tools

The current local runtime exposes a minimal workspace toolset.

## Implemented tools

- `list_files(path=".")`
- `read_file(path)`
- `write_file(path, content)`

These are normal agent tools used by the `pydantic-ai` loop.

## `list_files`

Behavior:

- lists files recursively
- skips `__pycache__`
- hides paths ignored by `.vcode/.vcodeignore`
- returns a simple newline-delimited listing

In ACP, `list_files` is projected as a `search`-kind tool call with text content preview.

## `read_file`

Behavior:

- reads a text file from the workspace
- truncates long files
- rejects ignored paths from `.vcode/.vcodeignore`

In ACP, `read_file` is projected as a `read`-kind tool call with file location and text preview.

## `write_file`

Behavior:

- resolves the path inside the workspace root
- checks mode rules
- checks the approval policy
- writes the file if allowed

Mode interaction:

- `Ask`: blocked
- `Plan`: only `.vcode/plans/**`
- `Agent`: allowed, but still approval-gated

In ACP, `write_file` is projected as an `edit`-kind tool call with structured diff content.

## `.vcode/.vcodeignore`

Current ignore behavior is scoped to workspace reading and listing.

Examples:

```text
secret.txt
private/
*.secret
```

Current guarantees:

- ignored files do not appear in `list_files`
- ignored files are rejected by `read_file`

Current non-goal:

- full gitignore compatibility

## Current limitation

There is no dedicated text search tool yet.

Planned future additions include:

- regex/text search
- terminal execution
- web search and scrape tools
