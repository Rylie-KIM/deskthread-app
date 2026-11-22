# DeskThread

A new session starts at `plan/START_HERE.md` (local only, not in git), then follows
`plan/dev.rules.md` and `plan/dev.tasks.md` task by task.

- `make check` must pass before any commit. One commit per feature unit; the user approves each commit.
- Live runs against the real Mac apps print counts and pass/fail only (`contracts/redact.py`).
- The app writes nothing to disk and connects only to `127.0.0.1`.
- Never commit `plan/`, `design-sample/`, model files, real data or recordings.
