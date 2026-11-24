"""A small window that shows the invented demo laptop being made.

    uv run python -B scripts/demo_progress.py [--out demo-laptop] [--hold 2]

It is used by the launcher (`DeskThread.app`) on the first start, before DeskThread itself
opens. It runs `demo-data/make_demo_data.py --progress` as a separate program and draws what
that program reports: a bar and "n of m files". The bar follows the real count; nothing is
slowed down. When the last file is written the window stays for `--hold` seconds, so the
finished state can be read, and then closes.

This is not part of the app: DeskThread itself writes nothing to disk. The files are written
by the generator program, only inside the demo folder.

Exit code: 0 when the folder was built, 1 when it was not (the launcher then says so).
"""

import argparse
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

import Quartz  # noqa: E402, F401  (lets pyobjc handle the CGColor values of the bar)
from AppKit import (  # noqa: E402
    NSApplication,
    NSApplicationActivationPolicyRegular,
    NSBackingStoreBuffered,
    NSColor,
    NSFont,
    NSMakeRect,
    NSObject,
    NSTextField,
    NSView,
    NSVisualEffectBlendingModeBehindWindow,
    NSVisualEffectMaterialPopover,
    NSVisualEffectStateActive,
    NSVisualEffectView,
    NSWindow,
    NSWindowStyleMaskFullSizeContentView,
    NSWindowStyleMaskTitled,
)
from Foundation import NSTimer  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
GENERATOR = REPO / "demo-data" / "make_demo_data.py"
WIDTH, HEIGHT, PAD = 440, 168, 32

# The app's colours (see ui/styles/globals.css): ink, muted text, royal blue.
INK = (0x0B / 255, 0x16 / 255, 0x40 / 255)
MUTED = (0x4A / 255, 0x56 / 255, 0x82 / 255)
ROYAL = (0x0A / 255, 0x17 / 255, 0xC4 / 255)


class State:
    """What the generator has reported so far, shared with the window's timer."""

    def __init__(self) -> None:
        self.done = 0
        self.total = 0
        self.finished = False
        self.code = 0
        self.finished_at = 0.0


def watch(out: Path, state: State) -> None:
    """Run the generator and keep `state` up to date. Runs in a thread of its own."""
    proc = subprocess.Popen(
        [sys.executable, "-B", str(GENERATOR), "--progress", "--out", str(out)],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        cwd=REPO,
    )
    assert proc.stdout is not None
    for line in proc.stdout:
        parts = line.split()
        if len(parts) == 3 and parts[0] == "PROGRESS":
            state.done, state.total = int(parts[1]), int(parts[2])
    state.code = proc.wait()
    state.finished_at = time.monotonic()
    state.finished = True


def colour(rgb: tuple[float, float, float], alpha: float = 1.0) -> Any:
    return NSColor.colorWithSRGBRed_green_blue_alpha_(rgb[0], rgb[1], rgb[2], alpha)


def label(text: str, size: float, rgb: tuple[float, float, float], bold: bool, y: float) -> Any:
    field = NSTextField.labelWithString_(text)
    name = "AvenirNext-DemiBold" if bold else "AvenirNext-Regular"
    field.setFont_(NSFont.fontWithName_size_(name, size) or NSFont.systemFontOfSize_(size))
    field.setTextColor_(colour(rgb))
    field.setFrame_(NSMakeRect(PAD, y, WIDTH - 2 * PAD, size + 8))
    return field


def rounded(frame: Any, fill: Any, border: Any = None) -> Any:
    """A rounded flat rectangle, used for the track and the fill of the bar."""
    view = NSView.alloc().initWithFrame_(frame)
    view.setWantsLayer_(True)
    layer = view.layer()
    layer.setCornerRadius_(frame.size.height / 2)
    layer.setBackgroundColor_(fill.CGColor())
    if border is not None:
        layer.setBorderWidth_(1)
        layer.setBorderColor_(border.CGColor())
    return view


class Ticker(NSObject):
    state: State | None = None
    hold: float = 2.0
    title: Any = None
    note: Any = None
    fill: Any = None
    track_width: float = 0.0

    def tick_(self, _timer: Any) -> None:
        state = self.state
        if state is None:
            return
        fraction = state.done / state.total if state.total else 0.0
        frame = self.fill.frame()
        frame.size.width = max(frame.size.height, self.track_width * fraction)
        self.fill.setFrame_(frame)
        if not state.finished:
            self.note.setStringValue_(
                f"{state.done} of {state.total} files" if state.total else "Starting…"
            )
            return
        if state.code != 0:
            self.title.setStringValue_("Could not make the demo data")
            self.note.setStringValue_("DeskThread opens without it.")
        else:
            self.note.setStringValue_(f"{state.done} of {state.total} files, ready")
        if time.monotonic() - state.finished_at >= self.hold:
            NSApplication.sharedApplication().terminate_(None)


def make_window(state: State, hold: float) -> tuple[Any, Any]:
    """The window and the timer target that keeps it up to date with `state`."""
    window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
        NSMakeRect(0, 0, WIDTH, HEIGHT),
        NSWindowStyleMaskTitled | NSWindowStyleMaskFullSizeContentView,
        NSBackingStoreBuffered,
        False,
    )
    window.setTitlebarAppearsTransparent_(True)
    window.setTitleVisibility_(1)  # NSWindowTitleHidden
    window.setMovableByWindowBackground_(True)
    window.setLevel_(3)  # floating, so it is not lost behind the Terminal or Finder

    glass = NSVisualEffectView.alloc().initWithFrame_(NSMakeRect(0, 0, WIDTH, HEIGHT))
    glass.setMaterial_(NSVisualEffectMaterialPopover)
    glass.setBlendingMode_(NSVisualEffectBlendingModeBehindWindow)
    glass.setState_(NSVisualEffectStateActive)
    window.setContentView_(glass)

    title = label("Generating demo data", 21, INK, True, HEIGHT - 78)
    note = label("Starting…", 14, MUTED, False, HEIGHT - 108)
    track_width = WIDTH - 2 * PAD
    track = rounded(
        NSMakeRect(PAD, 36, track_width, 12),
        colour((1, 1, 1), 0.7),
        colour((0x28 / 255, 0x46 / 255, 0xA0 / 255), 0.18),
    )
    fill = rounded(NSMakeRect(PAD, 36, 12, 12), colour(ROYAL))
    for view in (title, note, track, fill):
        glass.addSubview_(view)

    ticker = Ticker.alloc().init()
    ticker.state, ticker.hold = state, hold
    ticker.title, ticker.note, ticker.fill, ticker.track_width = title, note, fill, track_width
    return window, ticker


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--out", type=Path, default=REPO / "demo-laptop")
    parser.add_argument("--hold", type=float, default=2.0, help="seconds to stay when done")
    args = parser.parse_args()

    state = State()
    threading.Thread(target=watch, args=(args.out, state), name="generator", daemon=True).start()

    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(NSApplicationActivationPolicyRegular)
    window, ticker = make_window(state, args.hold)
    NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
        0.03, ticker, b"tick:", None, True
    )

    window.center()
    window.makeKeyAndOrderFront_(None)
    app.activateIgnoringOtherApps_(True)
    app.run()
    return 0 if state.finished and state.code == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
