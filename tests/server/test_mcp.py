"""The stdio protocol: JSON-RPC 2.0 lines in, replies out, notifications unanswered."""

from __future__ import annotations

import io
import json

from corunis_mcp import __version__
from corunis_mcp.server import PROTOCOLS, serve
from corunis_mcp.tools import TOOLS


def run(session, *messages) -> list[dict]:
    lines = b"".join((m if isinstance(m, bytes) else json.dumps(m).encode()) + b"\n" for m in messages)
    out = io.BytesIO()
    serve(session, io.BytesIO(lines), out)
    return [json.loads(line) for line in out.getvalue().splitlines()]


def request(n, method, params=None):
    message = {"jsonrpc": "2.0", "id": n, "method": method}
    if params is not None:
        message["params"] = params
    return message


def test_handshake_list_and_call(parish):
    replies = run(
        parish.session,
        request(1, "initialize", {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "t", "version": "0"}}),
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        request(2, "tools/list"),
        request(3, "tools/call", {"name": "search", "arguments": {"question": "What time is the Saturday vigil Mass?"}}),
        request(4, "ping"),
    )
    assert [r["id"] for r in replies] == [1, 2, 3, 4]
    init = replies[0]["result"]
    assert init["protocolVersion"] == "2025-03-26" and init["serverInfo"] == {"name": "corunis", "version": __version__}
    assert [t["name"] for t in replies[1]["result"]["tools"]] == [t["name"] for t in TOOLS]
    for tool in replies[1]["result"]["tools"]:
        assert tool["inputSchema"]["type"] == "object" and tool["description"]
    result = replies[2]["result"]
    assert result["structuredContent"]["answerable"] is True
    assert json.loads(result["content"][0]["text"]) == result["structuredContent"]
    assert replies[3]["result"] == {}


def test_unknown_protocol_gets_the_newest(parish):
    reply = run(parish.session, request(1, "initialize", {"protocolVersion": "1999-01-01"}))[0]
    assert reply["result"]["protocolVersion"] == PROTOCOLS[0]


def test_errors(parish):
    replies = run(
        parish.session,
        b"{not json",
        request(1, "nope"),
        {"jsonrpc": "1.0", "id": 2, "method": "ping"},
        request(3, "tools/call", {"arguments": {}}),
        request(4, "tools/call", {"name": "open", "arguments": {"passage_id": "p0", "extra": 1}}),
        request(5, "tools/call", {"name": "delete_everything", "arguments": {}}),
    )
    codes = [r.get("error", {}).get("code") for r in replies]
    assert codes == [-32700, -32601, -32600, -32602, None, None]
    assert replies[4]["result"]["isError"] and "Bad arguments" in replies[4]["result"]["content"][0]["text"]
    assert replies[5]["result"]["isError"] and "Unknown tool" in replies[5]["result"]["content"][0]["text"]


def test_refusal_is_a_tool_error_not_a_crash(parish):
    replies = run(
        parish.session,
        request(1, "tools/call", {"name": "search", "arguments": {"question": "payroll"}, "_meta": {"caller": {"member": "keeper"}}}),
        request(2, "ping"),
    )
    assert replies[0]["result"]["isError"] and "only the keeper" in replies[0]["result"]["content"][0]["text"]
    assert replies[1]["result"] == {}
