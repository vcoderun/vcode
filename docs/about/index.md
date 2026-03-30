# About vCode

vCode is being built as a local-first coding agent with ACP as its primary public integration surface.

## Product direction

The near-term goal is not maximum feature count. The goal is a reliable core that most coding agents share:

- ACP-compatible agent runtime
- local workspace read/write loop
- session persistence
- explicit modes
- approval-gated actions
- model selection

Once that base is stable, more advanced features can be layered on top:

- terminal execution
- search and retrieval
- web tooling
- Python quality loops
- subagents
- CodeMode
- recursive language model patterns

## Current engineering bias

vCode is currently optimized for becoming a strong Python coding agent first. That means the architecture is being shaped around:

- strict session state
- explicit approval boundaries
- type-safe Python code
- ACP compatibility from the beginning

## License

The project metadata currently declares an MIT license in `pyproject.toml`.
