"""Read the brain's files into the index. Only new or changed files are read again."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from corunis_mcp import brain as brainlib
from corunis_mcp.brain import Brain
from corunis_mcp.extract import Unit, Unsupported, decode, extract, frontmatter
from corunis_mcp.index import Index
from corunis_mcp.passages import split


@dataclass
class Report:
    added: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    unchanged: int = 0
    removed: list[str] = field(default_factory=list)
    skipped: list[dict] = field(default_factory=list)
    failed: list[dict] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "added": len(self.added),
            "updated": len(self.updated),
            "unchanged": self.unchanged,
            "removed": len(self.removed),
            "skipped": self.skipped,
            "failed": self.failed,
            "files": {"added": self.added, "updated": self.updated, "removed": self.removed},
        }


def hidden(parts: tuple[str, ...]) -> bool:
    return any(part.startswith((".", "~$")) for part in parts)


def in_scope(rel: str, scope: str) -> bool:
    return not scope or rel == scope or rel.startswith(scope + "/")


def files(brain: Brain, scope: str) -> list[tuple[Path, str]]:
    """(file, its brain-relative path) for every document file in scope, sorted."""
    found = []
    for top in (brain.spaces_dir, brain.notes_dir):
        if not top.is_dir():
            continue
        for path in top.rglob("*"):
            rel = path.relative_to(brain.root)
            if not path.is_file() or hidden(rel.parts) or not in_scope(rel.as_posix(), scope):
                continue
            if rel.parts[0] == brainlib.SPACES and len(rel.parts) < 3:
                continue  # a loose file directly under spaces/ belongs to no space
            found.append((path, rel.as_posix()))
    return sorted(found, key=lambda item: item[1])


def space_of(rel: str, note_fields: dict[str, str] | None) -> str:
    parts = rel.split("/")
    if parts[0] == brainlib.SPACES:
        return parts[1]
    space = (note_fields or {}).get("space", "").strip()
    return space if brainlib.valid_space(space) else brainlib.KEEPER_NOTES


def ingest(brain: Brain, index: Index, scope: str = "") -> Report:
    """Index every file whose brain-relative path is `scope` or under it ("" for the whole brain)."""
    report = Report()
    seen: set[str] = set()
    for path, rel in files(brain, scope):
        seen.add(rel)
        stat = path.stat()
        known = index.doc(rel)
        if known is not None and known[4] == stat.st_mtime_ns and known[5] == stat.st_size:
            report.unchanged += 1
            continue
        raw = path.read_bytes()
        version = hashlib.sha256(raw).hexdigest()[:16]
        if known is not None and known[3] == version:
            index.touch(rel, stat.st_mtime_ns, stat.st_size)
            report.unchanged += 1
            continue
        modified = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).date().isoformat()
        note_fields = None
        try:
            if rel.startswith(brainlib.NOTES + "/"):
                note_fields, body = frontmatter(decode(raw))
                units = [Unit(body.strip())]
                modified = note_fields.get("date", modified)[:10] or modified
            else:
                units = extract(path)
        except Unsupported as reason:
            index.put(rel, space_of(rel, None), version, stat.st_mtime_ns, stat.st_size, modified, [], str(reason))
            report.skipped.append({"file": rel, "reason": str(reason)})
            continue
        except Exception as error:  # noqa: BLE001 - one bad file must not stop the rest
            message = f"could not read it ({type(error).__name__}: {error})"
            index.put(rel, space_of(rel, None), version, stat.st_mtime_ns, stat.st_size, modified, [], message)
            report.failed.append({"file": rel, "reason": message})
            continue
        _, passages = split(units, rel, version)
        index.put(rel, space_of(rel, note_fields), version, stat.st_mtime_ns, stat.st_size, modified, passages)
        (report.updated if known is not None else report.added).append(rel)
    for rel in index.doc_paths(scope):
        if rel not in seen and in_scope(rel, scope):
            index.remove(rel)
            report.removed.append(rel)
    return report
