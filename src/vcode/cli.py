from __future__ import annotations as _annotations

import argparse
import asyncio

from vcode.acp.server import run_acp_server

__all__ = ("build_parser", "main")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="vcode")
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("acp", help="Run the ACP agent server")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.command in {None, "acp"}:
        asyncio.run(run_acp_server())
        return
    parser.error(f"Unknown command: {args.command}")
