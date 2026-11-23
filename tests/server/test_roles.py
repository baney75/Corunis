"""Leak tests: a role never sees, and is never told about, anything in a space it cannot read."""

from __future__ import annotations

import json
import os
import re
import shutil

import pytest

from corunis_mcp import brain as brainlib
from corunis_mcp import identity, tools
from corunis_mcp.tools import NO_ANSWER, NOT_FOUND
from parish import FILES, FIXED_TIME, RESTRICTED, ROLES, SPACES, UNANSWERABLE

PAIRS = [(role, space) for role in sorted(ROLES) for space in SPACES]
FAKE_ID = "p" + "0" * 15


def cite(sentence: str, pid: str, quote: str) -> str:
    return f'{sentence} [{pid} "{quote}"].'


def passages_in(session, space):
    rows = session.index.db.execute("SELECT pid, text FROM passages WHERE space = ? ORDER BY pid", (space,))
    return list(rows)


def probe_queries(text: str) -> list[str]:
    """Questions built from a passage's own words: its first words, and its rarest-looking words."""
    words = re.findall(r"[A-Za-z0-9]+", text)
    capitals = [w for w in words if w[0].isupper() or w[0].isdigit()]
    return [" ".join(words[:12]), " ".join(capitals[:10]) or " ".join(words[-8:])]


def test_every_role_and_space_pair_is_covered(parish):
    assert {space for _, space in PAIRS} == set(SPACES)
    assert {role for role, _ in PAIRS} == set(ROLES)
    assert len(PAIRS) == len(ROLES) * len(SPACES) == 9
    for space in SPACES:
        assert passages_in(parish, space), f"the parish has no passages in {space}"


@pytest.mark.parametrize("role,space", PAIRS)
def test_search_open_verify_respect_roles(parish, role, space):
    readable = space in ROLES[role]
    for pid, text in passages_in(parish, space):
        quote = " ".join(text.split()[:6])
        seen_here = False
        for question in probe_queries(text):
            result = parish.tool_search(question, k=20, include_weak=True, as_role=role)
            spaces = {p["document"].split("/")[1] for p in result["passages"]}
            assert spaces <= set(ROLES[role]), (role, question, spaces)
            assert set(result["searched"]["spaces"]) == set(ROLES[role])
            seen_here |= pid in {p["id"] for p in result["passages"]}
        opened = parish.tool_open(pid, as_role=role)
        checked = parish.tool_verify(cite("This is stated", pid, quote), as_role=role)
        if readable:
            assert seen_here, f"{role} could not find its own passage {pid} in {space}"
            assert opened["found"] is True and opened["passage"]["id"] == pid
            assert len(checked["kept"]) == 1, checked
        else:
            assert not seen_here
            assert opened == parish.tool_open(FAKE_ID, as_role=role) == {"found": False, "message": NOT_FOUND}
            fake = parish.tool_verify(cite("This is stated", FAKE_ID, quote), as_role=role)
            assert checked["kept"] == fake["kept"] == []
            assert checked["answer"] == fake["answer"] == NO_ANSWER
            assert checked["dropped"][0]["reason"] == fake["dropped"][0]["reason"] == NOT_FOUND


def test_ids_are_opaque_hashes(parish):
    ids = [row[0] for row in parish.index.db.execute("SELECT pid FROM passages")]
    assert ids and all(re.fullmatch(r"p[0-9a-f]{15}", pid) for pid in ids)
    assert len(set(ids)) == len(ids)
    assert not any(pid[1:].isdigit() for pid in ids)


def strip(result: dict) -> dict:
    """A search reply without the parts that echo the question itself."""
    return {**result, "searched": {k: v for k, v in result["searched"].items() if k != "terms"}}


@pytest.mark.parametrize("space,questions", sorted(RESTRICTED.items()))
def test_restricted_reply_equals_the_reply_when_the_document_does_not_exist(make_session, space, questions):
    with_docs = make_session("with")
    without = make_session("without", leave_out={rel for rel in FILES if rel.split("/")[1] == space})
    roles = [role for role, spaces in ROLES.items() if space not in spaces]
    assert roles
    for role in roles:
        for question in questions:
            for weak in (False, True):
                a = with_docs.tool_search(question, include_weak=weak, as_role=role)
                b = without.tool_search(question, include_weak=weak, as_role=role)
                assert a == b, (role, question)
            assert with_docs.tool_status(as_role=role) == without.tool_status(as_role=role)


@pytest.mark.parametrize("space,questions", sorted(RESTRICTED.items()))
def test_restricted_question_gets_the_unanswerable_reply(parish, space, questions):
    for role in (r for r, spaces in ROLES.items() if space not in spaces):
        expected = strip(parish.tool_search(UNANSWERABLE[0], as_role=role))
        assert expected["answerable"] is False and expected["passages"] == [] and expected["say"] == NO_ANSWER
        for question in questions:
            assert strip(parish.tool_search(question, as_role=role)) == expected, (role, question)


