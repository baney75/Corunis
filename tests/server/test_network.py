"""The server has no network code. Only fonsviva.py may import a network library, and only loopback http."""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SERVER = REPO / "server" / "corunis_mcp"
FORBIDDEN = {
    "socket", "ssl", "urllib", "http", "ftplib", "smtplib", "poplib", "imaplib", "nntplib", "telnetlib",
    "socketserver", "xmlrpc", "asyncio", "selectors", "select", "mailbox", "webbrowser", "requests", "httpx",
    "aiohttp", "websockets", "urllib3", "multiprocessing",
}
ALLOWED = {"fonsviva.py": {"http.client", "urllib.parse"}}


def imports(path: Path) -> set[str]:
    found = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            found |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            found.add(node.module)
        elif isinstance(node, ast.Call) and getattr(node.func, "id", getattr(node.func, "attr", None)) in {"__import__", "import_module"}:
            found.add("<dynamic import>")
    return found


def test_no_server_module_imports_a_network_library():
    files = sorted(SERVER.glob("*.py")) + [REPO / "bin" / "corunis-mcp"]
    assert len(files) > 5
    for path in files:
        for name in imports(path):
            assert name != "<dynamic import>", path
            if name in ALLOWED.get(path.name, set()):
                continue
            assert name.split(".")[0] not in FORBIDDEN, f"{path.name} imports {name}"


def test_nothing_imports_fonsviva_yet():
    for path in SERVER.glob("*.py"):
        if path.name != "fonsviva.py":
            assert not any("fonsviva" in name for name in imports(path)), path


def test_no_socket_is_opened_while_serving(tmp_path):
    """Run the real server through ingest, search, open and verify with an audit hook that aborts on any socket use."""
    script = textwrap.dedent(f"""
        import io, json, os, sys
        def hook(event, args):
            if event.startswith(("socket.", "ssl.")) or event in ("urllib.Request", "http.client.connect"):
                os.write(2, ("NETWORK " + event + "\\n").encode()); os._exit(97)
        sys.addaudithook(hook)
        sys.path[:0] = [{str(REPO / "server")!r}, {str(Path(__file__).parent)!r}]
        from parish import write_parish
        from corunis_mcp.server import serve
        from corunis_mcp.tools import Session
        root = write_parish(__import__("pathlib").Path({str(tmp_path)!r}) / "St. Brigid Parish")
        session = Session(home=root.parent, brain_path=root)
        def call(n, name, args):
            return json.dumps({{"jsonrpc": "2.0", "id": n, "method": "tools/call", "params": {{"name": name, "arguments": args}}}})
        lines = [call(1, "ingest", {{}}), call(2, "search", {{"question": "Who will replace the boiler?"}})]
        out = io.BytesIO(); serve(session, io.BytesIO(("\\n".join(lines) + "\\n").encode()), out)
        replies = [json.loads(l) for l in out.getvalue().splitlines()]
        pid = replies[1]["result"]["structuredContent"]["passages"][0]["id"]
        more = [call(3, "open", {{"passage_id": pid}}), call(4, "verify", {{"answer": "x [" + pid + ' \\"Sterling Mechanical\\"].'}}), call(5, "status", {{}})]
        out = io.BytesIO(); serve(session, io.BytesIO(("\\n".join(more) + "\\n").encode()), out)
        replies += [json.loads(l) for l in out.getvalue().splitlines()]
        print(json.dumps([r["result"].get("isError", False) for r in replies]))
    """)
    env = {k: v for k, v in os.environ.items() if k != "CORUNIS_SESSION"}
    done = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=120, env=env)
    assert done.returncode == 0, done.stderr
    assert json.loads(done.stdout.strip().splitlines()[-1]) == [False] * 5

    probe = script.split("sys.addaudithook(hook)")[0] + "sys.addaudithook(hook)\nimport socket\nsocket.socket()\n"
    caught = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True, timeout=60, env=env)
    assert caught.returncode == 97 and "NETWORK socket" in caught.stderr  # the hook does catch a socket
