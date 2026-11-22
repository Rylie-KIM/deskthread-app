"""A scripted stand-in for the local model, so pipeline tests are fast and exact.

What the real model does is measured separately by eval/run.py against the ground truth.
"""

import json
import re
from collections.abc import Callable
from pathlib import Path

from app.assistant import Assistant
from app.session import Session, open_folder, work_profile
from contracts.api import Answer
from contracts.gates import Gate, Outcome

Cite = tuple[str, str]  # (words in the note's heading line, words in the cited line)
Point = tuple[str, str, list[Cite]]  # label, status, citations
Script = Callable[[str], list[Point]]  # question -> points


class FakeModel:
    """Answers the four prompts the app sends. Cites by looking lines up in the prompt."""

    def __init__(self, script: Script, verify: str = "yes", words: list[str] | None = None):
        self.script, self.verify, self.words = script, verify, words or []
        self.calls = 0
        self.summary: list[dict[str, object]] = []  # what the fake writes as a summary
        self.prompts: list[str] = []
        self.raw_cites: list[dict[str, object]] = []  # extra citations to inject as they are
        self.image_text: dict[bytes, str] = {}  # what the fake "sees" in a given image

    def complete(self, prompt: str, images: list[bytes] | None = None) -> str:
        self.calls += 1
        self.prompts.append(prompt)
        if images:
            return self.image_text.get(images[0], "NONE")
        if "other single words" in prompt:
            return json.dumps({"words": self.words})
        if "one entry per line" in prompt:
            count = len(re.findall(r"^\d+\. \(from the note", prompt, re.M))
            return json.dumps({"answers": [self.verify] * count})
        if "lines it rests on" in prompt:
            return json.dumps({"sentences": self.summary})
        question = re.search(r"^Question: (.+)$", prompt, re.M)
        assert question
        points = []
        for label, status, cites in self.script(question[1]):
            found = [c for c in (self._locate(prompt, *cite) for cite in cites) if c]
            points.append({"label": label, "status": status, "cites": found + self.raw_cites})
        return "Here you go:\n" + json.dumps({"points": points})

    @staticmethod
    def _locate(prompt: str, title_words: str, line_words: str) -> dict[str, object] | None:
        notes = prompt.split("Notes:\n", 1)[1]
        for block in notes.split("\n\n"):
            head, *lines = block.split("\n")
            if title_words in head:
                for line in lines:
                    number, _, text = line.partition(". ")
                    if line_words in text:
                        return {"id": head[1 : head.index("]")], "line": int(number)}
        return None


SAM_BRIEF: list[Point] = [
    (
        "Online course",
        "open",
        [("recap", "data storytelling course"), ("Course budget", "Budget approved")],
    ),
    (
        "February conference",
        "superseded",
        [("follow-ups", "conference in Feb"), ("recap", "dropped")],
    ),
    ("Intro to Mark", "open", [("follow-ups", "intro to Mark")]),
    ("More ownership", "done", [("more ownership", "more ownership??")]),
]

STORY_NOW = "2026-11-22T19:00:00+00:00"  # Sunday evening; the one-to-one is Monday 10:00


def open_work(root: Path, model: FakeModel) -> tuple[Session, Assistant]:
    """A session on the demo laptop with the Work profile on."""
    session = open_folder(root, model)
    work_profile(session)
    return session, session.assistant


def gate(answer: Answer, which: Gate) -> tuple[Outcome, str]:
    result = next(g for g in answer.gate_trace if g.gate is which)
    return result.outcome, result.detail


def wait_until_prepared(client: object, seconds: float = 15.0) -> None:
    """Wait for the background job that reads the pictures after Pictures is switched on."""
    import time

    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if not client.get("/api/preparing").json()["active"]:  # type: ignore[attr-defined]
            return
        time.sleep(0.05)
    raise AssertionError("the pictures were not prepared in time")
