"""Build the invented demo laptop folder (FT-29). Same bytes on every run (test D3).

    uv run python demo-data/make_demo_data.py                 # writes ./demo-laptop
    uv run python demo-data/make_demo_data.py --out DIR --canary STRING

Everything is invented (see content.py). The folder is a build output and is not committed.
With --canary, the string is planted in one note, one mail and the key image, for the leak
tests (D5): a copy of it found anywhere else on disk afterwards means something leaked.
"""

import argparse
import hashlib
import io
import os
import re
import shutil
import sys
import zipfile
from datetime import UTC, datetime
from email.message import EmailMessage
from pathlib import Path
from xml.sax.saxutils import escape

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).parent))
import content
import content_more

# A file is dated by its own changed-time (user, 2026-11-22). Each demo file gets the time
# of the date written in it; a file with no date in it gets this one, two days before the
# day the demo plays on, so it does not turn up under "today".
EXPORT_TIME = datetime(2026, 11, 20, 18, 0, tzinfo=UTC).timestamp()
CANARY_NOTE = f"{content.NOTES}/qbr-prep.md"
CANARY_MAIL = "2026-11-04_expenses_approved.eml"
FONT_PATHS = ("/System/Library/Fonts/Helvetica.ttc", "/Library/Fonts/Arial.ttf")


def _eml(sender: str, to: str, subject: str, date: str, body: str, html: bool = False) -> bytes:
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"], msg["Date"] = sender, to, subject, date
    digest = hashlib.sha256((subject + date).encode()).hexdigest()[:16]
    msg["Message-ID"] = f"<{digest}@ukpharma.example>"
    msg.set_content(body, subtype="html" if html else "plain")
    return msg.as_bytes()


def _ics(name: str, events: list[tuple[str, str, str, int, tuple[str, ...]]]) -> str:
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//DeskThread demo//EN",
        f"X-WR-CALNAME:{name}",
    ]
    for uid, title, start, minutes, people in events:
        lines += [
            "BEGIN:VEVENT",
            f"UID:{uid}@ukpharma.example",
            f"DTSTART;TZID=Europe/London:{start}",
            f"DURATION:PT{minutes}M",
            f"SUMMARY:{title}",
            "ORGANIZER;CN=Seoyeon:mailto:seoyeon@ukpharma.example",
        ]
        lines += [f"ATTENDEE;CN={p}:mailto:{p.lower()}@ukpharma.example" for p in people]
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def _docx(title: str, lines: list[str]) -> bytes:
    """A minimal Word file: a zip with three XML parts, fixed timestamps."""
    ns = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    paragraphs = "".join(
        f'<w:p><w:r><w:t xml:space="preserve">{escape(t)}</w:t></w:r></w:p>'
        for t in [title, *lines]
    )
    parts = {
        "[Content_Types].xml": (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" '
            'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/word/document.xml" ContentType="application/vnd.'
            'openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>'
        ),
        "_rels/.rels": (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/'
            '2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>'
        ),
        "word/document.xml": (
            '<?xml version="1.0" encoding="UTF-8"?>'
            f'<w:document xmlns:w="{ns}"><w:body>{paragraphs}</w:body></w:document>'
        ),
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, xml in parts.items():
            zf.writestr(zipfile.ZipInfo(name, date_time=(2026, 11, 22, 18, 0, 0)), xml)
    return buf.getvalue()


def _pdf(title: str, lines: list[str]) -> bytes:
    """A minimal one-page PDF with plain text, written by hand so no library is needed."""

    def esc(text: str) -> str:
        return text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")

    ops = ["BT", "/F1 12 Tf", "72 760 Td", "16 TL"]
    ops += [f"({esc(t)}) Tj T*" for t in [title, "", *lines]]
    ops.append("ET")
    stream = "\n".join(ops).encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    out += b"".join(b"%010d 00000 n \n" % o for o in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objects) + 1,
        xref,
    )
    return bytes(out)


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in FONT_PATHS:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _image(lines: list[str], suffix: str) -> bytes:
    """A typed-screenshot style image, or a plain picture when there is no text."""
    img = Image.new("RGB", (1000, 520), "#FBFAF5" if lines else "#7FB48A")
    draw = ImageDraw.Draw(img)
    if lines:
        draw.rectangle((0, 0, 1000, 56), fill="#E9E6DC")  # a notes-style title bar
        for i, colour in enumerate(("#FF5F57", "#FEBC2E", "#28C840")):
            draw.ellipse((20 + i * 26, 20, 36 + i * 26, 36), fill=colour)
        for i, line in enumerate(lines):
            draw.text((48, 96 + i * 78), line, fill="#1B1B1B", font=_font(40 if i == 0 else 34))
    else:
        draw.ellipse((380, 140, 620, 380), fill="#2F6B3F")  # a shape, no text at all
        draw.rectangle((470, 360, 530, 470), fill="#8A5A2B")
    buf = io.BytesIO()
    if suffix == ".png":
        img.save(buf, format="PNG")
    else:
        img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def _add_more(out: dict[str, bytes]) -> None:
    """The second layer of the story (content_more.py). It never replaces a file of the first."""

    def put(path: str, data: bytes) -> None:
        assert path not in out, f"{path} is already in the demo laptop"
        out[path] = data

    for path, text in {
        **content_more.NOTE_FILES,
        **content_more.CHAT_FILES,
        **content_more.REMINDER_FILES,
        **content_more.DOC_FILES,
    }.items():
        put(path, text.encode("utf-8"))
    for name, sender, to, subject, date, body in content_more.MAILS_MORE:
        put(f"{content.MAIL}/{name}", _eml(sender, to, subject, date, body))
    for path, (title, lines) in content_more.DOCX_FILES.items():
        put(path, _docx(title, lines))
    for path, (title, lines) in content_more.PDF_FILES.items():
        put(path, _pdf(title, lines))
    for path, lines in content_more.IMAGES_MORE.items():
        put(path, _image(lines, Path(path).suffix))


