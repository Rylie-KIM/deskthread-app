"""Mac app connectors (FT-48, FT-49, FT-50, FT-52): read-only by construction (R2), scoped
to what the user ticked, and behind the broker. The app itself is replaced by canned replies
here; runs against the real apps are in tests/live and print counts only."""

import re
from pathlib import Path

import pytest

from app.broker import Broker
from app.meetings import upcoming
from app.sources.mac import FS, RS, SCRIPTS, MacAppAdapter, mac_apps
from app.store import SessionStore
from contracts.adapters import OsPermission, SourceAdapter
from contracts.errors import DeskThreadError, ErrorCode
from contracts.items import ItemKind, SourceKind
from tests.fakes import STORY_NOW

WRITE_VERBS = (
    "make", "delete", "save", "send", "move", "import", "duplicate", "close", "quit", "open",
    "print", "reply", "forward", "redirect", "show", "sync", "reload", "activate", "do shell",
    "keystroke", "click",
)  # fmt: skip


def _record(*fields: str) -> str:
    return FS.join(fields) + RS


class FakeApps:
    """Stands in for osascript: answers by which script is run, and records the arguments."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, list[str]]] = []
        self.refuse = False

    def __call__(self, script: str, args: list[str], timeout: float) -> str:
        name = next(k for k, v in SCRIPTS.items() if v == script)
        self.calls.append((name, args))
        if self.refuse:
            raise DeskThreadError(ErrorCode.OS_PERMISSION_MISSING)
        replies = {
            "calendar.list": _record("Work", "") + _record("Personal", ""),
            "calendar.read": _record("u1", "1:1 Sam", "2026-11-23T10:00:00", "2026-11-23T10:30:00", "", "Work")
            + _record("u2", "Team stand-up", "2026-11-23T09:30:00", "2026-11-23T09:45:00", "Sam, Alex, ", "Work"),
            "notes.list": _record("DeskThread Demo", "2") + _record("Private", "9"),
            "notes.read": _record("n1", "follow-ups", "2026-11-20T08:00:00",
                                  "follow-ups\n23/10 - after 1:1 w/ Sam\n- intro to Mark (Dev lead)", "DeskThread Demo")
            + _record("n2", "Sam - more ownership??", "2026-11-20T08:00:00", "Sam - more ownership?? course??", "DeskThread Demo"),
            "reminders.list": _record("Work", "2"),
            "reminders.read": _record("r1", "Intro Sam to Mark", "false", "2026-11-27T09:00:00", "", "Work")
            + _record("r2", "Email Sam about the course budget", "true", "", "", "Work"),
            "mail.list": _record("On My Mac / DeskThread Demo", "1") + _record("Work / INBOX", "13037"),
            "mail.read": _record("m1", "RE: Course budget request - Sam", "2026-11-10T11:24:00",
                                 "HR Learning <hr-learning@ukpharma.example>",
                                 "Hi Seoyeon,\nBudget approved up to 800 for Sam's online course.", "On My Mac / DeskThread Demo"),
        }  # fmt: skip
        return replies[name]


@pytest.fixture
def apps() -> FakeApps:
    return FakeApps()


def _on(adapter: MacAppAdapter, scopes: set[str]) -> SessionStore:
    broker = Broker()
    broker.register(adapter)
    store = SessionStore(broker)
    broker.grant(adapter.source_id, frozenset(scopes))
    store.load(adapter.source_id)
    return store


# ------------------------------------------------------------------ R2: read-only by construction


def test_r2_no_script_contains_a_command_that_writes_sends_or_deletes() -> None:
    assert len(SCRIPTS) == 8
    for name, script in SCRIPTS.items():
        code = re.sub(r'"[^"\n]*"', '""', script)  # words inside quoted text are not commands
        for verb in WRITE_VERBS:
            assert not re.search(rf"\b{verb}\b", code), f"{name} contains '{verb}'"
        for line in code.splitlines():
            if re.match(r"\s*set\b", line):
                # "set" may only fill one of the script's own variables, never an app's property
                assert re.match(r"\s*set [A-Za-z][A-Za-z0-9]* to ", line), f"{name}: {line.strip()}"
                assert re.match(r"\s*set (FS|RS|out|who|d1|d2|total|m) to ", line), line.strip()
        assert code.count("tell application") == 1


def test_r2_names_chosen_by_the_user_are_arguments_never_part_of_a_script(apps: FakeApps) -> None:
    nasty = 'Work" \n delete every event --'
    adapter = MacAppAdapter("calendar", SourceKind.CALENDAR, "Calendar", "/", apps)
    broker = Broker()
    broker.register(adapter)
    apps.calls.clear()
    list(adapter.read(type("G", (), {"source_id": "mac:calendar", "scope_ids": frozenset({nasty}),
                                    "cancelled": False, "raise_if_cancelled": lambda self: None})()))  # fmt: skip
    name, args = apps.calls[-1]
    assert name == "calendar.read" and args == [nasty]  # passed as data; the script is unchanged


# ------------------------------------------------------------------ each app


def test_calendar_only_the_ticked_calendar_and_a_one_to_one_names_its_person(
    apps: FakeApps, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DESKTHREAD_NOW", STORY_NOW)
    adapter = MacAppAdapter("calendar", SourceKind.CALENDAR, "Calendar", "/", apps)
    assert isinstance(adapter, SourceAdapter) and adapter.os_permission() is OsPermission.UNKNOWN
    assert [s.label for s in adapter.list_scopes()] == ["Personal", "Work"]
    assert adapter.os_permission() is OsPermission.GRANTED
    store = _on(adapter, {"Work"})
    assert apps.calls[-1] == ("calendar.read", ["Work"])  # the personal calendar is not asked for
    events = store.items()
    assert [e.kind for e in events] == [ItemKind.EVENT] * 2
    meetings = upcoming(events)
    assert [(m.title, m.person, m.start.hour) for m in meetings] == [("1:1 Sam", "Sam", 10)]


def test_notes_keep_the_writers_date_and_undated_stays_undated(apps: FakeApps) -> None:
    adapter = MacAppAdapter("notes", SourceKind.NOTES, "Notes", "/", apps)
    scopes = {s.label: s.item_count for s in adapter.list_scopes()}
    assert scopes == {"DeskThread Demo": 2, "Private": 9}
    notes = _on(adapter, {"DeskThread Demo"}).items()
    assert apps.calls[-1] == ("notes.read", ["DeskThread Demo"])
    follow, fragment = notes
    assert follow.date is not None and (follow.date.month, follow.date.day) == (10, 23)
    assert fragment.undated and fragment.meta["modified"].startswith("2026-11-20")
    assert follow.location == "Notes: DeskThread Demo" and len(follow.units) == 3


def test_reminders_carry_open_or_done_and_the_due_date(apps: FakeApps) -> None:
    items = _on(
        MacAppAdapter("reminders", SourceKind.REMINDERS, "Reminders", "/", apps), {"Work"}
    ).items()
    intro, mail = items
    assert intro.meta["status"] == "open" and intro.date is not None and intro.date.day == 27
    assert mail.meta["status"] == "done" and mail.units[0].text.endswith("[done]")


def test_mail_reads_one_chosen_mailbox(apps: FakeApps) -> None:
    adapter = MacAppAdapter("mail", SourceKind.MAIL, "Mail", "/", apps)
    scopes = {s.label: s.item_count for s in adapter.list_scopes()}
    assert scopes["Work / INBOX"] == 13037
    (message,) = _on(adapter, {"On My Mac / DeskThread Demo"}).items()
    assert apps.calls[-1] == ("mail.read", ["On My Mac / DeskThread Demo"])
    assert message.kind is ItemKind.MAIL and message.date is not None and message.date.day == 10
    assert any("Budget approved up to 800" in u.text for u in message.units)


# ------------------------------------------------------------------ consent and the OS layer


def test_an_app_is_off_until_allowed_and_revoke_drops_its_items(apps: FakeApps) -> None:
    adapter = MacAppAdapter("notes", SourceKind.NOTES, "Notes", "/", apps)
    broker = Broker()
    broker.register(adapter)
    store = SessionStore(broker)
    assert broker.states()[0].status.value == "off" and apps.calls == []  # not even asked yet
    with pytest.raises(DeskThreadError):
        store.load("mac:notes")
    broker.grant("mac:notes", frozenset({"DeskThread Demo"}))
    assert store.load("mac:notes") == 2
    broker.revoke("mac:notes")
    assert store.items() == []


def test_a_refusal_by_macos_is_reported_as_missing_permission(apps: FakeApps) -> None:
    apps.refuse = True
    adapter = MacAppAdapter("mail", SourceKind.MAIL, "Mail", "/", apps)
    with pytest.raises(DeskThreadError) as err:
        adapter.list_scopes()
    assert err.value.code is ErrorCode.OS_PERMISSION_MISSING
    assert adapter.os_permission() is OsPermission.MISSING


def test_the_four_apps_are_listed_a_to_z_and_only_if_installed(tmp_path: Path) -> None:
    found = mac_apps(FakeApps())
    assert [a.label for a in found] == sorted(a.label for a in found)
    assert {a.source_id for a in found} <= {
        "mac:calendar",
        "mac:mail",
        "mac:notes",
        "mac:reminders",
    }
    missing = MacAppAdapter(
        "notes", SourceKind.NOTES, "Notes", str(tmp_path / "No.app"), FakeApps()
    )
    assert missing.installed() is False
