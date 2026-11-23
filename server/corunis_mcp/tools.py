"""The brain's tools. Every read goes through the caller's spaces, decided in identity.py.

A passage the caller may not read is handled exactly like a passage that does not exist: same
reply, same wording, no count and no hint. Search statistics come only from readable spaces
(see index.py), so a restricted question gets the same reply an unanswerable one gets.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from corunis_mcp import answer as answerlib
from corunis_mcp import brain as brainlib
from corunis_mcp import extract
from corunis_mcp.answer import MIN_QUOTE, NO_ANSWER, clean_quote, normalize, quote_in, underived, unsupported_facts
from corunis_mcp.brain import Brain, BrainError
from corunis_mcp.identity import Caller, calling_session, caller, require_keeper
from corunis_mcp.index import Index
from corunis_mcp.ingest import ingest, sync

NOT_FOUND = "No passage with that id is available to you."

# Ranking: BM25 picks CANDIDATES passages per search, which are then ordered by coverage (how
# many of the question's search terms a passage contains), then BM25. A question is answerable
# when the top passage covers at least COVERAGE_MIN of its terms. Calibrated on the synthetic
# parish in tests/server (test_calibration.py): answerable questions there cover 0.4 to 1.0,
# unanswerable ones 0.2 at most. There is no BM25 score floor: in a small space a term found in
# most passages gets an IDF near zero, so a right passage can score 0.0.
COVERAGE_MIN = 0.4
CANDIDATES = 30
MAX_TERMS = 12
DEFAULT_K = 5
MAX_K = 20

STOPWORDS = frozenset(
    """
    a about above after again against all am an and any are as at be because been before being below
    between both but by can could did do does doing down during each few for from further had has have
    having he her here hers herself him himself his how i if in into is it its itself just me more most
    my myself no nor not now of off on once only or other our ours ourselves out over own same she should
    so some such than that the their theirs them themselves then there these they this those through to
    too under until up very was we were what when where which while who whom why will with would you your
    yours yourself yourselves tell know please find show give get got say said many much also any anyone
    anything something someone us let lets did does done ever there's what's who's where's when's how's
    """.split()
)

AS_ROLE = {
    "type": "string",
    "description": "Answer as this role would see it, to check what the role can read. It can only narrow what you see.",
}

TOOLS = [
    {
        "name": "search",
        "description": "Search the brain's documents and notes. Returns passages the caller may read, each with an id,"
        " document, page, character range, date and score, and `answerable`. If answerable is false, say: " + NO_ANSWER,
        "inputSchema": {
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "The question, in the asker's words."},
                "k": {"type": "integer", "minimum": 1, "maximum": MAX_K, "description": "How many passages (default 5)."},
                "include_weak": {"type": "boolean", "description": "Also return passages when answerable is false."},
                "as_role": AS_ROLE,
            },
            "required": ["question"],
        },
    },
    {
        "name": "open",
        "description": "Open one passage by its id, with its full text and the ids of the passages before and after it.",
        "inputSchema": {
            "type": "object",
            "properties": {"passage_id": {"type": "string"}, "as_role": AS_ROLE},
            "required": ["passage_id"],
        },
    },
    {
        "name": "verify",
        "description": "Check your whole answer before showing it. Write every sentence with its citations in"
        ' brackets: [p0123456789abcde "exact words from that passage"]. Cite several passages with several'
        " brackets. Mark a value you computed with [derived 79,650] and cite its inputs. Returns the answer with"
        " only the sentences that passed: each needs a citation whose quote is in its passage, and every number,"
        " date and name in the sentence must be in its quotes. Show only what it returns.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "answer": {"type": "string", "description": "The whole answer, with citations in brackets."},
                "as_role": AS_ROLE,
            },
            "required": ["answer"],
        },
    },
    {
        "name": "remember",
        "description": "Keeper only. Save a note with its author and date in a space's notes folder. Without a space,"
        " it goes to the narrowest space (the keeper's own space in a new brain).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "note": {"type": "string"},
                "space": {"type": "string", "description": "Which space may read the note, such as everyone."},
            },
            "required": ["note"],
        },
    },
    {
        "name": "ingest",
        "description": "Keeper only. Read new and changed files into the index. With no path, the whole brain."
        " Put files in a space folder first; a path outside the brain folder is refused.",
        "inputSchema": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "A file or folder inside the brain."}},
        },
    },
    {
        "name": "status",
        "description": "What brain is open, which spaces the caller reads and how many documents each holds.",
        "inputSchema": {"type": "object", "properties": {"as_role": AS_ROLE}},
    },
    {
        "name": "brain_new",
        "description": "Keeper only. Make a new brain folder with a name, such as St. Brigid Parish, and open it.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "path": {"type": "string", "description": "Where to make it (default: a folder named after it in the Corunis home)."},
            },
            "required": ["name"],
        },
    },
    {
        "name": "brain_open",
        "description": "Keeper only. Open an existing brain by its name in the Corunis home or by its folder path.",
        "inputSchema": {"type": "object", "properties": {"brain": {"type": "string"}}, "required": ["brain"]},
    },
    {
        "name": "role_add",
        "description": "Keeper only. Add a role, optionally with the spaces it reads.",
        "inputSchema": {
            "type": "object",
            "properties": {"role": {"type": "string"}, "spaces": {"type": "array", "items": {"type": "string"}}},
            "required": ["role"],
        },
    },
    {
        "name": "role_grant",
        "description": "Keeper only. Let a role read a space. Makes the space folder if it does not exist.",
        "inputSchema": {
            "type": "object",
            "properties": {"role": {"type": "string"}, "space": {"type": "string"}},
            "required": ["role", "space"],
        },
    },
    {
        "name": "role_revoke",
        "description": "Keeper only. Stop a role from reading a space.",
        "inputSchema": {
            "type": "object",
            "properties": {"role": {"type": "string"}, "space": {"type": "string"}},
            "required": ["role", "space"],
        },
    },
    {
        "name": "member_set",
        "description": "Keeper only. Add a member or change their name and roles.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "member": {"type": "string", "description": "A short id: lowercase letters, digits, - or _."},
                "name": {"type": "string"},
                "roles": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["member"],
        },
    },
]


def terms_of(question: str) -> list[str]:
    terms: list[str] = []
    for word in re.findall(r"[^\W_]+", question.casefold()):
        if word in STOPWORDS or (len(word) < 2 and not word.isdigit()) or word in terms:
            continue
        terms.append(word)
    return terms[:MAX_TERMS]


def fts_term(term: str) -> str:
    return '"' + term.replace('"', '""') + '"'




def default_home() -> Path:
    configured = os.environ.get("CORUNIS_HOME")
    return Path(configured).expanduser() if configured else Path.home() / "Corunis"


class Session:
    """One server process: the Corunis home folder, the open brain and its index."""

    def __init__(self, home: Path | None = None, brain_path: Path | None = None) -> None:
        self.home = (home or default_home()).expanduser()
        self.brain: Brain | None = None
        self.index: Index | None = None
        self.member: str | None = None  # set per call from identity.calling_session
        start = brain_path or self._remembered()
        if start is not None:
            try:
                self._open(start)
            except BrainError:
                self.brain = None

    def _remembered(self) -> Path | None:
        configured = os.environ.get("CORUNIS_BRAIN")
        if configured:
            return Path(configured).expanduser()
        current = self.home / ".current"
        if current.is_file():
            return Path(current.read_text(encoding="utf-8").strip())
        if self.home.is_dir():
            brains = [p for p in self.home.iterdir() if (p / brainlib.CONFIG).is_file()]
            if len(brains) == 1:
                return brains[0]
        return None

    def _open(self, root: Path) -> Brain:
        root = Path(os.path.realpath(root.expanduser()))
        loaded = brainlib.load(root)
        if self.index is not None:
            self.index.close()
        self.brain = loaded
        self.index = Index(loaded.index_path)
        return loaded

    def _remember_current(self) -> None:
        if self.brain is not None:
            self.home.mkdir(parents=True, exist_ok=True)
            (self.home / ".current").write_text(str(self.brain.root), encoding="utf-8")

    def close(self) -> None:
        if self.index is not None:
            self.index.close()
            self.index = None

    def call(self, name: str, args: dict, meta: dict | None = None) -> dict:
        """Run one tool. Identity is decided first, so a refused caller reaches no tool at all."""
        handler = getattr(self, "tool_" + name, None)
        if handler is None or name not in {tool["name"] for tool in TOOLS}:
            raise BrainError(f"Unknown tool: {name}")
        self.member = calling_session(meta)
        try:
            return handler(**args)
        finally:
            self.member = None

    def need(self) -> tuple[Brain, Index]:
        if self.brain is None or self.index is None:
            raise BrainError("No brain is open. Make one with brain_new, or open one with brain_open.")
        self.brain = brainlib.load(self.brain.root)  # pick up edits to brain.toml before every call
        return self.brain, self.index

    def who(self, brain: Brain, as_role: str | None = None) -> Caller:
        if self.member is None:
            raise BrainError("Call tools through Session.call.")
        return caller(brain, self.member, as_role)

    def reading(self, as_role: str | None = None) -> tuple[Brain, Index, Caller]:
        """For every read tool: catch up with moved, linked and changed files, then decide the view."""
        brain, index = self.need()
        sync(brain, index)
        return brain, index, self.who(brain, as_role)

    def admin(self) -> tuple[Brain, Index, Caller]:
        brain, index = self.need()
        who = self.who(brain)
        require_keeper(who)
        return brain, index, who

    @staticmethod
    def fresh(brain: Brain, document: str, mtime_ns: int, size: int, spaces: str, who: Caller) -> bool:
        """Query-time check against the current brain.toml and folder: every path that reaches the file
        is in a space the caller reads, and the file is still at its indexed real path, unchanged."""
        if not set(json.loads(spaces)) <= who.spaces:
            return False
        parts = document.split("/")
        if len(parts) < 3 or parts[0] != brainlib.SPACES:
            return False
        try:
            stat = (brain.root / document).stat()
        except OSError:
            return False
        return stat.st_mtime_ns == mtime_ns and stat.st_size == size

    def readable(self, brain: Brain, index: Index, pid: str, who: Caller) -> dict | None:
        """A passage the caller may read, or None: the same None for a restricted id and an unknown one."""
        passage = index.passage(pid, set(who.spaces)) if pid else None
        if passage is None:
            return None
        meta = (passage.pop("mtime_ns"), passage.pop("size"), passage.pop("spaces"))
        passage.pop("space")
        return passage if self.fresh(brain, passage["document"], *meta, who) else None

    def readable_spaces(self, who: Caller) -> list[str]:
        return sorted(s for s in who.spaces if s != brainlib.LINKED)

    # Reading

    def tool_search(self, question: str, k: int = DEFAULT_K, include_weak: bool = False, as_role: str | None = None) -> dict:
        brain, index, who = self.reading(as_role)
        k = max(1, min(int(k), MAX_K))
        terms = terms_of(question)
        counts = index.counts(set(who.spaces))
        searched = {
            "spaces": self.readable_spaces(who),
            "documents": sum(c["documents"] for c in counts.values()),
            "terms": terms,
        }
        phrases = [fts_term(t) for t in terms]
        hits = index.search(phrases, set(who.spaces), max(k, CANDIDATES)) if terms else []
        hits = [h for h in hits if self.fresh(brain, h.document, h.mtime_ns, h.size, h.spaces, who)]
        covered: dict[int, int] = {}
        for space in {h.space for h in hits}:
            covered.update(index.coverage(space, [h.rowid for h in hits if h.space == space], phrases))
        hits.sort(key=lambda h: (-covered[h.rowid], -h.score, h.id))
        hits = hits[:k]
        answerable = bool(hits) and covered[hits[0].rowid] / len(terms) >= COVERAGE_MIN
        result: dict = {"answerable": answerable, "passages": []}
        if answerable or include_weak:
            result["passages"] = [
                {
                    "id": h.id, "document": h.document, "page": h.page, "start": h.start, "end": h.end,
                    "date": h.date, "score": round(h.score, 3), "matched": f"{covered[h.rowid]} of {len(terms)} terms",
                    "text": h.text,
                }
                for h in hits
            ]
        if not answerable:
            result["say"] = NO_ANSWER
        result["searched"] = searched
        return result

    def tool_open(self, passage_id: str, as_role: str | None = None) -> dict:
        brain, index, who = self.reading(as_role)
        passage = self.readable(brain, index, str(passage_id).strip(), who)
        if passage is None:
            return {"found": False, "message": NOT_FOUND}
        return {"found": True, "passage": passage}

    def tool_verify(self, answer: str, as_role: str | None = None) -> dict:
        brain, index, who = self.reading(as_role)
        kept, dropped = [], []
        cited = 0
        for sentence in answerlib.sentences(str(answer)):
            if answerlib.is_abstention(sentence):
                kept.append({"sentence": sentence.raw, "abstention": True})
                continue
            reason, sources = self.check_sentence(brain, index, who, sentence)
            if reason:
                dropped.append({"sentence": sentence.raw, "reason": reason})
            else:
                kept.append({"sentence": sentence.raw, "citations": sources})
                cited += 1
        result: dict = {
            "answer": " ".join(k["sentence"] for k in kept) if cited else NO_ANSWER,
            "kept": kept if cited else [],
            "dropped": dropped,
        }
        if not cited:
            result["say"] = NO_ANSWER
        return result

    def check_sentence(self, brain: Brain, index: Index, who: Caller, sentence: answerlib.Sentence) -> tuple[str | None, list]:
        if sentence.bad_brackets:
            return 'A bracket in it is not in the form [p0123456789abcde "exact words"] or [derived 79,650].', []
        if not sentence.citations:
            return "It cites no passage.", []
        sources, quotes = [], []
        for pid, raw_quote in sentence.citations:
            passage = self.readable(brain, index, pid, who)
            quote = clean_quote(raw_quote)
            if passage is None:
                return NOT_FOUND, []
            if len(quote) < MIN_QUOTE:
                return f"A quote is shorter than {MIN_QUOTE} characters.", []
            if not quote_in(quote, normalize(passage["text"])):
                return f"The quote {raw_quote!r} is not in passage {pid}.", []
            quotes.append(raw_quote)
            sources.append({"passage_id": pid, "quote": raw_quote, "document": passage["document"],
                            "page": passage["page"], "date": passage["date"]})
        missing = unsupported_facts(sentence.text, quotes, sentence.derived)
        if missing:
            return f"It states {', '.join(missing)}, which none of its quotes contain.", []
        wrong = underived(sentence.derived, quotes)
        if wrong:
            return wrong, []
        return None, sources

    def tool_status(self, as_role: str | None = None) -> dict:
        if self.brain is None:
            return {"brain": None, "home": str(self.home), "next": "Make a brain with brain_new.", "pdf": extract.pdf_available()}
        brain, index, who = self.reading(as_role)
        readable = set(self.readable_spaces(who))
        result: dict = {
            "brain": brain.name,
            "caller": {"member": who.member, "keeper": who.keeper, "as_role": who.as_role},
            "spaces": index.counts(readable),
            "pdf": extract.pdf_available(),
        }
        if who.keeper:
            result.update({
                "path": str(brain.root),
                "roles": {role: sorted(spaces) for role, spaces in sorted(brain.roles.items())},
                "members": {m.id: {"name": m.name, "roles": m.roles} for m in sorted(brain.members.values(), key=lambda m: m.id)},
                "linked_keeper_only": index.counts({brainlib.LINKED})[brainlib.LINKED],
                "unread_files": [{"file": path, "reason": error} for path, error in index.failures(set(who.spaces))],
                "unread_spaces": sorted(s for s in brain.spaces() if not brain.readers(s)),
            })
        return result

    # Writing: keeper only

    def tool_remember(self, note: str, space: str | None = None) -> dict:
        brain, index, who = self.admin()
        text = str(note).strip()
        if not text:
            raise BrainError("The note is empty.")
        readable = set(self.readable_spaces(who))
        if space is None or not str(space).strip():
            space = brain.narrowest(readable)
        elif space not in readable or not brainlib.valid_space(space):
            raise BrainError(f"You cannot save a note to {space!r}. Spaces you can use: {', '.join(sorted(readable))}.")
        now = datetime.now(timezone.utc).replace(microsecond=0)
        stamp = now.isoformat().replace("+00:00", "Z")
        slug = "-".join(re.findall(r"[a-z0-9]+", text.casefold())[:6]) or "note"
        folder = brain.spaces_dir / space / brainlib.NOTES
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{now:%Y-%m-%d-%H%M%S}-{slug}.md"
        n = 2
        while path.exists():
            path = folder / f"{now:%Y-%m-%d-%H%M%S}-{slug}-{n}.md"
            n += 1
        path.write_text(f"---\nauthor: {who.member}\ndate: {stamp}\n---\n\n{text}\n", encoding="utf-8")
        rel = path.relative_to(brain.root).as_posix()
        ingest(brain, index, rel)
        return {"saved": rel, "author": who.member, "date": stamp, "space": space}

    def tool_ingest(self, path: str | None = None) -> dict:
        brain, index, _ = self.admin()
        root = Path(os.path.realpath(brain.root))
        scope = ""
        if path:
            target = Path(path).expanduser()
            target = Path(os.path.realpath(target if target.is_absolute() else root / target))
            if target != root and root not in target.parents:
                raise BrainError("That path is outside the brain folder. Put the files in one of its spaces first.")
            if not target.exists():
                raise BrainError("Nothing is at that path in the brain.")
            scope = "" if target == root else target.relative_to(root).as_posix()
        report = ingest(brain, index, scope).as_dict()
        unread = sorted(s for s in brain.spaces() if not brain.readers(s))
        if unread:
            report["unread_spaces"] = unread
            report["next"] = "No role reads these spaces; only the keeper sees them. Use role_grant to share one."
        return report

    def tool_brain_new(self, name: str, path: str | None = None) -> dict:
        root = Path(path).expanduser() if path else self.home / brainlib.folder_name(name)
        brainlib.create(root, str(name).strip())
        self._open(root)
        self._remember_current()
        return {
            "brain": self.brain.name,
            "path": str(self.brain.root),
            "spaces": self.brain.spaces(),
            "next": f"Put documents in {self.brain.spaces_dir / brainlib.DEFAULT_SPACE}, then call ingest.",
        }

    def tool_brain_open(self, brain: str) -> dict:
        candidate = Path(brain).expanduser()
        if not (candidate / brainlib.CONFIG).is_file():
            candidate = self.home / brainlib.folder_name(brain)
        self._open(candidate)
        self._remember_current()
        return self.tool_status()

    def tool_role_add(self, role: str, spaces: list | None = None) -> dict:
        brain, _, _ = self.admin()
        if not brainlib.valid_id(role):
            raise BrainError("A role name uses lowercase letters, digits, - or _, and starts with a letter or digit.")
        if role in brain.roles or role == "keeper":
            raise BrainError(f"The role {role!r} already exists.")
        spaces = [str(s) for s in spaces or []]
        for space in spaces:
            if not brainlib.valid_space(space):
                raise BrainError(f"{space!r} is not a valid space name.")
        brain.roles[role] = sorted(set(spaces))
        for space in spaces:
            (brain.spaces_dir / space).mkdir(parents=True, exist_ok=True)
        brain.save()
        return {"role": role, "spaces": brain.roles[role]}

    def tool_role_grant(self, role: str, space: str) -> dict:
        brain, _, _ = self.admin()
        current = brain.role_spaces(role)
        if not brainlib.valid_space(space):
            raise BrainError(f"{space!r} is not a valid space name.")
        (brain.spaces_dir / space).mkdir(parents=True, exist_ok=True)
        brain.roles[role] = sorted(current | {space})
        brain.save()
        return {"role": role, "spaces": brain.roles[role]}

    def tool_role_revoke(self, role: str, space: str) -> dict:
        brain, _, _ = self.admin()
        brain.roles[role] = sorted(brain.role_spaces(role) - {space})
        brain.save()
        return {"role": role, "spaces": brain.roles[role]}

    def tool_member_set(self, member: str, name: str | None = None, roles: list | None = None) -> dict:
        brain, _, _ = self.admin()
        if not brainlib.valid_id(member):
            raise BrainError("A member id uses lowercase letters, digits, - or _, and starts with a letter or digit.")
        entry = brain.members.get(member) or brainlib.Member(member)
        if name is not None:
            entry.name = str(name)
        if roles is not None:
            unknown = [r for r in roles if r not in brain.roles]
            if unknown:
                raise BrainError(f"No such role: {', '.join(unknown)}. Add it with role_add first.")
            entry.roles = sorted(set(roles))
        brain.members[member] = entry
        brain.save()
        return {"member": member, "name": entry.name, "roles": entry.roles,
                "note": "Members cannot ask Corunis yet; v0 answers the keeper alone."}
