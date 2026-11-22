"""The icon of an app on this Mac, exactly as the Mac shows it, for the Access screen.

The picture is asked from macOS and turned into PNG bytes in memory. Nothing is written to
disk and no file of the app is read by us.
"""

import subprocess
import threading
from pathlib import Path

APPS = {
    "mac:calendar": "/System/Applications/Calendar.app",
    "mac:mail": "/System/Applications/Mail.app",
    "mac:notes": "/System/Applications/Notes.app",
    "mac:reminders": "/System/Applications/Reminders.app",
}
_CACHE: dict[str, bytes] = {}
_LOCK = threading.Lock()


def show_original(source_id: str, path: Path | None) -> bool:
    """Take the user to the original: select the file in Finder, or bring up the Mac app the
    item came from. The Mac's own `open` does it; DeskThread does not open the file."""
    if path is not None:
        command = ["/usr/bin/open", "-R", str(path)]
    elif source_id in APPS:
        command = ["/usr/bin/open", APPS[source_id]]
    else:
        return False
    return subprocess.run(command, check=False, capture_output=True).returncode == 0


def app_icon(source_id: str, size: int = 128) -> bytes | None:
    """PNG bytes of the app's icon, or None when there is none to show."""
    path = APPS.get(source_id)
    if path is None or not Path(path).exists():
        return None
    with _LOCK:  # the Mac's drawing calls must not run two at a time
        if source_id not in _CACHE:
            data = _draw(path, size)
            if data is None:
                return None
            _CACHE[source_id] = data
        return _CACHE[source_id]


def _draw(path: str, size: int) -> bytes | None:
    try:
        from AppKit import (
            NSBitmapImageRep,
            NSCompositingOperationCopy,
            NSGraphicsContext,
            NSMakeRect,
            NSWorkspace,
        )
    except ImportError:
        return None
    icon = NSWorkspace.sharedWorkspace().iconForFile_(path)
    rep = NSBitmapImageRep.alloc().initWithBitmapDataPlanes_pixelsWide_pixelsHigh_bitsPerSample_samplesPerPixel_hasAlpha_isPlanar_colorSpaceName_bytesPerRow_bitsPerPixel_(
        None, size, size, 8, 4, True, False, "NSCalibratedRGBColorSpace", 0, 0
    )
    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.setCurrentContext_(NSGraphicsContext.graphicsContextWithBitmapImageRep_(rep))
    icon.drawInRect_fromRect_operation_fraction_(
        NSMakeRect(0, 0, size, size), NSMakeRect(0, 0, 0, 0), NSCompositingOperationCopy, 1.0
    )
    NSGraphicsContext.restoreGraphicsState()
    data = rep.representationUsingType_properties_(4, None)  # 4 = PNG
    return bytes(data) if data is not None else None
