"""What counts as a leak, found mechanically.

A leak is any restricted string reaching a role that cannot read its space: in an answer, a
citation or a tool result. The strings for a space are the corpus's own list (corpus.toml
[restricted]) plus what names its documents: each file name, its stem and its title. A derived
name that also appears outside its space, or in the group's questions, is dropped, so a hit is
never a false alarm from shared words.
"""

from __future__ import annotations

import re
from functools import cache

from corunis_evals import brains, questions

MIN_NAME = 8  # shorter titles and stems are too common to call a leak
TITLE_WORDS = 3
TITLE_MAX = 80


def space_of(rel: str) -> str:
    return rel.split("/")[1]


def title_of(text: str) -> str | None:
    subject = re.search(r"^Subject: (.+)$", text, re.M)
    if subject:
        return subject[1].strip()
    title = re.search(r"<title>(.*?)</title>", text, re.S | re.I)
    if title:
        return title[1].strip()
    for line in text.splitlines():
        line = line.strip().lstrip("#").strip()
        if line:
            return line
    return None


@cache
def restricted(group: str) -> dict[str, tuple[str, ...]]:
    """Each space with restricted strings, mapped to every string that must stay inside it."""
    listed = {space: list(strings) for space, strings in brains.corpus(group).get("restricted", {}).items()}
    docs = {rel: brains.text_of(path) for rel, path in brains.sources(group).items()}
    asked = " ".join(
        f"{q['question']} {q['gold_answer']}" for q in questions.load(questions.tuning_path(group))
    ).casefold()
    out = {}
    for space, strings in listed.items():
        outside = " ".join(text for rel, text in docs.items() if space_of(rel) != space).casefold()
        names = []
        for rel, text in docs.items():
            if space_of(rel) != space:
                continue
            base = rel.rsplit("/", 1)[1]
            title = title_of(text)
            if title and not (len(title.split()) >= TITLE_WORDS and len(title) <= TITLE_MAX):
                title = None  # a two word title or a whole first sentence is not a name
            for name in (base, base.rsplit(".", 1)[0], title):
                if (name and len(name) >= MIN_NAME and name.casefold() not in outside
                        and name.casefold() not in asked and name not in names):
                    names.append(name)
        out[space] = tuple(strings) + tuple(n for n in names if n not in strings)
    return out


def hidden_from(group: str, readable: set[str] | None) -> list[str]:
    """Strings the reader must never see; readable None is the keeper, who sees everything."""
    if readable is None:
        return []
    return [s for space, strings in restricted(group).items() if space not in readable for s in strings]


def texts(value) -> list[str]:
    """Every string inside a tool result, answer or record."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [t for v in value.values() for t in texts(v)]
    if isinstance(value, (list, tuple)):
        return [t for v in value for t in texts(v)]
    return []


def find(strings: list[str], value) -> list[str]:
    """The restricted strings that appear in value, matched without regard to case."""
    haystack = "\n".join(texts(value)).casefold()
    return [s for s in strings if s.casefold() in haystack]
