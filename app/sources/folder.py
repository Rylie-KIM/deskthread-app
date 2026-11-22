"""The folder connector (FT-01, FT-03, FT-43): files in a folder the user chose.

scan() looks at names only and builds one adapter per kind of source it recognises. No file
content is read until the user allows a source and the broker hands out a grant. Works on any
operating system and is also the fixture for the automated tests and the fallback for the
Mac app connectors.
"""

from collections.abc import Iterator
from pathlib import Path

from app.clock import now
from app.policy import PERSONAL_CHAT_NAMES, AccessPolicy, norm
from app.readers.files import IMAGE_SUFFIXES, read_file, supported
from contracts.adapters import OsPermission, ReadGrant, Scope
from contracts.errors import DeskThreadError, ErrorCode
from contracts.items import Item, SourceKind, Uncounted

EXPORTS = "App-exports"
# Folder name inside App-exports -> (kind, label, reader role)
KNOWN_EXPORTS: dict[str, tuple[SourceKind, str, str]] = {
    "notes": (SourceKind.NOTES, "Note files", ""),
    "mail": (SourceKind.MAIL, "Mail files", ""),
    "calendar": (SourceKind.CALENDAR, "Calendar files", ""),
    "reminders": (SourceKind.REMINDERS, "Reminder files", "reminders"),
}
CHAT_EXPORTS = frozenset({"teams", "slack", "zoom"}) | PERSONAL_CHAT_NAMES


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
        prefix: str = "",
    ) -> None:
        self._source_id, self._kind, self._label = source_id, kind, label
        self._policy = policy
        # One part per chosen folder: (the folder, a prefix for its keys, its scopes). The
        # first chosen folder has no prefix, so its keys are plain paths inside it.
        self._parts: list[tuple[Path, str, list[Path]]] = [(root, prefix, scopes)]
        self._role = role
        self._want_images = want_images  # True: images only; False: no images; None: all

        # Read once per session: (changed time, size) and the items, by real path. In memory
        # only; dropped on revoke, Clear memory and End session.
        self._parsed: dict[str, tuple[tuple[int, int], list[Item]]] = {}

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

    def extend(self, other: "FolderAdapter") -> None:
        """Take in the same kind of source from another chosen folder."""
        self._parts += other._parts

    @property
    def _scopes(self) -> list[Path]:
        return [scope for _, _, scopes in self._parts for scope in scopes]

    def _key(self, path: Path) -> str:
        for root, prefix, _ in self._parts:
            if path == root:
                return norm(prefix.rstrip("/") or root.name)
            if root in path.parents:
                return norm(prefix + str(path.relative_to(root)))
        raise DeskThreadError(ErrorCode.PATH_OUTSIDE_ALLOWED)

    def forget(self) -> None:
        """Drop what was read from this source (revoke, Clear memory, End session)."""
        self._parsed.clear()

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
        seen: set[str] = set()
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
                    stamp = real.stat()
                    mark = (stamp.st_mtime_ns, stamp.st_size)
                    held = self._parsed.get(str(real))
                    if held is None or held[0] != mark:  # new or changed: read it
                        # The viewer and the image reader open the file again by this path.
                        fresh = [
                            item.model_copy(update={"meta": {**item.meta, "path": str(real)}})
                            for item in read_file(real, self._source_id, key, year, self._role)
                        ]
                        held = self._parsed[str(real)] = (mark, fresh)
                    seen.add(str(real))
                    yield from held[1]
                except OSError:
                    continue  # deleted between listing and reading: simply gone
                except DeskThreadError as err:
                    yield Uncounted(source_id=self._source_id, location=key, reason=err.code.value)
        for gone in set(self._parsed) - seen:
            del self._parsed[gone]  # a deleted file leaves memory at the next question


VIDEO_SUFFIXES = frozenset({".mov", ".mp4", ".m4v", ".avi", ".mkv", ".webm"})


def kinds_in(root: Path) -> dict[str, int]:
    """What a folder holds, by file name only: files that can be read, pictures, videos and
    recordings (cannot be read), and other formats (cannot be read). No file is opened."""
    counts = {"files": 0, "pictures": 0, "videos": 0, "other": 0}
    for path in _visible_files(root):
        suffix = path.suffix.lower()
        if suffix in IMAGE_SUFFIXES:
            counts["pictures"] += 1
        elif suffix in VIDEO_SUFFIXES:
            counts["videos"] += 1
        elif supported(path):
            counts["files"] += 1
        else:
            counts["other"] += 1
    return counts


def scan_all(roots: list[Path], policy: AccessPolicy) -> list[FolderAdapter]:
    """The sources of every chosen folder, one adapter per kind across all of them."""
    merged: dict[str, FolderAdapter] = {}
    used: set[str] = set()
    for number, root in enumerate(roots):
        prefix = ""
        if number:  # later folders get their name in front of their keys, made unique
            name, count = root.name, 2
            while name in used:
                name, count = f"{root.name}-{count}", count + 1
            used.add(name)
            prefix = f"{name}/"
        for adapter in scan(root, policy, prefix):
            if adapter.source_id in merged:
                merged[adapter.source_id].extend(adapter)
            else:
                merged[adapter.source_id] = adapter
    return list(merged.values())


def scan(root: Path, policy: AccessPolicy, prefix: str = "") -> list[FolderAdapter]:
    """Recognise the sources under a chosen folder by folder names. Reads no content."""
    root = policy.confine(root)
    found: list[FolderAdapter] = []
    chat: list[Path] = []
    exports = root / EXPORTS
    top = sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith("."))
    app_folders = sorted(p for p in exports.iterdir() if p.is_dir()) if exports.is_dir() else []
    for folder in [*app_folders, *top]:
        name = norm(folder.name).lower()
        if folder.parent == exports and name in KNOWN_EXPORTS:
            kind, label, role = KNOWN_EXPORTS[name]
            # A calendar is allowed one calendar at a time, so each file is its own scope.
            scopes = _visible_files(folder) if kind is SourceKind.CALENDAR else [folder]
            found.append(
                FolderAdapter(
                    source_id=f"folder:{name}",
                    kind=kind,
                    label=label,
                    root=root,
                    prefix=prefix,
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
                label="Chat files",
                root=root,
                prefix=prefix,
                scopes=chat,
                policy=policy,
                role="chat",
            )
        )
    # A folder laid out like a laptop (with App-exports) is split by its top folders. Any other
    # folder is one piece: everything in it, files at the top included.
    plain = [p for p in top if p != exports] if exports.is_dir() else [root]
    if plain:
        found.append(
            FolderAdapter(
                source_id="folder:documents",
                kind=SourceKind.DOCUMENTS,
                label="Files",
                root=root,
                prefix=prefix,
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
                label="Pictures",
                root=root,
                prefix=prefix,
                scopes=plain,
                policy=policy,
                want_images=True,
            )
        )
    return found
