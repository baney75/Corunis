"""MCP over stdio: newline-delimited JSON-RPC 2.0 on stdin and stdout. No sockets, ever.

Handles initialize, ping, tools/list, tools/call and notifications. Logs go to stderr.
"""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from pathlib import Path

from corunis_mcp import __version__
from corunis_mcp.brain import BrainError
from corunis_mcp.tools import TOOLS, Session

PROTOCOLS = ("2025-06-18", "2025-03-26", "2024-11-05")
INSTRUCTIONS = (
    "Corunis answers only from this group's documents. Call search, answer only with claims that carry a passage id"
    " and an exact short quote, call verify, and drop failed claims. If nothing survives, say: The documents I can see"
    " don't answer this."
)

PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602


def log(message: str) -> None:
    print(f"corunis-mcp: {message}", file=sys.stderr, flush=True)


class Server:
    def __init__(self, session: Session) -> None:
        self.session = session

    def handle(self, message: object) -> dict | list | None:
        if isinstance(message, list):
            replies = [r for r in (self.handle(m) for m in message) if r is not None]
            return replies or None
        if not isinstance(message, dict) or message.get("jsonrpc") != "2.0" or not isinstance(message.get("method"), str):
            if isinstance(message, dict) and "id" in message and "method" not in message:
                return None  # a reply to a request we never send
            return error(message.get("id") if isinstance(message, dict) else None, INVALID_REQUEST, "Invalid request")
        method = message["method"]
        params = message.get("params") or {}
        if "id" not in message:
            return None  # notifications: initialized, cancelled and the rest need no reply
        request_id = message["id"]
        if method == "initialize":
            asked = params.get("protocolVersion") if isinstance(params, dict) else None
            return reply(request_id, {
                "protocolVersion": asked if asked in PROTOCOLS else PROTOCOLS[0],
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "corunis", "version": __version__},
                "instructions": INSTRUCTIONS,
            })
        if method == "ping":
            return reply(request_id, {})
        if method == "tools/list":
            return reply(request_id, {"tools": TOOLS})
        if method == "tools/call":
            if not isinstance(params, dict) or not isinstance(params.get("name"), str):
                return error(request_id, INVALID_PARAMS, "tools/call needs a tool name")
            arguments = params.get("arguments") or {}
            if not isinstance(arguments, dict):
                return error(request_id, INVALID_PARAMS, "arguments must be an object")
            return reply(request_id, self.call(params["name"], arguments))
        return error(request_id, METHOD_NOT_FOUND, f"Method not found: {method}")

    def call(self, name: str, arguments: dict) -> dict:
        try:
            result = self.session.call(name, arguments)
        except BrainError as problem:
            return {"content": [{"type": "text", "text": str(problem)}], "isError": True}
        except TypeError as problem:
            return {"content": [{"type": "text", "text": f"Bad arguments for {name}: {problem}"}], "isError": True}
        except Exception as problem:  # noqa: BLE001 - report, keep serving
            log(traceback.format_exc())
            return {"content": [{"type": "text", "text": f"{name} failed: {type(problem).__name__}"}], "isError": True}
        return {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}], "structuredContent": result}


def reply(request_id: object, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def error(request_id: object, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def serve(session: Session, stdin=None, stdout=None) -> None:
    stdin = stdin or sys.stdin.buffer
    stdout = stdout or sys.stdout.buffer
    server = Server(session)
    for raw in stdin:
        line = raw.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except ValueError:
            response: object = error(None, PARSE_ERROR, "Parse error")
        else:
            response = server.handle(message)
        if response is not None:
            stdout.write(json.dumps(response, ensure_ascii=False).encode("utf-8") + b"\n")
            stdout.flush()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="corunis-mcp", description="Corunis brain MCP server over stdio")
    parser.add_argument("--home", help="Folder that holds brains (default: CORUNIS_HOME or ~/Corunis)")
    parser.add_argument("--brain", help="Brain folder to open at start (default: CORUNIS_BRAIN or the last one opened)")
    parser.add_argument("--version", action="version", version=__version__)
    args = parser.parse_args(argv)
    session = Session(
        home=Path(args.home).expanduser() if args.home else None,
        brain_path=Path(args.brain).expanduser() if args.brain else None,
    )
    try:
        serve(session)
    except KeyboardInterrupt:
        pass
    finally:
        session.close()
    return 0
