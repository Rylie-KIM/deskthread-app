"""Put the English demo story into the user's own apps, and take it out again.

    uv run python -B -m scripts.seed.seed_demo seed      # write
    uv run python -B -m scripts.seed.seed_demo more      # add the second list of events
    uv run python -B -m scripts.seed.seed_demo notes-more # add the second, more abstract notes
    uv run python -B -m scripts.seed.seed_demo more2     # the third layer: more notes and events
    uv run python -B -m scripts.seed.seed_demo renumber  # n1, n2, ... in front of every note title
    uv run python -B -m scripts.seed.seed_demo unseed    # remove exactly what seed wrote
    uv run python -B -m scripts.seed.seed_demo status    # counts only

Only the user may ask for this (project rule: writes to real apps need approval at that
moment). It writes to three places and nowhere else: the Notes folder "Test-Notes", the
iCloud calendar "Test-Work", and new image files in ~/Documents/Snapshots. It never reads
or lists what is already there. Every item it creates is recorded by id in a manifest
(git-ignored), and `unseed` removes only those. This script is not part of the app: the
app's own scripts stay read-only.
"""

import html
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from scripts.seed import content

MANIFEST = Path(__file__).with_name(".manifest.json")
SNAPSHOTS = Path.home() / "Documents" / "Snapshots"
FOLDER, CALENDAR = "Test-Notes", "Test-Work"
FONTS = ("/System/Library/Fonts/Helvetica.ttc", "/System/Library/Fonts/Supplemental/Arial.ttf")

DATE = """
on makeDate(y, m, d, hh, mm)
    set t to current date
    set day of t to 1
    set year of t to (y as integer)
    set month of t to (m as integer)
    set day of t to (d as integer)
    set time of t to ((hh as integer) * hours + (mm as integer) * minutes)
    return t
end makeDate
"""
NEW_NOTE = (
    DATE
    + """
on run argv
    set when to my makeDate(item 2 of argv, item 3 of argv, item 4 of argv, item 5 of argv, item 6 of argv)
    tell application "Notes"
        set made to make new note at (first folder whose name is "%s") with properties {body:(item 1 of argv), creation date:when}
        return (id of made) & "|" & ((creation date of made) as «class isot» as string) & "|" & ((modification date of made) as «class isot» as string)
    end tell
end run
"""
    % FOLDER
)
READ_NOTE = """
on run argv
    tell application "Notes"
        set n to note id (item 1 of argv)
        return (name of n) & "|" & ((creation date of n) as «class isot» as string)
    end tell
end run
"""
SET_NOTE = """
on run argv
    tell application "Notes"
        set n to note id (item 1 of argv)
        set body of n to (item 2 of argv)
        return ((creation date of n) as «class isot» as string)
    end tell
end run
"""
DEL_NOTE = """
on run argv
    tell application "Notes" to delete note id (item 1 of argv)
end run
"""
NEW_EVENT = (
    DATE
    + """
on run argv
    set s to my makeDate(item 2 of argv, item 3 of argv, item 4 of argv, item 5 of argv, item 6 of argv)
    set e to s + ((item 7 of argv) as integer) * minutes
    tell application "Calendar"
        tell (first calendar whose name is "%s")
            set made to make new event with properties {summary:(item 1 of argv), start date:s, end date:e, location:(item 8 of argv), description:(item 9 of argv)}
            return uid of made
        end tell
    end tell
end run
"""
    % CALENDAR
)
DEL_EVENT = (
    """
on run argv
    tell application "Calendar"
        tell (first calendar whose name is "%s")
            delete (first event whose uid is (item 1 of argv))
        end tell
    end tell
end run
"""
    % CALENDAR
)


def osa(script: str, *args: str, timeout: float = 120) -> str:
    done = subprocess.run(
        ["/usr/bin/osascript", "-e", script, *args],
        capture_output=True, text=True, timeout=timeout, check=False,
    )  # fmt: skip
    if done.returncode != 0:
        raise RuntimeError("osascript failed: " + done.stderr.strip().splitlines()[-1][-160:])
    return done.stdout.strip()


