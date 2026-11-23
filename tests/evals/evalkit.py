"""Build and ingest an eval corpus as a brain, for the tests under tests/evals."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "evals"))

from corunis_evals import brains, questions  # noqa: E402  (puts server/ on the path)
from corunis_mcp.tools import Session  # noqa: E402

KEEPER_CALLER = "local:4242"


class Brain:
    """One group's built and ingested brain, called the way the MCP server calls tools."""

    def __init__(self, group: str, root: Path, home: Path) -> None:
        self.group = group
        self.root = root
        self.home = home
        self.session = Session(home=home, brain_path=root)
        self.roles = brains.roles(group)
        self.questions = questions.load(questions.tuning_path(group))
        self.report = self.call("ingest")

    def call(self, name: str, meta: dict | None = None, **args) -> dict:
        return self.session.call(name, args, meta)

    def passages(self, file: str | None = None, space: str | None = None) -> list[tuple[str, str, str]]:
        """(id, document, text) of every passage in a file or a space."""
        sql = "SELECT p.pid, d.path, p.text FROM passages p JOIN docs d ON d.id = p.doc_id"
        if file is not None:
            return list(self.session.index.db.execute(sql + " WHERE d.path = ? ORDER BY p.seq", (file,)))
        return list(self.session.index.db.execute(sql + " WHERE p.space = ? ORDER BY p.pid", (space,)))

    def resolve(self, locator: dict) -> list[str]:
        quote = questions.normalize(locator["quote"])
        return [pid for pid, _, text in self.passages(locator["file"]) if questions.quote_in(quote, questions.normalize(text))]

    def close(self) -> None:
        self.session.close()


def make(group: str, where: Path) -> Brain:
    pytest.importorskip("pypdf", reason="the corpora have PDFs; install the server's pdf extra")
    root = brains.build(group, where / "home" / group, KEEPER_CALLER)
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("LOCAL_STUDIO_CALLER", KEEPER_CALLER)
        return Brain(group, root, where / "home")
