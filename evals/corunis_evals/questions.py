"""Question sets and their gold passages.

One JSON object per line in evals/questions/<group>/tuning.jsonl:

    id            unique, such as parish-single-01
    kind          single, multi, unanswerable, restricted, stale or conflicting
    question      in the asker's words
    as_role       the role a restricted question is asked as; null for the keeper
    gold_answer   the right answer; for unanswerable and restricted, the abstention sentence
    gold          locators of the passages a right answer cites: {"file", "quote"}, plus "date"
                  for each source of a conflicting question (both sources are listed)
    acceptable    optional locators a right answer may also cite without losing precision
                  (the older document of a stale question)
    restricted    for a restricted question, where the answer sits: locators in spaces the
                  role cannot read

A locator's quote is a short exact span of the file's text. After ingest the harness resolves
each locator to the passage ids that contain it.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from corunis_evals.brains import QUESTIONS
from corunis_mcp.answer import NO_ANSWER, normalize, quote_in

KINDS = ("single", "multi", "unanswerable", "restricted", "stale", "conflicting")
ANSWERABLE = ("single", "multi", "stale", "conflicting")
ABSTAIN = ("unanswerable", "restricted")
FIELDS = {"id", "kind", "question", "as_role", "gold_answer", "gold", "acceptable", "restricted"}


def tuning_path(group: str) -> Path:
    return QUESTIONS / group / "tuning.jsonl"


def load(path: Path) -> list[dict]:
    questions = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except ValueError as error:
            raise ValueError(f"{path}:{number}: {error}") from None
        unknown = set(item) - FIELDS
        if unknown:
            raise ValueError(f"{path}:{number}: unknown fields {sorted(unknown)}")
        item.setdefault("as_role", None)
        item.setdefault("gold", [])
        item.setdefault("acceptable", [])
        item.setdefault("restricted", [])
        if item["kind"] not in KINDS:
            raise ValueError(f"{path}:{number}: kind {item['kind']!r}")
        if item["kind"] in ABSTAIN and item["gold_answer"] != NO_ANSWER:
            raise ValueError(f"{path}:{number}: an {item['kind']} question's gold answer is the abstention sentence")
        questions.append(item)
    return questions


class Resolver:
    """Find passage ids for locators in an ingested brain's index (read only)."""

    def __init__(self, brain: Path) -> None:
        uri = (brain / ".corunis" / "index.sqlite").resolve().as_uri() + "?mode=ro"
        self.db = sqlite3.connect(uri, uri=True)

    def passages(self, file: str) -> list[tuple[str, str]]:
        return list(self.db.execute(
            "SELECT p.pid, p.text FROM passages p JOIN docs d ON d.id = p.doc_id WHERE d.path = ? ORDER BY p.seq",
            (file,),
        ))

    def resolve(self, locator: dict) -> list[dict]:
        """Every passage of the locator's file that contains its quote, as {"id", "text"}."""
        quote = normalize(locator["quote"])
        return [{"id": pid, "text": text} for pid, text in self.passages(locator["file"])
                if quote_in(quote, normalize(text))]

    def close(self) -> None:
        self.db.close()
