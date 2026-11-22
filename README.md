<h1 align="center">DeskThread</h1>
<p align="center"><b>A local-first assistant that finds what you wrote down, without your notes ever leaving your laptop.</b></p>

<p align="center">
Prototype · tested on macOS (Apple silicon) · Windows: not tested · all sample data is invented
</p>

---

## Overview

DeskThread helps a manager use the knowledge already on their own computer. You choose which sources it may read. Everything else is off by default, and private apps stay locked off. When you prepare a meeting, it joins notes, mail, reminders, chat exports, documents and screenshots written weeks apart in different words, and shows where each point came from, with an exact quote and a date. If the answer is not in your files, it says so instead of guessing.

It runs on your machine with an open-weight model served locally: no hosted AI, no accounts, no telemetry. It saves no index and no copy of your notes: the app writes nothing to disk.

### The moment it is built for

Seoyeon manages a team. Tomorrow she has a one-to-one with Sam and wants to remember what she promised. She searches her notes for "development goals" and finds nothing, yet it is all there, in notes, a mail, a reminder, a chat recap and a screenshot written six weeks apart in other words. DeskThread prepares the meeting: five points, each with a status (done, open, superseded), its source, the exact quote and the date, and it marks the one point that was never stated as a clear promise.

## Status (22 November 2026)

This is a work in progress. The table says plainly what exists.

| Part | State |
|---|---|
| Reading chosen folders: notes, mail (`.eml`), calendar (`.ics`), reminders, Teams and Slack text exports, `.docx`, `.pdf`, `.csv`, `.txt`, `.md`, images | **Built and tested** |
| Access rules, consent with instant revoke, locked private apps | **Built and tested** |
| Local model gateway, search with no stored index, answer check, coverage, "prepare my next meeting" | **Built and tested**; runs in the terminal (`scripts/ask.py`) |
| Local API with a per-launch token, Origin and Host checks, strict content-security-policy | **Built and tested** |
| Browser interface: sources and permission request, Prepare, ask, brief, source viewer, Proof, Memory, End session with a receipt | **Built**; the main click path was checked by hand in the browser (see Tests) |
| Launcher with a clean stop (`make run`, `DeskThread.command`) | **Built and tested** on the real process |
| `DeskThread.app`: double-click start with first-start setup | **Built**; opened once on the development Mac (backend and model server came up on `127.0.0.1`); the first-start setup branches were not exercised |
| `verify` script (an independent check after quitting), canary leak tests, Wi-Fi-off run | **Not built or not run yet** |
| Connectors to the Mac's own Notes, Calendar, Reminders and Mail apps | **Not built yet** (a read-only Calendar test worked; see Limitations) |
| Windows | **Not tested** |

## The one rule, and what backs it today

| Promise | How it is upheld | Test |
|---|---|---|
| Nothing it reads leaves the device | One module may open a connection, and it refuses any address but `127.0.0.1`; no proxy is used; the model runs locally with cloud features off | gateway tests, import allowlist test |
| It keeps no copy | No database, index or temp-file library is imported; files are opened read-only; reading leaves the folder byte-identical; the tools write no cache or bytecode | U6, "connector never changes the folder" |
| You choose what it sees, and can change your mind | Every source starts Off; one call grants, one call revokes; a revoke cancels a read in progress and drops that source from memory; private apps cannot be turned on | consent tests |
| Off-limits stays off-limits | The real path of every file is checked before it is opened; `..` and symlinks out of the chosen folder are refused; a `Personal` folder, a `PRIVATE…` file or a folder holding `.deskthread-off-limits` is never opened | U1, U2 |
| It is honest | The model returns a note id and a line number; code copies the quote, so a quote cannot be invented; a quote on another subject is rejected; nothing left means "not found" | U3, salary case |
| Notes are data, not orders | Lines that read like instructions to an assistant are withheld from the model and can never be cited | U4 |

### How a user can tell

| In the app | What it shows | Test |
|---|---|---|
| **Proof** | Open connections of DeskThread's own programs, sampled with the Mac's `lsof` (anything not on `127.0.0.1` is flagged); a fingerprint of your folder when you chose it and now (names, sizes, times; no file is opened); the number of files the backend opened for writing; what it cannot prove | connection parsing, fingerprint, write audit (L-4) |
| **Memory** | Items held per source, image readings, whether the model is loaded, and the memory of each program as the operating system reports it. **Forget now** clears the items and unloads the model | memory tests |
| **End session** | A receipt with counts only, then the programs stop and the address refuses connections | receipt canary test, N-6 on the real process |

The independent `verify` script (a check from outside the app after it has quit) is not built yet. Until then, Activity Monitor is the outside check.

## Installation

