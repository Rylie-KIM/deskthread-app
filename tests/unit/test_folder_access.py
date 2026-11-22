"""U1, U2 and the Unicode path test: gate G1 and the folder connector (FT-01, FT-03, FT-43)."""

import hashlib
import unicodedata
from pathlib import Path

import pytest

from app.policy import AccessPolicy
from app.sources.folder import FolderAdapter, LockedSource, scan
from contracts.errors import DeskThreadError, ErrorCode
from contracts.items import Item, SourceKind, Uncounted


class OpenGrant:
    """A stand-in grant for these tests. The real one comes from the permission broker."""

    cancelled = False

    def __init__(self, adapter: FolderAdapter | LockedSource) -> None:
        self.source_id = adapter.source_id
        self.scope_ids = frozenset(s.scope_id for s in adapter.list_scopes())

    def raise_if_cancelled(self) -> None:
        return None


def _read_all(root: Path, policy: AccessPolicy | None = None) -> list[Item | Uncounted]:
    policy = policy or AccessPolicy([root])
    out: list[Item | Uncounted] = []
    for adapter in scan(root, policy):
        if isinstance(adapter, FolderAdapter):
            out += list(adapter.read(OpenGrant(adapter)))
    return out


def _text(things: list[Item | Uncounted]) -> str:
    return "\n".join(u.text for t in things if isinstance(t, Item) for u in t.units)


def test_the_scanner_recognises_sources_by_folder_name_only(demo_laptop: Path) -> None:
    found = {a.source_id: a for a in scan(demo_laptop, AccessPolicy([demo_laptop]))}
    assert set(found) == {
        "folder:notes", "folder:mail", "folder:calendar", "folder:reminders",
        "folder:chat-exports", "folder:documents", "folder:images",
        "private:whatsapp", "private:kakaotalk",
    }  # fmt: skip
    notes = found["folder:notes"].list_scopes()
    assert [(s.label, s.item_count) for s in notes] == [("Notes", 21)]  # PRIVATE one not counted
    calendars = {s.label for s in found["folder:calendar"].list_scopes()}
    assert calendars == {"work", "personal"}  # one scope per calendar


def test_private_apps_are_detected_and_can_never_be_read(demo_laptop: Path) -> None:
    found = {a.source_id: a for a in scan(demo_laptop, AccessPolicy([demo_laptop]))}
    whatsapp = found["private:whatsapp"]
    assert isinstance(whatsapp, LockedSource) and whatsapp.kind is SourceKind.PRIVATE_APP
    assert whatsapp.list_scopes() == []  # not even counted
    with pytest.raises(DeskThreadError) as err:
        whatsapp.read(OpenGrant(whatsapp))
    assert err.value.code is ErrorCode.SOURCE_LOCKED


def test_u1_off_limits_files_are_never_read_even_with_everything_allowed(
    demo_laptop: Path,
) -> None:
    things = _read_all(demo_laptop)
    text = _text(things)
    assert "Budget approved up to 800" in text  # an allowed mail is there
    for words in ("performance plan", "Tax return", "Landlord", "are you coming on Sunday"):
        assert words not in text
    locations = {t.location for t in things}
    assert not any("PRIVATE" in loc or "Personal/" in loc for loc in locations)
    assert not any("WhatsApp" in loc or "KakaoTalk" in loc for loc in locations)


def test_u1_asking_for_an_off_limits_file_by_name_is_refused(demo_laptop: Path) -> None:
    policy = AccessPolicy([demo_laptop])
    for rel, code in [
        ("App-exports/Notes/PRIVATE-alex-concerns.md", ErrorCode.ITEM_OFF_LIMITS),
        ("Documents/Personal/gp-appointment.txt", ErrorCode.ITEM_OFF_LIMITS),
        ("App-exports/WhatsApp/Family.txt", ErrorCode.SOURCE_LOCKED),
    ]:
        with pytest.raises(DeskThreadError) as err:
            policy.check_read(demo_laptop / rel)
        assert err.value.code is code


