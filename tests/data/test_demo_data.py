"""D1 to D6: the invented demo data is what the story and the tests need (plan 33.4)."""

import json
import re
from pathlib import Path
from types import ModuleType

from tests.conftest import CANARY, REPO

TRUTH = json.loads((REPO / "eval" / "ground_truth.json").read_text())
TEXT_SUFFIXES = {".md", ".txt", ".eml", ".ics", ".csv", ".vtt"}


def _texts(root: Path) -> dict[str, str]:
    return {
        str(p.relative_to(root)): p.read_text(encoding="utf-8")
        for p in sorted(root.rglob("*"))
        if p.is_file() and p.suffix in TEXT_SUFFIXES
    }


def test_d1_the_words_the_manager_searches_for_appear_nowhere(demo_laptop: Path) -> None:
    for path, text in _texts(demo_laptop).items():
        low = text.lower()
        assert "development goal" not in low, path
        assert not re.search(r"\b(development|goals?)\b", low), path


def test_d2_every_email_address_is_on_the_reserved_example_domain(demo_laptop: Path) -> None:
    address = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
    found = [a for text in _texts(demo_laptop).values() for a in address.findall(text)]
    assert len(found) > 30
    assert all(a.endswith(".example") for a in found)


def test_d3_two_builds_give_identical_files(generator: ModuleType, tmp_path: Path) -> None:
    first = generator.build(tmp_path / "a" / "demo-laptop")
    second = generator.build(tmp_path / "b" / "demo-laptop")
    assert first == second


def test_d3_a_rebuild_refuses_a_folder_it_did_not_make(
    generator: ModuleType, tmp_path: Path
) -> None:
    other = tmp_path / "someone-elses-folder"
    other.mkdir()
    (other / "keep.txt").write_text("keep")
    try:
        generator.build(other)
    except SystemExit:
        assert (other / "keep.txt").exists()
    else:
        raise AssertionError("build replaced a folder that was not a demo folder")


def test_d4_file_counts_match_the_ground_truth(demo_laptop: Path) -> None:
    counts = TRUTH["counts"]
    files = [p for p in demo_laptop.rglob("*") if p.is_file() and p.name != ".deskthread-demo"]
    assert len(files) == counts["total_files"]
    assert len(list((demo_laptop / "App-exports/Notes").iterdir())) == counts["notes"]
    assert len(list((demo_laptop / "App-exports/Mail").iterdir())) == counts["mail"]
    assert len(list((demo_laptop / "App-exports/Calendar").iterdir())) == counts["calendar_files"]
    work = (demo_laptop / "App-exports/Calendar/work.ics").read_text()
    assert work.count("BEGIN:VEVENT") == counts["work_events"]
    images = [p for p in files if p.suffix in {".png", ".jpg"}]
    assert len(images) == counts["images"]
    assert len(list((demo_laptop / "Documents/Personal").iterdir())) == counts["personal_folder"]


def test_d4_every_ground_truth_source_exists_and_holds_its_words(demo_laptop: Path) -> None:
    for promise in TRUTH["promises"]:
        for source in promise["sources"]:
            path = demo_laptop / source["path"]
            assert path.is_file(), source["path"]
            if path.suffix in TEXT_SUFFIXES:
                assert source["contains"] in path.read_text(), source
    for rel in [*TRUTH["forbidden_paths"], TRUTH["injection_path"]]:
        assert (demo_laptop / rel).is_file(), rel


def test_d5_the_canary_is_planted_in_a_note_a_mail_and_the_image(
    generator: ModuleType, demo_laptop: Path
) -> None:
    plain, planted = generator.files(), generator.files(CANARY)
    changed = sorted(p for p in plain if plain[p] != planted[p])
    assert len(changed) == 3
    assert sum(CANARY.encode() in planted[p] for p in changed) == 2  # the note and the mail
    assert any(p.endswith(".png") for p in changed)  # the image carries it as pixels
    assert all(CANARY not in text for text in _texts(demo_laptop).values())


def test_d6_no_file_supports_a_pay_promise_to_sam(demo_laptop: Path) -> None:
    for path, text in _texts(demo_laptop).items():
        low = text.lower()
        assert "salary" not in low and "pay rise" not in low and "bonus" not in low, path
        if re.search(r"\bpay\b", low):
            assert "sam" not in low, path


def test_d7_the_rich_layer_follows_the_same_rules_and_leaves_the_first_layer_alone(
    generator: ModuleType, tmp_path: Path
) -> None:
    core, rich = generator.files(), generator.files(rich=True)
    assert len(core) == TRUTH["counts"]["total_files"] and len(rich) > 2 * len(core)
    calendar = "App-exports/Calendar/work.ics"  # the only file that grows: more events
    assert all(rich[path] == data for path, data in core.items() if path != calendar)
    assert rich[calendar].count(b"BEGIN:VEVENT") > core[calendar].count(b"BEGIN:VEVENT")
    root = tmp_path / "demo-laptop"
    hashes = generator.build(root, rich=True)
    assert hashes == generator.build(tmp_path / "again" / "demo-laptop", rich=True)  # repeatable
    texts = _texts(root)
    address = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
    for path, text in texts.items():
        low = text.lower()
        assert not re.search(r"\b(development|goals?)\b", low), path
        assert "salary" not in low and "pay rise" not in low and "bonus" not in low, path
        if re.search(r"\bpay\b", low):
            assert "sam" not in low, path
        assert all(a.endswith(".example") for a in address.findall(text)), path
    work = (root / "App-exports/Calendar/work.ics").read_text()
    assert work.count("BEGIN:VEVENT") == TRUTH["counts"]["work_events"] + 28
    # the first layer's story is still found where it was
    for promise in TRUTH["promises"]:
        for source in promise["sources"]:
            assert (root / source["path"]).is_file(), source["path"]


def test_the_generator_reports_every_file_for_the_progress_window(
    generator: ModuleType, tmp_path: Path
) -> None:
    seen: list[tuple[int, int]] = []
    hashes = generator.build(tmp_path / "demo-laptop", progress=lambda d, t: seen.append((d, t)))
    assert len(seen) == len(hashes)
    assert [done for done, _ in seen] == list(range(1, len(hashes) + 1))
    assert {total for _, total in seen} == {len(hashes)}
    # Reporting progress changes nothing in the files.
    assert hashes == generator.build(tmp_path / "again" / "demo-laptop")
