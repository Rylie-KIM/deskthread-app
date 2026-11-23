# Install and run

[Back to the README](../README.md)

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

