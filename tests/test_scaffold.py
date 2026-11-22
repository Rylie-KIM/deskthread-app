"""The scaffold keeps its promises: private folders stay out of git, tools write nothing."""

from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def test_planning_material_models_and_recordings_are_ignored_by_git() -> None:
    ignored = (REPO / ".gitignore").read_text().splitlines()
    for entry in ("plan/", "design-sample/", ".env", "demo-laptop/", "*.mov", "*.gguf"):
        assert entry in ignored, entry


def test_make_check_runs_without_bytecode_caches_or_telemetry() -> None:
    makefile = (REPO / "Makefile").read_text()
    for setting in ("PYTHONDONTWRITEBYTECODE := 1", "DO_NOT_TRACK := 1", "OLLAMA_NO_CLOUD := 1"):
        assert setting in makefile, setting
    assert "check: lint typecheck test" in makefile
    pyproject = (REPO / "pyproject.toml").read_text()
    assert "no:cacheprovider" in pyproject and "no-build = true" in pyproject
