"""The folder connector (FT-01, FT-03, FT-43): files in a folder the user chose.

scan() looks at names only and builds one adapter per kind of source it recognises. No file
content is read until the user allows a source and the broker hands out a grant. Works on any
operating system and is also the fixture for the automated tests and the fallback for the
Mac app connectors.
"""

from collections.abc import Iterator
from pathlib import Path

from app.clock import now
from app.policy import PRIVATE_APP_NAMES, AccessPolicy, norm
from app.readers.files import IMAGE_SUFFIXES, read_file, supported
from contracts.adapters import OsPermission, ReadGrant, Scope
from contracts.errors import DeskThreadError, ErrorCode
from contracts.items import Item, SourceKind, Uncounted

EXPORTS = "App-exports"
# Folder name inside App-exports -> (kind, label, reader role)
KNOWN_EXPORTS: dict[str, tuple[SourceKind, str, str]] = {
    "notes": (SourceKind.NOTES, "Notes", ""),
    "mail": (SourceKind.MAIL, "Mail", ""),
    "calendar": (SourceKind.CALENDAR, "Calendar", ""),
    "reminders": (SourceKind.REMINDERS, "Reminders", "reminders"),
}
CHAT_EXPORTS = frozenset({"teams", "slack", "zoom"})


def _visible_files(folder: Path) -> list[Path]:
    """Files under a folder, by name only, in a fixed order. Hidden files are not sources."""
    if folder.is_file():
        return [folder]
    return sorted(
        p
        for p in folder.rglob("*")
        if p.is_file() and not any(part.startswith(".") for part in p.relative_to(folder).parts)
    )


class FolderAdapter:
    """One source made of files: for example the Notes folder, or the images of a laptop."""

    def __init__(
        self,
        *,
        source_id: str,
        kind: SourceKind,
        label: str,
        root: Path,
        scopes: list[Path],
        policy: AccessPolicy,
        role: str = "",
        want_images: bool | None = None,
    ) -> None:
        self._source_id, self._kind, self._label = source_id, kind, label
        self._root, self._scopes, self._policy = root, scopes, policy
        self._role = role
        self._want_images = want_images  # True: images only; False: no images; None: all

    @property
    def source_id(self) -> str:
        return self._source_id

    @property
    def kind(self) -> SourceKind:
        return self._kind

    @property
    def label(self) -> str:
        return self._label

    def os_permission(self) -> OsPermission:
        return OsPermission.NOT_NEEDED

    def _key(self, path: Path) -> str:
        return norm(str(path.relative_to(self._root)))

    def _mine(self, path: Path) -> bool:
        is_image = path.suffix.lower() in IMAGE_SUFFIXES
        return self._want_images is None or self._want_images == is_image

    def _files(self, scope: Path) -> list[Path]:
        return [p for p in _visible_files(scope) if self._mine(p)]

    def _readable(self, path: Path) -> bool:
        try:
            self._policy.check_read(path)
        except DeskThreadError:
            return False
        return True

    def list_scopes(self) -> list[Scope]:
        """Names and counts only: no file is opened here."""
        return [
            Scope(
                scope_id=self._key(scope),
                label=scope.stem if scope.is_file() else scope.name,
                item_count=sum(1 for p in self._files(scope) if self._readable(p)),
            )
            for scope in self._scopes
        ]

    def off_limits_count(self) -> int:
        """How many of this source's files the policy keeps out of reach (a count only)."""
        return sum(1 for s in self._scopes for p in self._files(s) if not self._readable(p))

    def read(self, grant: ReadGrant) -> Iterator[Item | Uncounted]:
        if grant.source_id != self._source_id:
            raise DeskThreadError(ErrorCode.SOURCE_NOT_ALLOWED)
        year = now().year
        for scope in self._scopes:
            if self._key(scope) not in grant.scope_ids:
                continue
            for path in self._files(scope):
                grant.raise_if_cancelled()  # a revoke stops the read between two files
                try:
                    real = self._policy.check_read(path)  # G1, on the real path
                except DeskThreadError:
                    continue  # off-limits or outside: never opened, counted as not accessible
                key = self._key(path)
                if not supported(path):
                    yield Uncounted(
                        source_id=self._source_id,
                        location=key,
                        reason=ErrorCode.UNSUPPORTED_TYPE.value,
                    )
                    continue
                try:
                    for item in read_file(real, self._source_id, key, year, self._role):
                        # The viewer and the image reader open the file again by this path.
                        yield item.model_copy(update={"meta": {**item.meta, "path": str(real)}})
                except DeskThreadError as err:
                    yield Uncounted(source_id=self._source_id, location=key, reason=err.code.value)


class LockedSource:
    """A private app that was noticed by its folder name. It can never be read."""

    def __init__(self, source_id: str, label: str) -> None:
        self._source_id, self._label = source_id, label

    @property
    def source_id(self) -> str:
        return self._source_id

    @property
    def kind(self) -> SourceKind:
        return SourceKind.PRIVATE_APP

    @property
    def label(self) -> str:
        return self._label

    def os_permission(self) -> OsPermission:
        return OsPermission.NOT_NEEDED

    def list_scopes(self) -> list[Scope]:
        return []  # not even counted

    def read(self, grant: ReadGrant) -> Iterator[Item | Uncounted]:
        raise DeskThreadError(ErrorCode.SOURCE_LOCKED)


def scan(root: Path, policy: AccessPolicy) -> list[FolderAdapter | LockedSource]:
    """Recognise the sources under a chosen folder by folder names. Reads no content."""
    root = policy.confine(root)
    found: list[FolderAdapter | LockedSource] = []
    chat: list[Path] = []
    exports = root / EXPORTS
    top = sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith("."))
    app_folders = sorted(p for p in exports.iterdir() if p.is_dir()) if exports.is_dir() else []
    for folder in [*app_folders, *top]:
        name = norm(folder.name).lower()
        if name in PRIVATE_APP_NAMES:
            found.append(LockedSource(f"private:{name}", folder.name))
        elif folder.parent == exports and name in KNOWN_EXPORTS:
            kind, label, role = KNOWN_EXPORTS[name]
            # A calendar is allowed one calendar at a time, so each file is its own scope.
            scopes = _visible_files(folder) if kind is SourceKind.CALENDAR else [folder]
            found.append(
                FolderAdapter(
                    source_id=f"folder:{name}",
                    kind=kind,
                    label=label,
                    root=root,
                    scopes=scopes,
                    policy=policy,
                    role=role,
                )
            )
        elif folder.parent == exports and name in CHAT_EXPORTS:
            chat.append(folder)
    if chat:
        found.append(
            FolderAdapter(
                source_id="folder:chat-exports",
                kind=SourceKind.CHAT_EXPORT,
                label="Teams and Slack exports",
                root=root,
                scopes=chat,
                policy=policy,
                role="chat",
            )
        )
    plain = [p for p in top if p != exports and norm(p.name).lower() not in PRIVATE_APP_NAMES]
    if plain:
        found.append(
            FolderAdapter(
                source_id="folder:documents",
                kind=SourceKind.DOCUMENTS,
                label="Documents",
                root=root,
                scopes=plain,
                policy=policy,
                role="document",
                want_images=False,
            )
        )
        found.append(
            FolderAdapter(
                source_id="folder:images",
                kind=SourceKind.IMAGES,
                label="Images and screenshots",
                root=root,
                scopes=plain,
                policy=policy,
                want_images=True,
            )
        )
    return found
