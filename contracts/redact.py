"""Output guard for live runs against the user's real apps (dev rule R1).

Anything printed by a command is read by a hosted assistant and so leaves the machine.
A live script therefore prints only through live_print(), which lets through numbers, ids
and a fixed list of words, and raises on everything else. The error never repeats the text.
"""

import re

from contracts.errors import DeskThreadError, ErrorCode

# Words a live report may contain. Deliberately small: add a word here, never loosen the rule.
ALLOWED_WORDS: frozenset[str] = frozenset(
    {
        "pass",
        "fail",
        "ok",
        "error",
        "errors",
        "skipped",
        "blocked",
        "allowed",
        "denied",
        "yes",
        "no",
        "true",
        "false",
        "none",
        "count",
        "counts",
        "total",
        "items",
        "item",
        "scopes",
        "scope",
        "sources",
        "source",
        "notes",
        "calendar",
        "calendars",
        "events",
        "mail",
        "mailboxes",
        "messages",
        "reminders",
        "lists",
        "folders",
        "files",
        "images",
        "documents",
        "units",
        "read",
        "reads",
        "writes",
        "write",
        "locked",
        "unsupported",
        "canary",
        "found",
        "missing",
        "live",
        "test",
        "tests",
        "result",
        "results",
        "seconds",
        "ms",
        "s",
        "mb",
        "gb",
        "per",
        "min",
        "max",
        "avg",
        "code",
        "class",
        "timeout",
        "permission",
        "granted",
        "unknown",
        "t",
        "u",
        "l",
        "n",
        "d",
        "e",
        "ft",
        "un",
        "g",
        "p",
    }
)

_WORD = re.compile(r"[A-Za-z]+")
_ALLOWED_CHARS = re.compile(r"[A-Za-z0-9 \n.,:;=()\[\]/%+_\-|]*")


def redact(text: str) -> str:
    """Return text unchanged if it is safe to print, else raise REDACTION_BLOCKED."""
    if not _ALLOWED_CHARS.fullmatch(text):
        # Any other character (quotes, non-ASCII letters, @ ...) can only come from content.
        raise DeskThreadError(ErrorCode.REDACTION_BLOCKED, "output held back: characters")
    bad = sum(1 for w in _WORD.findall(text) if w.lower() not in ALLOWED_WORDS)
    if bad:
        raise DeskThreadError(ErrorCode.REDACTION_BLOCKED, f"output held back: {bad} words")
    return text


def live_print(text: str) -> None:
    """The only print a live script may use."""
    print(redact(text))


def safe_error(exc: BaseException) -> str:
    """A printable stand-in for an exception: its code only, never its message or trace."""
    code = exc.code.value if isinstance(exc, DeskThreadError) else ErrorCode.INTERNAL.value
    return f"error code={code}"
