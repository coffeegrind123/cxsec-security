"""Shared fixtures for the carried-helper suites.

Helpers that import vendored modules (workbench_target, validate_scan_contract) only
run beside the vendored runtime, so `plugin_root` assembles one: the bundled
runtime/ tree with assets/local-additions/ copied over it, exactly as install.sh
lays out $CXSEC_HOME. Run with: python3 -m pytest tests/
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

SKILL_ROOT = Path(__file__).resolve().parents[1]
RUNTIME = SKILL_ROOT / "runtime"
LOCAL_ADDITIONS = SKILL_ROOT / "assets" / "local-additions"
RUNTIME_DIRS = ("scripts", "schemas", "examples", "shared", "skills")


def _ignore(directory: str, names: list[str]) -> set[str]:
    return {name for name in names if name == "__pycache__"}


@pytest.fixture(scope="session")
def plugin_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("plugin") / "codex-security"
    for name in RUNTIME_DIRS:
        if (RUNTIME / name).is_dir():
            shutil.copytree(RUNTIME / name, root / name, ignore=_ignore)
    shutil.copytree(LOCAL_ADDITIONS, root, dirs_exist_ok=True, ignore=_ignore)
    return root


@pytest.fixture(scope="session")
def plugin_scripts(plugin_root: Path) -> Path:
    return plugin_root / "scripts"
