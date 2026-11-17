"""A synthetic parish brain for tests. Every name, figure and event here is invented.

Three spaces (everyone, council, staff) and three roles:
    member  reads everyone
    council reads everyone and council
    staff   reads everyone and staff
Files of every supported format are written by code, so the repo holds no binary fixtures.
"""

from __future__ import annotations

import os
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

FIXED_TIME = 1_790_000_000  # 2026-09-21, so two copies of the brain have identical dates

ROLES = {"member": ["everyone"], "council": ["council", "everyone"], "staff": ["everyone", "staff"]}
SPACES = ["council", "everyone", "staff"]

BRAIN_TOML = """name = "St. Brigid Parish"
keeper = "keeper"

[roles.member]
spaces = ["everyone"]

[roles.council]
spaces = ["council", "everyone"]

[roles.staff]
spaces = ["everyone", "staff"]

[members.keeper]
name = "Parish Office"
roles = []

[members.hollis]
name = "Ada Hollis"
roles = ["council"]
"""

BULLETIN = """# St. Brigid Parish Bulletin, October 5

## Mass times

The Saturday vigil Mass is at 5:00 pm. Sunday Masses are at 8:00 am and 10:30 am. Confessions are heard on Saturday from 3:30 pm to 4:30 pm in the side chapel.

## Parish picnic

The parish picnic is on Saturday, October 18, at Larkfield Commons from noon to 4:00 pm. Bring a side dish to share. The Knights will grill, and there will be a pie contest judged by the youth group.

## Food pantry

The food pantry needs volunteers on Tuesday evenings to sort donations. Peanut butter, canned tuna and cereal are the items most needed this month.
"""

SCHEDULE_HTML = """<!doctype html>
<html><head><title>Weekday schedule</title><style>p { color: red; }</style>
<script>var secret = "this script text must never be indexed";</script></head>
<body>
<h1>Weekday Mass and devotions</h1>
<p>Weekday Mass is celebrated Monday through Friday at 7:00 am in the chapel.</p>
<p>Eucharistic adoration is held every Thursday from 7:00 pm to 8:00 pm &amp; ends with Benediction.</p>
<table><tr><td>Holy day vigil</td><td>6:30 pm</td></tr><tr><td>Holy day morning</td><td>9:00 am</td></tr></table>
</body></html>
"""

HANDBOOK = [
    "Volunteer Handbook",
    "Every volunteer who works with children completes a background check before their first shift.",
    "Safe environment training must be renewed every two years. The parish office tracks renewal dates.",
    "Building keys are signed out from the parish office and returned by the last Sunday of each month.",
    "The parish office is open Monday through Thursday from 9:00 am to 3:00 pm.",
]

RETREAT_PDF = [
    ["Youth Retreat at Camp Wrenwood", "November 14 to 16 for students in grades 8 to 12."],
    ["The retreat costs 85 dollars per student, and scholarships are available.", "Permission slips are due November 1."],
]

ANNOUNCEMENTS_MBOX = """From office@stbrigid.example Mon Sep 29 10:00:00 2026
From: Parish Office <office@stbrigid.example>
To: Parish List <list@stbrigid.example>
Subject: Choir rehearsal moved
Date: Mon, 29 Sep 2026 10:00:00 -0500

Choir rehearsal moves to Wednesday at 7:15 pm in the music room for the rest of the fall.

From office@stbrigid.example Tue Sep 30 09:00:00 2026
From: Parish Office <office@stbrigid.example>
To: Parish List <list@stbrigid.example>
Subject: Snow closures
Date: Tue, 30 Sep 2026 09:00:00 -0500
Content-Type: text/html; charset=utf-8

<p>When the Brookvale school district closes for snow, the parish office also closes.</p>
<p>Weekend Masses go on unless the pastor posts a cancellation by 6:00 am.</p>
"""

