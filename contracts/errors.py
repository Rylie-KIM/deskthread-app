"""Error codes. Errors are explicit values with a code, never bare exceptions (R7)."""

from enum import StrEnum


class ErrorCode(StrEnum):
    # Access and consent (G1, FT-53)
    SOURCE_NOT_ALLOWED = "E-101"
    SOURCE_LOCKED = "E-102"
    SOURCE_UNKNOWN = "E-103"
    PATH_OUTSIDE_ALLOWED = "E-104"
    ITEM_OFF_LIMITS = "E-105"
    READ_CANCELLED = "E-106"
    OS_PERMISSION_MISSING = "E-107"
    # Readers
    UNSUPPORTED_TYPE = "E-201"
    READ_FAILED = "E-202"
    # Model gateway (G3)
    MODEL_UNAVAILABLE = "E-301"
    MODEL_NOT_PINNED = "E-302"
    MODEL_BAD_OUTPUT = "E-303"
    # Answer gate (G4)
    CITATION_INVALID = "E-401"
    NOT_FOUND = "E-402"
    # Local API (FT-23)
    BAD_TOKEN = "E-501"
    BAD_ORIGIN = "E-502"
    BAD_HOST = "E-503"
    BAD_REQUEST = "E-504"
    # Live-run output guard (R1)
    REDACTION_BLOCKED = "E-601"
    # Anything else
    INTERNAL = "E-999"


class DeskThreadError(Exception):
    """An error with a code. The message must never contain content from a source."""

    def __init__(self, code: ErrorCode, message: str = "") -> None:
        super().__init__(f"{code.value} {message}".strip())
        self.code = code
        self.message = message
