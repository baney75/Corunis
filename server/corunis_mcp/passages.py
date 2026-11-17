"""Split extracted text into passages of about 150 to 300 words on paragraph boundaries."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from corunis_mcp.extract import Unit

MIN_WORDS = 150
MAX_WORDS = 300
# A paragraph longer than MAX_WORDS is cut into pieces of about this many words.
LONG_PIECE = 250

PARAGRAPH_BREAK = re.compile(r"\n[ \t]*\n\s*")
WORD = re.compile(r"\S+")
SENTENCE_END = re.compile(r"[.!?][\"')\]]*$")


@dataclass
class Passage:
    id: str
    page: int | None
    start: int
    end: int
    text: str


def passage_id(path: str, version: str, start: int, end: int) -> str:
    """Stable id: the same file content always gives the same ids; any edit gives new ones."""
    digest = hashlib.sha256(f"{path}\0{version}\0{start}\0{end}".encode()).hexdigest()
    return "p" + digest[:15]


def join_units(units: list[Unit]) -> tuple[str, list[tuple[int, int, int | None]]]:
    """Join units into one document text; returns it and each unit's (start, end, page)."""
    parts: list[str] = []
    spans: list[tuple[int, int, int | None]] = []
    offset = 0
    for unit in units:
        if parts:
            parts.append("\n\n")
            offset += 2
        parts.append(unit.text)
        spans.append((offset, offset + len(unit.text), unit.page))
        offset += len(unit.text)
    return "".join(parts), spans


def paragraphs(text: str, start: int, end: int) -> list[tuple[int, int, int]]:
    """(start, end, words) for each paragraph of text[start:end], trimmed of outer whitespace."""
    found = []
    cursor = start
    for match in PARAGRAPH_BREAK.finditer(text, start, end):
        found.append((cursor, match.start()))
        cursor = match.end()
    found.append((cursor, end))
    result = []
    for s, e in found:
        chunk = text[s:e]
        stripped = chunk.strip()
        if not stripped:
            continue
        s += len(chunk) - len(chunk.lstrip())
        e = s + len(stripped)
        result.append((s, e, len(WORD.findall(stripped))))
    return result


def long_pieces(text: str, start: int, end: int) -> list[tuple[int, int]]:
    """Cut one long paragraph into pieces of about LONG_PIECE words, at a sentence end when one is near."""
    words = [(m.start() + start, m.end() + start, m.group()) for m in WORD.finditer(text[start:end])]
    pieces = []
    i = 0
    while i < len(words):
        stop = min(i + LONG_PIECE, len(words))
        if len(words) - stop < MIN_WORDS // 3:
            stop = len(words)
        else:
            for j in range(stop, max(i + MIN_WORDS, stop - 60), -1):
                if SENTENCE_END.search(words[j - 1][2]):
                    stop = j
                    break
        pieces.append((words[i][0], words[stop - 1][1]))
        i = stop
    return pieces


def split(units: list[Unit], path: str, version: str) -> tuple[str, list[Passage]]:
    text, spans = join_units(units)
    out: list[Passage] = []

    def emit(s: int, e: int, page: int | None) -> None:
        out.append(Passage(passage_id(path, version, s, e), page, s, e, text[s:e]))

    for unit_start, unit_end, page in spans:
        current: tuple[int, int] | None = None
        words = 0
        for s, e, n in paragraphs(text, unit_start, unit_end):
            if n > MAX_WORDS:
                if current:
                    emit(*current, page)
                    current, words = None, 0
                for ps, pe in long_pieces(text, s, e):
                    emit(ps, pe, page)
                continue
            if current and words + n > MAX_WORDS:
                emit(*current, page)
                current, words = None, 0
            current = (current[0], e) if current else (s, e)
            words += n
            if words >= MIN_WORDS:
                emit(*current, page)
                current, words = None, 0
        if current:
            emit(*current, page)
    return text, out
