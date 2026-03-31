from __future__ import annotations as _annotations

from vcode.hooks.adapter import build_hooks_capability
from vcode.hooks.errors import HookCommandError, HookCommandTimeoutError
from vcode.hooks.events import HookEventCollector, HookExecutionEvent

__all__ = (
    "HookEventCollector",
    "HookCommandError",
    "HookCommandTimeoutError",
    "HookExecutionEvent",
    "build_hooks_capability",
)
