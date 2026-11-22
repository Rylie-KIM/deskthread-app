"""U-redact: the live-run output guard blocks content and lets counts through (R1.2)."""

import pytest

from contracts.errors import DeskThreadError, ErrorCode
from contracts.redact import live_print, redact, safe_error

CANARY = "ZX9-CANARY-4471-BLUEHERON"


@pytest.mark.parametrize(
    "line",
    [
        "T-05 calendar: calendars=3 events=120 seconds=0.42 pass",
        "notes: folders=2 items=57 locked=1 writes=0 ok",
        "U1 pass | U2 pass | L-1 fail (count=2)",
        "error code=E-107",
        "",
    ],
)
def test_counts_ids_and_fixed_words_pass(line: str) -> None:
    assert redact(line) == line


@pytest.mark.parametrize(
    "line",
    [
        CANARY,
        f"found {CANARY} in 1 item",
        "1:1 with Sam - development plan",  # a sample title
        "Budget approved up to 800",
        "sam@ukpharma.example",
        "회의 메모",  # non-ASCII content
        'title="x"',
        "Traceback (most recent call last)",
    ],
)
def test_content_is_blocked(line: str) -> None:
    with pytest.raises(DeskThreadError) as err:
        redact(line)
    assert err.value.code is ErrorCode.REDACTION_BLOCKED


def test_the_error_never_repeats_the_content() -> None:
    with pytest.raises(DeskThreadError) as err:
        redact(f"note title {CANARY}")
    assert "CANARY" not in str(err.value)
    assert "BLUEHERON" not in str(err.value)


def test_live_print_prints_nothing_when_blocked(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(DeskThreadError):
        live_print(f"items=3 {CANARY}")
    assert capsys.readouterr().out == ""
    live_print("items=3 pass")
    assert capsys.readouterr().out == "items=3 pass\n"


def test_safe_error_gives_a_code_and_passes_the_guard() -> None:
    assert safe_error(ValueError(CANARY)) == "error code=E-999"
    coded = DeskThreadError(ErrorCode.OS_PERMISSION_MISSING, CANARY)
    assert safe_error(coded) == "error code=E-107"
    assert redact(safe_error(coded))
