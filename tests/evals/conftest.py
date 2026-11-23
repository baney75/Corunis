from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from evalkit import KEEPER_CALLER, Brain, make  # noqa: E402


@pytest.fixture(autouse=True)
def on_host(monkeypatch):
    """Every call runs as the keeper's Local Studio session, as the harness does."""
    monkeypatch.setenv("LOCAL_STUDIO_CALLER", KEEPER_CALLER)
    monkeypatch.delenv("CORUNIS_SESSION", raising=False)
    monkeypatch.delenv("CORUNIS_BRAIN", raising=False)


@pytest.fixture(scope="session")
def pristine(tmp_path_factory):
    """pristine(group): a shared ingested brain for tests that only read."""
    made: dict[str, Brain] = {}

    def get(group: str) -> Brain:
        if group not in made:
            made[group] = make(group, tmp_path_factory.mktemp(group))
        return made[group]

    yield get
    for brain in made.values():
        brain.close()


@pytest.fixture
def fresh(tmp_path):
    """fresh(group): a brain of its own, for tests that move, link or add files."""
    made: list[Brain] = []

    def get(group: str) -> Brain:
        made.append(make(group, tmp_path / str(len(made))))
        return made[-1]

    yield get
    for brain in made:
        brain.close()
