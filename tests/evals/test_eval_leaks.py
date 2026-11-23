"""The leak suite: every way SPEC.md names for a restricted fact to escape, on all four eval corpora.

Mechanical, no model. A leak is any string from leaks.restricted(group) for a space the role cannot
read, found in what the server returns: search results, opened passages, verified answers, status
and refusals.
"""

from __future__ import annotations

import os
import re
import shutil

import pytest

from corunis_evals import brains, leaks
from corunis_evals.mcp import Client
from corunis_mcp import identity, index, tools
from corunis_mcp.brain import BrainError
from corunis_mcp.tools import NO_ANSWER, NOT_FOUND

from evalkit import KEEPER_CALLER

GROUPS = brains.GROUPS
FAKE_ID = "p" + "0" * 15
LATER = 60


def cite(sentence: str, pid: str, quote: str) -> str:
    return f'{sentence} [{pid} "{quote}"].'


def probes(text: str) -> list[str]:
    """Questions built from a passage's own words: its first words, and its names and numbers."""
    words = re.findall(r"[A-Za-z0-9$]+", text)
    capitals = [w for w in words if w[0].isupper() or w[0].isdigit() or w[0] == "$"]
    return [" ".join(words[:12]), " ".join(capitals[:10]) or " ".join(words[-8:])]


def shut_out(brain):
    """(role, space) for every role kept out of a space with restricted strings."""
    return [(role, space) for space in leaks.restricted(brain.group)
            for role, readable in sorted(brain.roles.items()) if space not in readable]


def hidden(brain, role: str) -> list[str]:
    return leaks.hidden_from(brain.group, brain.roles[role])


def served(result: dict) -> dict:
    """A reply without what echoes the caller's own words (search terms, dropped sentences)."""
    out = dict(result)
    if "searched" in out:
        out["searched"] = {k: v for k, v in out["searched"].items() if k != "terms"}
    out.pop("dropped", None)
    return out


def first_words(text: str, n: int = 6) -> str:
    """A quote of a passage's first plain words (no brackets or double quotes to break the citation)."""
    return " ".join([w for w in text.split() if not set(w) & set('[]"')][:n])


def assert_closed(brain, role: str, pid: str, quote: str) -> None:
    """open and verify answer for a restricted id exactly as for an id that does not exist."""
    opened = brain.call("open", passage_id=pid, as_role=role)
    assert opened == brain.call("open", passage_id=FAKE_ID, as_role=role) == {"found": False, "message": NOT_FOUND}
    checked = brain.call("verify", answer=cite("This is stated", pid, quote), as_role=role)
    fake = brain.call("verify", answer=cite("This is stated", FAKE_ID, quote), as_role=role)
    assert checked["kept"] == fake["kept"] == [] and checked["answer"] == fake["answer"] == NO_ANSWER
    assert checked["dropped"][0]["reason"] == fake["dropped"][0]["reason"] == NOT_FOUND


def assert_no_leak(brain, role: str, *results) -> None:
    found = leaks.find(hidden(brain, role), [served(r) for r in results])
    assert found == [], (brain.group, role, found)


def search_all(brain, role: str, question: str) -> list[dict]:
    return [brain.call("search", question=question, k=20, include_weak=weak, as_role=role) for weak in (False, True)]


def readable_quote(brain) -> tuple[str, str, str]:
    """(id, document, quote) of a single question's gold passage in the everyone space."""
    for q in brain.questions:
        if q["kind"] == "single" and leaks.space_of(q["gold"][0]["file"]) == "everyone":
            locator = q["gold"][0]
            return brain.resolve(locator)[0], locator["file"], locator["quote"]
    raise AssertionError("no single question cites the everyone space")


# open and verify with restricted ids


@pytest.mark.parametrize("group", GROUPS)
def test_open_verify_and_search_with_restricted_ids(pristine, group):
    brain = pristine(group)
    pairs = shut_out(brain)
    assert pairs, "the corpus restricts no space from any role"
    for role, space in pairs:
        rows = brain.passages(space=space)
        assert rows, space
        for pid, document, text in rows:
            assert_closed(brain, role, pid, first_words(text))
            for question in probes(text):
                results = search_all(brain, role, question)
                assert all(leaks.space_of(p["document"]) in brain.roles[role] for r in results for p in r["passages"])
                assert pid not in {p["id"] for r in results for p in r["passages"]}
                assert_no_leak(brain, role, *results)


