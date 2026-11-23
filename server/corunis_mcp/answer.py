"""Check a whole answer: split it into sentences, read each sentence's citations, keep only supported ones.

The model never says which sentences are claims; every sentence is checked. Citation forms:

    The vigil Mass is at 5:00 pm [p0123456789abcde "vigil Mass is at 5:00 pm"].
    Both bids total 79,650 dollars [derived 79,650] [p0123456789abcde "61,250 dollars"; pfedcba987654321 "18,400 dollars"].

A sentence stands only when it has at least one citation, every bracket in it is a citation or a
`[derived ...]` marker, every quote is in its passage on whole words, and every number, date and
proper name in the sentence appears in the union of its quotes. Numbers are compared as whole
values with their unit or am/pm, so 5:00 am is not 5:00 pm. A value marked `[derived ...]` is
exempt only when a sum, difference, product, ratio or count of the numbers in its quotes, or the
days between two of their dates, gives it. The fixed abstention sentence needs no citation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from itertools import combinations, permutations
from math import prod

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
CITATIONS = re.compile(rf"\s*{CITATION.pattern}(?:\s*[;,]\s*{CITATION.pattern})*\s*[;,]?\s*")
VALUE = r"\d+(?:,\d{3})*(?:\.\d+)?"
DERIVED = re.compile(rf"\s*derived\s*:?\s*({VALUE}(?:(?:\s*;\s*|\s*,\s+|\s+){VALUE})*)\s*", re.I)
LIST_MARK = re.compile(r"^\s*(?:[-*\u2022]|\d+[.)])\s+")
SENTENCE_END = re.compile(r"[.!?]+[\"')]*\s+")
ABBREVIATIONS = {"st", "mr", "mrs", "ms", "dr", "fr", "sr", "jr", "rev", "mt", "no", "vs", "etc", "e.g", "i.e", "a.m", "p.m", "inc", "co", "msgr", "dept"}

WORD_NUMBERS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
    "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16,
    "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
    "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90, "hundred": 100, "thousand": 1000, "million": 1_000_000,
}
_WORDS = "|".join(sorted(WORD_NUMBERS, key=len, reverse=True))
# A number in digits or words, with a leading $ or a unit or am/pm after it.
FACT = re.compile(
    rf"(?P<dollar>\$\s*)?(?:(?P<digits>\d+(?:[.,:/]\d+)*)|\b(?P<words>(?:{_WORDS})(?:[\s-]+(?:{_WORDS}))*)\b)"
    r"(?:\s*(?P<unit>%|[ap]\.?m\b\.?|(?:percent|dollars?|usd|days?|hours?|minutes?|weeks?|months?|years?)\b))?",
    re.I,
)
UNITS = {"%": "percent", "percent": "percent", "dollar": "dollars", "usd": "dollars", "am": "am", "pm": "pm"}
# "one" as a pronoun, not a count: "no one", "the one", "one of".
PRONOUN_ONE_BEFORE = re.compile(r"\b(?:no|any|each|every|some|the|this|that|which|someone|anyone)\s+$", re.I)
MONTHS = {m: i for i, m in enumerate(
    "january february march april may june july august september october november december".split(), 1)}
DATE = re.compile(rf"\b({'|'.join(MONTHS)})\s+(\d{{1,2}})(?:,?\s+(\d{{4}}))?\b", re.I)
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


def word_value(words: str) -> int:
    total = current = 0
    for word in re.split(r"[\s-]+", words.casefold()):
        number = WORD_NUMBERS[word]
        if number == 100:
            current = max(current, 1) * 100
        elif number >= 1000:
            total += max(current, 1) * number
            current = 0
        else:
            current += number
    return total + current


def facts(text: str) -> list[tuple[str, str, str | None]]:
    """Every number in the text as (as written, value, unit): 5 pm is ("5 pm", "5:00", "pm")."""
    out = []
    for match in FACT.finditer(text):
        words = match.group("words")
        if words and words.casefold() == "one" and (
            PRONOUN_ONE_BEFORE.search(text[:match.start()]) or re.match(r"\s+(?:of|another)\b", text[match.end("words"):], re.I)
        ):
            continue
        unit = match.group("unit")
        if unit:
            unit = unit.casefold().replace(".", "")
            unit = UNITS.get(unit, unit.removesuffix("s") + "s")
        elif match.group("dollar"):
            unit = "dollars"
        if words:
            value = str(word_value(words))
        else:
            value = match.group("digits").replace(",", "")
            if unit in ("am", "pm") and not re.search(r"[.:/]", value):
                value += ":00"
        shown = match.group(0).strip() if unit else (words or match.group("digits"))
        out.append((shown, value, unit))
    return out


def quote_in(quote: str, text: str) -> bool:
    """The normalized quote is in the normalized text on whole words: it cuts into no word or number."""
    head = r"(?<!\w)" + (r"(?<!\d[.,:/])" if quote[:1].isdigit() else "") if quote[:1].isalnum() else ""
    tail = r"(?!\w)" + (r"(?![.,:/]\d)" if quote[-1:].isdigit() else "") if quote[-1:].isalnum() else ""
    return re.search(head + re.escape(quote) + tail, text) is not None


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
    quoted = facts(joined)
    values = {value for _, value, _ in quoted}
    with_units = {(value, unit) for _, value, unit in quoted}
    quote_units = {unit for _, _, unit in quoted if unit}
    quote_words = set(re.findall(r"[^\W_]+", joined.casefold()))

    def computed(value: str, unit: str | None) -> bool:
        # A derived value is one the quotes do not state; a quoted number keeps its quoted unit.
        # A computed value's unit must be one its quotes use, or days counted between their dates.
        # Quotes with no numbers at all are left to underived(), which always rejects them.
        if value not in derived or value in values:
            return False
        return not values or unit is None or unit in quote_units or (unit == "days" and DATE.search(joined) is not None)

    missing = [
        shown for shown, value, unit in facts(sentence)
        if not computed(value, unit) and (value, unit) not in with_units and not (unit is None and value in values)
    ]
    missing += [w for w in names_in(sentence) if w.casefold() not in quote_words]
    return list(dict.fromkeys(missing))


def underived(derived: dict[str, str], quotes: list[str]) -> str | None:
    """Why a [derived ...] value does not follow from the numbers and dates its quotes give, or None."""
    if not derived:
        return None
    joined = " ".join(quotes)
    numbers = [float(value) for _, value, _ in facts(joined) if re.fullmatch(r"\d+(?:\.\d+)?", value)]
    days = []
    for year_month_day in DATE.findall(joined):
        month, day, year = year_month_day
        try:
            days.append(date(int(year or 2001), MONTHS[month.casefold()], int(day)))
        except ValueError:
            continue
    spans = {abs((a - b).days) + extra for a, b in combinations(days, 2) for extra in (0, 1)}
    if not numbers and not spans:
        return f"Its derived value {next(iter(derived.values()))} has no numbers in its quotes to come from."
    candidates = set(numbers) | spans | {float(len(numbers)), float(len(quotes))}
    few = numbers[:12]
    for size in range(2, len(few) + 1):
        candidates |= {sum(c) for c in combinations(few, size)}
    if few:
        candidates.add(prod(few))
    for a, b in permutations(numbers[:40], 2):
        candidates |= {a - b, a * b}
        if b:
            candidates |= {a / b, a / b * 100}
    for value, shown in derived.items():
        places = len(value.split(".")[1]) if "." in value else 0
        if not any(abs(c - float(value)) <= 0.5 * 10 ** -places + 1e-9 for c in candidates):
            return f"Its derived value {shown} does not follow from the numbers in its quotes."
    return None


@dataclass
class Sentence:
    raw: str
    text: str = ""
    citations: list[tuple[str, str]] = field(default_factory=list)
    derived: dict[str, str] = field(default_factory=dict)
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
            derived = DERIVED.fullmatch(inner)
            if derived:
                sentence.derived |= {n.replace(",", ""): n for n in re.findall(VALUE, derived.group(1))}
            elif CITATIONS.fullmatch(inner):
                sentence.citations.extend(CITATION.findall(inner))
            else:  # any other bracket is an uncited claim, even beside a good citation
                sentence.bad_brackets.append(inner)
        sentence.text = " ".join(BRACKET.sub(" ", sentence.raw).split())
    return [s for s in out if s.text.strip(" .!?;,") or s.citations]


def is_abstention(sentence: Sentence) -> bool:
    """The fixed abstention sentence, alone: any bracket on it (citation, derived marker or stray) disqualifies it."""
    return not BRACKET.search(sentence.raw) and normalize(sentence.text).rstrip(".") == normalize(NO_ANSWER).rstrip(".")