def load() -> dict[str, list[str]]:
    if MANIFEST.exists():
        found: dict[str, list[str]] = json.loads(MANIFEST.read_text())
        return found
    return {"notes": [], "events": [], "files": []}


def save(manifest: dict[str, list[str]]) -> None:
    MANIFEST.write_text(json.dumps(manifest, indent=1))


def body_of(title: str, lines: list[str]) -> str:
    rows = "".join(f"<div>{html.escape(line)}</div>" for line in lines)
    return f"<div><h1>{html.escape(title)}</h1></div>{rows}"


def font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in FONTS:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def draw(kind: str, title: str, lines: list[str]) -> Image.Image:
    """A screenshot-like picture: a window with a title bar and big, readable text."""
    paper = {"board": "#F4F6EF", "slide": "#1F2A44", "browser": "#FFFFFF"}.get(kind, "#F7F8FB")
    ink = "#F3F5FA" if kind == "slide" else "#1B1F2A"
    img = Image.new("RGB", (1280, 760), paper)
    pen = ImageDraw.Draw(img)
    pen.rectangle((0, 0, 1280, 64), fill="#2B3350" if kind == "slide" else "#E6E9F2")
    for i, colour in enumerate(("#FF5F57", "#FEBC2E", "#28C840")):
        pen.ellipse((24 + i * 30, 22, 42 + i * 30, 40), fill=colour)
    pen.text(
        (640, 20),
        title if kind != "board" else "Whiteboard",
        fill="#8A93AD",
        font=font(26),
        anchor="ma",
    )
    y = 120
    pen.text((70, y), title, fill="#3D5AFE" if kind != "slide" else "#9FB4FF", font=font(54))
    y += 110
    for line in lines:
        if kind == "chat":
            pen.rounded_rectangle((60, y - 12, 1220, y + 62), radius=26, fill="#E3E9FF")
        pen.text((90, y), line, fill=ink, font=font(40))
        y += 100
    return img


def seed() -> None:
    manifest = load()
    if any(manifest.values()):
        sys.exit("Already seeded. Run unseed first.")
    print("Notes ...", flush=True)
    for index, (when, title, lines) in enumerate(content.NOTES):
        made = osa(NEW_NOTE, body_of(title, lines), *map(str, when))
        note_id, created, modified = made.split("|")
        manifest["notes"].append(note_id)
        save(manifest)
        if index == 0 and created[:16] != datetime(*when).isoformat()[:16]:
            osa(DEL_NOTE, note_id)  # the app did not take the date: do not go on
            manifest["notes"].clear()
            save(manifest)
            sys.exit("Notes did not accept the creation date; the test note was removed.")
        if index == 0:
            print(f"  creation date accepted: {created[:16] == datetime(*when).isoformat()[:16]};"
                  f" modification date follows it: {modified[:16] == created[:16]}")  # fmt: skip
    print(f"  {len(manifest['notes'])} notes written")
    print("Calendar ...", flush=True)
    for title, when, minutes, place, about in content.EVENTS:
        manifest["events"].append(
            osa(NEW_EVENT, title, *map(str, when), str(minutes), place, about)
        )
        save(manifest)
    print(f"  {len(manifest['events'])} events written")
    print("Screenshots ...", flush=True)
    if not SNAPSHOTS.is_dir():
        sys.exit("The Snapshots folder does not exist.")
    for when, kind, title, lines in content.SCREENSHOTS:
        stamp = datetime(*when, 7)
        name = f"Demo Screenshot {stamp:%Y-%m-%d} at {stamp:%H.%M.%S}.png"
        path = SNAPSHOTS / name
        with path.open("xb") as handle:  # never replaces a file that is already there
            draw(kind, title, lines).save(handle, format="PNG")
        os.utime(path, (stamp.timestamp(), stamp.timestamp()))  # its Date Modified is the day
        manifest["files"].append(name)
        save(manifest)
    print(f"  {len(manifest['files'])} pictures written")


