# DeskThread

A local-first Mac app that finds what the user wrote down and quotes the source. It runs on the
user's Mac only, reads with read permission only, and writes nothing to disk.

## Start of every session

1. Read the "Current state" section of `plan/dev.tasks.md` (local only, not in git).
2. Follow `plan/dev.rules.md` and the task list, task by task.
3. Reply to the user in Korean. Everything inside the product is English only: UI, prompts, demo and seeded data.

## Rules that never bend

- The app writes nothing to disk and connects only to `127.0.0.1`.
- Read is the only permission. No code path may write, send, move or delete in the user's data or apps.
- Live runs against the real Mac apps print counts and pass/fail only (`contracts/redact.py`).
- Never commit `plan/`, `design-sample/`, model files, real data or recordings.

## Working agreement

- `make check` must pass before any commit.
- One commit per task or feature, in the message format of `plan/dev.rules.md` R9. Never bundle two.
- Push to `origin/main` after each commit (user, 2026-11-22).
- Update `plan/dev.tasks.md` in the same step as the commit.
- Download page (`site/`): after every change run `npx vercel deploy --prod` in `site/` (project `sy-ffeb/deskthread`, live at deskthread.vercel.app).
- UI design change: write the plan into `plan/dev.tasks.md` and get the user's approval before coding. Use `plan/design-sample/` (glass look, no left accent bar, no green).

## Where things are

| Path | What |
|---|---|
| `app/` | Backend: policy (G1), sources, readers, model gateway, search, answer gate |
| `ui/` | The page (Next.js static export) |
| `site/` | Download page for Vercel (no outside resources) |
| `docs/` | Public documents: status, privacy checks, install, how it works, tests, test report, traceability |
| `demo-data/`, `eval/` | Generator of the invented laptop; ground truth and questions |
| `README.md` | Short front page with links into `docs/` |

When a feature changes, update its row in `docs/traceability.md` and the numbers in `docs/status.md` and `docs/tests.md`.
