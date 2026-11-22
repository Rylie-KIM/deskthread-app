"""Run DeskThread in the terminal: prepare the next meeting, then ask questions.

    uv run python -m scripts.ask                      # the invented demo laptop, story clock
    uv run python -m scripts.ask --folder ~/SomeFolder --now ""    # your own folder, real clock

Starts its own model server on 127.0.0.1, switches on the Work profile for the folder and
stops the server when you leave. Nothing is written to disk. Printed text is your own
notes: run this in your own terminal, not through a hosted assistant.
"""

import argparse
import os
import sys
from pathlib import Path

from app.clock import ENV_NOW
from app.model import ModelGateway, ModelServer
from app.session import open_folder, work_profile
from contracts.api import Answer

REPO = Path(__file__).resolve().parent.parent
STORY_NOW = "2026-11-22T19:00:00+00:00"


def show(answer: Answer) -> None:
    print(f"\nQ: {answer.question}")
    if answer.message:
        print(f"   {answer.message}")
    for point in answer.points:
        note = f"  ({point.note})" if point.note else ""
        print(f"\n  [{point.status.value}] {point.label}{note}")
        for cite in point.citations:
            when = cite.date.strftime("%d %b %Y") if cite.date else "undated"
            via = ", read from the image by the model" if cite.read_by_model else ""
            print(f'      "{cite.quote}"')
            print(f"        {cite.source_label}: {cite.title} ({when}{via})")
    cov = answer.coverage
    print(
        f"\n  Coverage: {cov.accessible} readable, {cov.searched} searched, {cov.unsupported} "
        f"unreadable, {cov.given_to_model} shown to the model, {cov.cited} cited"
    )
    out_of_reach = ", ".join(
        f"{name}: {'locked' if count is None else count}"
        for name, count in cov.not_accessible.items()
    )
    print(f"  Out of reach: {out_of_reach}")
    for gate in answer.gate_trace:
        print(f"  {gate.gate.value} {gate.outcome.value}: {gate.detail}")
    print(f"  ({answer.seconds} s)")


def main() -> int:
    parser = argparse.ArgumentParser(description="DeskThread in the terminal")
    parser.add_argument("--folder", type=Path, default=REPO / "demo-laptop")
    parser.add_argument("--now", default=STORY_NOW, help='fixed clock; "" for the real time')
    parser.add_argument("question", nargs="*", help="ask this and exit")
    args = parser.parse_args()
    if args.now:
        os.environ[ENV_NOW] = args.now
    folder = args.folder.expanduser()
    if not folder.is_dir():
        print(f"Folder not found: {folder}")
        print("Build the demo one first: uv run python demo-data/make_demo_data.py")
        return 2

    gateway, server = ModelGateway(), ModelServer()
    if not server.start(gateway):
        print("The local model server did not start. Is Ollama installed (brew install ollama)?")
        return 2
    try:
        session = open_folder(folder, gateway)
        work_profile(session)
        on = [s.label for s in session.broker.states() if s.status.value == "on"]
        locked = [s.label for s in session.broker.states() if s.status.value == "locked"]
        print(f"On: {', '.join(on)}\nLocked off: {', '.join(locked) or 'none'}")
        if args.question:
            show(session.assistant.ask(" ".join(args.question)))
            return 0
        meetings = session.assistant.meetings()
        if meetings:
            first = meetings[0]
            print(f"\nNext meeting: {first.title}, {first.start:%a %d %b %H:%M}. Preparing...")
            show(session.assistant.prepare(first.meeting_id))
        while True:
            try:
                question = input("\nAsk (empty line to end the session): ").strip()
            except EOFError:
                break
            if not question:
                break
            show(session.assistant.ask(question))
        session.broker.revoke_all()
        session.assistant.forget()
        print("Session ended: sources revoked, memory cleared, model server stopping.")
        return 0
    finally:
        gateway.unload()
        server.stop()


if __name__ == "__main__":
    sys.exit(main())
