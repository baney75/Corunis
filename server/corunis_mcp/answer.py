"""Check a whole answer: split it into sentences, read each sentence's citations, keep only supported ones.

The model never says which sentences are claims; every sentence is checked. Citation forms:

    The vigil Mass is at 5:00 pm [p0123456789abcde "vigil Mass is at 5:00 pm"].
    Both bids total 79,650 dollars [derived 79,650] [p0123456789abcde "61,250 dollars"; pfedcba987654321 "18,400 dollars"].

A sentence stands only when it has at least one citation, every quote is in its passage, and every
number, date and proper name in the sentence appears in the union of its quotes. A value marked
`[derived ...]` is exempt itself, but the inputs it comes from must be cited. The fixed abstention
sentence needs no citation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

NO_ANSWER = "The documents I can see don't answer this."
MIN_QUOTE = 4
MAX_ANSWER = 20_000

QUOTE_MAP = str.maketrans({
    "\u2018": "'", "\u2019": "'", "\u201a": "'", "\u201b": "'",
    "\u201c": '"', "\u201d": '"', "\u201e": '"', "\u201f": '"',
    "\u2010": "-", "\u2011": "-", "\u2012": "-", "\u2013": "-", "\u2014": "-", "\u2212": "-",
    "\u00a0": " ", "\u2026": "...",
})

BRACKET = re.compile(r"\[([^\[\]]*)\]")
CITATION = re.compile(r"(p[0-9a-f]{15})\s*:?\s*\"([^\"]*)\"")
DERIVED = re.compile(r"^\s*derived\b[:\s]*(.*)$", re.I | re.S)
LIST_MARK = re.compile(r"^\s*(?:[-*\u2022]|\d+[.)])\s+")
SENTENCE_END = re.compile(r"[.!?]+[\"')]*\s+")
ABBREVIATIONS = {"st", "mr", "mrs", "ms", "dr", "fr", "sr", "jr", "rev", "mt", "no", "vs", "etc", "e.g", "i.e", "a.m", "p.m", "inc", "co", "msgr", "dept"}

NUMBER = re.compile(r"\d+(?:[.,:/]\d+)*")
WORD_NUMBERS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
    "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16,
    "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
    "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90, "hundred": 100,
}
# Capitalized words that are not names: sentence starters and question words.
NOT_NAMES = frozenset(
    """
    a an the this that these those there here it its they their we our you your he she his her i yes no not
    and but or so if when where what which who whom whose why how both each every all any some none
    also according based per in on at for from to of by with as after before during until since about
    total together combined overall sum difference however sure okay meanwhile then than
    is are was were be been will would can could should may might must do does did has have had
    """.split()
)


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


def numbers_in(text: str) -> set[str]:
    found = {n.replace(",", "") for n in NUMBER.findall(text)}
    found |= {str(WORD_NUMBERS[w]) for w in re.findall(r"[a-z]+", text.casefold()) if w in WORD_NUMBERS}
    return found


def names_in(text: str) -> list[str]:
    """Capitalized words: proper names, months and days."""
    names: list[str] = []
    for word in re.findall(r"[^\W\d_]+", text):
        if word[0].isupper() and word.casefold() not in NOT_NAMES and word not in names:
            names.append(word)
    return names


def unsupported_facts(sentence: str, quotes: list[str], derived: set[str]) -> list[str]:
    """Numbers, dates and names the sentence states that none of its quotes contain."""
    joined = " ".join(quotes)
    quote_numbers = numbers_in(joined)
    quote_words = set(re.findall(r"[^\W_]+", joined.casefold()))
    missing = [n for n in NUMBER.findall(sentence) if n.replace(",", "") not in quote_numbers | derived]
    missing += [w for w in names_in(sentence) if w.casefold() not in quote_words]
    return list(dict.fromkeys(missing))


@dataclass
class Sentence:
    raw: str
    text: str = ""
    citations: list[tuple[str, str]] = field(default_factory=list)
    derived: set[str] = field(default_factory=set)
    bad_brackets: list[str] = field(default_factory=list)


def sentences(answer: str) -> list[Sentence]:
    """Split an answer into sentences on line breaks and sentence ends, never inside a citation."""
    answer = answer.translate(QUOTE_MAP)[:MAX_ANSWER]
    out: list[Sentence] = []
    for line in answer.split("\n"):
        line = LIST_MARK.sub("", line)
        brackets: list[str] = []

        def mask(match: re.Match) -> str:
            brackets.append(match.group(0))
            return f"\x00{len(brackets) - 1}\x00"

        masked = BRACKET.sub(mask, line)
        pieces: list[str] = []
        cursor = 0
        for end in SENTENCE_END.finditer(masked):
            before = masked[cursor:end.start()].rstrip()
            last = re.split(r"\s", before)[-1].casefold().strip("(\"'") if before else ""
            after = masked[end.end():end.end() + 1]
            if last in ABBREVIATIONS or re.fullmatch(r"[a-z]", last) or (after and after.islower()):
                continue
            pieces.append(masked[cursor:end.end()])
            cursor = end.end()
        pieces.append(masked[cursor:])
        for piece in pieces:
            restored = re.sub(r"\x00(\d+)\x00", lambda m: brackets[int(m.group(1))], piece).strip()
            if not restored:
                continue
            bare = BRACKET.sub("", restored).strip(" .!?;,")
            if not bare and out:  # a citation that trails its sentence's period belongs to that sentence
                out[-1].raw += " " + restored
                continue
            out.append(Sentence(restored))
    for sentence in out:
        for inner in BRACKET.findall(sentence.raw):
            derived = DERIVED.match(inner)
            if derived:
                sentence.derived |= {n.replace(",", "") for n in NUMBER.findall(derived.group(1))}
                continue
            found = CITATION.findall(inner)
            if found:
                sentence.citations.extend(found)
            else:
                sentence.bad_brackets.append(inner)
        sentence.text = " ".join(BRACKET.sub(" ", sentence.raw).split())
    return [s for s in out if s.text.strip(" .!?;,") or s.citations]


def is_abstention(sentence: Sentence) -> bool:
    return not sentence.citations and normalize(sentence.text).rstrip(".") == normalize(NO_ANSWER).rstrip(".")
