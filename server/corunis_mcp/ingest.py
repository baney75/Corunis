"""Read the brain's files into the index. Only new or changed files are read again.

A file's space is the folder it sits in under spaces/, so moving a file between spaces is a
removal at the old path and an addition at the new one. `sync` runs before every read tool, so
the index follows the folder before the next search.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from corunis_mcp import brain as brainlib
from corunis_mcp.brain import Brain
from corunis_mcp.extract import Unsupported, extract
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


def in_scope(rel: str, scope: str) -> bool:
    return not scope or rel == scope or rel.startswith(scope + "/")


@dataclass
class Found:
    """One real file and every path in the brain that reaches it."""

    file: Path
    mtime_ns: int
    size: int
    paths: list[str]
    spaces: list[str]
    space: str

    def key(self) -> tuple[int, int, str, str]:
        return self.mtime_ns, self.size, json.dumps(self.paths), self.space


MAX_DEPTH = 40


def walk(brain: Brain) -> tuple[dict[str, Found], list[dict]]:
    """Every document file in a space, keyed by its real brain-relative path, and the links skipped.

    Symlinked files and folders are followed, so a file reachable from several spaces (by a
    symlink, an alias that is a symlink, or a hard link) is one entry with all its paths, placed
    in the most restrictive of their spaces. Links that lead outside spaces/ are skipped.
    """
    root = Path(os.path.realpath(brain.root))
    spaces_root = root / brainlib.SPACES
    groups: dict[tuple[int, int], dict] = {}
    skipped: list[dict] = []
    if not brain.spaces_dir.is_dir():
        return {}, skipped
    stack: list[tuple[str, str, frozenset]] = [(str(brain.spaces_dir), brainlib.SPACES, frozenset())]
    while stack:
        folder, rel_folder, ancestors = stack.pop()
        try:
            entries = list(os.scandir(folder))
        except OSError:
            continue
        for entry in entries:
            if entry.name.startswith((".", "~$")):
                continue
            rel = f"{rel_folder}/{entry.name}"
            try:
                info = os.stat(entry.path)
            except OSError:
                continue  # a dangling link
            real = Path(os.path.realpath(entry.path))
            if real != spaces_root and spaces_root not in real.parents:
                skipped.append({"file": rel, "reason": "it links outside the brain's spaces folder"})
                continue
            real_rel = real.relative_to(root).as_posix()
            if any(part.startswith((".", "~$")) for part in real_rel.split("/")):
                continue
            if stat.S_ISDIR(info.st_mode):
                node = (info.st_dev, info.st_ino)
                if node not in ancestors and len(ancestors) < MAX_DEPTH:
                    stack.append((entry.path, rel, ancestors | {node}))
            elif stat.S_ISREG(info.st_mode) and rel.count("/") >= 2 and real_rel.count("/") >= 2:
                group = groups.setdefault((info.st_dev, info.st_ino), {"paths": set(), "reals": set(), "info": info})
                group["paths"].update((rel, real_rel))
                group["reals"].add(real_rel)
    found: dict[str, Found] = {}
    for group in groups.values():
        paths = sorted(group["paths"])
        spaces = sorted({path.split("/")[1] for path in paths})
        space = brain.most_restrictive(set(spaces))
        # Name a hard-linked file by its path in the space it is placed in, when it has one there.
        key = min(group["reals"], key=lambda real: (real.split("/")[1] != space, real))
        info = group["info"]
        found[key] = Found(root / key, info.st_mtime_ns, info.st_size, paths, spaces, space)
    return found, skipped


def sync(brain: Brain, index: Index) -> Report | None:
    """Re-ingest when any file was added, moved, linked, changed or removed, or a role changed placement."""
    found, skipped = walk(brain)
    if {rel: f.key() for rel, f in found.items()} == index.snapshot():
        return None
    return ingest(brain, index, found=(found, skipped))


def ingest(brain: Brain, index: Index, scope: str = "", found: tuple | None = None) -> Report:
    """Index every file whose real brain-relative path is `scope` or under it ("" for the whole brain)."""
    report = Report()
    every, skipped = found if found is not None else walk(brain)
    files = {rel: f for rel, f in every.items() if in_scope(rel, scope)}
    report.skipped.extend(s for s in skipped if in_scope(s["file"], scope))
    known_all = index.snapshot()
    for rel in sorted(files):
        f = files[rel]
        if known_all.get(rel) == f.key():
            report.unchanged += 1
            continue
        known = index.doc(rel)
        raw = f.file.read_bytes()
        version = hashlib.sha256(raw).hexdigest()[:16]
        paths, spaces = json.dumps(f.paths), json.dumps(f.spaces)
        if known is not None and known[3] == version and known_all[rel][2:] == f.key()[2:]:
            index.touch(rel, f.mtime_ns, f.size)
            report.unchanged += 1
            continue
        modified = datetime.fromtimestamp(f.mtime_ns / 1e9, tz=timezone.utc).date().isoformat()
        try:
            units = extract(f.file)
        except Unsupported as reason:
            index.put(rel, f.space, version, f.mtime_ns, f.size, modified, [], str(reason), paths, spaces)
            report.skipped.append({"file": rel, "reason": str(reason)})
            continue
        except Exception as error:  # noqa: BLE001 - one bad file must not stop the rest
            message = f"could not read it ({type(error).__name__}: {error})"
            index.put(rel, f.space, version, f.mtime_ns, f.size, modified, [], message, paths, spaces)
            report.failed.append({"file": rel, "reason": message})
            continue
        _, passages = split(units, rel, version)
        index.put(rel, f.space, version, f.mtime_ns, f.size, modified, passages, None, paths, spaces)
        (report.updated if known is not None else report.added).append(rel)
    for rel in index.doc_paths(scope):
        if rel not in files and in_scope(rel, scope):
            index.remove(rel)
            report.removed.append(rel)
    return report
