"""Making a brain, and the keeper's admin tools."""

from __future__ import annotations

import pytest

from conftest import Client
from corunis_mcp import brain as brainlib
from corunis_mcp.tools import Session


@pytest.fixture
def empty(tmp_path):
    session = Session(home=tmp_path / "home")
    yield Client(session)
    session.close()


def test_brain_new_layout(empty, tmp_path):
    made = empty.tool_brain_new("Holy Rood Choir")
    root = tmp_path / "home" / "Holy Rood Choir"
    assert made["path"] == str(root)
    assert (root / "brain.toml").is_file()
    for folder in ("spaces/everyone", "spaces/keeper", ".corunis"):
        assert (root / folder).is_dir(), folder
    brain = brainlib.load(root)
    assert brain.name == "Holy Rood Choir" and brain.keeper == "keeper"
    assert brain.roles == {"member": ["everyone"]}
    assert "keeper" in brain.spaces() and brain.readers("keeper") == frozenset()
    with pytest.raises(brainlib.BrainError):
        empty.tool_brain_new("Holy Rood Choir")


def test_reopen_after_restart(empty, tmp_path):
    empty.tool_brain_new("Holy Rood Choir")
    (tmp_path / "home/Holy Rood Choir/spaces/everyone/notice.txt").write_text("Choir robes are cleaned in May.", encoding="utf-8")
    empty.tool_ingest()
    again = Client(Session(home=tmp_path / "home"))
    assert again.tool_status()["brain"] == "Holy Rood Choir"
    assert again.tool_search("When are choir robes cleaned?")["answerable"]
    again.session.close()


def test_no_brain_open(empty):
    with pytest.raises(brainlib.BrainError, match="No brain is open"):
        empty.tool_search("anything")


def test_admin_tools_edit_brain_toml(parish):
    root = parish.brain.root
    parish.tool_role_add("choir", ["everyone", "choir"])
    assert (root / "spaces/choir").is_dir()
    parish.tool_role_grant("choir", "staff")
    parish.tool_role_revoke("choir", "staff")
    parish.tool_member_set("vance", name="Lior Vance", roles=["choir"])
    brain = brainlib.load(root)
    assert sorted(brain.roles["choir"]) == ["choir", "everyone"]
    assert brain.members["vance"].roles == ["choir"]
    with pytest.raises(brainlib.BrainError):
        parish.tool_role_grant("ghost", "staff")
    with pytest.raises(brainlib.BrainError):
        parish.tool_role_add("Bad Name!")
    with pytest.raises(brainlib.BrainError):
        parish.tool_member_set("vance", roles=["ghost"])


def test_narrowest_and_most_restrictive(parish):
    brain = parish.brain
    assert brain.narrowest({"everyone", "council"}) == "council"
    assert brain.most_restrictive({"everyone", "staff"}) == "staff"
    assert brain.most_restrictive({"everyone"}) == "everyone"
    assert brain.most_restrictive({"council", "staff"}) == brainlib.LINKED
    assert brain.most_restrictive({"keeper", "staff"}) == "keeper"
