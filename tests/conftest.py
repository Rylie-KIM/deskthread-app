"""Shared fixtures. All test data is invented."""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO = Path(__file__).resolve().parent.parent
CANARY = "ZX9-CANARY-4471-BLUEHERON"


def _load_generator() -> ModuleType:
    # demo-data/ is a folder of scripts, not a package: load the generator by path.
    path = REPO / "demo-data" / "make_demo_data.py"
    spec = importlib.util.spec_from_file_location("make_demo_data", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["make_demo_data"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def generator() -> ModuleType:
    return _load_generator()


@pytest.fixture(scope="session")
def demo_laptop(generator: ModuleType, tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A fresh copy of the invented demo laptop, built once per test run."""
    root: Path = tmp_path_factory.mktemp("laptop") / "demo-laptop"
    generator.build(root)
    return root
