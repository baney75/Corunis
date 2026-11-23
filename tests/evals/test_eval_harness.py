"""run.py and score.py end to end, with a scripted chat endpoint on loopback standing in for the model."""

from __future__ import annotations

import json
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from corunis_mcp.tools import NO_ANSWER
from evalkit import REPO

IDS = ["class-single-01", "class-single-05", "class-restricted-04", "class-unanswerable-01"]


def plain_words(text: str, n: int = 5) -> str:
    return " ".join([w for w in text.split() if not set(w) & set('[]"')][:n])


class Scripted(BaseHTTPRequestHandler):
    """Searches once, then answers from the top passage or abstains. A request with no tools is the judge."""

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        last = body["messages"][-1]
        if not body.get("tools"):
            message = {"role": "assistant", "content": '{"correct": true, "reason": "matches"}'}
        elif last["role"] == "user":
            question = last["content"].split("</skill>", 1)[1].strip()
            call = {"id": "c1", "type": "function",
                    "function": {"name": "search", "arguments": json.dumps({"question": question, "as_role": "keeper"})}}
            message = {"role": "assistant", "content": "", "tool_calls": [call]}
        else:
            result = json.loads(last["content"])
            if result.get("answerable") and result["passages"]:
                top = result["passages"][0]
                quote = plain_words(top["text"])
                content = f'<think>scratch</think>It says {quote} [{top["id"]} "{quote}"].'
            else:
                content = NO_ANSWER
            message = {"role": "assistant", "content": content}
        reply = json.dumps({"choices": [{"message": message}], "usage": {"prompt_tokens": 10, "completion_tokens": 5}}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(reply)))
        self.end_headers()
        self.wfile.write(reply)

    def log_message(self, *args):
        pass


@pytest.fixture
def endpoint():
    server = ThreadingHTTPServer(("127.0.0.1", 0), Scripted)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}/v1"
    server.shutdown()
    server.server_close()


def test_run_then_score(endpoint, tmp_path):
    pytest.importorskip("pypdf")
    out = tmp_path / "run.jsonl"
    subprocess.run([sys.executable, str(REPO / "evals" / "run.py"), "--group", "class", "--base-url", endpoint,
                    "--model", "scripted", "--card", "M", "--out", str(out), "--work", str(tmp_path / "work"),
                    "--ids", *IDS], check=True, timeout=300)
    records = {r["id"]: r for r in map(json.loads, out.read_text(encoding="utf-8").splitlines())}
    assert set(records) == set(IDS)
    for r in records.values():
        assert r["error"] is None and r["turns"] == 2 and r["run"]["documents"] >= 60
        assert "<think>" not in r["answer"]
        search = r["tool_calls"][0]
        assert search["name"] == "search" and search["arguments"].get("as_role") == r["as_role"]
        assert all(g["ids"] and g["texts"] for g in r["gold"] + r["restricted"])
    assert records["class-restricted-04"]["tool_calls"][0]["arguments"]["as_role"] == "coteacher"
    assert records["class-unanswerable-01"]["answer"] == NO_ANSWER

    scores = tmp_path / "scores.json"
    printed = subprocess.run([sys.executable, str(REPO / "evals" / "score.py"), str(out), "--tier", "M",
                              "--judge", "openai", "--judge-base-url", endpoint, "--judge-model", "scripted",
                              "--json", str(scores)], check=True, capture_output=True, text=True, timeout=300).stdout
    result = json.loads(scores.read_text(encoding="utf-8"))
    assert result["leaks"][0] == 0 and result["leaked"] == {}
    assert result["abstains"][1] == "2/2"
    assert result["questions"] == 4 and result["errors"] == 0
    assert result["correct"][1].endswith("/2 judged")
    assert "citation precision" in printed and "vs M" in printed
    assert (tmp_path / "run.judged.jsonl").is_file()


def test_score_counts_a_leak_and_an_abstention(tmp_path):
    record = {
        "id": "class-restricted-04", "kind": "restricted", "question": "q", "as_role": "coteacher",
        "gold_answer": NO_ANSWER, "gold": [], "acceptable": [], "restricted": [],
        "run": {"group": "class", "model": "m", "card": "M"}, "cited": [],
        "answer": "Ezra Malloy has 71 percent.",
        "tool_calls": [{"name": "search", "arguments": {}, "error": False,
                        "result": {"answerable": False, "passages": [], "searched": {"terms": ["71 percent"]}}}],
    }
    quiet = {**record, "id": "class-unanswerable-01", "kind": "unanswerable", "as_role": None, "answer": NO_ANSWER}
    path = tmp_path / "r.jsonl"
    path.write_text(json.dumps(record) + "\n" + json.dumps(quiet) + "\n", encoding="utf-8")
    sys.path.insert(0, str(REPO / "evals"))
    import score

    result = score.score(score.load([path]), None)
    assert result["leaked"] == {"class-restricted-04": ["71 percent"]}  # the echoed search term is not a leak
    assert result["abstains"][1] == "1/2"
