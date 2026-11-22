# DeskThread

A new session starts at the "Current state" section of `plan/dev.tasks.md` (local only, not in
git), then follows `plan/dev.rules.md` and that task list task by task.

- `make check` must pass before any commit. One commit per task or feature, with the message format of `plan/dev.rules.md` R9, pushed to `origin/main` after each (user, 2026-11-22). Update `plan/dev.tasks.md` in the same step.
- Live runs against the real Mac apps print counts and pass/fail only (`contracts/redact.py`).
- The app writes nothing to disk and connects only to `127.0.0.1`.
- Never commit `plan/`, `design-sample/`, model files, real data or recordings.
