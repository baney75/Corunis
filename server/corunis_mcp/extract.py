"""Turn a file into plain text units. A unit is a page (PDF), a message (email) or the whole file.

Standard library only, except PDF, which needs the optional pypdf package (BSD). Without it,
PDFs are listed as skipped with the reason, never guessed at.
"""

from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass
from email import policy
from email.parser import BytesParser
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree

try:  # Optional extra: PDF text.
    import pypdf  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - depends on the host
    pypdf = None

MAX_FILE = 100 * 1024 * 1024
MAX_XML = 64 * 1024 * 1024

TEXT = {".txt", ".text", ".md", ".markdown"}
HTML = {".html", ".htm"}
DOCX = {".docx"}
PDF = {".pdf"}
MAIL = {".eml", ".mbox"}
SUPPORTED = TEXT | HTML | DOCX | PDF | MAIL


@dataclass
class Unit:
    text: str
    page: int | None = None


class Unsupported(Exception):
    """The file type is not read in this version; the message says why."""


def pdf_available() -> bool:
    return pypdf is not None


def extract(path: Path) -> list[Unit]:
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED:
        raise Unsupported(f"{suffix or 'files without an extension'} is not a supported type")
    if path.stat().st_size > MAX_FILE:
        raise Unsupported("larger than 100 MB")
    if suffix in TEXT:
        return [Unit(decode(path.read_bytes()))]
    if suffix in HTML:
        return [Unit(html_text(decode(path.read_bytes())))]
    if suffix in DOCX:
        return [Unit(docx_text(path))]
    if suffix in PDF:
        return pdf_units(path)
    if suffix == ".eml":
        return [Unit(message_text(path.read_bytes()))]
    return [Unit(message_text(raw)) for raw in mbox_messages(path.read_bytes())]


def decode(raw: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return normalize_newlines(raw.decode(encoding))
        except UnicodeDecodeError:
            continue
    return normalize_newlines(raw.decode("latin-1"))


def normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


BLOCK_TAGS = {
    "p", "div", "br", "li", "ul", "ol", "tr", "table", "section", "article", "header", "footer",
    "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "pre", "hr", "dd", "dt", "title",
}
SKIP_TAGS = {"script", "style", "head", "noscript", "template", "svg"}


class _HTMLText(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in SKIP_TAGS:
            self.skip += 1
        elif tag in BLOCK_TAGS:
            self.parts.append("\n\n")
        elif tag in {"td", "th"}:
            self.parts.append(" | ")

    def handle_endtag(self, tag: str) -> None:
        if tag in SKIP_TAGS:
            self.skip = max(0, self.skip - 1)
        elif tag in BLOCK_TAGS:
            self.parts.append("\n\n")

    def handle_data(self, data: str) -> None:
        if not self.skip:
            self.parts.append(data)


def html_text(markup: str) -> str:
    parser = _HTMLText()
    parser.feed(markup)
    parser.close()
    return tidy("".join(parser.parts))


def tidy(text: str) -> str:
    """Collapse runs of spaces inside lines and runs of blank lines, keeping paragraph breaks."""
    lines = [re.sub(r"[ \t ]+", " ", line).strip() for line in normalize_newlines(text).split("\n")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def docx_text(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        info = archive.getinfo("word/document.xml")
        if info.file_size > MAX_XML:
            raise Unsupported("its document.xml is larger than 64 MB")
        root = ElementTree.fromstring(archive.read(info))
    body = root.find(f"{W}body")
    if body is None:
        return ""
    blocks: list[str] = []
    for child in body:
        if child.tag == f"{W}p":
            blocks.append(_paragraph(child))
        elif child.tag == f"{W}tbl":
            for row in child.iter(f"{W}tr"):
                cells = [" ".join(_paragraph(p) for p in cell.iter(f"{W}p")).strip() for cell in row.iter(f"{W}tc")]
                blocks.append(" | ".join(cells))
    return tidy("\n\n".join(b for b in blocks if b.strip()))


def _paragraph(element: ElementTree.Element) -> str:
    parts: list[str] = []
    for node in element.iter():
        if node.tag == f"{W}t" and node.text:
            parts.append(node.text)
        elif node.tag == f"{W}tab":
            parts.append("\t")
        elif node.tag in {f"{W}br", f"{W}cr"}:
            parts.append("\n")
    return "".join(parts)


def pdf_units(path: Path) -> list[Unit]:
    if pypdf is None:
        raise Unsupported("PDF text needs the optional pypdf package, which is not installed")
    reader = pypdf.PdfReader(str(path))
    return [Unit(tidy(page.extract_text() or ""), number) for number, page in enumerate(reader.pages, start=1)]


def mbox_messages(raw: bytes) -> list[bytes]:
    """Split an mbox file on its "From " separator lines (mboxrd quoting is undone)."""
    raw = raw.replace(b"\r\n", b"\n")
    messages: list[bytes] = []
    current: list[bytes] | None = None
    previous_blank = True
    for line in raw.split(b"\n"):
        if line.startswith(b"From ") and previous_blank:
            if current is not None:
                messages.append(b"\n".join(current))
            current = []
        elif current is not None:
            current.append(re.sub(rb"^>(>*From )", rb"\1", line))
        previous_blank = line == b""
    if current is not None:
        messages.append(b"\n".join(current))
    return [m for m in messages if m.strip()]


def message_text(raw: bytes) -> str:
    message = BytesParser(policy=policy.default).parsebytes(raw)
    header = [f"{name}: {message[name]}" for name in ("From", "To", "Date", "Subject") if message[name]]
    body = message.get_body(preferencelist=("plain", "html"))
    text = ""
    if body is not None:
        try:
            content = body.get_content()
        except (LookupError, ValueError):
            content = body.get_payload(decode=True) or b""
            content = decode(content) if isinstance(content, bytes) else str(content)
        text = html_text(content) if body.get_content_type() == "text/html" else tidy(content)
    return tidy("\n".join(header) + "\n\n" + text)


FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n?", re.S)


def frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Split simple `key: value` frontmatter from a note. Returns (fields, body)."""
    match = FRONTMATTER.match(text)
    if not match:
        return {}, text
    fields = {}
    for line in match.group(1).split("\n"):
        key, sep, value = line.partition(":")
        if sep:
            fields[key.strip()] = value.strip().strip('"')
    return fields, text[match.end():]
