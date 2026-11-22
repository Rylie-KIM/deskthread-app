# Dependencies

Every dependency is listed here with its version, licence, whose it is and why DeskThread uses
it. Nothing is added without a line in this table. Versions are the ones pinned (with hashes)
in `uv.lock`. Python packages are installed from wheels only (`no-build = true`), so no
package runs a build or install script on the machine.

## Runtime

| Name | Version | Licence | Whose it is | Why we use it |
|---|---|---|---|---|
| Python | 3.13 | PSF-2.0 | Python Software Foundation | Language of the backend |
| FastAPI | 0.165.0 | MIT | Sebastián Ramírez and contributors (open source) | The local HTTP API between the page and the backend, bound to 127.0.0.1 |
| Starlette | 1.10.0 | BSD-3-Clause | Encode / Kim Christie and contributors | Comes with FastAPI: request handling |
| Pydantic | 2.14.4 | MIT | Pydantic Services Inc. and contributors | Typed data shapes for items, the API and the model's structured output |
| Uvicorn | 0.54.0 | BSD-3-Clause | Encode and contributors | The local web server process that runs FastAPI |
| pypdf | 7.1.1 | BSD-3-Clause | pypdf contributors (open source, pure Python) | Reads the text of PDF documents the user allows. Word files and CSV are read with Python's standard library |
| Ollama (server, Homebrew formula) | 0.40.9 | MIT | Ollama Inc. (US) | Runs the model on the laptop; started by the launcher on 127.0.0.1 with cloud features off (`OLLAMA_NO_CLOUD=1`). The desktop app is not used |
| Gemma 4 E4B (`gemma4:e4b`) | digest `eb2177adf764…` (full value in the README) | Apache-2.0 (licence text shipped with the model: `ollama show gemma4:e4b --license`) | Google (US) | The one local model: answers and image reading. Downloaded once at setup |

## Development only

| Name | Version | Licence | Whose it is | Why we use it |
|---|---|---|---|---|
| uv | 0.13.5 | MIT or Apache-2.0 | Astral (US) | Installs the locked dependencies with hashes |
| pytest | 9.2.0 | MIT | pytest-dev (open source) | Test runner |
| Ruff | 0.17.6 | MIT | Astral (US) | Lint and format |
| Pillow | 13.0.0 | MIT-CMU (HPND) | Jeffrey A. Clark and contributors (open source) | Draws the invented demo screenshots and test images from typed text. Not used by the app at run time |
| mypy | 2.4.1 | MIT | mypy contributors / Python community | Static type check |

Transitive packages (for example `anyio`, `h11`, `click`, `typing-extensions`) are pinned in
`uv.lock`; none of them contacts a server on its own.