def files(canary: str | None = None, rich: bool = False) -> dict[str, bytes]:
    """Every file of the demo laptop as path -> bytes, in a fixed order. `rich` adds the
    second layer of the story (content_more.py); the tests and the evaluation use the first."""
    out: dict[str, bytes] = {}
    for path, text in content.TEXT_FILES.items():
        if canary and path == CANARY_NOTE:
            text += f"- ref {canary}\n"
        out[path] = text.encode("utf-8")
    for name, sender, to, subject, date, body in content.MAILS:
        if canary and name == CANARY_MAIL:
            body += f"Reference: {canary}\n"
        out[f"{content.MAIL}/{name}"] = _eml(sender, to, subject, date, body)
    out[f"{content.MAIL}/{content.NEWSLETTER_NAME}"] = _eml(
        "UK Pharma Weekly <newsletter@ukpharma.example>",
        "UK all staff <all@ukpharma.example>",
        "UK Pharma Weekly: launch countdown",
        "Fri, 13 Nov 2026 07:30:00 +0000",
        content.NEWSLETTER_HTML,
        html=True,
    )
    extra = content_more.WORK_EVENTS_MORE if rich else []
    out["App-exports/Calendar/work.ics"] = _ics("Work", [*content.WORK_EVENTS, *extra]).encode()
    out["App-exports/Calendar/personal.ics"] = _ics("Personal", content.PERSONAL_EVENTS).encode()
    out["Downloads/hr-learning-budget-policy.pdf"] = _pdf(
        content.HR_POLICY_TITLE, content.HR_POLICY_LINES
    )
    out["OneDrive - UK Pharma/Shared/hr-learning-budget-policy.docx"] = _docx(
        content.HR_POLICY_TITLE, content.HR_POLICY_LINES
    )
    out["Documents/Work/team-plan-q1-2027.docx"] = _docx(
        content.TEAM_PLAN_TITLE, content.TEAM_PLAN_LINES
    )
    for path, lines in content.IMAGES.items():
        if canary and path == content.SCREENSHOT_KEY:
            lines = [*lines, canary]
        out[path] = _image(lines, Path(path).suffix)
    out.update(content.UNSUPPORTED)
    if rich:
        _add_more(out)
    return dict(sorted(out.items()))


def _written(path: Path) -> float | None:
    """Noon of the date written at the top of a note or document, as the app's own reader
    finds it; None when the file names no date or is not a note or document."""
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from app.readers.files import read_file

    try:
        items = read_file(path, "demo", path.name, 2026)
    except Exception:  # noqa: BLE001  # a format the reader does not take: no date
        return None
    day = next((i.meta["written"] for i in items if i.meta.get("written")), None)
    return datetime.fromisoformat(f"{day}T12:00:00+00:00").timestamp() if day else None


SHOT = re.compile(r"Screenshot (\d{4})-(\d\d)-(\d\d) at (\d\d)\.(\d\d)\.(\d\d)")


def _stamp(rel: str, path: Path) -> float:
    """The file time of a demo file: a time given for it, the time in a screenshot's name,
    the noon of the date written in it, or the export time."""
    if rel in content_more.FILE_TIMES:
        return datetime(*content_more.FILE_TIMES[rel], tzinfo=UTC).timestamp()
    shot = SHOT.search(rel)
    if shot:
        year, month, day, hour, minute, second = map(int, shot.groups())
        return datetime(year, month, day, hour, minute, second, tzinfo=UTC).timestamp()
    return _written(path) or EXPORT_TIME


def build(root: Path, canary: str | None = None, rich: bool = False) -> dict[str, str]:
    """Write the folder (replacing an earlier build) and return path -> sha256."""
    if root.exists():
        marker = root / ".deskthread-demo"
        if not marker.exists():
            raise SystemExit(
                f"refusing to replace {root}: it is not a demo folder built by this script"
            )
        shutil.rmtree(root)
    root.mkdir(parents=True)
    (root / ".deskthread-demo").write_text("Invented demo data. Safe to delete.\n")
    hashes: dict[str, str] = {}
    for rel, data in files(canary, rich).items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        stamp = _stamp(rel, path)
        os.utime(path, (stamp, stamp))
        hashes[rel] = hashlib.sha256(data).hexdigest()
    return hashes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--out", type=Path, default=Path("demo-laptop"))
    parser.add_argument("--canary", default=None)
    parser.add_argument("--core", action="store_true", help="only the first layer (65 files)")
    args = parser.parse_args()
    hashes = build(args.out, args.canary, rich=not args.core)
    combined = hashlib.sha256("".join(f"{p}:{h}\n" for p, h in hashes.items()).encode()).hexdigest()
    print(f"built {len(hashes)} files in {args.out}  sha256 {combined[:16]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
