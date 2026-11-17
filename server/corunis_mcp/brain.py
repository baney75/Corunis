"""The brain folder: brain.toml, spaces/, notes/ and the .corunis/ index cache.

brain.toml holds the brain's name, its keeper, its members and which roles read which spaces.
Corunis writes it; a keeper may also edit it by hand, so reads tolerate missing tables.
"""

from __future__ import annotations

import json
import os
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

CONFIG = "brain.toml"
SPACES = "spaces"
NOTES = "notes"
CACHE = ".corunis"
INDEX = "index.sqlite"

# Notes saved without a space go here. It is never a folder under spaces/ (folders starting
# with a dot are skipped), and only the keeper reads it.
KEEPER_NOTES = ".keeper"
DEFAULT_SPACE = "everyone"
DEFAULT_ROLE = "member"

ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,39}$")


class BrainError(Exception):
    """A request the brain cannot carry out; the message is shown to the caller as is."""


def valid_id(value: str) -> bool:
    return bool(ID.match(value or ""))


def valid_space(name: str) -> bool:
    return (
        bool(name)
        and name == name.strip()
        and not name.startswith(".")
        and "/" not in name
        and "\\" not in name
        and len(name) <= 80
    )


@dataclass
class Member:
    id: str
    name: str = ""
    roles: list[str] = field(default_factory=list)


@dataclass
class Brain:
    root: Path
    name: str
    keeper: str
    roles: dict[str, list[str]]
    members: dict[str, Member]

    @property
    def spaces_dir(self) -> Path:
        return self.root / SPACES

    @property
    def notes_dir(self) -> Path:
        return self.root / NOTES

    @property
    def index_path(self) -> Path:
        return self.root / CACHE / INDEX

    def spaces(self) -> list[str]:
        """Every space: each folder under spaces/ plus any a role names before it has files."""
        found = set()
        if self.spaces_dir.is_dir():
            found = {p.name for p in self.spaces_dir.iterdir() if p.is_dir() and valid_space(p.name)}
        for spaces in self.roles.values():
            found.update(spaces)
        return sorted(found)

    def role_spaces(self, role: str) -> set[str]:
        if role not in self.roles:
            raise BrainError(f"There is no role named {role!r}. Roles: {', '.join(sorted(self.roles)) or 'none'}.")
        return set(self.roles[role])

    def save(self) -> None:
        lines = [
            "# Corunis brain. Corunis writes this file through chat; you can also edit it by hand.",
            f"name = {_q(self.name)}",
            f"keeper = {_q(self.keeper)}",
            "",
        ]
        for role in sorted(self.roles):
            lines += [f"[roles.{role}]", f"spaces = {_list(sorted(self.roles[role]))}", ""]
        for member_id in sorted(self.members):
            member = self.members[member_id]
            lines += [f"[members.{member_id}]", f"name = {_q(member.name)}", f"roles = {_list(sorted(member.roles))}", ""]
        _write_atomic(self.root / CONFIG, "\n".join(lines))


def _q(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _list(values: list[str]) -> str:
    return "[" + ", ".join(_q(v) for v in values) + "]"


def _write_atomic(path: Path, text: str) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def load(root: Path) -> Brain:
    path = root / CONFIG
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise BrainError(f"{root} is not a brain: it has no {CONFIG}.") from None
    except tomllib.TOMLDecodeError as error:
        raise BrainError(f"{path} is not valid TOML: {error}") from None
    roles: dict[str, list[str]] = {}
    for role, table in (data.get("roles") or {}).items():
        spaces = table.get("spaces", []) if isinstance(table, dict) else []
        roles[role] = [s for s in spaces if isinstance(s, str) and valid_space(s)]
    members: dict[str, Member] = {}
    for member_id, table in (data.get("members") or {}).items():
        table = table if isinstance(table, dict) else {}
        member_roles = [r for r in table.get("roles", []) if isinstance(r, str)]
        members[member_id] = Member(member_id, str(table.get("name", "")), member_roles)
    keeper = str(data.get("keeper") or "keeper")
    members.setdefault(keeper, Member(keeper, "Keeper", []))
    return Brain(root=root, name=str(data.get("name") or root.name), keeper=keeper, roles=roles, members=members)


def create(root: Path, name: str) -> Brain:
    if (root / CONFIG).exists():
        raise BrainError(f"A brain already exists at {root}.")
    (root / SPACES / DEFAULT_SPACE).mkdir(parents=True, exist_ok=True)
    (root / NOTES).mkdir(exist_ok=True)
    (root / CACHE).mkdir(exist_ok=True)
    brain = Brain(
        root=root,
        name=name,
        keeper="keeper",
        roles={DEFAULT_ROLE: [DEFAULT_SPACE]},
        members={"keeper": Member("keeper", "Keeper", [])},
    )
    brain.save()
    return brain


def folder_name(name: str) -> str:
    """A safe folder name for a brain called `name`, keeping its words."""
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", name).strip().strip(".")
    if not cleaned:
        raise BrainError("Give the brain a name with at least one letter or digit.")
    return cleaned[:80]