MINUTES = """Parish Council Minutes, September 9

Present: Ada Hollis (chair), Rowan Pell, Imogen Sato, Father Lucan Ferry. Absent: Desmond Achebe.

The chair opened the meeting with a prayer at 7:02 pm. The minutes of the August meeting were approved as written.

Facilities. The council reviewed three bids to replace the boiler in the school building. """ + " ".join(
    f"Bid note {n}: the contractor visited the boiler room, measured the flue, and reviewed the age of the existing unit."
    for n in range(1, 16)
) + """

Decision. The council approved replacing the boiler with Sterling Mechanical for 18,400 dollars, to be paid from the building reserve. Work begins after the heating season ends in April.

Finance. Rowan Pell reported that weekly collections are four percent above last year. The council asked the finance committee to prepare the 2027 budget draft for October.

The next council meeting is October 14 at 7:00 pm in the parish hall. The meeting closed with a prayer at 8:41 pm.
"""

BUDGET = [
    "Proposed 2027 Operating Budget",
    "The finance committee proposes the following lines for council review.",
    [["Line", "Amount"], ["Utilities", "42,000 dollars"], ["Building repairs", "25,000 dollars"], ["Youth ministry", "9,500 dollars"]],
    "The proposal holds staff costs flat and draws nothing from the building reserve.",
]

ROOF_EML = """From: Rowan Pell <rowan@stbrigid.example>
To: Parish Council <council@stbrigid.example>
Subject: Roof bid from Ardent Roofing
Date: Fri, 3 Oct 2026 16:20:00 -0500

Ardent Roofing bid 61,250 dollars to replace the church roof over the north transept. The bid holds until January 31.
"""

PAYROLL = """Payroll notes, fall

Marisol Quintero, office manager, receives a raise to 23.50 dollars per hour effective January 1.

Gideon Farrow, maintenance lead, moves from part time to full time on November 1.
"""

LEAVE_EML = """From: Gideon Farrow <gideon@stbrigid.example>
To: Parish Office <office@stbrigid.example>
Subject: Leave request
Date: Mon, 6 Oct 2026 08:15:00 -0500

I am asking for medical leave from November 3 to December 12 for knee surgery at Linden Valley Hospital.
"""

STAFF_POLICY = """# Staff policy

Full time staff earn ten sick days each year. Unused sick days carry over up to a limit of twenty.
"""

# Questions and the document that answers them, for calibration and role tests.
ANSWERABLE = [
    ("What time is the Saturday vigil Mass?", "spaces/everyone/bulletin-2026-10-05.md"),
    ("When is the parish picnic and where?", "spaces/everyone/bulletin-2026-10-05.md"),
    ("What does the food pantry need this month?", "spaces/everyone/bulletin-2026-10-05.md"),
    ("When is eucharistic adoration?", "spaces/everyone/weekday-schedule.html"),
    ("How often must safe environment training be renewed?", "spaces/everyone/volunteer-handbook.docx"),
    ("When are building keys returned?", "spaces/everyone/volunteer-handbook.docx"),
    ("Where is choir rehearsal held now?", "spaces/everyone/announcements.mbox"),
    ("Does the parish office close for snow?", "spaces/everyone/announcements.mbox"),
    ("Who will replace the boiler and for how much?", "spaces/council/minutes-2026-09.txt"),
    ("When is the next council meeting?", "spaces/council/minutes-2026-09.txt"),
    ("How much is budgeted for youth ministry in 2027?", "spaces/council/budget-2027.docx"),
    ("What did Ardent Roofing bid for the church roof?", "spaces/council/roof-bid.eml"),
    ("What is Marisol Quintero's new hourly pay?", "spaces/staff/payroll-notes.txt"),
    ("When is Gideon Farrow on medical leave?", "spaces/staff/leave-request.eml"),
    ("How many sick days do full time staff earn?", "spaces/staff/staff-policy.md"),
]
PDF_ANSWERABLE = [("How much does the youth retreat cost?", "spaces/everyone/youth-retreat.pdf")]