def test_restricted_note_is_never_served(parish):
    saved = parish.tool_remember("The new alarm code for the rectory is 4417, starting Monday.", space="staff")
    assert saved["saved"].startswith("spaces/staff/notes/")
    found = parish.tool_search("rectory alarm code", as_role="staff")
    assert found["answerable"] and found["passages"][0]["document"] == saved["saved"]
    pid = found["passages"][0]["id"]
    for role in ("member", "council"):
        result = parish.tool_search("rectory alarm code", k=20, include_weak=True, as_role=role)
        assert all("/staff/" not in p["document"] for p in result["passages"])
        assert result["answerable"] is False
        assert parish.tool_open(pid, as_role=role) == parish.tool_open(FAKE_ID, as_role=role)
        check = parish.tool_verify(cite("There is an alarm code", pid, "alarm code for the rectory"), as_role=role)
        assert check["kept"] == [] and check["dropped"][0]["reason"] == NOT_FOUND


def test_note_default_is_the_narrowest_space(parish):
    # The keeper reads every space. council and staff are each read by one role; only Ada Hollis
    # (council) reaches council, nobody reaches staff, so staff is narrowest.
    saved = parish.tool_remember("Order more votive candles before Advent.")
    assert saved["space"] == "staff" and saved["saved"].startswith("spaces/staff/notes/")
    text = (parish.brain.root / saved["saved"]).read_text(encoding="utf-8")
    assert "author: keeper" in text and re.search(r"date: \d{4}-\d\d-\d\dT", text)
    assert not (parish.brain.root / "notes").exists()


def move(parish, rel: str, space: str) -> str:
    source = parish.brain.root / rel
    target = parish.brain.root / "spaces" / space / source.name
    shutil.move(source, target)
    os.utime(target, (FIXED_TIME + 60, FIXED_TIME + 60))
    return target.relative_to(parish.brain.root).as_posix()


def test_file_just_moved_into_a_restricted_space_is_never_served(parish):
    question = "What time is the Saturday vigil Mass?"
    before = parish.tool_search(question, as_role="member")
    assert before["answerable"] and before["passages"][0]["document"].endswith("bulletin-2026-10-05.md")
    pid = before["passages"][0]["id"]
    move(parish, "spaces/everyone/bulletin-2026-10-05.md", "staff")
    after = parish.tool_search(question, k=20, include_weak=True, as_role="member")
    assert all("bulletin" not in p["document"] for p in after["passages"])
    assert parish.tool_open(pid, as_role="member") == {"found": False, "message": NOT_FOUND}
    assert parish.tool_verify(cite("Mass is on Saturday", pid, "Saturday vigil Mass"), as_role="member")["kept"] == []
    staff = parish.tool_search(question, as_role="staff")
    assert staff["passages"][0]["document"] == "spaces/staff/bulletin-2026-10-05.md"


def test_query_time_path_check_holds_without_the_reindex(parish, monkeypatch):
    """Even if the index were stale, search checks each result's current path before serving it."""
    question = "What time is the Saturday vigil Mass?"
    pid = parish.tool_search(question, as_role="member")["passages"][0]["id"]
    monkeypatch.setattr(tools, "sync", lambda brain, index: None)
    move(parish, "spaces/everyone/bulletin-2026-10-05.md", "staff")
    assert parish.index.doc("spaces/everyone/bulletin-2026-10-05.md") is not None  # stale entry still there
    after = parish.tool_search(question, k=20, include_weak=True, as_role="member")
    assert all("bulletin" not in p["document"] for p in after["passages"])
    assert parish.tool_open(pid, as_role="member") == {"found": False, "message": NOT_FOUND}
    assert parish.tool_verify(cite("Mass is on Saturday", pid, "Saturday vigil Mass"), as_role="member")["kept"] == []


def test_role_change_in_brain_toml_applies_at_the_next_call(parish):
    question = "What did Ardent Roofing bid for the church roof?"
    assert parish.tool_search(question, as_role="council")["answerable"]
    parish.tool_role_revoke("council", "council")
    result = parish.tool_search(question, k=20, include_weak=True, as_role="council")
    assert all("/council/" not in p["document"] for p in result["passages"])


ALL_TOOLS = [tool["name"] for tool in tools.TOOLS]
REFUSE_WAYS = ["remote_serving", "meta_caller_claims_keeper", "meta_remote", "env", "check_fails"]


