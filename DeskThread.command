#!/bin/zsh
# Double-click to start DeskThread. Everything runs on this Mac only.
cd "$(dirname "$0")" || exit 1
export PYTHONDONTWRITEBYTECODE=1 DO_NOT_TRACK=1 OLLAMA_NO_CLOUD=1 UV_PYTHON_DOWNLOADS=never
# Opens DeskThread in its own Mac window. For a browser tab instead: make run-browser
exec uv run --frozen --no-dev python -B -m app.window "$@"