@pytest.mark.parametrize("group", GROUPS)
def test_restricted_tuning_questions_leak_nothing(pristine, group):
    brain = pristine(group)
    for q in (q for q in brain.questions if q["kind"] == "restricted"):
        role = q["as_role"]
        status = brain.call("status", as_role=role)
        assert set(status["spaces"]) == brain.roles[role]
        results = search_all(brain, role, q["question"]) + [status]
        for locator in q["restricted"]:
            results += search_all(brain, role, locator["quote"])
            for pid in brain.resolve(locator):
                assert_closed(brain, role, pid, locator["quote"])
        assert_no_leak(brain, role, *results)


# a note remembered in a restricted space


STONES = ["slate", "granite", "basalt", "marble", "quartz", "shale", "flint", "jasper", "agate", "onyx", "pumice", "gneiss"]


@pytest.mark.parametrize("group", GROUPS)
def test_note_remembered_in_a_restricted_space(fresh, group):
    brain = fresh(group)
    for n, (role, space) in enumerate(shut_out(brain)):
        hiding = f"{STONES[n]} turtle"
        saved = brain.call("remember", note=f"The spare key for the storage shed is under the {hiding} by the gate.", space=space)
        assert saved["saved"].startswith(f"spaces/{space}/notes/")
        question = f"spare key storage shed {hiding}"
        found = brain.call("search", question=question)
        assert found["answerable"] and found["passages"][0]["document"] == saved["saved"]
        pid = found["passages"][0]["id"]
        results = search_all(brain, role, question)
        assert all(p["document"] != saved["saved"] for r in results for p in r["passages"])
        assert not leaks.find([hiding], [served(r) for r in results])
        assert_closed(brain, role, pid, f"under the {hiding} by the gate")


# a file just moved into a restricted space


def move(brain, rel: str, space: str) -> str:
    source = brain.root / rel
    target = brain.root / "spaces" / space / ("moved-" + source.name)
    shutil.move(source, target)
    stamp = os.stat(target).st_mtime + LATER
    os.utime(target, (stamp, stamp))
    return target.relative_to(brain.root).as_posix()


@pytest.mark.parametrize("group", GROUPS)
@pytest.mark.parametrize("stale_index", [False, True])
def test_file_just_moved_into_a_restricted_space(fresh, monkeypatch, group, stale_index):
    brain = fresh(group)
    pid, document, quote = readable_quote(brain)
    role, space = next((r, s) for r, s in shut_out(brain) if "everyone" in brain.roles[r])
    texts = [brains.text_of(path) for rel, path in brains.sources(group).items() if rel != document]
    question = next(q["question"] for q in brain.questions if q["gold"] and q["gold"][0]["file"] == document)
    before = brain.call("search", question=quote, k=20, as_role=role)
    assert pid in {p["id"] for p in before["passages"]}
    if stale_index:
        monkeypatch.setattr(tools, "sync", lambda brain, index: None)  # the query-time path check alone
    moved = move(brain, document, space)
    results = search_all(brain, role, question) + search_all(brain, role, quote)
    names = {p["document"] for r in results for p in r["passages"]}
    assert document not in names and moved not in names
    if not any(quote.casefold() in t.casefold() for t in texts):
        assert not leaks.find([quote], [served(r) for r in results])
    assert_closed(brain, role, pid, quote)
    if not stale_index:
        keeper = brain.call("search", question=quote, k=20)
        assert moved in {p["document"] for p in keeper["passages"]}


# a symlink (and a hard link) to a restricted file


def link_or_skip(kind: str, source, target) -> None:
    try:
        (os.symlink if kind == "symlink" else os.link)(source, target)
    except (OSError, NotImplementedError) as error:
        pytest.skip(f"cannot make a {kind} here: {error}")


@pytest.mark.parametrize("group", GROUPS)
@pytest.mark.parametrize("kind", ["symlink", "hardlink"])
def test_link_to_a_restricted_file(fresh, group, kind):
    brain = fresh(group)
    for role, space in shut_out(brain):
        if "everyone" not in brain.roles[role]:
            continue
        for rel in [r for r in brains.sources(group) if leaks.space_of(r) == space][:3]:
            name = f"link-{space}-" + rel.rsplit("/", 1)[1]
            link = brain.root / "spaces" / "everyone" / name
            if not link.exists():
                link_or_skip(kind, brain.root / rel, link)
            for pid, _, text in brain.passages(file=rel):
                results = [r for question in probes(text) for r in search_all(brain, role, question)]
                names = {p["document"] for r in results for p in r["passages"]}
                assert f"spaces/everyone/{name}" not in names and rel not in names
                assert_no_leak(brain, role, *results)
                assert_closed(brain, role, pid, first_words(text))


