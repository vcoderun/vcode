from __future__ import annotations as _annotations

from acp import run_agent

from vcode.acp.agent import VCodeAcpAgent

__all__ = ("run_acp_server",)


async def run_acp_server() -> None:
    await run_agent(VCodeAcpAgent())
