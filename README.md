<h1 align="center">DeskThread</h1>
<p align="center"><b>A local-first assistant that finds what you wrote down, without your notes ever leaving your laptop.</b></p>

<p align="center">
Prototype · tested on macOS (Apple silicon) · Windows: not tested · all sample data is invented
</p>

---

## Overview

DeskThread helps a manager use the knowledge already on their own computer. You choose what it may read: apps on the Mac (Calendar, Mail, Notes, Reminders) and folders. Everything is Off until you switch it on, and switching on gives **read permission only**: DeskThread cannot change, send or delete anything, and no setting would allow it. When you prepare a meeting, it joins notes, mail, reminders, chat exports, documents and screenshots written weeks apart in different words, and shows where each point came from, with an exact quote and a date. If the answer is not in your files, it says so instead of guessing.

It runs on your machine with an open-weight model served locally: no hosted AI, no accounts, no telemetry. It saves no index and no copy of your notes: the app writes nothing to disk.

### The moment it is built for

Seoyeon manages a team. Tomorrow she has a one-to-one with Sam and wants to remember what she promised. She searches her notes for "development goals" and finds nothing, yet it is all there, in notes, a mail, a reminder, a chat recap and a screenshot written six weeks apart in other words. DeskThread prepares the meeting: five points, each with a status (done, open, superseded), its source, the exact quote and the date, and it marks the one point that was never stated as a clear promise.

## Status (22 November 2026)

This is a work in progress. The table says plainly what exists.

| Part | State |
|---|---|
| Reading chosen folders: notes, mail (`.eml`), calendar (`.ics`), reminders, Teams and Slack text exports, `.docx`, `.pdf`, `.csv`, `.txt`, `.md`, images | **Built and tested** |
| Access rules; consent with instant revoke; any source can be allowed for reading, nothing can be allowed for more | **Built and tested** |
| Local model gateway, search with no stored index, answer check, coverage, "prepare my next meeting" | **Built and tested**; runs in the terminal (`scripts/ask.py`) |
| Local API with a per-launch token, Origin and Host checks, strict content-security-policy | **Built and tested** |
| Browser interface: sources and permission request, Prepare, ask, brief, source viewer, Proof, Memory, End session with a receipt | **Built**; the main click path was checked by hand in the browser (see Tests) |
| Launcher with a clean stop (`make run`, `DeskThread.command`) | **Built and tested** on the real process |
| `DeskThread.app`: double-click start in its own Mac window, with first-start setup | **Built**; the window was opened on the development Mac and showed the first screen (checked by asking the web view), and a quit stopped every program; the first-start setup branches were not exercised |
| `verify` script (an independent check after quitting), canary leak tests, Wi-Fi-off run | **Not built or not run yet** |
| Connectors to the Mac's own Calendar, Mail, Notes and Reminders apps, read only | **Built**; tested with canned app replies; against the real apps only the listing of calendars, folders, lists and mailboxes was run (names and counts). Reading real content through them has not been run |
| Choosing the AI model, with download | **Built**; a real download and a real switch have not been run |
| Windows | **Not tested** |

## The one rule, and what backs it today

| Promise | How it is upheld | Test |
|---|---|---|
| Nothing it reads leaves the device | One module may open a connection, and it refuses any address but `127.0.0.1`; no proxy is used; the model runs locally with cloud features off | gateway tests, import allowlist test |
| It keeps no copy | No database, index or temp-file library is imported; files are opened read-only; reading leaves the folder byte-identical; the tools write no cache or bytecode | U6, "connector never changes the folder" |
| You choose what it sees, and can change your mind | Every source starts Off, personal chat apps included; one switch allows reading, the same switch stops it; stopping cancels a read in progress and drops that source from memory. Nothing is ticked until you tick it, and Calendar and Mail are read only for the period you choose. Reading is the only permission: the Mac app scripts contain read commands only | consent tests, R2 read-only scan |
| Off-limits stays off-limits | The real path of every file is checked before it is opened; `..` and symlinks out of the chosen folder are refused; a `Personal` folder, a `PRIVATE…` file or a folder holding `.deskthread-off-limits` is never opened | U1, U2 |
| It is honest | The model returns a note id and a line number; code copies the quote, so a quote cannot be invented; a quote on another subject is rejected; nothing left means "not found" | U3, salary case |
| Notes are data, not orders | Lines that read like instructions to an assistant are withheld from the model and can never be cited | U4 |

## Check it yourself

DeskThread is built so that you can see what it does and stop it, instead of being asked to trust it. Each claim below says how DeskThread counts it and how you can check it without DeskThread.

