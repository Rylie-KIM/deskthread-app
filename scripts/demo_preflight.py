"""Is everything ready for the recording? Counts and pass/fail only (project rule R1).

    uv run python -B -m scripts.demo_preflight

Nothing is printed that comes from a note, an event or a picture: only how many there are,
whether a named demo file exists, and whether a model is on this Mac. It writes nothing.
"""

import subprocess
from datetime import datetime
from pathlib import Path

from scripts.seed import seed_demo

STORY_DAY = "2026-11-22"
OLLAMA = Path.home() / ".ollama" / "models" / "manifests" / "registry.ollama.ai" / "library"


def count(script: str) -> int | None:
    done = subprocess.run(
        ["/usr/bin/osascript", "-e", script],
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    return (
        int(done.stdout.strip()) if done.returncode == 0 and done.stdout.strip().isdigit() else None
    )


def show(ok: bool, text: str) -> bool:
    print(("PASS  " if ok else "FAIL  ") + text)
    return ok


def main() -> int:
    manifest = seed_demo.load()
    results: list[bool] = []

    listening = subprocess.run(
        ["/usr/sbin/lsof", "-nP", "-iTCP:11435", "-sTCP:LISTEN", "-t"],
        capture_output=True, text=True, check=False,
    ).stdout.strip()  # fmt: skip
    results.append(show(not listening, "DeskThread and its AI server are closed (a clean start)"))

    notes = count(
        'tell application "Notes" to count of notes of (first folder whose name is "Test-Notes")'
    )
    want = len(manifest["notes"])
    results.append(
        show(
            notes is not None and notes >= want > 0,
            f"Test-Notes holds {notes} notes; the seeder wrote {want}",
        )
    )

    events = count(
        'tell application "Calendar" to count of events of (first calendar whose name is "Test-Work")'
    )
    want = len(manifest["events"])
    results.append(
        show(
            events is not None and events >= want > 0,
            f"Test-Work holds {events} events; the seeder wrote {want}",
        )
    )
    if events is not None and events > want:
        print(
            f"      note: {events - want} other events in Test-Work are not the demo's: check they may be on camera"
        )

    here = [name for name in manifest["files"] if (seed_demo.SNAPSHOTS / name).exists()]
    results.append(
        show(
            len(here) == len(manifest["files"]) > 0,
            f"{len(here)} of {len(manifest['files'])} demo pictures are in place",
        )
    )

    for tag, path in (
        ("answering model gemma4:e4b", "gemma4/e4b"),
        ("search model embeddinggemma:300m", "embeddinggemma/300m"),
    ):
        results.append(show((OLLAMA / path).exists(), f"{tag} is on this Mac"))

    results.append(
        show(
            Path("DeskThread.app/Contents/MacOS/DeskThread").exists(),
            "DeskThread.app is in the project folder",
        )
    )
    results.append(show(Path("ui/out/index.html").exists(), "the screens are built (ui/out)"))

    today = datetime.now().date().isoformat()
    same = today == STORY_DAY
    show(
        same,
        f"today is {today}; the story's day is {STORY_DAY}"
        + ("" if same else " (start the app with DESKTHREAD_NOW=2026-11-22T19:00:00+00:00)"),
    )
    print(f"\n{sum(results)} of {len(results)} checks passed")
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