@pytest.mark.parametrize("way", REFUSE_WAYS)
def test_non_keeper_caller_is_refused_by_every_tool(parish, monkeypatch, way):
    meta = None
    if way == "remote_serving":
        monkeypatch.setattr(identity, "remote_serving", lambda: True)
    elif way == "meta_caller_claims_keeper":
        meta = {"caller": {"member": "keeper", "origin": "host"}}  # a claim is not trusted until the core signs it
    elif way == "meta_remote":
        meta = {"remote": True}
    elif way == "env":
        monkeypatch.setenv("CORUNIS_SESSION", "remote")
    else:
        monkeypatch.undo()
        monkeypatch.delenv("CORUNIS_SESSION", raising=False)

        def broken():
            raise OSError("no process list")

        monkeypatch.setattr(identity, "process_commands", broken)
    pid = parish.index.db.execute("SELECT pid FROM passages WHERE space = 'everyone' LIMIT 1").fetchone()[0]
    args = {
        "search": {"question": "Saturday vigil Mass"}, "open": {"passage_id": pid},
        "verify": {"answer": cite("Mass is at 5:00 pm", pid, "5:00 pm")}, "remember": {"note": "planted"},
        "ingest": {}, "status": {}, "brain_new": {"name": "Other"}, "brain_open": {"brain": "St. Brigid Parish"},
        "role_add": {"role": "x"}, "role_grant": {"role": "member", "space": "staff"},
        "role_revoke": {"role": "staff", "space": "staff"}, "member_set": {"member": "x"},
    }
    assert set(args) == set(ALL_TOOLS)
    toml_before = (parish.brain.root / "brain.toml").read_text()
    for name in ALL_TOOLS:
        with pytest.raises(identity.NotServed) as refused:
            parish.call(name, args[name], meta)
        assert str(refused.value).startswith(identity.REFUSED)
    assert (parish.brain.root / "brain.toml").read_text() == toml_before
    assert not list(parish.brain.spaces_dir.rglob("notes"))


def test_remote_serving_detects_the_serve_process(monkeypatch):
    monkeypatch.undo()
    monkeypatch.setattr(identity, "process_commands", lambda: [["/usr/bin/bash"], ["/opt/local-studio", "--smoke"]])
    assert identity.remote_serving() is False
    monkeypatch.setattr(identity, "process_commands", lambda: [["/opt/ls/local-studio", "serve", "--port", "18093"]])
    assert identity.remote_serving() is True
    monkeypatch.setattr(identity, "process_commands", lambda: [["local-studio-controller", "serve"]])
    assert identity.remote_serving() is False


def test_ask_as_can_only_lower(parish):
    brain = parish.brain
    keeper = identity.keeper_view(brain)
    for role in ROLES:
        assert identity.lower(keeper, brain, role).spaces == frozenset(ROLES[role])
    council = identity.lower(keeper, brain, "council")
    assert identity.lower(council, brain, "member").spaces == frozenset({"everyone"})
    with pytest.raises(tools.BrainError, match="only lower"):
        identity.lower(council, brain, "staff")
    parish.tool_role_add("trustee", ["council", "staff", "everyone"])
    with pytest.raises(tools.BrainError, match="only lower"):
        identity.lower(council, parish.session.need()[0], "trustee")
    for bad in ("keeper", "nobody"):
        with pytest.raises(tools.BrainError):
            parish.tool_search("payroll", as_role=bad)
    with pytest.raises(TypeError):
        parish.call("ingest", {"as_role": "member"})
    with pytest.raises(TypeError):
        parish.call("role_grant", {"role": "member", "space": "staff", "as_role": "member"})


def test_ask_as_hides_keeper_only_fields(parish):
    status = parish.tool_status(as_role="member")
    assert set(status) == {"brain", "caller", "spaces", "pdf"}
    assert set(status["spaces"]) == {"everyone"}


def link_or_skip(kind, source, target):
    try:
        (os.symlink if kind == "symlink" else os.link)(source, target)
    except (OSError, NotImplementedError) as error:
        pytest.skip(f"cannot make a {kind} here: {error}")


@pytest.mark.parametrize("kind", ["symlink", "hardlink"])
def test_restricted_file_reached_through_a_link_from_another_space(parish, kind):
    root = parish.brain.root
    link_or_skip(kind, root / "spaces/staff/payroll-notes.txt", root / "spaces/everyone/payroll-copy.txt")
    question = "What is Marisol Quintero's new hourly pay?"
    member = parish.tool_search(question, k=20, include_weak=True, as_role="member")
    assert all("payroll" not in p["document"] for p in member["passages"]) and member["answerable"] is False
    assert strip(member) == strip(parish.tool_search(UNANSWERABLE[0], as_role="member"))
    staff = parish.tool_search(question, as_role="staff")
    assert staff["answerable"] and staff["passages"][0]["document"].startswith("spaces/staff/")
    pid = staff["passages"][0]["id"]
    assert parish.tool_open(pid, as_role="member") == {"found": False, "message": NOT_FOUND}
    doc = parish.index.doc(staff["passages"][0]["document"])
    assert doc[2] == "staff"
    assert parish.index.doc("spaces/everyone/payroll-copy.txt") is None or kind == "hardlink"


