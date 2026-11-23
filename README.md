<h1 align="center">DeskThread</h1>
<p align="center"><b>Find what you wrote down. Your notes never leave your laptop.</b></p>

<p align="center">
<a href="https://github.com/Rylie-KIM/deskthread-app/archive/refs/heads/main.zip"><b>Download for Mac</b></a> ·
<a href="https://deskthread.vercel.app">Website</a> ·
Demo video (link coming)
</p>

<p align="center"><img src="docs/images/access.png" alt="DeskThread: choose what it can read" width="760"></p>

## What it is

A native **Mac app** that finds what you wrote down in Notes, Calendar, Mail, Reminders and your folders.
Every answer shows the exact quote, the date and where it came from. If the answer is not there, it says "not found".

- **Local:** the AI runs on your Mac. No accounts, no telemetry.
- **Read only:** everything starts Off. You switch on what it may read.
- **No copies:** the app writes nothing to disk.

Prototype for macOS on Apple silicon. All sample data is invented. Windows is not tested.

## Try it

```bash
git clone https://github.com/Rylie-KIM/deskthread-app.git && cd deskthread-app
brew install ollama uv
make setup ui demo-data
make run
```

Then click **Try the demo** and **Prepare**. Full steps: [Install and run](docs/install-and-run.md).

## More

| | |
|---|---|
| [Status](docs/status.md) | What is built and what is not |
| [Privacy and how to check it](docs/privacy-checks.md) | The promises, and how you can verify each one |
| [Install and run](docs/install-and-run.md) | Requirements, steps, terminal use |
| [How it works](docs/how-it-works.md) | Parts, gates, project structure |
| [Tests](docs/tests.md) | What the tests prove |
| [Demo data and limits](docs/data-and-limits.md) | The invented data, known limits |
| [Dependencies](docs/dependencies.md) | Every dependency and its licence |

Prototype built for a hackathon in November 2026. No licence chosen yet.
