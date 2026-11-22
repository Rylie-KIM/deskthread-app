"""Gate G1: what may be read. Enforced in code before any file is opened, never in a prompt.

Two rules, checked on the real path of a file (symlinks and ".." resolved first):
1. Path confinement (FT-43): the file must be inside a folder the user chose.
2. Off-limits (FT-03): a folder holding a file named .deskthread-off-limits, a folder named
   Personal or Private, a file whose name starts with PRIVATE, or anything the user marked
   in this session. Off-limits files are never opened, also when asked for by name.

No app is closed for good: the user may allow reading of any source (user, 2026-11-22).
Reading is the only permission there is.
"""

import unicodedata
from pathlib import Path

from contracts.errors import DeskThreadError, ErrorCode

OFF_LIMITS_MARKER = ".deskthread-off-limits"
OFF_LIMITS_FOLDER_NAMES = frozenset({"personal", "private"})
OFF_LIMITS_FILE_PREFIX = "private"
# Personal chat apps. They can be allowed like anything else; presets leave them Off.
PERSONAL_CHAT_NAMES = frozenset(
    {"whatsapp", "kakaotalk", "line", "discord", "imessage", "messages", "telegram", "signal"}
)


def norm(text: str) -> str:
    """One Unicode form for comparisons: macOS may hand back Hangul as NFC or NFD."""
    return unicodedata.normalize("NFC", text)


class AccessPolicy:
    def __init__(self, roots: list[Path]) -> None:
        self._roots = [r.resolve() for r in roots]
        self._session_off_limits: set[Path] = set()

    @property
    def roots(self) -> list[Path]:
        return list(self._roots)

    def set_roots(self, roots: list[Path]) -> None:
        """Choose another folder. Earlier session marks do not carry over."""
        self._roots = [r.resolve() for r in roots]
        self._session_off_limits.clear()

    def mark_off_limits(self, path: Path) -> None:
        """A choice for this session only; nothing is saved."""
        self._session_off_limits.add(path.resolve())

    def _root_of(self, real: Path) -> Path | None:
        for root in self._roots:
            if real == root or root in real.parents:
                return root
        return None

    def confine(self, path: Path) -> Path:
        """The real path if it is inside an allowed folder, else PATH_OUTSIDE_ALLOWED."""
        real = path.resolve()
        if self._root_of(real) is None:
            raise DeskThreadError(ErrorCode.PATH_OUTSIDE_ALLOWED)
        return real

    def is_off_limits(self, path: Path) -> bool:
        real = path.resolve()
        root = self._root_of(real)
        if root is None:
            return True
        if norm(real.name).lower().startswith(OFF_LIMITS_FILE_PREFIX):
            return True
        if real in self._session_off_limits:
            return True
        folder = real if real.is_dir() else real.parent
        while True:
            if folder in self._session_off_limits:
                return True
            if folder != root and norm(folder.name).lower() in OFF_LIMITS_FOLDER_NAMES:
                return True
            if (folder / OFF_LIMITS_MARKER).exists():
                return True
            if folder == root:
                return False
            folder = folder.parent

    def check_read(self, path: Path) -> Path:
        """The one call every reader makes before opening a file."""
        real = self.confine(path)
        if self.is_off_limits(real):
            raise DeskThreadError(ErrorCode.ITEM_OFF_LIMITS)
        return real
