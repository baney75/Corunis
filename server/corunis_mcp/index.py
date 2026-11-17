"""The SQLite index in .corunis/index.sqlite. It is a cache: delete it and ingest rebuilds it.

Each space has its own FTS5 table. A search reads only the tables of the spaces the caller may
read, so a forbidden passage is never touched, and BM25 statistics (row counts, term counts)
come only from readable passages: adding or removing a forbidden document cannot change a
readable passage's score.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

SCHEMA_VERSION = "1"

SCHEMA = """
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE spaces (id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL);
CREATE TABLE docs (
    id INTEGER PRIMARY KEY,
    path TEXT UNIQUE NOT NULL,
    space TEXT NOT NULL,
    version TEXT NOT NULL,
    mtime_ns INTEGER NOT NULL,
    size INTEGER NOT NULL,
    modified TEXT NOT NULL,
    passages INTEGER NOT NULL,
    error TEXT
);
CREATE TABLE passages (
    rowid INTEGER PRIMARY KEY,
    pid TEXT UNIQUE NOT NULL,
    doc_id INTEGER NOT NULL REFERENCES docs(id),
    space TEXT NOT NULL,
    seq INTEGER NOT NULL,
    page INTEGER,
    start INTEGER NOT NULL,
    end INTEGER NOT NULL,
    text TEXT NOT NULL
);
CREATE INDEX passages_doc ON passages (doc_id, seq);
CREATE INDEX docs_space ON docs (space);
"""


@dataclass
class Hit:
    rowid: int
    id: str
    document: str
    space: str
    page: int | None
    start: int
    end: int
    date: str
    score: float
    text: str


class Index:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.db = self._open()

    def _open(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, isolation_level=None)
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA synchronous=NORMAL")
        version = None
        try:
            row = db.execute("SELECT value FROM meta WHERE key = 'schema'").fetchone()
            version = row[0] if row else None
        except sqlite3.DatabaseError:
            pass
        if version != SCHEMA_VERSION:
            db.close()
            for suffix in ("", "-wal", "-shm"):
                Path(str(self.path) + suffix).unlink(missing_ok=True)
            db = sqlite3.connect(self.path, isolation_level=None)
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("PRAGMA synchronous=NORMAL")
            db.executescript(SCHEMA)
            db.execute("INSERT INTO meta VALUES ('schema', ?)", (SCHEMA_VERSION,))
        return db

    def close(self) -> None:
        self.db.close()

    def fts(self, space: str, create: bool = False) -> str | None:
        row = self.db.execute("SELECT id FROM spaces WHERE name = ?", (space,)).fetchone()
        if row is None:
            if not create:
                return None
            row = (self.db.execute("INSERT INTO spaces (name) VALUES (?)", (space,)).lastrowid,)
            self.db.execute(
                f"CREATE VIRTUAL TABLE fts_{row[0]} USING fts5(text, tokenize='porter unicode61 remove_diacritics 2')"
            )
        return f"fts_{row[0]}"

    def doc(self, path: str) -> sqlite3.Row | None:
        cursor = self.db.execute(
            "SELECT id, path, space, version, mtime_ns, size, modified, passages, error FROM docs WHERE path = ?", (path,)
        )
        return cursor.fetchone()

    def doc_paths(self, prefix: str = "") -> list[str]:
        if not prefix:
            return [r[0] for r in self.db.execute("SELECT path FROM docs")]
        return [r[0] for r in self.db.execute("SELECT path FROM docs WHERE substr(path, 1, ?) = ?", (len(prefix), prefix))]

    def touch(self, path: str, mtime_ns: int, size: int) -> None:
        self.db.execute("UPDATE docs SET mtime_ns = ?, size = ? WHERE path = ?", (mtime_ns, size, path))

    def remove(self, path: str) -> None:
        row = self.db.execute("SELECT id, space FROM docs WHERE path = ?", (path,)).fetchone()
        if row is None:
            return
        doc_id, space = row
        table = self.fts(space)
        if table:
            self.db.execute(f"DELETE FROM {table} WHERE rowid IN (SELECT rowid FROM passages WHERE doc_id = ?)", (doc_id,))
        self.db.execute("DELETE FROM passages WHERE doc_id = ?", (doc_id,))
        self.db.execute("DELETE FROM docs WHERE id = ?", (doc_id,))

    def put(self, path: str, space: str, version: str, mtime_ns: int, size: int, modified: str,
            passages: list, error: str | None = None) -> None:
        """Replace a document and its passages in one transaction."""
        self.db.execute("BEGIN")
        try:
            self.remove(path)
            doc_id = self.db.execute(
                "INSERT INTO docs (path, space, version, mtime_ns, size, modified, passages, error)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (path, space, version, mtime_ns, size, modified, len(passages), error),
            ).lastrowid
            if passages:
                table = self.fts(space, create=True)
                for seq, p in enumerate(passages):
                    rowid = self.db.execute(
                        "INSERT INTO passages (pid, doc_id, space, seq, page, start, end, text)"
                        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (p.id, doc_id, space, seq, p.page, p.start, p.end, p.text),
                    ).lastrowid
                    self.db.execute(f"INSERT INTO {table} (rowid, text) VALUES (?, ?)", (rowid, p.text))
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def search(self, expression: str, spaces: set[str], limit: int) -> list[Hit]:
        """Top passages for an FTS5 expression, read only from the given spaces' tables."""
        hits: list[Hit] = []
        for space in sorted(spaces):
            table = self.fts(space)
            if table is None:
                continue
            rows = self.db.execute(
                f"""
                SELECT p.rowid, p.pid, d.path, p.space, p.page, p.start, p.end, d.modified, -m.rank, p.text
                FROM (SELECT rowid, rank FROM {table} WHERE {table} MATCH ? ORDER BY rank LIMIT ?) AS m
                JOIN passages p ON p.rowid = m.rowid
                JOIN docs d ON d.id = p.doc_id
                WHERE p.space = ?
                """,
                (expression, limit, space),
            )
            hits.extend(Hit(*row) for row in rows)
        hits.sort(key=lambda h: (-h.score, h.id))
        return hits[:limit]

    def coverage(self, space: str, rowids: list[int], terms: list[str]) -> dict[int, int]:
        """For each rowid, how many of the terms (FTS5 phrase strings) its passage contains."""
        counts = dict.fromkeys(rowids, 0)
        table = self.fts(space)
        if table is None or not rowids:
            return counts
        marks = ",".join("?" * len(rowids))
        for term in terms:
            for (rowid,) in self.db.execute(f"SELECT rowid FROM {table} WHERE {table} MATCH ? AND rowid IN ({marks})", (term, *rowids)):
                counts[rowid] += 1
        return counts

    def passage(self, pid: str, spaces: set[str]) -> dict | None:
        """One passage, only if it sits in a space the caller may read; None otherwise."""
        row = self.db.execute(
            "SELECT p.pid, d.path, p.space, p.page, p.start, p.end, d.modified, p.text, p.doc_id, p.seq"
            " FROM passages p JOIN docs d ON d.id = p.doc_id WHERE p.pid = ?",
            (pid,),
        ).fetchone()
        if row is None or row[2] not in spaces:
            return None
        neighbors = {
            seq: pid
            for pid, seq in self.db.execute(
                "SELECT pid, seq FROM passages WHERE doc_id = ? AND seq IN (?, ?)", (row[8], row[9] - 1, row[9] + 1)
            )
        }
        return {
            "id": row[0], "document": row[1], "space": row[2], "page": row[3], "start": row[4], "end": row[5],
            "date": row[6], "text": row[7], "previous": neighbors.get(row[9] - 1), "next": neighbors.get(row[9] + 1),
        }

    def counts(self, spaces: set[str]) -> dict[str, dict[str, int]]:
        result = {space: {"documents": 0, "passages": 0} for space in sorted(spaces)}
        for space, documents, passages in self.db.execute(
            "SELECT space, count(*), coalesce(sum(passages), 0) FROM docs WHERE error IS NULL GROUP BY space"
        ):
            if space in result:
                result[space] = {"documents": documents, "passages": passages}
        return result

    def failures(self) -> list[tuple[str, str]]:
        return list(self.db.execute("SELECT path, error FROM docs WHERE error IS NOT NULL ORDER BY path"))
