"""Who is asking, and which spaces they may read. v0 answers the keeper alone and fails closed.

A Local Studio Remote session runs on the host with the session's own tools, so no plugin can
keep a member out of the brain folder. Member access waits for the core to give a signed caller
identity that says whether a session is local or Remote, and member sessions limited to Corunis's
own tools (baney75/local-studio issue #8). Until then every tool refuses any caller that is not
the keeper in a session on the host, decided by `calling_session`, the one identity source:

- a call whose `_meta` carries any caller or Remote marker is refused (a claim to be the keeper
  is not trusted until the core strips forged values);
- CORUNIS_SESSION=remote is refused;
- while Local Studio Remote serves on this computer (a `local-studio serve` process runs), or
  when that cannot be checked, no session can be told apart from a Remote one, so all are refused.

The keeper may "ask as" a role to see what it would see. That can only lower what the caller
sees, never raise it.
"""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from corunis_mcp import brain as brainlib
from corunis_mcp.brain import Brain, BrainError

KEEPER = "keeper"
REFUSED = "Corunis v0 answers only the keeper, in a session on the brain's own computer."
REMOTE_ON = (
    " Local Studio Remote is serving on this computer, and Corunis cannot yet tell a Remote session"
    " from a local one, so it answers no one until Remote stops."
)


class NotServed(BrainError):
    """The caller is not the keeper on the host; every tool refuses."""


@dataclass(frozen=True)
class Caller:
    member: str
    keeper: bool
    roles: tuple[str, ...]
    spaces: frozenset[str]
    as_role: str | None = None


def process_commands() -> list[list[str]]:
    """Every running process's argv. Raises OSError when it cannot be read."""
    if sys.platform.startswith("linux"):
        commands = []
        for entry in Path("/proc").iterdir():
            if entry.name.isdigit():
                try:
                    raw = (entry / "cmdline").read_bytes()
                except OSError:
                    continue  # the process ended, or belongs to someone we cannot see
                commands.append([part.decode(errors="replace") for part in raw.split(b"\0") if part])
        return commands
    if sys.platform == "win32":
        out = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True, text=True, timeout=10, check=True)
        # tasklist shows image names only, so any Local Studio process counts as possibly serving.
        return [["local-studio", "serve"] for line in out.stdout.splitlines() if line.lower().startswith('"local-studio')]
    out = subprocess.run(["ps", "-axww", "-o", "command="], capture_output=True, text=True, timeout=10, check=True)
    return [line.split() for line in out.stdout.splitlines() if line.strip()]


def remote_serving() -> bool:
    """True when Local Studio Remote serves on this machine, or when that cannot be checked."""
    try:
        commands = process_commands()
    except (OSError, subprocess.SubprocessError):
        return True
    for argv in commands:
        if argv and Path(argv[0]).name.removesuffix(".exe") == "local-studio" and "serve" in argv[1:]:
            return True
    return False


def calling_session(meta: dict | None = None) -> str:
    """The one identity source: the calling member's id, or NotServed. Today: the keeper or nobody."""
    meta = meta if isinstance(meta, dict) else {}
    if meta.get("caller") or meta.get("remote") or os.environ.get("CORUNIS_SESSION", "").strip().lower() == "remote":
        raise NotServed(REFUSED)
    if remote_serving():
        raise NotServed(REFUSED + REMOTE_ON)
    return KEEPER


def keeper_view(brain: Brain) -> Caller:
    return Caller(brain.keeper, True, (KEEPER,), frozenset(brain.spaces()) | {brainlib.LINKED})


def lower(who: Caller, brain: Brain, role: str) -> Caller:
    """The view of `role`, refused unless it sees no more than `who` already does."""
    spaces = frozenset(brain.role_spaces(role))
    if not spaces <= who.spaces:
        raise BrainError("Ask as can only lower what you see, and that role reads spaces you cannot.")
    return Caller(who.member, False, (role,), spaces, role)


def caller(brain: Brain, member: str, as_role: str | None = None) -> Caller:
    """The view for a member that calling_session let through."""
    if member != KEEPER:
        raise NotServed(REFUSED)
    who = keeper_view(brain)
    return lower(who, brain, as_role) if as_role else who


def require_keeper(who: Caller) -> None:
    if not who.keeper:
        raise BrainError("Only the keeper can do that.")
