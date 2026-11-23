"""Compare the answering models that are already on this Mac, and a no-model baseline.

    uv run python -m eval.compare --models gemma4:e4b,gemma4:e2b,phi4-mini:latest --runs 3 \
        --folder <core demo folder> --out result.json

It never downloads a model. Invented data only; it prints counts, seconds and pass or fail.
The baseline (the "floor") is an ordinary exact-phrase search of the question, with no model.
"""

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Any

from app.model import ModelGateway, ModelServer
from app.search import keyword_floor
from app.session import Session, open_folder, work_profile
from contracts.errors import DeskThreadError
from eval.run import QUESTIONS, TRUTH, cited_paths, score

REPO = Path(__file__).resolve().parent.parent


def floor_passes(session: Session, question: dict[str, Any]) -> bool:
    """What a plain search would give: pass only if it finds the expected material."""
    hits = keyword_floor(question["question"].rstrip("?"), session.store.items())
    expect = question["expect"]
    if expect.get("not_found"):
        return not hits
    wanted = set(expect.get("paths", []))
    for pid in expect.get("promises", []):
        wanted |= {s["path"] for p in TRUTH["promises"] if p["id"] == pid for s in p["sources"]}
    return bool({h.location for h in hits} & wanted)


def run_model(
    session: Session, gateway: ModelGateway, tag: str, runs: int, questions: list[dict[str, Any]]
) -> dict[str, Any]:
    gateway.select(tag)
    per_question: dict[str, dict[str, Any]] = {
        q["id"]: {"pass": [], "seconds": [], "cited": [], "errors": 0} for q in questions
    }
    for run in range(runs):
        for q in questions:
            slot = per_question[q["id"]]
            try:
                answer = session.assistant.ask(q["question"])
            except DeskThreadError as err:
                slot["errors"] += 1
                slot["pass"].append(False)
                print(f"  {tag} run {run + 1} {q['id']}: error {err.code}", flush=True)
                continue
            ok, _why = score(session, answer, q["expect"])
            slot["pass"].append(ok)
            slot["seconds"].append(answer.seconds)
            paths = sorted(set().union(*cited_paths(session, answer)) if answer.points else set())
            slot["cited"].append(paths)
            print(
                f"  {tag} run {run + 1} {q['id']}: {'pass' if ok else 'fail'} "
                f"{answer.seconds:.1f}s",
                flush=True,
            )
    return per_question


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", required=True, help="comma-separated tags already on this Mac")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--set", default="tuning", choices=["tuning", "held_out"])
    parser.add_argument("--folder", type=Path, default=REPO / "demo-laptop")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    questions: list[dict[str, Any]] = QUESTIONS[args.set]

    gateway, server = ModelGateway(), ModelServer()
    if not server.start(gateway):
        print("the local model server did not start")
        return 2
    try:
        installed = gateway.installed()
        tags = [t for t in args.models.split(",") if t]
        missing = [t for t in tags if t not in installed]
        if missing:
            print("not on this Mac (no download is done here):", ", ".join(missing))
            return 2
        session = open_folder(args.folder, gateway)
        work_profile(session)
        session.store.refresh()
        result: dict[str, Any] = {
            "set": args.set,
            "runs": args.runs,
            "items": len(session.store.items()),
            "models": {},
        }
        result["floor"] = {q["id"]: floor_passes(session, q) for q in questions}
        print(f"floor (no model): {sum(result['floor'].values())} of {len(questions)}", flush=True)
        for tag in tags:
            print(f"model {tag}", flush=True)
            result["models"][tag] = run_model(session, gateway, tag, args.runs, questions)
            slots = result["models"][tag].values()
            seconds = [s for slot in slots for s in slot["seconds"]]
            mean_pass = sum(sum(slot["pass"]) / max(len(slot["pass"]), 1) for slot in slots)
            print(
                f"  {tag}: about {mean_pass:.1f} of {len(questions)} per run, "
                f"median {statistics.median(seconds or [0]):.1f}s",
                flush=True,
            )
        args.out.write_text(json.dumps(result, indent=1))
        return 0
    finally:
        server.stop()


if __name__ == "__main__":
    sys.exit(main())
