"""Read the text of a picture with macOS's own text recognition (Apple Vision).

It is a system feature, not an AI model that is downloaded. The picture comes in as bytes in
memory and the text goes out as lines in memory: nothing is written by this code, and nothing
is sent anywhere (Vision runs on this Mac). Only English is asked for (the product is English
only). Without Vision (another system, or `DESKTHREAD_OCR=off`) `available()` is False and
the caller falls back to the AI model that reads pictures.
"""

import os
from typing import Any

LANGUAGES = ["en-GB", "en-US"]


def available() -> bool:
    if os.environ.get("DESKTHREAD_OCR") == "off":
        return False
    try:
        import Vision  # noqa: F401
    except ImportError:
        return False
    return True


def recognise(data: bytes) -> list[str] | None:
    """The lines of text in a picture, top to bottom; [] when there is none; None when this
    picture could not be read at all (or Vision is not there)."""
    if not available():
        return None
    import Vision
    from Foundation import NSData

    handler = Vision.VNImageRequestHandler.alloc().initWithData_options_(
        NSData.dataWithBytes_length_(data, len(data)), {}
    )
    request = Vision.VNRecognizeTextRequest.alloc().init()
    request.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
    request.setRecognitionLanguages_(LANGUAGES)
    request.setUsesLanguageCorrection_(True)
    done, _error = handler.performRequests_error_([request], None)
    if not done:
        return None
    found: list[tuple[float, float, str]] = []
    for observation in request.results() or []:
        best: Any = observation.topCandidates_(1)
        if not best:
            continue
        box = observation.boundingBox()  # 0 to 1, the origin is at the bottom left
        found.append((-(box.origin.y + box.size.height), box.origin.x, str(best[0].string())))
    found.sort()  # top to bottom, then left to right
    return [text.strip() for _y, _x, text in found if text.strip()]
