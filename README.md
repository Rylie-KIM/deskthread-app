<p align="center"><img src="docs/images/icon.png" alt="DeskThread app icon" width="112"></p>
<h1 align="center">DeskThread</h1>
<p align="center"><b>Find what you wrote down. Your notes never leave your laptop.</b></p>

<p align="center">
<a href="https://deskthread.vercel.app"><b>Download for Mac</b></a> ·
<a href="https://youtu.be/0CBEZsb4PlA">Demo video</a>
</p>

<p align="center"><img src="docs/images/access.png" alt="DeskThread: choose what it can read" width="760"></p>

## Problem

Managers keep their work notes in many places: Notes, Calendar, Mail, Reminders and folders. Before a meeting, finding what was promised or decided means searching each one. Cloud assistants could help, but sending work notes outside the laptop is often not allowed.

DeskThread is a native **Mac app** that finds what you wrote down in Notes, Calendar, Mail, Reminders and your folders.
Every answer shows the exact quote, the date and where it came from. If the answer is not there, it says "not found".

- **Local:** the AI runs on your Mac. No accounts, no telemetry.
- **Read only:** everything starts Off. You switch on what it may read.
- **No copies:** the app writes nothing to disk.

Prototype for macOS on Apple silicon. All sample data is invented. Windows is not tested.

## Main user needs and features

| User need | Main features |
|---|---|
| Recall what I promised before a one-to-one, and prepare for the next meeting | Brief, "Prepare my next meeting" |
| See the exact words, the note and the date behind every answer | Quote and source viewer, coverage view (which files were read) |
| Get an honest "not found" instead of an invented answer | Answer gate, closest notes after "not found" |
| Choose what it can read, and take it back at once | Sources Off by default, one-click access, instant revoke, off-limits list |
| Cover where I keep work information | Notes, Calendar, Mail, Reminders, folders and image readers |
| Be sure my notes stay on my laptop, and check it myself | Local model, no files written, Memory panel with Forget now, Proof panel and `verify` script |
| Use it like any app | One-click launcher, native Mac window, "Choose folder..." button |

Every need, feature and test is linked in [Traceability: user need → feature → test](docs/traceability.md).

## Structure of the app

<p align="center"><img src="docs/images/structure.png" alt="Structure of DeskThread: Mac window, page, backend and model server, with four gates between your files and every answer" width="900"></p>

| | |
|---|---|
| [How it works](docs/how-it-works.md) | Parts, gates, project structure. The model (`gemma4:e4b`, run locally) only names a note and a line; plain code copies the quote |

## How to install the application

```bash
git clone https://github.com/Rylie-KIM/deskthread-app.git && cd deskthread-app
brew install ollama uv
make setup ui demo-data
make run
```

Then click **Try the demo** and **Prepare**.

| | |
|---|---|
| [Install and run](docs/install-and-run.md) | Requirements, steps, terminal use |

## Tests

`make check` runs lint, strict type checks and **180 automated tests** in about 13 seconds, without the model. All pass (run of 23 Nov 2026).

| What is checked | Result |
|---|---|
| Access and consent: sources start Off, off-limits files are never opened, access can be taken back at once | pass |
| Privacy: the app connects to `127.0.0.1` only, writes nothing to disk, keeps nothing after End session | pass |
| Answers: invented citations are dropped, instructions hidden in a note are ignored, "not found" when nothing fits | pass, with a scripted fake model |
| Evaluation with the real model on the invented laptop | **5 of 8** (65 files) and **4 of 8** (143 files) |
| Model comparison: three installed models and a no-model baseline | best model about 5 of 8, plain search 2 of 8 |

The answer quality is still being worked on. Not yet done: a canary leak test on the whole flow, and the Ask and My data screens have not been re-checked by hand since the redesign.

| | |
|---|---|
| [Tests](docs/tests.md) | What the tests prove, group by group |
| [Test report](docs/test-report.md) | The run of 23 Nov 2026, with results |
| [Model comparison](docs/model-comparison.md) | Three models and a no-model baseline, measured |

## Demo

Watch the [demo video](https://youtu.be/0CBEZsb4PlA), or click **Try the demo** in the app. It opens an invented laptop: a fictional company, a manager and a team of four. No real notes are used, and the expected answers are kept outside the folder the app can read.

| | |
|---|---|
| [Demo data and limits](docs/data-and-limits.md) | The invented data, known limits |

## Documented files

| Document | What it covers |
|---|---|
| [Status](docs/status.md) | What is built and what is not |
| [Privacy and how to check it](docs/privacy-checks.md) | The promises, and how you can verify each one |
| [Traceability](docs/traceability.md) | User need → feature → test |
| [How it works](docs/how-it-works.md) | Parts, gates, project structure |
| [Install and run](docs/install-and-run.md) | Requirements, steps, terminal use |
| [Tests](docs/tests.md) | What the tests prove, group by group |
| [Test report](docs/test-report.md) | The run of 23 Nov 2026, with results |
| [Model comparison](docs/model-comparison.md) | Three models and a no-model baseline, measured |
| [Demo data and limits](docs/data-and-limits.md) | The invented data, known limits |
| [Dependencies](docs/dependencies.md) | Every dependency and its licence |

Prototype built for a hackathon in November 2026. No licence chosen yet.
