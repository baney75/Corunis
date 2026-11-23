"""Drive bin/corunis-mcp over stdio the way Local Studio does: newline-delimited JSON-RPC 2.0."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from corunis_evals import REPO

SERVER = REPO / "bin" / "corunis-mcp"


class ServerError(Exception):
    pass


class Client:
    """One corunis-mcp process. `caller` is LOCAL_STUDIO_CALLER; None leaves it unset."""

    def __init__(self, home: Path, brain: Path | None = None, caller: str | None = None,
                 extra_env: dict[str, str] | None = None) -> None:
        env = {k: v for k, v in os.environ.items()
               if k not in ("CORUNIS_BRAIN", "CORUNIS_SESSION", "LOCAL_STUDIO_CALLER")}
        env["CORUNIS_HOME"] = str(home)
        if brain is not None:
            env["CORUNIS_BRAIN"] = str(brain)
        if caller is not None:
            env["LOCAL_STUDIO_CALLER"] = caller
        env.update(extra_env or {})
        self.process = subprocess.Popen(
            [sys.executable, str(SERVER)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, env=env,
        )
        self.next_id = 0
        self.request("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                    "clientInfo": {"name": "corunis-evals", "version": "0"}})
        self.send({"jsonrpc": "2.0", "method": "notifications/initialized"})

    def send(self, message: dict) -> None:
        self.process.stdin.write(json.dumps(message).encode() + b"\n")
        self.process.stdin.flush()

    def request(self, method: str, params: dict | None = None) -> dict:
        self.next_id += 1
        self.send({"jsonrpc": "2.0", "id": self.next_id, "method": method, "params": params or {}})
        line = self.process.stdout.readline()
        if not line:
            raise ServerError(f"corunis-mcp closed; stderr:\n{self.process.stderr.read().decode(errors='replace')}")
        reply = json.loads(line)
        if reply.get("id") != self.next_id or "error" in reply:
            raise ServerError(f"bad reply to {method}: {reply}")
        return reply["result"]

    def tools(self) -> list[dict]:
        return self.request("tools/list")["tools"]

    def call(self, name: str, arguments: dict, meta: dict | None = None) -> dict:
        """The raw tools/call result: content, isError and structuredContent."""
        params: dict = {"name": name, "arguments": arguments}
        if meta is not None:
            params["_meta"] = meta
        return self.request("tools/call", params)

    def tool(self, name: str, arguments: dict) -> dict:
        result = self.call(name, arguments)
        if result.get("isError"):
            raise ServerError(result["content"][0]["text"])
        return result["structuredContent"]

    def close(self) -> None:
        if self.process.poll() is None:
            self.process.stdin.close()
            try:
                self.process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                self.process.kill()
        for stream in (self.process.stdout, self.process.stderr):
            stream.close()

    def __enter__(self) -> "Client":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