def test_u1_a_file_marked_in_the_session_is_not_read(demo_laptop: Path) -> None:
    policy = AccessPolicy([demo_laptop])
    policy.mark_off_limits(demo_laptop / "App-exports/Notes/follow-ups.md")
    assert "conference in Feb (Manchester)" not in _text(_read_all(demo_laptop, policy))


def test_u2_dotdot_and_symlinks_out_of_the_folder_are_refused(tmp_path: Path) -> None:
    allowed, outside = tmp_path / "allowed", tmp_path / "outside"
    (allowed / "Work").mkdir(parents=True)
    outside.mkdir()
    (outside / "secret.txt").write_text("outside secret")
    (allowed / "Work" / "ok.txt").write_text("fine")
    (allowed / "Work" / "link.txt").symlink_to(outside / "secret.txt")
    (allowed / "Work" / "linked-folder").symlink_to(outside, target_is_directory=True)
    policy = AccessPolicy([allowed])

    assert policy.check_read(allowed / "Work" / "ok.txt").name == "ok.txt"
    for path in [
        allowed / "Work" / ".." / ".." / "outside" / "secret.txt",
        allowed / "Work" / "link.txt",
        allowed / "Work" / "linked-folder" / "secret.txt",
        outside / "secret.txt",
    ]:
        with pytest.raises(DeskThreadError) as err:
            policy.check_read(path)
        assert err.value.code is ErrorCode.PATH_OUTSIDE_ALLOWED
    text = _text(_read_all(allowed))
    assert "fine" in text and "outside secret" not in text


def test_u2_a_symlink_to_the_personal_folder_is_refused(demo_laptop: Path, tmp_path: Path) -> None:
    work = tmp_path / "chosen" / "Work"
    work.mkdir(parents=True)
    (work / "shortcut").symlink_to(demo_laptop / "Documents" / "Personal")
    assert _read_all(tmp_path / "chosen") == []


def test_unicode_paths_in_both_forms_are_read(tmp_path: Path) -> None:
    root = tmp_path / "laptop"
    for form in ("NFC", "NFD"):
        folder = root / unicodedata.normalize(form, f"회의록-{form}")
        folder.mkdir(parents=True)
        (folder / unicodedata.normalize(form, "메모.txt")).write_text("팀 회의 메모\n", "utf-8")
    things = _read_all(root)
    assert len(things) == 2
    assert all(t.location == unicodedata.normalize("NFC", t.location) for t in things)


def test_unsupported_and_broken_files_are_counted_not_skipped(
    demo_laptop: Path, tmp_path: Path
) -> None:
    missed = {t.location: t.reason for t in _read_all(demo_laptop) if isinstance(t, Uncounted)}
    assert missed == {
        "Desktop/IMG_2041.heic": ErrorCode.UNSUPPORTED_TYPE.value,
        "Downloads/offsite-photos.zip": ErrorCode.UNSUPPORTED_TYPE.value,
    }
    work = tmp_path / "laptop" / "Work"
    work.mkdir(parents=True)
    (work / "broken.docx").write_bytes(b"not a zip file")
    things = _read_all(tmp_path / "laptop")
    assert [t.reason for t in things if isinstance(t, Uncounted)] == [ErrorCode.READ_FAILED.value]


def test_an_adapter_refuses_a_grant_made_for_another_source(demo_laptop: Path) -> None:
    found = {a.source_id: a for a in scan(demo_laptop, AccessPolicy([demo_laptop]))}
    with pytest.raises(DeskThreadError) as err:
        list(found["folder:notes"].read(OpenGrant(found["folder:mail"])))
    assert err.value.code is ErrorCode.SOURCE_NOT_ALLOWED


def test_the_connector_never_changes_the_folder(demo_laptop: Path) -> None:
    def digest() -> str:
        h = hashlib.sha256()
        for p in sorted(demo_laptop.rglob("*")):
            if p.is_file():
                h.update(str(p.relative_to(demo_laptop)).encode() + p.read_bytes())
                h.update(str(p.stat().st_mtime_ns).encode())
        return h.hexdigest()

    before = digest()
    assert len(_read_all(demo_laptop)) > 60
    assert digest() == before
