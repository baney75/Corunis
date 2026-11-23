"""Build a brain folder from a corpus under evals/corpora/<group>/.

A corpus is authored as text so every document can be read and reviewed in a diff:

    corpus.toml         the group's name, the date for undated files, and the restricted strings
    brain.toml.in       the brain.toml template; {{KEEPER_CALLER}} is filled when the brain is built
    spaces/<space>/...  the documents. `name.docx.src` becomes `name.docx` and `name.pdf.src`
                        becomes `name.pdf`; every other file is copied as is.

A `.docx.src` holds paragraphs separated by blank lines; a paragraph whose every line has " | "
is a table, one row per line. A `.pdf.src` holds pages separated by a line with a form feed
alone; each line is a line of text, wrapped at 90 characters.

Each built file's modified time is the date in its name (2026-03-14 or 2026-03), else the
corpus's default date, so the server's passage dates match what the documents say.
"""

from __future__ import annotations

import os
import re
import shutil
import tomllib
import zipfile
from calendar import timegm
from io import BytesIO
from pathlib import Path
from textwrap import wrap
from xml.sax.saxutils import escape

from corunis_evals import EVALS

CORPORA = EVALS / "corpora"
QUESTIONS = EVALS / "questions"
GROUPS = ("family", "parish", "business", "class")
PLACEHOLDER = "{{KEEPER_CALLER}}"
SOURCES = {".docx.src": ".docx", ".pdf.src": ".pdf"}
DATE_IN_NAME = re.compile(r"(20\d\d)-(0[1-9]|1[0-2])(?:-(0[1-9]|[12]\d|3[01]))?(?!\d)")
YEAR_IN_NAME = re.compile(r"(?<!\d)(20\d\d)(?!\d)")
PAGE_BREAK = "\f"
PDF_WIDTH = 90


def corpus_dir(group: str) -> Path:
    if group not in GROUPS:
        raise ValueError(f"unknown group {group!r}; groups: {', '.join(GROUPS)}")
    return CORPORA / group


def corpus(group: str) -> dict:
    return tomllib.loads((corpus_dir(group) / "corpus.toml").read_text(encoding="utf-8"))


def roles(group: str) -> dict[str, set[str]]:
    """Each role and the spaces it reads, from the brain template."""
    text = (corpus_dir(group) / "brain.toml.in").read_text(encoding="utf-8").replace(PLACEHOLDER, "local:0")
    return {role: set(table.get("spaces", [])) for role, table in tomllib.loads(text).get("roles", {}).items()}


def built_name(source: str) -> str:
    for suffix, out in SOURCES.items():
        if source.endswith(suffix):
            return source[: -len(suffix)] + out
    return source


def sources(group: str) -> dict[str, Path]:
    """Every document as it will sit in the built brain (spaces/<space>/...), mapped to its source file."""
    root = corpus_dir(group)
    found = {}
    for path in sorted((root / "spaces").rglob("*")):
        if path.is_file() and not path.name.startswith("."):
            rel = path.relative_to(root).as_posix()
            found[built_name(rel)] = path
    return found


def text_of(path: Path) -> str:
    """A source file's text, for checks over the corpus (restricted strings, quotes, dashes)."""
    return path.read_text(encoding="utf-8")


def date_of(name: str, default: str) -> tuple[int, int, int]:
    match = DATE_IN_NAME.search(name)
    if match:
        return int(match[1]), int(match[2]), int(match[3] or 1)
    year, month, day = (int(part) for part in default.split("-"))
    match = YEAR_IN_NAME.search(name)
    if match and int(match[1]) != year:  # sitter-pay-2025.txt dates to 2025's start; a name with this year keeps the default
        return int(match[1]), 1, 1
    return year, month, day


def docx_bytes(text: str) -> bytes:
    """A minimal valid DOCX: one paragraph per block, and a table for a block whose every line has " | "."""
    body = []
    for block in re.split(r"\n\s*\n", text.strip()):
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if lines and all(" | " in line for line in lines):
            rows = "".join(
                "<w:tr>" + "".join(f"<w:tc><w:p><w:r><w:t>{escape(cell.strip())}</w:t></w:r></w:p></w:tc>"
                                   for cell in line.split(" | ")) + "</w:tr>"
                for line in lines
            )
            body.append(f"<w:tbl>{rows}</w:tbl>")
        elif lines:
            body.append(f'<w:p><w:r><w:t xml:space="preserve">{escape(" ".join(lines))}</w:t></w:r></w:p>')
    w = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
    document = f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document {w}><w:body>{"".join(body)}</w:body></w:document>'
    types = (
        '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        "</Types>"
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
        "</Relationships>"
    )
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in (("[Content_Types].xml", types), ("_rels/.rels", rels), ("word/document.xml", document)):
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))  # same bytes on every build
            archive.writestr(info, data, zipfile.ZIP_DEFLATED)
    return buffer.getvalue()


def pdf_bytes(text: str) -> bytes:
    """A minimal valid PDF, one Helvetica text block per page; text must be ASCII."""

    def esc(line: str) -> str:
        return line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    pages = []
    for page in text.strip("\n").split("\n" + PAGE_BREAK + "\n"):
        lines: list[str] = []
        for line in page.splitlines():
            lines.extend(wrap(line, PDF_WIDTH) or [""])
        pages.append(lines)
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>"]
    kids = " ".join(f"{4 + 2 * i} 0 R" for i in range(len(pages)))
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>".encode())
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    for i, lines in enumerate(pages):
        content = "BT /F1 10 Tf 54 750 Td 13 TL " + " ".join(f"({esc(line)}) Tj T*" for line in lines) + " ET"
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 3 0 R >> >>"
            f" /Contents {5 + 2 * i} 0 R >>".encode()
        )
        objects.append(f"<< /Length {len(content)} >>\nstream\n{content}\nendstream".encode("ascii"))
    out = b"%PDF-1.4\n"
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    out += b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets)
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return out


def build(group: str, dest: Path, keeper_caller: str) -> Path:
    """Write the group's brain folder at dest (replacing what is there) and return it. Not ingested."""
    if not keeper_caller.startswith("local:"):
        raise ValueError("the keeper caller is Local Studio's local:<uid>")
    info = corpus(group)
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    template = (corpus_dir(group) / "brain.toml.in").read_text(encoding="utf-8")
    (dest / "brain.toml").write_text(template.replace(PLACEHOLDER, keeper_caller), encoding="utf-8")
    for space in roles_spaces(group):
        (dest / "spaces" / space).mkdir(parents=True, exist_ok=True)
    for rel, source in sources(group).items():
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if rel.endswith(".docx") and source.name.endswith(".docx.src"):
            target.write_bytes(docx_bytes(text_of(source)))
        elif rel.endswith(".pdf") and source.name.endswith(".pdf.src"):
            target.write_bytes(pdf_bytes(text_of(source)))
        else:
            target.write_bytes(source.read_bytes())
        year, month, day = date_of(target.name, info["default_date"])
        stamp = timegm((year, month, day, 12, 0, 0))
        os.utime(target, (stamp, stamp))
    return dest


def roles_spaces(group: str) -> set[str]:
    spaces = set()
    for readable in roles(group).values():
        spaces |= readable
    spaces |= {p.name for p in (corpus_dir(group) / "spaces").iterdir() if p.is_dir()}
    return spaces
