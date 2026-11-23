"""The eval corpora and tuning questions are what the evals section of SPEC.md asks for."""

from __future__ import annotations

from collections import Counter

import pytest

from corunis_evals import brains, leaks, questions
from corunis_mcp import extract

GROUPS = brains.GROUPS


def source_texts(group: str) -> dict[str, str]:
    return {rel: brains.text_of(path) for rel, path in brains.sources(group).items()}


@pytest.mark.parametrize("group", GROUPS)
def test_corpus_size_and_types(group):
    docs = brains.sources(group)
    assert 60 <= len(docs) <= 80, len(docs)
    suffixes = Counter("." + rel.rsplit(".", 1)[1] for rel in docs)
    assert set(suffixes) <= extract.SUPPORTED, suffixes
    assert {".md", ".txt", ".html", ".docx", ".pdf", ".eml"} <= set(suffixes), suffixes
    for rel, text in source_texts(group).items():
        if rel.endswith(".pdf"):
            assert text.isascii(), rel


@pytest.mark.parametrize("group", GROUPS)
def test_brain_template_has_a_restricted_space(group):
    roles = brains.roles(group)
    assert roles and "everyone" in set.union(*roles.values())
    spaces = brains.roles_spaces(group)
    assert any(space not in readable for space in spaces for readable in roles.values())
    for space in brains.corpus(group)["restricted"]:
        assert any(space not in readable for readable in roles.values()), f"every role reads {space}"
    assert brains.PLACEHOLDER in (brains.corpus_dir(group) / "brain.toml.in").read_text(encoding="utf-8")


@pytest.mark.parametrize("group", GROUPS)
def test_questions_cover_every_kind(group):
    items = questions.load(questions.tuning_path(group))
    assert Counter(q["kind"] for q in items) == {kind: 8 for kind in questions.KINDS}
    assert len({q["id"] for q in items}) == len(items) == 48
    roles = brains.roles(group)
    docs = brains.sources(group)
    for q in items:
        assert q["id"].startswith(f"{group}-{q['kind']}-"), q["id"]
        for locator in q["gold"] + q["acceptable"] + q["restricted"]:
            assert locator["file"] in docs, (q["id"], locator)
        if q["kind"] in questions.ANSWERABLE:
            assert q["gold"] and q["as_role"] is None, q["id"]
        if q["kind"] == "conflicting":
            assert len({g["file"] for g in q["gold"]}) >= 2 and all("date" in g for g in q["gold"]), q["id"]
        if q["kind"] == "stale":
            assert len(q["gold"]) == 1, q["id"]
        if q["kind"] == "unanswerable":
            assert not q["gold"] and not q["restricted"], q["id"]
        if q["kind"] == "restricted":
            assert q["as_role"] in roles and q["restricted"] and not q["gold"], q["id"]
            for locator in q["restricted"]:
                assert leaks.space_of(locator["file"]) not in roles[q["as_role"]], q["id"]


@pytest.mark.parametrize("group", GROUPS)
def test_restricted_strings_stay_in_their_space(group):
    texts = source_texts(group)
    asked = [f"{q['question']} {q['gold_answer']}" for q in questions.load(questions.tuning_path(group))
             if q["kind"] == "restricted"]
    for space, strings in leaks.restricted(group).items():
        for string in strings:
            homes = {leaks.space_of(rel) for rel, text in texts.items() if string.casefold() in text.casefold()
                     or string.casefold() in rel.casefold()}
            assert homes == {space}, (string, homes)
            assert not any(string.casefold() in a.casefold() for a in asked), string
    for q in questions.load(questions.tuning_path(group)):
        assert not leaks.find(leaks.hidden_from(group, set()), q["question"]), q["id"]


@pytest.mark.parametrize("group", GROUPS)
def test_every_locator_is_one_passage_after_ingest(pristine, group):
    brain = pristine(group)
    assert brain.report["failed"] == [] and brain.report["skipped"] == [], brain.report
    assert brain.report["added"] == len(brains.sources(group))
    for q in brain.questions:
        for locator in q["gold"] + q["acceptable"] + q["restricted"]:
            assert len(brain.resolve(locator)) == 1, (q["id"], locator)


@pytest.mark.parametrize("group", GROUPS)
def test_passage_dates_follow_the_file_names(pristine, group):
    brain = pristine(group)
    default = brains.corpus(group)["default_date"]
    rows = brain.session.index.db.execute("SELECT path, modified FROM docs")
    for path, modified in rows:
        year, month, day = brains.date_of(path.rsplit("/", 1)[1], default)
        assert modified.startswith(f"{year:04d}-{month:02d}-{day:02d}"), (path, modified)


@pytest.mark.parametrize("group", GROUPS)
def test_every_stale_answer_is_newer_than_what_it_replaced(pristine, group):
    brain = pristine(group)
    modified = dict(brain.session.index.db.execute("SELECT path, modified FROM docs"))
    stale = [q for q in brain.questions if q["kind"] == "stale"]
    assert stale
    for q in stale:
        for gold in q["gold"]:
            for old in q["acceptable"]:
                assert modified[gold["file"]] > modified[old["file"]], (q["id"], gold["file"], old["file"])


def test_a_name_with_only_a_year_dates_to_that_year():
    assert brains.date_of("sitter-pay-2025.txt", "2026-03-01") == (2025, 1, 1)
    assert brains.date_of("sitter-rate-2026-01-15.eml", "2026-03-01") == (2026, 1, 15)
    assert brains.date_of("biscuit-care.md", "2026-03-01") == (2026, 3, 1)
    assert brains.date_of("service-menu-2026.html", "2026-04-01") == (2026, 4, 1)


def test_a_leak_string_ending_in_a_number_matches_that_number_only():
    assert leaks.find(["$18"], "The fee is $180.") == []
    assert leaks.find(["$18"], "It came to $18,500 in all.") == []
    assert leaks.find(["$18"], "The fee is $18.") == ["$18"]
    assert leaks.find(["Ezra Malloy"], "ezra malloyson") == ["Ezra Malloy"]  # names still match as before
