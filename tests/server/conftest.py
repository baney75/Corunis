from __future__ import annotations

import inspect
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "server"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from corunis_mcp import identity  # noqa: E402
from corunis_mcp.tools import Session  # noqa: E402
from parish import write_parish  # noqa: E402


class Client:
    """Calls tools the way the MCP server does, through Session.call, so identity runs every time.

    client.tool_search("question", as_role="member") is session.call("search", {...}).
    """

    def __init__(self, session: Session) -> None:
        self.session = session

    def call(self, name: str, args: dict | None = None, meta: dict | None = None) -> dict:
        return self.session.call(name, args or {}, meta)

    def __getattr__(self, name: str):
        if not name.startswith("tool_"):
            return getattr(self.session, name)
        signature = inspect.signature(getattr(self.session, name))

        def run(*args, **kwargs):
            return self.session.call(name[5:], dict(signature.bind(*args, **kwargs).arguments))

        return run


@pytest.fixture(autouse=True)
def on_host(monkeypatch):
    """Every test runs as the keeper's host session with Remote off, unless it patches this again."""
    monkeypatch.setattr(identity, "remote_serving", lambda: False)
    monkeypatch.delenv("CORUNIS_SESSION", raising=False)


@pytest.fixture
def parish(tmp_path: Path):
    """An ingested parish brain; yields a Client on its open Session."""
    root = write_parish(tmp_path / "home" / "St. Brigid Parish")
    session = Session(home=tmp_path / "home", brain_path=root)
    client = Client(session)
    client.tool_ingest()
    yield client
    session.close()


@pytest.fixture
def make_session(tmp_path: Path):
    """Build extra brains: make_session(name, leave_out=set()) returns an ingested Client."""
    sessions = []

    def make(name: str, leave_out: set[str] = frozenset()) -> Client:
        root = write_parish(tmp_path / name / "St. Brigid Parish", set(leave_out))
        session = Session(home=tmp_path / name, brain_path=root)
        sessions.append(session)
        client = Client(session)
        client.tool_ingest()
        return client

    yield make
    for session in sessions:
        session.close()