def test_symlinked_folder_into_a_restricted_space(parish):
    root = parish.brain.root
    link_or_skip("symlink", root / "spaces/staff", root / "spaces/everyone/staff-folder")
    for question in RESTRICTED["staff"]:
        result = parish.tool_search(question, k=20, include_weak=True, as_role="member")
        assert all("/staff" not in p["document"] for p in result["passages"]), question
    assert parish.tool_search(RESTRICTED["staff"][0], as_role="staff")["answerable"]


def test_file_linked_from_spaces_with_unrelated_readers_is_keeper_only(parish):
    root = parish.brain.root
    link_or_skip("symlink", root / "spaces/staff/payroll-notes.txt", root / "spaces/council/payroll-link.txt")
    question = "What is Marisol Quintero's new hourly pay?"
    for role in ROLES:
        result = parish.tool_search(question, k=20, include_weak=True, as_role=role)
        assert all("payroll" not in p["document"] for p in result["passages"]), role
    keeper = parish.tool_search(question)
    assert keeper["answerable"] and keeper["passages"][0]["document"] == "spaces/staff/payroll-notes.txt"
    assert parish.index.doc("spaces/staff/payroll-notes.txt")[2] == brainlib.LINKED
    assert parish.tool_status()["linked_keeper_only"]["documents"] == 1


def test_link_leading_outside_the_brain_is_not_indexed(parish, tmp_path):
    outside = tmp_path / "outside-secret.txt"
    outside.write_text("The outside vault combination is 3141 and Marisol keeps it.", encoding="utf-8")
    link_or_skip("symlink", outside, parish.brain.root / "spaces/everyone/vault.txt")
    report = parish.tool_ingest()
    assert {"file": "spaces/everyone/vault.txt", "reason": "it links outside the brain's spaces folder"} in report["skipped"]
    assert parish.tool_search("outside vault combination")["answerable"] is False


def test_ingest_refuses_paths_outside_the_brain(parish, tmp_path):
    outside = tmp_path / "loose"
    outside.mkdir()
    (outside / "secret.txt").write_text("Outside words about a zebra parade.", encoding="utf-8")
    before = parish.index.snapshot()
    for path in (str(outside), str(outside / "secret.txt"), "../../loose", "spaces/../../../loose"):
        with pytest.raises(tools.BrainError, match="outside the brain"):
            parish.tool_ingest(path)
    try:
        os.symlink(outside, parish.brain.root / "spaces" / "everyone" / "loose-link")
    except OSError:
        pass
    else:
        with pytest.raises(tools.BrainError, match="outside the brain"):
            parish.tool_ingest("spaces/everyone/loose-link")
    assert parish.index.snapshot() == before
    assert not list(parish.brain.root.rglob("secret.txt"))


def test_status_and_ingest_progress_name_only_readable_spaces(parish):
    before = parish.tool_status(as_role="member")
    (parish.brain.root / "spaces/staff/new-hire.txt").write_text("Tamsin Vale starts as bookkeeper on May 4.", encoding="utf-8")
    (parish.brain.root / "spaces/staff/broken.docx").write_bytes(b"not a zip")
    report = parish.tool_ingest()
    assert report["added"] == 1 and report["failed"][0]["file"] == "spaces/staff/broken.docx"
    after = parish.tool_status(as_role="member")
    assert before == after
    assert "staff" not in json.dumps(after) and "new-hire" not in json.dumps(after)
    for role in ("member", "council"):
        assert "broken.docx" not in json.dumps(parish.tool_status(as_role=role))


def test_file_moved_into_a_restricted_space_and_replaced_by_a_link_is_not_served(parish, monkeypatch):
    """A swap between sync and the freshness check: the old path now links to a staff file."""
    root = parish.brain.root
    question = "When is the Saturday vigil Mass?"
    before = parish.tool_search(question, as_role="member")
    assert before["answerable"] and before["passages"][0]["document"] == "spaces/everyone/bulletin-2026-10-05.md"
    pid = before["passages"][0]["id"]
    from corunis_mcp import tools as toolsmod
    monkeypatch.setattr(toolsmod, "sync", lambda brain, index: None)  # the swap lands after this call's sync
    moved = root / "spaces/staff/bulletin-2026-10-05.md"
    os.rename(root / "spaces/everyone/bulletin-2026-10-05.md", moved)
    link_or_skip("symlink", moved, root / "spaces/everyone/bulletin-2026-10-05.md")
    after = parish.tool_search(question, k=20, include_weak=True, as_role="member")
    assert all("bulletin-2026-10-05" not in p["document"] for p in after["passages"]), after
    assert parish.tool_open(pid, as_role="member") == {"found": False, "message": NOT_FOUND}
