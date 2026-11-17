"""MCP smoke: start bin/corunis-mcp the way Local Studio does and drive it over stdio.

Runs initialize, tools/list, brain_new, ingest, search, open and verify against a throwaway
brain in a temporary folder, and prints one ok line per step.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXPECTED_TOOLS = {"search", "open", "verify", "remember", "ingest", "status", "brain_new", "brain_open",
                  "role_add", "role_grant", "role_revoke", "member_set"}


class Client:
    def __init__(self, home: Path) -> None:
        env = {k: v for k, v in os.environ.items() if k not in ("CORUNIS_BRAIN", "CORUNIS_SESSION")}
        env["CORUNIS_HOME"] = str(home)
        self.process = subprocess.Popen(
            [sys.executable, str(ROOT / "bin" / "corunis-mcp")],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env,
        )
        self.next_id = 0

    def send(self, message: dict) -> None:
        self.process.stdin.write(json.dumps(message).encode() + b"\n")
        self.process.stdin.flush()

    def request(self, method: str, params: dict | None = None) -> dict:
        self.next_id += 1
        self.send({"jsonrpc": "2.0", "id": self.next_id, "method": method, "params": params or {}})
        line = self.process.stdout.readline()
        if not line:
            raise SystemExit(f"FAIL server closed; stderr:\n{self.process.stderr.read().decode()}")
        reply = json.loads(line)
        assert reply.get("id") == self.next_id, reply
        assert "error" not in reply, reply
        return reply["result"]

    def tool(self, name: str, arguments: dict) -> dict:
        result = self.request("tools/call", {"name": name, "arguments": arguments})
        assert not result.get("isError"), result["content"][0]["text"]
        return result["structuredContent"]

    def close(self) -> int:
        self.process.stdin.close()
        return self.process.wait(timeout=30)


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        client = Client(Path(tmp))
        init = client.request("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                             "clientInfo": {"name": "corunis-smoke", "version": "0"}})
        assert init["serverInfo"]["name"] == "corunis", init
        client.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        print(f"ok   initialize: {init['serverInfo']['name']} {init['serverInfo']['version']}, protocol {init['protocolVersion']}")

        names = {tool["name"] for tool in client.request("tools/list")["tools"]}
        assert names == EXPECTED_TOOLS, names ^ EXPECTED_TOOLS
        print(f"ok   tools/list: {len(names)} tools")

        made = client.tool("brain_new", {"name": "Smoke Test Club"})
        space = Path(made["path"]) / "spaces" / "everyone"
        (space / "schedule.md").write_text(
            "# Club schedule\n\nThe smoke test club meets every Wednesday at 6:30 pm in the library annex.\n",
            encoding="utf-8",
        )
        report = client.tool("ingest", {})
        assert report["added"] == 1, report
        print(f"ok   brain_new and ingest: {report['added']} file added")

        found = client.tool("search", {"question": "When does the club meet?"})
        assert found["answerable"] and found["passages"], found
        passage = found["passages"][0]
        print(f"ok   search: answerable, top passage {passage['id']} in {passage['document']}")

        opened = client.tool("open", {"passage_id": passage["id"]})
        assert opened["found"] and "Wednesday" in opened["passage"]["text"], opened
        missing = client.tool("open", {"passage_id": "p" + "0" * 15})
        assert missing["found"] is False, missing
        print("ok   open: the passage, and the not-found reply for an unknown id")

        pid = passage["id"]
        checked = client.tool("verify", {"answer": (
            f'The club meets every Wednesday at 6:30 pm [{pid} "meets every Wednesday at 6:30 pm"]. '
            f'It meets on Fridays too [{pid} "meets every Friday"].'
        )})
        assert len(checked["kept"]) == 1 and len(checked["dropped"]) == 1, checked
        print("ok   verify: kept the supported sentence, dropped the fabricated one")

        unanswerable = client.tool("search", {"question": "Who won the chess tournament?"})
        assert unanswerable["answerable"] is False and unanswerable["passages"] == [], unanswerable
        print("ok   search: an unanswerable question says so")

        code = client.close()
        assert code == 0, code
        print("ok   server exited cleanly")
    return 0


if __name__ == "__main__":
    sys.exit(main())
