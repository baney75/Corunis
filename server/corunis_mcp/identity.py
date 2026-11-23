"""Who is asking, and which spaces they may read. v0 answers the keeper alone and fails closed.

Local Studio names the caller of every session's server in LOCAL_STUDIO_CALLER, set by the core
and never by the model: `local:<uid>` for a thread started on the host, `device:<id>` for one a
paired device started through Remote (local-studio docs/plugins.md, "Caller identity"). v0 serves
only the keeper's own `local:` caller, recorded in brain.toml when the brain is made, and refuses
a `device:` caller, any other caller and a missing one. `calling_session` is the one identity
source:

- a call whose `_meta` carries any caller or Remote marker is refused (only the core names callers);
- CORUNIS_SESSION=remote is refused;
- a caller that is not `local:` is refused before any tool runs, and a `local:` caller that is not
  the brain's recorded keeper is refused before any brain is read.

A Remote session still runs on the host with the session's own tools, including bash, so it could
read the brain folder directly; no plugin can close that. Member access waits for member sessions
limited to Corunis's own tools (local-studio#3) and the per-session sandbox (local-studio#33).

The keeper may "ask as" a role to see what it would see. That can only lower what the caller
sees, never raise it.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from corunis_mcp import brain as brainlib
from corunis_mcp.brain import Brain, BrainError

KEEPER = "keeper"
REFUSED = "Corunis v0 answers only the keeper, in a session on the brain's own computer."
NO_CALLER = " Local Studio did not name a caller for this session, so Corunis cannot tell who is asking."
NOT_KEEPER = " This session's caller is not the keeper this brain was made by."
NO_KEEPER_CALLER = " This brain records no keeper caller; make it again with brain_new in Local Studio."


class NotServed(BrainError):
    """The caller is not the keeper on the host; every tool refuses."""


@dataclass(frozen=True)
class Caller:
    member: str
    keeper: bool
    roles: tuple[str, ...]
    spaces: frozenset[str]
    as_role: str | None = None


def calling_session(meta: dict | None = None) -> str:
    """The one identity source: the session's `local:` caller from Local Studio, or NotServed."""
    meta = meta if isinstance(meta, dict) else {}
    if meta.get("caller") or meta.get("remote") or os.environ.get("CORUNIS_SESSION", "").strip().lower() == "remote":
        raise NotServed(REFUSED)
    named = os.environ.get("LOCAL_STUDIO_CALLER", "").strip()
    if not named:
        raise NotServed(REFUSED + NO_CALLER)
    if not named.startswith("local:") or len(named) == len("local:"):
        raise NotServed(REFUSED)
    return named


def keeper_view(brain: Brain) -> Caller:
    return Caller(brain.keeper, True, (KEEPER,), frozenset(brain.spaces()) | {brainlib.LINKED})


def lower(who: Caller, brain: Brain, role: str) -> Caller:
    """The view of `role`, refused unless it sees no more than `who` already does."""
    spaces = frozenset(brain.role_spaces(role))
    if not spaces <= who.spaces:
        raise BrainError("Ask as can only lower what you see, and that role reads spaces you cannot.")
    return Caller(who.member, False, (role,), spaces, role)


def caller(brain: Brain, member: str, as_role: str | None = None) -> Caller:
    """The view for the session caller that calling_session let through: the keeper's, or NotServed."""
    if not brain.keeper_caller:
        raise NotServed(REFUSED + NO_KEEPER_CALLER)
    if member != brain.keeper_caller:
        raise NotServed(REFUSED + NOT_KEEPER)
    who = keeper_view(brain)
    return lower(who, brain, as_role) if as_role else who


def require_keeper(who: Caller) -> None:
    if not who.keeper:
        raise BrainError("Only the keeper can do that.")
