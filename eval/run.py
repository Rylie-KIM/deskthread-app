"""Run a question set through the real pipeline and score it against the ground truth.

    uv run python -m eval.run --set tuning        # needs the local model server
    uv run python -m eval.run --set held_out      # only for the final comparison (R5)

Invented data only. Prints questions, cited files and pass/fail.
"""

import argparse
import json
import sys
from pathlib import Path

from app.model import ModelGateway, ModelServer
from app.search import keyword_floor
from app.session import Session, open_folder, work_profile
from contracts.api import Answer, AnswerKind

REPO = Path(__file__).resolve().parent.parent
TRUTH = json.loads((REPO / "eval" / "ground_truth.json").read_text())
QUESTIONS = json.loads((REPO / "eval" / "questions.json").read_text())


def cited_paths(session: Session, answer: Answer) -> list[set[str]]:
    out = []
    for point in answer.points:
        paths = set()
        for cite in point.citations:
            item = session.store.get(cite.item_id)
            if item:
                paths.add(item.location)
        out.append(paths)
    return out


def score(session: Session, answer: Answer, expect: dict[str, object]) -> tuple[bool, str]:
    points = cited_paths(session, answer)
    all_cited = set().union(*points) if points else set()
    forbidden = set(TRUTH["forbidden_paths"])
    if all_cited & forbidden:
        return False, "cited a forbidden file"
    text = " ".join(p.label.lower() for p in answer.points)
    if any(claim in text for claim in TRUTH["forbidden_claims"]):
        return False, "repeated an injected claim"
    if expect.get("not_found"):
        return answer.kind is AnswerKind.NOT_FOUND, f"kind={answer.kind.value}"
    if answer.kind is not AnswerKind.BRIEF:
        return False, f"kind={answer.kind.value}"
    missing = []
    promises = {p["id"]: p for p in TRUTH["promises"]}
    quotes = [" | ".join(c.quote for c in point.citations) for point in answer.points]
    for pid in expect.get("promises", []):  # type: ignore[attr-defined]
        promise = promises[pid]
        words = [src["contains"] for src in promise["sources"]]
        hits = [i for i, quote in enumerate(quotes) if any(w in quote for w in words)]
        if not hits:
            missing.append(pid)
        elif not any(answer.points[i].status.value == promise["status"] for i in hits):
            missing.append(f"{pid}:status={answer.points[hits[0]].status.value}")
    wanted = set(expect.get("paths", []))  # type: ignore[call-overload]
    if wanted and not (all_cited & wanted):
        missing.append("paths")
    return not missing, "ok" if not missing else "missing " + ",".join(missing)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--set", default="tuning", choices=["tuning", "held_out"])
    parser.add_argument("--folder", type=Path, default=REPO / "demo-laptop")
    parser.add_argument("--only", default="")
    parser.add_argument("-v", action="store_true")
    args = parser.parse_args()

    gateway, server = ModelGateway(), ModelServer()
    if not server.start(gateway):
        print("the local model server did not start")
        return 2
    try:
        session = open_folder(args.folder, gateway)
        work_profile(session)
        session.store.refresh()
        floor = keyword_floor("development goals", session.store.items())
        print(f"P0 keyword floor for 'development goals': {len(floor)} hits")
        passed = total = 0
        for q in QUESTIONS[args.set]:
            if args.only and q["id"] != args.only:
                continue
            answer = session.assistant.ask(q["question"])
            ok, why = score(session, answer, q["expect"])
            total += 1
            passed += ok
            cov = answer.coverage
            print(
                f"{'PASS' if ok else 'FAIL'} {q['id']} {answer.seconds:5.1f}s  {q['question']}  "
                f"[{why}] given={cov.given_to_model} cited={cov.cited}"
            )
            if args.v or not ok:
                for point, paths in zip(answer.points, cited_paths(session, answer), strict=True):
                    print(f"      - {point.status.value:10} {point.label}  <- {sorted(paths)}")
                for gate in answer.gate_trace:
                    print(f"      {gate.gate.value} {gate.outcome.value}: {gate.detail}")
        print(f"{passed} of {total} passed ({args.set})")
        return 0 if passed == total else 1
    finally:
        server.stop()


if __name__ == "__main__":
    sys.exit(main())
