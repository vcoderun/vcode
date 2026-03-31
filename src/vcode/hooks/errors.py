from __future__ import annotations as _annotations

from dataclasses import dataclass

__all__ = ("HookCommandError", "HookCommandTimeoutError")


@dataclass(slots=True, kw_only=True)
class HookCommandError(RuntimeError):
    event_id: str
    command: str
    returncode: int
    stderr: str = ""

    def __post_init__(self) -> None:
        detail = f"Hook command failed for {self.event_id}: {self.command} (exit {self.returncode})"
        if self.stderr:
            detail = f"{detail}\n{self.stderr}"
        RuntimeError.__init__(self, detail)


@dataclass(slots=True, kw_only=True)
class HookCommandTimeoutError(TimeoutError):
    event_id: str
    command: str
    timeout_seconds: float

    def __post_init__(self) -> None:
        TimeoutError.__init__(
            self,
            f"Hook command timed out for {self.event_id}: {self.command} after {self.timeout_seconds}s",
        )
