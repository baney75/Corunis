"""Loopback-only client for Fonsviva's embedding endpoint (tiers M and L). A stub for now.

This is the only module in the server allowed to import a network library
(tests/server/test_network.py enforces that). It refuses any address that is not the literal
loopback 127.0.0.1 or ::1: no host names, so no DNS lookup and no hosts-file surprise.
Nothing in tier S imports it.

Loopback is not enough: Fonsviva can route a job to a cloud provider. Every call asks for local
hardware only and refuses a reply that does not say the job ran on this host. The header names
below are the ones proposed in baney75/Fonsviva issue #3; change them here when that issue settles.
"""

from __future__ import annotations

import http.client
import json
from urllib.parse import urlsplit

LOOPBACK = {"127.0.0.1", "::1"}
DEFAULT_URL = "http://127.0.0.1:7341/v1/embeddings"
LOCAL_ONLY_HEADER = "Fonsviva-Local-Only"
RAN_ON_HEADER = "Fonsviva-Ran-On"


class NotLoopback(ValueError):
    """The embedding URL points somewhere other than this computer's loopback address."""


class NotLocal(RuntimeError):
    """Fonsviva did not say the job ran on this host, so its result is not used."""


def check(url: str) -> tuple[str, int, str]:
    """(host, port, path) for a loopback http URL; raises NotLoopback for anything else."""
    parts = urlsplit(url)
    if parts.scheme != "http":
        raise NotLoopback(f"Fonsviva embeddings must use http on loopback, not {parts.scheme or 'no scheme'}")
    host = parts.hostname or ""
    if host not in LOOPBACK:
        raise NotLoopback(f"Fonsviva embeddings must be at 127.0.0.1 or ::1, not {host or 'no host'}")
    if parts.username or parts.password:
        raise NotLoopback("Fonsviva embeddings take no user name or password in the URL")
    return host, parts.port or 80, (parts.path or "/") + (f"?{parts.query}" if parts.query else "")


def embed(texts: list[str], model: str, url: str = DEFAULT_URL, timeout: float = 30.0) -> list[list[float]]:
    """Embeddings for texts from an OpenAI-style /v1/embeddings endpoint on loopback."""
    host, port, path = check(url)
    connection = http.client.HTTPConnection(host, port, timeout=timeout)
    try:
        body = json.dumps({"model": model, "input": texts, "placement": "local"})
        headers = {"Content-Type": "application/json", LOCAL_ONLY_HEADER: "1"}
        connection.request("POST", path, body=body, headers=headers)
        response = connection.getresponse()
        payload = response.read()
        ran_on = (response.getheader(RAN_ON_HEADER) or "").strip()
        if response.status != 200:
            raise RuntimeError(f"Fonsviva embeddings answered {response.status}")
    finally:
        connection.close()
    if not ran_on.startswith("local:") and ran_on != "local":
        raise NotLocal(f"Fonsviva did not say the job ran on this host ({RAN_ON_HEADER}: {ran_on or 'missing'})")
    data = sorted(json.loads(payload)["data"], key=lambda item: item["index"])
    return [item["embedding"] for item in data]
