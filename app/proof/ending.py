"""End session and its receipt (FT-16, FT-40).

End session revokes every source, clears memory, unloads the model, stops the model server
and then stops this backend, so the address refuses connections afterwards (N-6). Just
before, the page gets a receipt: counts and fingerprints only, never note text.
"""

from fastapi import BackgroundTasks, FastAPI

from app.proof.evidence import LIMITS, Evidence, files_written
from app.runtime import Runtime
from contracts.api import Receipt
from contracts.broker import AuditAction


def receipt(runtime: Runtime, evidence: Evidence) -> Receipt:
    """Summarise the session, then clear it. The numbers are taken before the clearing."""
    session = runtime.session
    proof = evidence.proof()
    read = given = questions = 0
    read_by: dict[str, int] = {}
    given_by: dict[str, int] = {}
    if session is not None:
        labels = {s.source_id: s.label for s in session.broker.states()}
        # A folder is read again for every question: count a source once, at its largest.
        for line in session.broker.audit():
            if line.action is AuditAction.READ:
                name = labels.get(line.source_id, line.source_id)
                read_by[name] = max(read_by.get(name, 0), line.count)
        read = sum(read_by.values())
        given, questions = session.assistant.items_given, session.assistant.questions
        given_by = {labels.get(k, k): v for k, v in session.assistant.given_by.items()}
        session.broker.revoke_all()
        session.assistant.forget()
    unloaded = runtime.gateway.unload() if runtime.gateway else True
    cleared = session is None or session.store.items() == []
    return Receipt(
        items_read=read,
        items_given_to_model=given,
        questions=questions,
        memory_cleared=cleared,
        model_unloaded=unloaded,
        files_written_by_app=files_written(),
        all_connections_local=proof.all_local,
        folders=proof.folders,
        limits=LIMITS,
        read_by_source=read_by,
        given_by_source=given_by,
    )


def shut_down(runtime: Runtime) -> None:
    """Stop the model server we started, then this backend."""
    if runtime.server is not None:
        runtime.server.stop()
    runtime.stop()


def register(app: FastAPI, runtime: Runtime, evidence: Evidence) -> None:
    @app.post("/api/end-session")
    def end_session(background: BackgroundTasks) -> Receipt:
        with runtime.ask_lock:
            result = receipt(runtime, evidence)
        background.add_task(shut_down, runtime)  # after the receipt has been sent
        return result
