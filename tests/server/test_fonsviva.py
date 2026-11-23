"""The Fonsviva client asks for local hardware, refuses a reply that ran elsewhere, and talks only to loopback."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from corunis_mcp import fonsviva


class Fake:
    ran_on: str | None = "local:chapel1"
    seen: list = []


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        Fake.seen.append((dict(self.headers), body))
        payload = json.dumps({"data": [{"index": i, "embedding": [float(i)]} for i in reversed(range(len(body["input"])))]}).encode()
        self.send_response(200)
        if Fake.ran_on is not None:
            self.send_header(fonsviva.RAN_ON_HEADER, Fake.ran_on)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):
        pass


@pytest.fixture
def server():
    httpd = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    Fake.seen = []
    yield f"http://127.0.0.1:{httpd.server_address[1]}/v1/embeddings"
    httpd.shutdown()
    httpd.server_close()


def test_local_reply_is_used_and_local_only_is_asked(server):
    Fake.ran_on = "local:chapel1"
    assert fonsviva.embed(["a", "b"], "nomic", url=server) == [[0.0], [1.0]]
    headers, body = Fake.seen[0]
    assert headers[fonsviva.LOCAL_ONLY_HEADER] == "1" and body["placement"] == "local"


@pytest.mark.parametrize("ran_on", ["cloud:openrouter", None, "", "localhost-proxy:cloud", "remote"])
def test_reply_that_did_not_run_on_the_host_is_refused(server, ran_on):
    """Fonsviva set up with a cloud provider: its answer is never used."""
    Fake.ran_on = ran_on
    with pytest.raises(fonsviva.NotLocal):
        fonsviva.embed(["a"], "nomic", url=server)


@pytest.mark.parametrize("url", [
    "http://localhost:7341/v1/embeddings", "http://10.0.0.5:7341/v1/embeddings", "https://127.0.0.1/v1/embeddings",
    "http://user:pw@127.0.0.1:7341/", "http://api.openai.com/v1/embeddings", "http://127.0.0.1.example.com/",
    "file:///etc/passwd",
])
def test_non_loopback_urls_are_refused_before_any_connection(url):
    with pytest.raises(fonsviva.NotLoopback):
        fonsviva.embed(["a"], "nomic", url=url)