def more() -> None:
    """Add the second list of events to what `seed` already wrote."""
    manifest = load()
    for title, when, minutes, place, about in content.EVENTS_MORE:
        manifest["events"].append(
            osa(NEW_EVENT, title, *map(str, when), str(minutes), place, about)
        )
        save(manifest)
    print(f"  {len(content.EVENTS_MORE)} more events written; {len(manifest['events'])} in all")


def more_notes() -> None:
    """Add the second, more abstract list of notes."""
    manifest = load()
    for when, title, lines in content.NOTES_MORE:
        made = osa(NEW_NOTE, body_of(title, lines), *map(str, when))
        manifest["notes"].append(made.split("|")[0])
        save(manifest)
    print(f"  {len(content.NOTES_MORE)} more notes written; {len(manifest['notes'])} in all")


def more2() -> None:
    """Add the third layer: more notes and more calendar entries."""
    manifest = load()
    for when, title, lines in content.NOTES_THIRD:
        made = osa(NEW_NOTE, body_of(title, lines), *map(str, when))
        manifest["notes"].append(made.split("|")[0])
        save(manifest)
    for title, when, minutes, place, about in content.EVENTS_THIRD:
        manifest["events"].append(
            osa(NEW_EVENT, title, *map(str, when), str(minutes), place, about)
        )
        save(manifest)
    print(f"  {len(content.NOTES_THIRD)} notes and {len(content.EVENTS_THIRD)} events written;"
          f" {len(manifest['notes'])} notes and {len(manifest['events'])} events in all")  # fmt: skip


def renumber() -> None:
    """Put a number in front of every seeded note's title: n1 for the oldest, n2, n3 and so on
    (by creation date). Safe to run again. The creation date of each note is set back after
    its text is rewritten (the app does not allow setting it on an existing note, and
    rewriting the text keeps it)."""
    manifest = load()
    entries = [*content.NOTES, *content.NOTES_MORE, *content.NOTES_THIRD]
    ids = manifest["notes"]
    if len(entries) != len(ids):
        sys.exit(f"The manifest holds {len(ids)} notes but the content lists {len(entries)}.")
    for note_id, (_when, title, _lines) in zip(ids, entries, strict=True):
        name = osa(READ_NOTE, note_id).split("|")[0]
        if name != title and not (name.startswith("n") and name.endswith(" " + title)):
            sys.exit(
                "A note does not have the title it was written with; nothing more was changed."
            )
    order = sorted(range(len(entries)), key=lambda i: (entries[i][0], i))
    for number, index in enumerate(order, 1):
        when, title, lines = entries[index]
        before = osa(READ_NOTE, ids[index]).split("|")[1]
        after = osa(SET_NOTE, ids[index], body_of(f"n{number} {title}", lines))
        if after[:16] != datetime(*when).isoformat()[:16] or before[:16] != after[:16]:
            sys.exit(f"The creation date of note {number} is not what it should be.")
    print(f"  {len(ids)} notes numbered n1 to n{len(ids)}")


def unseed() -> None:
    manifest = load()
    for note_id in manifest["notes"]:
        osa(DEL_NOTE, note_id)
    for uid in manifest["events"]:
        osa(DEL_EVENT, uid)
    for name in manifest["files"]:
        (SNAPSHOTS / name).unlink(missing_ok=True)
    print(f"removed {len(manifest['notes'])} notes, {len(manifest['events'])} events,"
          f" {len(manifest['files'])} pictures")  # fmt: skip
    MANIFEST.unlink(missing_ok=True)


def status() -> None:
    manifest = load()
    print({k: len(v) for k, v in manifest.items()})


if __name__ == "__main__":
    {
        "seed": seed,
        "more": more,
        "notes-more": more_notes,
        "more2": more2,
        "renumber": renumber,
        "unseed": unseed,
        "status": status,
    }.get(sys.argv[1] if len(sys.argv) > 1 else "", status)()