# ingest of a path outside the brain


@pytest.mark.parametrize("group", GROUPS)
def test_ingest_outside_the_brain(fresh, tmp_path, group):
    brain = fresh(group)
    outside = tmp_path / f"outside-{group}"
    outside.mkdir()
    secret = outside / "vault.txt"
    secret.write_text("The outside vault combination is 8361 and the porcupine keeps it.", encoding="utf-8")
    for path in (str(outside), str(secret), "../outside", "spaces/../../outside"):
        with pytest.raises(BrainError, match="outside the brain"):
            brain.call("ingest", path=path)
    try:
        os.symlink(secret, brain.root / "spaces" / "everyone" / "vault.txt")
    except (OSError, NotImplementedError):
        pass
    else:
        report = brain.call("ingest")
        assert {"file": "spaces/everyone/vault.txt", "reason": "it links outside the brain's spaces folder"} in report["skipped"]
    result = brain.call("search", question="outside vault combination porcupine", k=20, include_weak=True)
    assert not leaks.find(["porcupine", "8361"], served(result))


# status (and search) while a restricted space is being ingested


@pytest.mark.parametrize("group", GROUPS)
def test_status_during_restricted_ingest(tmp_path, monkeypatch, group):
    root = brains.build(group, tmp_path / "home" / group, KEEPER_CALLER)
    keeper = tools.Session(home=tmp_path / "home", brain_path=root)
    watcher = tools.Session(home=tmp_path / "home", brain_path=root)  # a second server on the same brain
    roles = brains.roles(group)
    restricted = leaks.restricted(group)
    seen: list[tuple[str, dict]] = []
    put = index.Index.put

    def put_and_look(self, path, space, *args, **kwargs):
        out = put(self, path, space, *args, **kwargs)
        if space in restricted and self is keeper.index:
            self.db.commit()  # the worst case: the half done ingest is visible to other readers
            for role, readable in roles.items():
                if space not in readable:
                    seen.append((role, watcher.call("status", {"as_role": role})))
                    for string in restricted[space][:2]:
                        seen.append((role, watcher.call("search", {"question": string, "include_weak": True, "as_role": role})))
        return out

    monkeypatch.setattr(index.Index, "put", put_and_look)
    monkeypatch.setattr(tools, "sync", lambda brain, idx: None)  # the watcher must not start an ingest of its own
    try:
        keeper.call("ingest", {})
        assert seen, "no restricted file was ingested"
        for role, result in seen:
            assert not leaks.find(leaks.hidden_from(group, roles[role]), served(result)), (role, result)
            if "spaces" in result and isinstance(result["spaces"], dict):
                assert set(result["spaces"]) <= roles[role]
    finally:
        keeper.close()
        watcher.close()


# a Remote session, or one that claims to be the keeper


REFUSE_WAYS = {
    "device": ({"LOCAL_STUDIO_CALLER": "device:phone-1"}, None),
    "missing": ({}, None),
    "other_local": ({"LOCAL_STUDIO_CALLER": "local:2000"}, None),
    "meta_claims_keeper": ({"LOCAL_STUDIO_CALLER": "local:2000"}, {"caller": {"member": "keeper", "origin": "host"}}),
    "meta_remote": ({"LOCAL_STUDIO_CALLER": KEEPER_CALLER}, {"remote": True}),
    "env_remote": ({"LOCAL_STUDIO_CALLER": KEEPER_CALLER, "CORUNIS_SESSION": "remote"}, None),
}


