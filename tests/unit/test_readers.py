"""U8: every reader returns text with a title and the date the writer gave (FT-04 to FT-07)."""

from pathlib import Path

import pytest

from app.readers.common import find_date
from app.readers.files import html_to_text, read_file, supported
from contracts.errors import DeskThreadError, ErrorCode
from contracts.items import Item, ItemKind


def _read(root: Path, rel: str, role: str = "") -> list[Item]:
    return read_file(root / rel, "test", rel, 2026, role)


def test_u8_notes_carry_the_writers_date_or_are_undated(demo_laptop: Path) -> None:
    recap = _read(demo_laptop, "App-exports/Notes/1on1-sam-recap-nov.md")[0]
    assert recap.kind is ItemKind.NOTE and recap.title == "1:1 Sam - recap"
    assert recap.date is not None and (recap.date.month, recap.date.day) == (11, 6)
    assert [u.number for u in recap.units] == list(range(1, len(recap.units) + 1))
    follow = _read(demo_laptop, "App-exports/Notes/follow-ups.md")[0]
    assert follow.date is not None and (follow.date.month, follow.date.day) == (10, 23)
    assert _read(demo_laptop, "App-exports/Notes/sam-fragment.md")[0].undated


def test_dates_come_only_from_what_the_writer_wrote() -> None:
    assert find_date("Fri 6 Nov 2026", 2026) == find_date("06/11/2026", 2026)
    assert find_date("Wednesday 4 November 2026, 14:00", 2025).year == 2026  # type: ignore[union-attr]
    assert find_date("23/10 - after 1:1", 2026).month == 10  # type: ignore[union-attr]
    assert find_date("more ownership?? course??", 2026) is None
    assert find_date("14/21 is not a date", 2026) is None


def test_u8_mail_has_sender_date_subject_and_body(demo_laptop: Path) -> None:
    mail = _read(demo_laptop, "App-exports/Mail/2026-11-10_RE_Sam_course_budget.eml")[0]
    assert mail.kind is ItemKind.MAIL and mail.date is not None and mail.date.day == 10
    assert mail.units[0].text == "Subject: RE: Course budget request - Sam"
    assert any("Budget approved up to 800" in u.text for u in mail.units)
    assert mail.meta["from"].endswith("<hr-learning@ukpharma.example>")


def test_u8_html_mail_is_text_only_and_scripts_are_dropped(demo_laptop: Path) -> None:
    news = _read(demo_laptop, "App-exports/Mail/2026-11-13_newsletter.eml")[0]
    text = "\n".join(u.text for u in news.units)
    assert "launch countdown" in text
    assert "tracker.example" not in text and "<" not in text and "fetch(" not in text
    assert html_to_text("<p>a</p><style>x{}</style><script>bad()</script>b").split() == ["a", "b"]


def test_u8_calendar_events_have_start_time_and_attendees(demo_laptop: Path) -> None:
    events = _read(demo_laptop, "App-exports/Calendar/work.ics")
    assert len(events) == 12 and all(e.kind is ItemKind.EVENT for e in events)
    one = next(e for e in events if e.title == "1:1 Sam" and e.date and e.date.day == 23)
    assert one.date is not None and (one.date.hour, one.date.minute) == (10, 0)
    assert one.meta["attendees"] == "Sam"


def test_u8_reminders_carry_open_or_done_and_a_due_date(demo_laptop: Path) -> None:
    reminders = _read(demo_laptop, "App-exports/Reminders/work-reminders.txt", "reminders")
    assert len(reminders) == 5 and {r.meta["status"] for r in reminders} == {"open", "done"}
    intro = next(r for r in reminders if "Mark" in r.title)
    assert intro.meta["status"] == "open" and intro.date is not None and intro.date.day == 27
    assert intro.units[0].text.endswith("[open]") and intro.meta["list"] == "Work"


def test_u8_documents_word_pdf_and_csv(demo_laptop: Path) -> None:
    pdf = _read(demo_laptop, "Downloads/hr-learning-budget-policy.pdf")[0]
    docx = _read(demo_laptop, "OneDrive - UK Pharma/Shared/hr-learning-budget-policy.docx")[0]
    for doc in (pdf, docx):
        assert doc.kind is ItemKind.DOCUMENT
        assert any("up to 800 GBP" in u.text for u in doc.units)
    csv = _read(demo_laptop, "Documents/Work/budget-tracker-2026.csv")[0]
    assert any(u.text.startswith("line: Training") for u in csv.units)


def test_u8_chat_exports_and_transcripts(demo_laptop: Path) -> None:
    slack = _read(demo_laptop, "App-exports/Slack/saved-items.txt", "chat")[0]
    assert slack.kind is ItemKind.CHAT and any("Dev lead intro" in u.text for u in slack.units)
    assert _read(demo_laptop, "App-exports/Zoom/2026-11-12_team-sync.vtt")[0].kind is ItemKind.CHAT


def test_u8_an_image_has_no_text_until_the_model_reads_it(demo_laptop: Path) -> None:
    image = _read(demo_laptop, "Desktop/office-plant.png")[0]
    assert image.kind is ItemKind.IMAGE and image.units == ()
    assert image.meta["reading"] == "pending"


def test_u8_unsupported_and_broken_files_raise_a_code(demo_laptop: Path, tmp_path: Path) -> None:
    assert not supported(demo_laptop / "Desktop/IMG_2041.heic")
    with pytest.raises(DeskThreadError) as err:
        _read(demo_laptop, "Desktop/IMG_2041.heic")
    assert err.value.code is ErrorCode.UNSUPPORTED_TYPE
    (tmp_path / "broken.docx").write_bytes(b"not a zip file")
    (tmp_path / "broken.pdf").write_bytes(b"%PDF-1.4 broken")
    for name in ("broken.docx", "broken.pdf"):
        with pytest.raises(DeskThreadError) as err:
            _read(tmp_path, name)
        assert err.value.code is ErrorCode.READ_FAILED
