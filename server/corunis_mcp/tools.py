"""The brain's tools. Every read goes through the caller's spaces, decided in identity.py.

A passage the caller may not read is handled exactly like a passage that does not exist: same
reply, same wording, no count and no hint. Search statistics come only from readable spaces
(see index.py), so a restricted question gets the same reply an unanswerable one gets.
"""

from __future__ import annotations

import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

from corunis_mcp import brain as brainlib
from corunis_mcp import extract
from corunis_mcp.brain import Brain, BrainError
from corunis_mcp.identity import Caller, caller, require_keeper
from corunis_mcp.index import Index
from corunis_mcp.ingest import ingest

NO_ANSWER = "The documents I can see don't answer this."
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
MIN_QUOTE = 4

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
    "description": "Keeper only: answer as this role would see it, to check what the role can read.",
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
        "description": "Check an answer before showing it. Each claim names a passage id and a short exact quote from"
        " that passage. Returns the claims whose quote is in their passage (supported) and the ones that fail."
        " Show only supported claims.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "claims": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "text": {"type": "string", "description": "The claim in your own words."},
                            "passage_id": {"type": "string"},
                            "quote": {"type": "string", "description": "Words copied exactly from the passage."},
                        },
                        "required": ["passage_id", "quote"],
                    },
                },
                "as_role": AS_ROLE,
            },
            "required": ["claims"],
        },
    },
    {
        "name": "remember",
        "description": "Save a note to the brain with its author and date. Without a space, only the keeper can read it.",
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
        " A path outside the brain is copied into the named space first.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "A file or folder, inside the brain or outside it."},
                "space": {"type": "string", "description": "The space to copy an outside path into."},
            },
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


QUOTE_MAP = str.maketrans({
    "‘": "'", "’": "'", "‚": "'", "‛": "'",
    "“": '"', "”": '"', "„": '"', "‟": '"',
    "‐": "-", "‑": "-", "‒": "-", "–": "-", "—": "-", "−": "-",
    " ": " ", "…": "...",
})


def normalize(text: str) -> str:
    return " ".join(text.translate(QUOTE_MAP).casefold().split())


def clean_quote(quote: str) -> str:
    """Normalize a quote and drop wrapping quote marks or ellipses a model may add around it."""
    text = normalize(quote)
    previous = None
    while text != previous:
        previous = text
        text = text.strip().strip("\"'").strip()
        text = text.removeprefix("...").removesuffix("...").strip()
    return text


def default_home() -> Path:
    configured = os.environ.get("CORUNIS_HOME")
    return Path(configured).expanduser() if configured else Path.home() / "Corunis"


