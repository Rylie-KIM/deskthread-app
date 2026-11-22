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
    if session is not None:
        read = sum(a.count for a in session.broker.audit() if a.action is AuditAction.READ)
        given, questions = session.assistant.items_given, session.assistant.questions
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
