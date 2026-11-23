# How it works

[Back to the README](../README.md)

## How it works

| Part | Tech | Whose it is and why |
|---|---|---|
| Window | A native macOS window with the system web view (WebKit), opened from Python through pyobjc | Apple's frameworks; pyobjc is open source (MIT). No browser, and a non-persistent store: nothing the page does is kept on disk |
| Page | React 19 and Next.js 16, built once into static files | Meta and Vercel (US), MIT; served by the local backend, nothing loaded from outside |
| Backend | Python 3.13, FastAPI, Pydantic | Open source; typed data shapes between every part; bound to `127.0.0.1` |
| Model runtime | Ollama server 0.40.9 on `127.0.0.1:11435` | Ollama Inc. (US), MIT; runs the model on the laptop |
| Model | `gemma4:e4b` by default, digest `eb2177adf7646d15faead94fdad6d3e170dc8015653418a3b7d5d52a6380be5b` | Google (US), Apache-2.0; answers and picture reading; a different digest is refused. Seven more can be downloaded in the app. Gemma 4 small (Google) and Phi-4 mini (Microsoft) passed a short smoke test and are pinned to a digest; Llama 3.1 8B and 3.2 3B (Meta), gpt-oss 20B (OpenAI), Nemotron Mini (NVIDIA) and SmolLM2 (Hugging Face) were never run with DeskThread and are not pinned. No model from a Chinese lab is offered; a test enforces the list of makers |

Every dependency, with its licence and the reason it is used, is in [the dependency list](dependencies.md).

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
├── docs/         the detailed documents (status, privacy checks, install, tests) and images
├── site/         static download page (no external resources, no analytics)
├── ui/           browser interface (Next.js static export)
├── DeskThread.app       double-click to start (a small script bundle; prepares the first start)
└── DeskThread.command   the same from a terminal window
```

