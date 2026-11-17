"""Who is asking, and which spaces they may read.

Local Studio does not yet tell a plugin's MCP server which member is calling
(baney75/local-studio issue #8). Until it does, every call comes from the keeper, and the keeper
can pass `as_role` to see exactly what a role would see. When the core gives a signed member
identity, replace `calling_member` and nothing else.
"""

from __future__ import annotations

from dataclasses import dataclass

from corunis_mcp import brain as brainlib
from corunis_mcp.brain import Brain, BrainError


@dataclass(frozen=True)
class Caller:
    member: str
    keeper: bool
    roles: tuple[str, ...]
    spaces: frozenset[str]
    as_role: str | None = None


def calling_member(brain: Brain) -> str:
    """The member id of the session that made this call. Today: always the keeper."""
    return brain.keeper


def caller(brain: Brain, as_role: str | None = None) -> Caller:
    member_id = calling_member(brain)
    member = brain.members.get(member_id)
    keeper = member_id == brain.keeper
    if as_role:
        if not keeper:
            raise BrainError("Only the keeper can ask as a role.")
        return Caller(member_id, False, (as_role,), frozenset(brain.role_spaces(as_role)), as_role)
    if keeper:
        return Caller(member_id, True, ("keeper",), frozenset(brain.spaces()) | {brainlib.KEEPER_NOTES})
    roles = tuple(r for r in (member.roles if member else []) if r in brain.roles)
    spaces: set[str] = set()
    for role in roles:
        spaces |= set(brain.roles[role])
    return Caller(member_id, False, roles, frozenset(spaces))


def require_keeper(who: Caller) -> None:
    if not who.keeper:
        raise BrainError("Only the keeper can do that.")