| Claim | How DeskThread counts it | How you check it yourself |
|---|---|---|
| **It only reads** | "Read" is the only permission that exists in the app. The part that talks to a source has no function for writing. A test fails the build if a command that writes, sends, moves or deletes appears in what is sent to the Mac apps (`tests/unit/test_mac_apps.py`, the R2 scan) | Read the scripts in `app/sources/mac.py`: they contain `get`-style commands only. Run `make check` |
| **Nothing was sent to the internet** | It asks macOS for the open connections of its own programs (`lsof -nP -iTCP -a -p <its process numbers>`). `127.0.0.1` is the Mac talking to itself; any other address is marked "Outside" | **My data → Check it now** shows what macOS printed, explains how to read it and gives the command with a Copy button. Paste it into Terminal: every line must contain `127.0.0.1`. Or switch Wi-Fi off: DeskThread keeps answering |
| **DeskThread saved nothing** | From launch, Python reports every file the program opens (an audit hook). If a file is opened for writing, creating or adding, a counter goes up. The target is 0 and the real number is shown on the receipt | The folder comparison below. Also: no DeskThread folder appears in `~/Library/Application Support`, and the window is set to keep no history, cache or cookies |
| **Your files are untouched** | When you choose a folder, the name, size and changed-time of every file in it are kept in memory (no file is opened). The same listing is taken again and compared | **My data** shows "Same" or "Changed" per folder and lists the files that were added, changed or removed, with the time. In Finder, sort the folder by "Date Modified" |
| **Memory is cleared** | After **Clear memory** or **End session** the pop-up ticks each step only when it is confirmed: no items held, no AI model loaded, the programs stopped | Open Activity Monitor and search for "DeskThread", "Python" and "ollama": after End session they are gone |
| **You decide what it reads** | Every source starts Off. Nothing is ticked in the permission pop-up until you tick it. Switching off stops a read in progress and drops that source from memory | **My data → What happened** lists what you allowed, what was read and how many items, with the time |

What these checks cannot show, said plainly:

- "Saved" and "Sent" are counted by DeskThread itself. That is why each has a check that does not depend on it.
- The connection list is a snapshot, so a very short connection could be missed. Wi-Fi off is the stronger check.
- macOS records the time and the account of a file change, not the app. A change in your folder is attributed to "you or another app" because DeskThread's own write count is 0, not because macOS names the app.
- The write count covers DeskThread's own program. The AI server is a separate program; the one thing it keeps on the Mac is an AI model you chose to download.
- Erasing memory cannot be proven from inside an app: freed memory and swap belong to the operating system.
- An independent `verify` script (a check from outside the app after it has quit) is not built.

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
- Then it starts its own model server and the backend on `127.0.0.1` and opens DeskThread in **its own Mac window: no browser is involved**. The window holds macOS's built-in web view, set to keep no history, cache or cookies on disk. The address inside carries a secret token for this launch; nothing answers without it.
- macOS may ask once whether to open an app from an unidentified developer: the app is a small unsigned script. Right-click it and choose Open.

**In the window:**

1. Click **Try it with the demo laptop**. One click chooses the invented folder, switches on the work sources and shows tomorrow's one-to-one. (Or click **Choose my folder…** for your own files: everything in it starts Off and you allow each source yourself.)
2. Click **Prepare**. The first answer takes about 30 seconds (the model loads and reads the pictures). Click any quote to open its source, read only. Ask your own questions in the box. At the bottom of **Ask** you can choose another AI model; one that is not on the Mac yet is downloaded on a click.
3. **Access** lists "Apps on this Mac" and your folder as rows with a switch. Switching on asks "Allow DeskThread to read …?" (read only) and lets you tick the calendars, folders, lists or mailbox; macOS also asks once per app. Switching off takes effect at once. **My data** shows that nothing was sent, nothing was saved, your files are untouched, and what is held right now.
4. **End session** asks first, then clears everything from the session, shows a receipt and stops both programs; from there you can **Start a new session** or **Quit DeskThread**. Closing the window (or Cmd+Q) ends the session too.

Without the app bundle, `make run` (or `DeskThread.command`) does the same from a terminal, after `make setup ui demo-data`. `make run-browser` opens the page in your default browser instead of the window.

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
make check                                            # lint, type checks and 145 tests (no model needed)
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
| Window | A native macOS window with the system web view (WebKit), opened from Python through pyobjc | Apple's frameworks; pyobjc is open source (MIT). No browser, and a non-persistent store: nothing the page does is kept on disk |
| Page | React 19 and Next.js 16, built once into static files | Meta and Vercel (US), MIT; served by the local backend, nothing loaded from outside |
| Backend | Python 3.13, FastAPI, Pydantic | Open source; typed data shapes between every part; bound to `127.0.0.1` |
| Model runtime | Ollama server 0.40.9 on `127.0.0.1:11435` | Ollama Inc. (US), MIT; runs the model on the laptop |
| Model | `gemma4:e4b` by default, digest `eb2177adf7646d15faead94fdad6d3e170dc8015653418a3b7d5d52a6380be5b` | Google (US), Apache-2.0; answers and picture reading; a different digest is refused. Two more can be chosen in the app (Gemma 4 small, Google; Phi-4 mini, Microsoft): they are offered **untested**, see Limitations |

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

