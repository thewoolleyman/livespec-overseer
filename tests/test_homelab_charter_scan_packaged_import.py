"""Packaged import coverage for the homelab charter scan console script."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

__all__: list[str] = []

_REPO_ROOT = Path(__file__).resolve().parent.parent
_PACKAGE_DIR = str(_REPO_ROOT / "overseer")


def test_scan_module_imports_without_the_package_dir_on_sys_path(*, monkeypatch) -> None:
    monkeypatch.setattr(sys, "path", [entry for entry in sys.path if entry != _PACKAGE_DIR])
    _ = sys.modules.pop("streams", None)
    _ = sys.modules.pop("overseer.homelab_charter_scan", None)

    module = importlib.import_module("overseer.homelab_charter_scan")

    assert module.main
