from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "server"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from corunis_mcp.tools import Session  # noqa: E402
from parish import write_parish  # noqa: E402


@pytest.fixture
def parish(tmp_path: Path):
    """An ingested parish brain; yields its open Session."""
    root = write_parish(tmp_path / "home" / "St. Brigid Parish")
    session = Session(home=tmp_path / "home", brain_path=root)
    session.tool_ingest()
    yield session
    session.close()


@pytest.fixture
def make_session(tmp_path: Path):
    """Build extra brains: make_session(name, leave_out=set()) returns an ingested Session."""
    sessions = []

    def make(name: str, leave_out: set[str] = frozenset()) -> Session:
        root = write_parish(tmp_path / name / "St. Brigid Parish", set(leave_out))
        session = Session(home=tmp_path / name, brain_path=root)
        session.tool_ingest()
        sessions.append(session)
        return session

    yield make
    for session in sessions:
        session.close()