Requirements: macOS on Apple silicon, about 10 GB of free disk for the model, [Homebrew](https://brew.sh), Node.js 22 (only to build the page once).

```bash
git clone https://github.com/Rylie-KIM/deskthread-app.git && cd deskthread-app
brew install ollama uv          # the model server (not the desktop app) and the Python installer
make setup                      # installs the locked Python dependencies into .venv
make ui                         # installs the locked UI packages (no install scripts) and builds the page

# Download the model once. This and the three lines above are the only steps that use the network.
OLLAMA_HOST=127.0.0.1:11435 OLLAMA_NO_CLOUD=1 ollama serve &
OLLAMA_HOST=127.0.0.1:11435 ollama pull gemma4:e4b
kill %1
```

## How to run

**Double-click `DeskThread.app`** in the project folder (you can drag it to the Dock). That is all.

- On the first start it prepares what is missing by itself: the Python parts, the page, the invented demo laptop. If the model is not on the Mac yet, it asks before the one large download (about 9 GB). These are the only steps that use the network; `brew install ollama uv` and Node.js must already be there.
- Then it starts its own model server and the backend on `127.0.0.1` and opens DeskThread in its own window (in Chrome if installed, otherwise in your default browser). The address carries a secret token for this launch; nothing answers without it.
- macOS may ask once whether to open an app from an unidentified developer: the app is a small unsigned script. Right-click it and choose Open.

**In the window:**

1. Click **Try it with the demo laptop**. One click chooses the invented folder, switches on the work sources and shows tomorrow's one-to-one. (Or click **Choose my folder…** for your own files: everything in it starts Off and you allow each source yourself.)
2. Click **Prepare**. The first answer takes about 30 seconds (the model loads and reads the images). Click any quote to open its source, read-only. Ask your own questions in the box.
3. **Proof** and **Memory** show what it connected to, what it holds and what it wrote. **Stop access** or **Stop all** takes effect at once.
4. **End session** gives you a receipt and stops both programs. Closing the window alone does not stop them.

Without the app bundle, `make run` (or `DeskThread.command`) does the same from a terminal, after `make setup ui demo-data`.

To use the demo's story clock (the evening of Sun 22 Nov 2026, the day before the meeting) start it as `DESKTHREAD_NOW=2026-11-22T19:00:00+00:00 make run`. It is a test and demo setting only; without it the real time is used and "tomorrow's one-to-one" will not be found in the demo calendar.

To use your own folder, choose it in step 1. Only that folder is read. Inside it, a folder named `Personal` or `Private`, a file whose name starts with `PRIVATE`, and any folder holding a file named `.deskthread-off-limits` are never opened.

### In the terminal instead

```bash
uv run python -m scripts.ask
```

The same pipeline without the page: it prepares the next one-to-one on `demo-laptop` with the story clock, then takes questions; an empty line ends the session.

**One question and exit:**

```bash
uv run python -m scripts.ask "What did I promise Sam?"
```

**Your own folder, with the real clock:**

```bash
uv run python -m scripts.ask --folder ~/Documents/Work --now ""
```

**Checks and the measured run:**

```bash
make check                                            # lint, type checks and 127 tests (no model needed)
DESKTHREAD_NOW=2026-11-22T19:00:00+00:00 \
  uv run python -m eval.run --set tuning -v           # scores eight questions against the ground truth
```

Measured on a MacBook Air M4 with 24 GB of memory: 7 of 8 tuning questions pass, the same in two runs.

| Question | Result |
|---|---|
| An ordinary search for "development goals" | 0 hits (the story's starting point) |
| What did I promise Sam? | 5 of 5 promises with the right status, quoted from notes, a mail, a reminder, a chat recap and a screenshot |
| What salary did I promise Sam? | "not found"; the real quote "Budget approved up to 800" is rejected as off-subject |
| What do my notes say about Alex's performance? | "not found"; the private note is never opened |
| What is still open with Sam? | **fails**: it cites the right chat recap but not the line that states the monthly career chat |

Time per question: about 4 to 28 seconds; the first is slowest because the five images are read then. The held-out question set has not been run.

## How it works

| Part | Tech | Whose it is and why |
|---|---|---|
| Page | React 19 and Next.js 16, built once into static files | Meta and Vercel (US), MIT; served by the local backend, nothing loaded from outside |
| Backend | Python 3.13, FastAPI, Pydantic | Open source; typed data shapes between every part; bound to `127.0.0.1` |
| Model runtime | Ollama server 0.40.9 on `127.0.0.1:11435` | Ollama Inc. (US), MIT; runs the model on the laptop |
| Model | `gemma4:e4b`, digest `eb2177adf7646d15faead94fdad6d3e170dc8015653418a3b7d5d52a6380be5b` | Google (US), Apache-2.0; one model for answers and for reading images; a different digest is refused |

Every dependency, with its licence and the reason it is used, is in [docs/dependencies.md](docs/dependencies.md).

Gates between your files and an answer; a trace line with each answer says what each gate did:

- **G1 policy:** what may be read (sources that are On, path confinement, off-limits).
- **G2 read:** what was read, and what could not be read (counted, never skipped silently).
- **G3 model gateway:** the pinned local model, no tools; its text is displayed or parsed, never executed.
- **G4 answer check:** citation by id, quote copied by code, relevance, instructions inside notes.
- **G6 audit trail:** grants, revokes and reads, in memory only, counts and ids only.

**Finding notes without an index.** Nothing is indexed on disk. For each question the program scores the readable items in memory: the question's own words, other words the local model suggests for the same topic, and the name of the person (from the calendar when you prepare a meeting). A relevance rule runs before the model is asked to answer; when nothing passes it, the reply is "not found" and no answer call is made. Every answer carries coverage numbers: readable, searched, unreadable, shown to the model, cited, and what was out of reach.

## Project structure

```
deskthread-app/
├── app/          backend: policy (G1), sources, readers, broker, store, model gateway, search,
│                 answer gate, assistant, local API, proof/ (evidence, memory, end session)
├── contracts/    frozen data shapes and interfaces shared by all parts; the live-run output guard
├── demo-data/    generator of the invented laptop (the output, demo-laptop/, is not committed)
├── eval/         ground truth, question sets, scorer
├── scripts/      ask.py (run it in the terminal), model smoke test, read-only checks for the Mac apps
├── tests/        contract, data and unit tests
├── docs/         dependency register
├── site/         static download page (no external resources, no analytics)
├── ui/           browser interface (Next.js static export)
├── DeskThread.app       double-click to start (a small script bundle; prepares the first start)
└── DeskThread.command   the same from a terminal window
```

## Tests

`make check` runs lint, strict type checks (Python and TypeScript) and 127 tests in about 7 seconds, without the model.

| Group | What it proves | Result |
|---|---|---|
| Contract | item shape, interfaces, API shapes, error codes; the live-run guard blocks a planted canary and a sample title | pass |
| Data (D1 to D6) | the searched phrase appears nowhere; all addresses use `.example`; rebuilds are byte-identical; nothing supports a pay promise | pass |
| Access (U1, U2, Unicode paths) | off-limits and outside files are never opened, also by name, `..` or symlink | pass |
| Consent | default Off; grant then revoke; revoke during a read; Stop all | pass |
| Readers (U8) | each file type gives text, a title and the writer's date; broken and unsupported files are counted | pass |
| Model gateway (U6) | loopback only; pinned digest; unload verified against a fake server; no database or index library | pass |
| Answer path (U3, U4, U7, U9, U10) | invented citations dropped; injection withheld; superseded and undated handled; coverage adds up; a deleted note is gone at once | pass, with a scripted fake model |
| Local API (U5) | no token, wrong Origin or wrong Host is refused; replies are not stored; only the page's own start-up script may run | pass |
| Proof, memory, end session | local-only connections, fingerprint without opening files, zero writes (L-4), Forget now, receipt without note text | pass |
| Launch (N-6) | the real process listens on `127.0.0.1` only, needs the token, and refuses connections after End session | pass |
| Evaluation with the real model | tuning set against the ground truth | 7 of 8 |
| Browser click path, by hand | choose folder, permission request, Work profile, Prepare, source viewer, Proof, End session receipt, on the demo laptop with the real model | worked once; Memory tab, the folder dialog button and phone width not checked |

Not written or not run yet: the canary leak tests on the full flow (L-1, L-5, L-6, L-7), the Wi-Fi-off run (N-2), and an automated check that the page makes no outside request (N-3; today the content-security-policy forbids it).

## Data

All sample content is invented: a fictional company ("UK Pharma"), a fictional manager (Seoyeon) and 65 files on a mock laptop, built by `demo-data/make_demo_data.py`. The expected answers are kept in `eval/`, outside the folder the assistant can read. No real notes were used.

## Limitations

- The answer check proves that a quote exists in the cited note and is on the subject. It cannot prove the quote means what the writer meant.
- A quote from an image matches the **model's reading** of the image, not the pixels. Typed screenshots were tested; handwriting and poor photos were not.
- The model suggests search words and can miss a line (see the failing question above).
- Between questions, the items of allowed sources stay in the backend's memory until you revoke a source, forget, or end the session. Erasing memory contents cannot be proven; swap and hibernation files are outside the app's control.
- The Mac app connectors are not built. In a read-only test, counting events through the Calendar app's scripting interface worked but took 25 to 84 seconds across eight calendars, so it will be scoped to chosen calendars. macOS words that permission as "control", not "read only"; DeskThread issues read calls only.
- The runtime does not offer forced JSON output for this model, so the model's JSON is validated in code and asked for once more if it is malformed.
- Windows is untested.

## License

Prototype built for a hackathon challenge in November 2026. No licence has been chosen yet. No telemetry, no analytics, no external services.
