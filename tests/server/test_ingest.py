"""Every format ingests, passages have the right size, and re-ingest reads only what changed."""

from __future__ import annotations

import os
import re

import pytest

from corunis_mcp import extract
from corunis_mcp.extract import Unit
from corunis_mcp.passages import MAX_WORDS, MIN_WORDS, split
from parish import FILES, FIXED_TIME


def texts_of(parish, document: str) -> list[str]:
    rows = parish.index.db.execute(
        "SELECT p.text FROM passages p JOIN docs d ON d.id = p.doc_id WHERE d.path = ? ORDER BY p.seq", (document,)
    )
    return [row[0] for row in rows]


def doc_error(parish, document: str):
    return parish.index.db.execute("SELECT error FROM docs WHERE path = ?", (document,)).fetchone()[0]


@pytest.mark.parametrize("document,must,never", [
    ("spaces/everyone/bulletin-2026-10-05.md", ["vigil Mass is at 5:00 pm", "Larkfield Commons"], []),
    ("spaces/everyone/weekday-schedule.html", ["Thursday from 7:00 pm to 8:00 pm & ends", "Holy day vigil"], ["this script text", "color: red"]),
    ("spaces/everyone/volunteer-handbook.docx", ["renewed every two years"], []),
    ("spaces/everyone/announcements.mbox", ["Subject:"], []),
    ("spaces/council/minutes-2026-09.txt", ["Sterling Mechanical for 18,400 dollars"], []),
    ("spaces/council/budget-2027.docx", ["Youth ministry"], []),
    ("spaces/council/roof-bid.eml", ["Ardent Roofing bid 61,250 dollars", "From:"], []),
    ("spaces/staff/leave-request.eml", ["Gideon Farrow"], []),
])
def test_every_format_ingests(parish, document, must, never):
    assert doc_error(parish, document) is None
    text = "\n".join(texts_of(parish, document))
    for phrase in must:
        assert phrase in text, (document, phrase)
    for phrase in never:
        assert phrase not in text, (document, phrase)


def test_mbox_gives_each_message_and_reads_html_bodies(parish):
    text = "\n".join(texts_of(parish, "spaces/everyone/announcements.mbox"))
    assert text.count("Subject:") == 2
    assert "Choir rehearsal" in text and not re.search(r"</?[a-z]+[\s>/]", text)


def test_pdf_ingests_by_page_when_pypdf_is_present(parish):
    document = "spaces/everyone/youth-retreat.pdf"
    if not extract.pdf_available():
        assert "pypdf" in doc_error(parish, document)
        pytest.skip("pypdf is not installed")
    pages = parish.index.db.execute(
        "SELECT p.page, p.text FROM passages p JOIN docs d ON d.id = p.doc_id WHERE d.path = ? ORDER BY p.seq", (document,)
    ).fetchall()
    assert {page for page, _ in pages} == {1, 2}
    assert any("85 dollars per student" in text and page == 2 for page, text in pages)


def test_passage_sizes(parish):
    rows = parish.index.db.execute("SELECT text FROM passages").fetchall()
    assert rows
    assert all(len(text.split()) <= MAX_WORDS for (text,) in rows)
    minutes = texts_of(parish, "spaces/council/minutes-2026-09.txt")
    assert len(minutes) >= 2 and all(len(t.split()) >= MIN_WORDS for t in minutes[:-1])
    long_paragraph = " ".join(f"Sentence {i} has a few more words in it." for i in range(120))
    _, pieces = split([Unit("Short heading.\n\n" + long_paragraph, None)], "x", "v")
    sizes = [len(piece.text.split()) for piece in pieces]
    assert sum(sizes) == 2 + len(long_paragraph.split()) and all(MIN_WORDS <= size <= MAX_WORDS for size in sizes), sizes


def test_unsupported_and_broken_files_are_reported_not_fatal(parish):
    root = parish.brain.root
    (root / "spaces/everyone/photo.jpg").write_bytes(b"\xff\xd8\xff")
    (root / "spaces/everyone/broken.docx").write_bytes(b"not a zip")
    report = parish.tool_ingest()
    assert any(s["file"] == "spaces/everyone/photo.jpg" for s in report["skipped"])
    assert [f["file"] for f in report["failed"]] == ["spaces/everyone/broken.docx"]
    assert report["unchanged"] == len(FILES)


def test_reingest_reads_only_what_changed(parish):
    root = parish.brain.root
    again = parish.tool_ingest()
    assert (again["added"], again["updated"], again["removed"], again["unchanged"]) == (0, 0, 0, len(FILES))

    bulletin = root / "spaces/everyone/bulletin-2026-10-05.md"
    os.utime(bulletin, (FIXED_TIME + 60, FIXED_TIME + 60))  # touched, same bytes
    touched = parish.tool_ingest()
    assert (touched["updated"], touched["unchanged"]) == (0, len(FILES))

    old_ids = {pid for (pid,) in parish.index.db.execute(
        "SELECT p.pid FROM passages p JOIN docs d ON d.id = p.doc_id WHERE d.path = ?", (bulletin.relative_to(root).as_posix(),))}
    bulletin.write_text(bulletin.read_text(encoding="utf-8").replace("5:00 pm", "5:30 pm"), encoding="utf-8")
    edited = parish.tool_ingest()
    assert edited["files"]["updated"] == ["spaces/everyone/bulletin-2026-10-05.md"] and edited["unchanged"] == len(FILES) - 1
    for pid in old_ids:
        assert parish.tool_open(pid)["found"] is False
    assert parish.tool_search("What time is the Saturday vigil Mass?")["passages"][0]["text"].count("5:30 pm") == 1

    (root / "spaces/staff/staff-policy.md").unlink()
    gone = parish.tool_ingest()
    assert gone["files"]["removed"] == ["spaces/staff/staff-policy.md"]
    assert parish.index.doc("spaces/staff/staff-policy.md") is None


def test_ids_are_stable_across_brains(make_session):
    first, second = make_session("one"), make_session("two")
    ids = "SELECT pid FROM passages ORDER BY pid"
    assert first.index.db.execute(ids).fetchall() == second.index.db.execute(ids).fetchall()


def test_ingest_of_one_folder(parish):
    (parish.brain.root / "spaces/council/agenda.txt").write_text("Agenda for the October council meeting.", encoding="utf-8")
    (parish.brain.root / "spaces/staff/roster.txt").write_text("Staff roster for October.", encoding="utf-8")
    report = parish.tool_ingest("spaces/council")
    assert report["files"]["added"] == ["spaces/council/agenda.txt"]
