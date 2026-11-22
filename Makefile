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

.PHONY: setup check lint format typecheck test test-live

setup:            ## install the locked dependencies into .venv (the one network step besides the model)
	uv sync --frozen

check: lint typecheck test  ## lint, type check, unit tests, contract tests, quick leak test

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