`make check` runs lint, strict type checks (Python and TypeScript) and 145 tests in about 7 seconds, without the model.

| Group | What it proves | Result |
|---|---|---|
| Contract | item shape, interfaces, API shapes, error codes; the live-run guard blocks a planted canary and a sample title | pass |
| Data (D1 to D6) | the searched phrase appears nowhere; all addresses use `.example`; rebuilds are byte-identical; nothing supports a pay promise | pass |
| Access (U1, U2, Unicode paths) | off-limits and outside files are never opened, also by name, `..` or symlink | pass |
| Consent | default Off, chat apps included; allow then stop; stop during a read; turn everything off; reading is the only permission | pass |
| Readers (U8) | each file type gives text, a title and the writer's date; broken and unsupported files are counted | pass |
| Model gateway (U6) | loopback only; pinned digest; unload verified against a fake server; no database or index library | pass |
| Answer path (U3, U4, U7, U9, U10) | invented citations dropped; injection withheld; superseded and undated handled; coverage adds up; a deleted note is gone at once | pass, with a scripted fake model |
| Local API (U5) | no token, wrong Origin or wrong Host is refused; replies are not stored; only the page's own start-up script may run | pass |
| Proof, memory, end session | local-only connections, fingerprint without opening files, zero writes (L-4), Clear memory, receipt without note text | pass |
| Launch (N-6) | the real process listens on `127.0.0.1` only, needs the token, and refuses connections after End session | pass |
| Evaluation with the real model | tuning set against the ground truth | 7 of 8 |
| Click path, by hand | earlier design: choose folder, permission request, Prepare, source viewer, Proof, End session, with the real model. Current design: the Access screen and the one-click demo only | the Ask and My data screens, the model card, the end-session pop-up and "Start a new session" have **not** been looked at since the redesign |

Not written or not run yet: the canary leak tests on the full flow (L-1, L-5, L-6, L-7), the Wi-Fi-off run (N-2), and an automated check that the page makes no outside request (N-3; today the content-security-policy forbids it).

## Data

All sample content is invented: a fictional company ("UK Pharma"), a fictional manager (Seoyeon) and 65 files on a mock laptop, built by `demo-data/make_demo_data.py`. The expected answers are kept in `eval/`, outside the folder the assistant can read. No real notes were used.

## Limitations

- The answer check proves that a quote exists in the cited note and is on the subject. It cannot prove the quote means what the writer meant.
- A quote from an image matches the **model's reading** of the image, not the pixels. Typed screenshots were tested; handwriting and poor photos were not.
- The model suggests search words and can miss a line (see the failing question above).
- Between questions, the items of allowed sources stay in the backend's memory until you revoke a source, forget, or end the session. Erasing memory contents cannot be proven; swap and hibernation files are outside the app's control.
- macOS has no read-only permission for calendars: to read events an app must ask for "Full Access" (the only other choice, "Add Only", cannot read). DeskThread uses fetch calls only, and a test fails if a call that saves or removes an event appears in the code. If you refuse, the slower scripting route is used.
- The other Mac app connectors read through each app's scripting interface. macOS words that permission as "control", not "read only"; DeskThread sends read commands only, and a test fails on any command that writes, sends, moves or deletes. Calendar is slow through this route (25 to 84 seconds across eight calendars in a test), so tick only the calendars you need; Mail reads the newest 25 messages of one mailbox, as far as Mail has them on this Mac. The connectors were timed on the real apps with counts only (Notes 50 notes in 0.4 s, Reminders 55 items in 10 s, Mail 25 messages in 38 s); answer quality on real app content has not been measured.
- Only the default model has been run through DeskThread's tests. The other two models are offered untested: answer quality, picture reading and the output format are not verified for them.
- Downloading a model is the one time the model server uses the internet; during it, "My data" will show an outside connection.
- The runtime does not offer forced JSON output for this model, so the model's JSON is validated in code and asked for once more if it is malformed.
- Windows is untested.

## License

Prototype built for a hackathon challenge in November 2026. No licence has been chosen yet. No telemetry, no analytics, no external services.