UNANSWERABLE = [
    "Who won the regional chess tournament last spring?",
    "What is the capital of Australia?",
    "How many parking spaces does the cathedral downtown have?",
    "What is the wifi password for the guest network?",
    "Which hymnal publisher did the music director choose?",
    "What color will the new carpet in the rectory be?",
    "Who is the bishop's secretary?",
    "When does the bowling league start?",
]

# For each restricted space: questions whose only answer sits there.
RESTRICTED = {
    "staff": ["What is Marisol Quintero's new hourly pay?", "When is Gideon Farrow on medical leave?",
              "How many sick days do full time staff earn?"],
    "council": ["What did Ardent Roofing bid for the church roof?", "How much is budgeted for youth ministry in 2027?",
                "Who will replace the boiler and for how much?"],
}


def docx_bytes(blocks: list) -> bytes:
    """A minimal valid DOCX. A block is a paragraph string or a table (list of rows of cells)."""
    w = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
    body = []
    for block in blocks:
        if isinstance(block, str):
            body.append(f"<w:p><w:r><w:t>{escape(block)}</w:t></w:r></w:p>")
        else:
            rows = "".join(
                "<w:tr>" + "".join(f"<w:tc><w:p><w:r><w:t>{escape(c)}</w:t></w:r></w:p></w:tc>" for c in row) + "</w:tr>"
                for row in block
            )
            body.append(f"<w:tbl>{rows}</w:tbl>")
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
    from io import BytesIO

    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", types)
        archive.writestr("_rels/.rels", rels)
        archive.writestr("word/document.xml", document)
    return buffer.getvalue()


def pdf_bytes(pages: list[list[str]]) -> bytes:
    """A minimal valid PDF with one Helvetica text block per page."""

    def esc(text: str) -> str:
        return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    objects = [b"<< /Type /Catalog /Pages 2 0 R >>"]
    kids = " ".join(f"{4 + 2 * i} 0 R" for i in range(len(pages)))
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>".encode())
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    for i, lines in enumerate(pages):
        content = "BT /F1 12 Tf 72 720 Td 16 TL " + " ".join(f"({esc(line)}) Tj T*" for line in lines) + " ET"
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 3 0 R >> >>"
            f" /Contents {5 + 2 * i} 0 R >>".encode()
        )
        objects.append(f"<< /Length {len(content)} >>\nstream\n{content}\nendstream".encode())
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


FILES: dict[str, str | bytes] = {
    "spaces/everyone/bulletin-2026-10-05.md": BULLETIN,
    "spaces/everyone/weekday-schedule.html": SCHEDULE_HTML,
    "spaces/everyone/volunteer-handbook.docx": docx_bytes(HANDBOOK),
    "spaces/everyone/youth-retreat.pdf": pdf_bytes(RETREAT_PDF),
    "spaces/everyone/announcements.mbox": ANNOUNCEMENTS_MBOX,
    "spaces/council/minutes-2026-09.txt": MINUTES,
    "spaces/council/budget-2027.docx": docx_bytes(BUDGET),
    "spaces/council/roof-bid.eml": ROOF_EML,
    "spaces/staff/payroll-notes.txt": PAYROLL,
    "spaces/staff/leave-request.eml": LEAVE_EML,
    "spaces/staff/staff-policy.md": STAFF_POLICY,
}


def write_parish(root: Path, leave_out: set[str] = frozenset()) -> Path:
    """Write the parish brain under root (without its index) and return root."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "brain.toml").write_text(BRAIN_TOML, encoding="utf-8")
    (root / "notes").mkdir(exist_ok=True)
    for space in SPACES:
        (root / "spaces" / space).mkdir(parents=True, exist_ok=True)
    for rel, content in FILES.items():
        if rel in leave_out:
            continue
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content.encode("utf-8") if isinstance(content, str) else content)
        os.utime(path, (FIXED_TIME, FIXED_TIME))
    return root
