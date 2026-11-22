# DeskThread: one command for every check (dev rule R7).
# The tools themselves write nothing: no bytecode, no pytest cache, no ruff or mypy cache (R4).

export PYTHONDONTWRITEBYTECODE := 1
export UV_PYTHON_DOWNLOADS := never
# Telemetry switches (R3). Nothing in the stack should report home; these make it explicit.
export DO_NOT_TRACK := 1
export NEXT_TELEMETRY_DISABLED := 1
export OLLAMA_NO_CLOUD := 1
export HF_HUB_DISABLE_TELEMETRY := 1

UV := uv run --frozen

.PHONY: setup check lint format typecheck test test-live ui ui-check run run-browser demo-data demo-data-core

setup:            ## install the locked dependencies into .venv (the one network step besides the model)
	uv sync --frozen

check: lint typecheck test ui-check  ## lint, type check, tests, and the UI type check

lint:
	$(UV) ruff check --no-cache .
	$(UV) ruff format --no-cache --check .

format:
	$(UV) ruff check --no-cache --fix .
	$(UV) ruff format --no-cache .

typecheck:
	$(UV) mypy

test:
	$(UV) pytest

test-live:        ## touches the real Mac apps; prints counts and pass/fail only (R1)
	$(UV) pytest -m live

ui:               ## install the locked UI packages (no install scripts) and build the static page
	cd ui && npm ci --ignore-scripts && npm run build

ui-check:         ## strict TypeScript check of the UI (needs `make ui` once)
	@if [ -d ui/node_modules ]; then cd ui && npm run --silent typecheck; else echo "ui-check skipped: run make ui first"; fi

demo-data:        ## build the rich invented demo laptop in ./demo-laptop (143 files)
	$(UV) python -B demo-data/make_demo_data.py

demo-data-core:   ## build only the first layer of it (65 files), the one the tests and eval/ use
	$(UV) python -B demo-data/make_demo_data.py --core

run:              ## start DeskThread in its own Mac window (model server, backend, page), on this Mac only
	./DeskThread.command

run-browser:      ## the same, but the page opens in your default browser
	$(UV) python -B -m app
