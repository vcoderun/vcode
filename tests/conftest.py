from __future__ import annotations as _annotations

from pathlib import Path


def workspace_root(tmp_path: Path) -> Path:
    root = tmp_path / "workspace"
    root.mkdir()
    return root