@pytest.mark.parametrize("group", GROUPS)
def test_remote_or_claimed_keeper_session_is_refused_over_stdio(pristine, group):
    brain = pristine(group)
    everything = leaks.hidden_from(group, set())
    q = next(q for q in brain.questions if q["kind"] == "restricted")
    pid = brain.resolve(q["restricted"][0])[0]
    calls = [("status", {}), ("search", {"question": q["question"], "include_weak": True}),
             ("search", {"question": q["restricted"][0]["quote"], "include_weak": True}),
             ("open", {"passage_id": pid}), ("verify", {"answer": cite("It says", pid, q["restricted"][0]["quote"])})]
    with Client(brain.home, brain.root, KEEPER_CALLER) as host:
        assert host.tool("status", {})["brain"] == brains.corpus(group)["name"]
    for way, (env, meta) in REFUSE_WAYS.items():
        env = dict(env)
        caller = env.pop("LOCAL_STUDIO_CALLER", None)
        with Client(brain.home, brain.root, caller, extra_env=env) as client:
            for name, args in calls:
                result = client.call(name, args, meta)
                assert result.get("isError"), (way, name, result)
                assert result["content"][0]["text"].startswith(identity.REFUSED), (way, name, result)
                assert not leaks.find(everything, result), (way, name)


# ask as a higher role


@pytest.mark.parametrize("group", GROUPS)
def test_ask_as_a_higher_role_is_refused(pristine, group):
    brain = pristine(group)
    loaded = brain.session.need()[0]
    keeper = identity.keeper_view(loaded)
    for low, low_spaces in brain.roles.items():
        view = identity.lower(keeper, loaded, low)
        for high, high_spaces in brain.roles.items():
            if not high_spaces <= low_spaces:
                with pytest.raises(BrainError, match="only lower"):
                    identity.lower(view, loaded, high)
    members = list(brains.corpus(group).get("members", {})) + ["keeper", "nobody", "everyone"]
    for name in members:
        if name not in brain.roles:
            with pytest.raises(BrainError):
                brain.call("search", question="anything at all", as_role=name)
    with Client(brain.home, brain.root, KEEPER_CALLER) as client:
        result = client.call("search", {"question": "anything at all", "as_role": "keeper"})
        assert result.get("isError")


# an unsupported claim on a real quote, and an uncited sentence


CODE = re.compile(r"\d[^\W\d_]|[^\W\d_]\d")  # a word that mixes letters and digits, such as 7KQ2MX


@pytest.mark.xfail(strict=True, reason="verify reads 7KQ2MX as the names KQ and MX and drops a cited, true sentence")
def test_a_cited_code_of_letters_and_digits_is_kept(pristine):
    brain = pristine("class")
    q = next(q for q in brain.questions if q["id"] == "class-single-07")
    locator = q["gold"][0]
    assert CODE.search(locator["quote"])
    pid = brain.resolve(locator)[0]
    result = brain.call("verify", answer=cite("The class code is 7KQ2MX", pid, locator["quote"]))
    assert len(result["kept"]) == 1, result["dropped"]


def nudge(quote: str) -> str | None:
    """The quote with its first number changed, or None when it has no number."""
    match = re.search(r"\d+", quote)
    if not match:
        return None
    return quote[: match.start()] + str(int(match[0]) + 7) + quote[match.end():]


@pytest.mark.parametrize("group", GROUPS)
def test_unsupported_claim_on_a_real_quote(pristine, group):
    brain = pristine(group)
    checked = 0
    for q in (q for q in brain.questions if q["kind"] == "single"):
        locator = q["gold"][0]
        pid = brain.resolve(locator)[0]
        quote = locator["quote"].replace('"', "")
        if CODE.search(quote):
            continue  # see test_a_cited_code_of_letters_and_digits_is_kept
        assert len(brain.call("verify", answer=cite(f"It says {quote}", pid, quote))["kept"]) == 1, (q["id"], quote)
        wrong = [cite(f"It says {quote} in 2031", pid, quote)]
        changed = nudge(quote)
        if changed:
            wrong.append(cite(f"It says {changed}", pid, quote))
        for answer in wrong:
            result = brain.call("verify", answer=answer)
            assert result["kept"] == [] and result["answer"] == NO_ANSWER, (q["id"], answer, result)
            checked += 1
    assert checked >= 8


@pytest.mark.parametrize("group", GROUPS)
def test_uncited_sentence_is_dropped(pristine, group):
    brain = pristine(group)
    pid, _, quote = readable_quote(brain)
    for q in (q for q in brain.questions if q["kind"] == "restricted"):
        role = q["as_role"]
        stated = q["restricted"][0]["quote"].rstrip(".")
        answer = cite(f"It says {quote}", pid, quote) + f" Also, {stated}."
        result = brain.call("verify", answer=answer, as_role=role)
        assert len(result["kept"]) == 1 and result["dropped"][0]["reason"] == "It cites no passage.", (q["id"], result)
        assert stated not in result["answer"]
        assert_no_leak(brain, role, result)