class Session:
    """One server process: the Corunis home folder, the open brain and its index."""

    def __init__(self, home: Path | None = None, brain_path: Path | None = None) -> None:
        self.home = (home or default_home()).expanduser()
        self.brain: Brain | None = None
        self.index: Index | None = None
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
        root = root.expanduser().resolve()
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

    def need(self) -> tuple[Brain, Index]:
        if self.brain is None or self.index is None:
            raise BrainError("No brain is open. Make one with brain_new, or open one with brain_open.")
        self.brain = brainlib.load(self.brain.root)  # pick up hand edits to brain.toml
        return self.brain, self.index

    def call(self, name: str, args: dict) -> dict:
        handler = getattr(self, "tool_" + name, None)
        if handler is None or name not in {tool["name"] for tool in TOOLS}:
            raise BrainError(f"Unknown tool: {name}")
        return handler(**args)

    # Reading

    def tool_search(self, question: str, k: int = DEFAULT_K, include_weak: bool = False, as_role: str | None = None) -> dict:
        brain, index = self.need()
        who = caller(brain, as_role)
        k = max(1, min(int(k), MAX_K))
        terms = terms_of(question)
        counts = index.counts(set(who.spaces))
        searched = {
            "spaces": sorted(s for s in who.spaces if s != brainlib.KEEPER_NOTES) + (["keeper notes"] if who.keeper else []),
            "documents": sum(c["documents"] for c in counts.values()),
            "terms": terms,
        }
        phrases = [fts_term(t) for t in terms]
        hits = index.search(" OR ".join(phrases), set(who.spaces), max(k, CANDIDATES)) if terms else []
        covered: dict[int, int] = {}
        for space in {h.space for h in hits}:
            covered.update(index.coverage(space, [h.rowid for h in hits if h.space == space], phrases))
        hits.sort(key=lambda h: (-covered[h.rowid], -h.score, h.id))
        hits = hits[:k]
        answerable = bool(hits) and covered[hits[0].rowid] / len(terms) >= COVERAGE_MIN
        result: dict = {"answerable": answerable}
        if answerable or include_weak:
            result["passages"] = [
                {
                    "id": h.id, "document": h.document, "page": h.page, "start": h.start, "end": h.end,
                    "date": h.date, "score": round(h.score, 3), "matched": f"{covered[h.rowid]} of {len(terms)} terms",
                    "text": h.text,
                }
                for h in hits
            ]
        else:
            result["passages"] = []
        if not answerable:
            result["say"] = NO_ANSWER
        result["searched"] = searched
        return result

    def tool_open(self, passage_id: str, as_role: str | None = None) -> dict:
        brain, index = self.need()
        who = caller(brain, as_role)
        passage = index.passage(str(passage_id).strip(), set(who.spaces))
        if passage is None:
            return {"found": False, "message": NOT_FOUND}
        passage.pop("space")
        return {"found": True, "passage": passage}

    def tool_verify(self, claims: list, as_role: str | None = None) -> dict:
        brain, index = self.need()
        who = caller(brain, as_role)
        supported, failed = [], []
        for claim in claims if isinstance(claims, list) else []:
            claim = claim if isinstance(claim, dict) else {}
            pid = str(claim.get("passage_id", "")).strip()
            quote = clean_quote(str(claim.get("quote", "")))
            echo = {key: claim[key] for key in ("text", "passage_id", "quote") if key in claim}
            passage = index.passage(pid, set(who.spaces)) if pid else None
            if passage is None:
                failed.append({**echo, "reason": NOT_FOUND})
            elif len(quote) < MIN_QUOTE:
                failed.append({**echo, "reason": f"The quote is shorter than {MIN_QUOTE} characters."})
            elif quote in normalize(passage["text"]):
                supported.append({**echo, "document": passage["document"], "page": passage["page"], "date": passage["date"]})
            else:
                failed.append({**echo, "reason": "The quote is not in that passage. Drop this claim."})
        result: dict = {"supported": supported, "failed": failed}
        if not supported:
            result["say"] = NO_ANSWER
        return result

    def tool_status(self, as_role: str | None = None) -> dict:
        if self.brain is None:
            return {"brain": None, "home": str(self.home), "next": "Make a brain with brain_new.", "pdf": extract.pdf_available()}
        brain, index = self.need()
        who = caller(brain, as_role)
        counts = index.counts(set(who.spaces) - {brainlib.KEEPER_NOTES})
        result: dict = {
            "brain": brain.name,
            "caller": {"member": who.member, "keeper": who.keeper, "roles": list(who.roles), "as_role": who.as_role},
            "spaces": counts,
            "pdf": extract.pdf_available(),
        }
        if who.keeper:
            notes = index.counts({brainlib.KEEPER_NOTES})[brainlib.KEEPER_NOTES]
            result.update({
                "path": str(brain.root),
                "keeper_notes": notes,
                "roles": {role: sorted(spaces) for role, spaces in sorted(brain.roles.items())},
                "members": {m.id: {"name": m.name, "roles": m.roles} for m in sorted(brain.members.values(), key=lambda m: m.id)},
                "unread_files": [{"file": path, "reason": error} for path, error in index.failures()],
                "unread_spaces": sorted(s for s in brain.spaces() if not any(s in v for v in brain.roles.values())),
            })
        return result

    # Writing

    def tool_remember(self, note: str, space: str | None = None) -> dict:
        brain, index = self.need()
        who = caller(brain)
        text = str(note).strip()
        if not text:
            raise BrainError("The note is empty.")
        if space:
            if space not in who.spaces or not brainlib.valid_space(space):
                raise BrainError(f"You cannot save a note to {space!r}. Spaces you can use: {', '.join(sorted(s for s in who.spaces if s != brainlib.KEEPER_NOTES))}.")
        elif not who.keeper:
            raise BrainError("Name the space the note belongs to.")
        now = datetime.now(timezone.utc).replace(microsecond=0)
        slug = "-".join(re.findall(r"[a-z0-9]+", text.casefold())[:6]) or "note"
        brain.notes_dir.mkdir(exist_ok=True)
        path = brain.notes_dir / f"{now:%Y-%m-%d-%H%M%S}-{slug}.md"
        n = 2
        while path.exists():
            path = brain.notes_dir / f"{now:%Y-%m-%d-%H%M%S}-{slug}-{n}.md"
            n += 1
        lines = ["---", f"author: {who.member}", f"date: {now.isoformat().replace('+00:00', 'Z')}"]
        if space:
            lines.append(f"space: {space}")
        path.write_text("\n".join(lines + ["---", "", text, ""]), encoding="utf-8")
        rel = path.relative_to(brain.root).as_posix()
        ingest(brain, index, rel)
        return {"saved": rel, "author": who.member, "date": lines[2][6:], "space": space or "keeper notes"}

    def tool_ingest(self, path: str | None = None, space: str | None = None) -> dict:
        brain, index = self.need()
        require_keeper(caller(brain))
        scope = ""
        copied = None
        if path:
            target = Path(path).expanduser()
            if not target.is_absolute():
                target = brain.root / target
            target = target.resolve()
            root = brain.root.resolve()
            if not target.exists():
                raise BrainError(f"Nothing at {target}.")
            if target == root or root in target.parents:
                scope = target.relative_to(root).as_posix()
            else:
                if not space or not brainlib.valid_space(space):
                    raise BrainError("That path is outside the brain. Name the space to copy it into.")
                destination = brain.spaces_dir / space / target.name
                if destination.exists():
                    raise BrainError(f"{destination.relative_to(root).as_posix()} already exists. Rename or remove it first.")
                destination.parent.mkdir(parents=True, exist_ok=True)
                if target.is_dir():
                    shutil.copytree(target, destination)
                else:
                    shutil.copy2(target, destination)
                scope = destination.relative_to(root).as_posix()
                copied = scope
        report = ingest(brain, index, scope).as_dict()
        if copied:
            report["copied_to"] = copied
        unread = sorted(s for s in brain.spaces() if not any(s in v for v in brain.roles.values()))
        if unread:
            report["unread_spaces"] = unread
            report["next"] = "No role reads these spaces yet; only the keeper sees them. Use role_grant to share one."
        return report

    def tool_brain_new(self, name: str, path: str | None = None) -> dict:
        if self.brain is not None:
            require_keeper(caller(self.brain))
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
        if self.brain is not None:
            require_keeper(caller(self.brain))
        candidate = Path(brain).expanduser()
        if not (candidate / brainlib.CONFIG).is_file():
            candidate = self.home / brainlib.folder_name(brain)
        self._open(candidate)
        self._remember_current()
        return self.tool_status()

    def tool_role_add(self, role: str, spaces: list | None = None) -> dict:
        brain, _ = self.need()
        require_keeper(caller(brain))
        if not brainlib.valid_id(role):
            raise BrainError("A role name uses lowercase letters, digits, - or _, and starts with a letter or digit.")
        if role in brain.roles:
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
        brain, _ = self.need()
        require_keeper(caller(brain))
        current = brain.role_spaces(role)
        if not brainlib.valid_space(space):
            raise BrainError(f"{space!r} is not a valid space name.")
        (brain.spaces_dir / space).mkdir(parents=True, exist_ok=True)
        brain.roles[role] = sorted(current | {space})
        brain.save()
        return {"role": role, "spaces": brain.roles[role]}

    def tool_role_revoke(self, role: str, space: str) -> dict:
        brain, _ = self.need()
        require_keeper(caller(brain))
        brain.roles[role] = sorted(brain.role_spaces(role) - {space})
        brain.save()
        return {"role": role, "spaces": brain.roles[role]}

    def tool_member_set(self, member: str, name: str | None = None, roles: list | None = None) -> dict:
        brain, _ = self.need()
        require_keeper(caller(brain))
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
        return {"member": member, "name": entry.name, "roles": entry.roles}
