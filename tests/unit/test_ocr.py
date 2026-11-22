"""macOS text recognition (app/ocr.py): the text of a picture, read in memory."""

import io

import pytest
from PIL import Image, ImageDraw, ImageFont

from app import ocr


def _picture(lines: list[str]) -> bytes:
    image = Image.new("RGB", (900, 120 + 90 * len(lines)), "white")
    pen = ImageDraw.Draw(image)
    font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 44)
    for number, line in enumerate(lines):
        pen.text((40, 40 + 90 * number), line, fill="black", font=font)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture
def recognition(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("Vision")
    monkeypatch.delenv("DESKTHREAD_OCR", raising=False)


def test_the_text_of_a_picture_comes_back_top_to_bottom(recognition: None) -> None:
    lines = ocr.recognise(
        _picture(["Budget approved for the course", "Book by 18 December", "Ask Mark"])
    )
    assert lines is not None and len(lines) == 3
    assert "Budget" in lines[0] and "December" in lines[1] and "Mark" in lines[2]


def test_a_picture_without_text_gives_an_empty_list_and_junk_gives_none(recognition: None) -> None:
    blank = io.BytesIO()
    Image.new("RGB", (300, 200), "white").save(blank, format="PNG")
    assert ocr.recognise(blank.getvalue()) == []
    assert ocr.recognise(b"this is not a picture") is None


def test_recognition_can_be_switched_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DESKTHREAD_OCR", "off")
    assert ocr.available() is False and ocr.recognise(b"x") is None
