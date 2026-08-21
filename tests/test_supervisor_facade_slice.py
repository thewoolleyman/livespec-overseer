"""Repo-level Red/Green guard for the supervisor facade/core size slice."""

from __future__ import annotations

import importlib
from pathlib import Path

import supervisor

__all__: list[str] = []


def test_facade_cli_parser_and_core_tick_are_extracted_cohesively() -> None:
    root = Path(supervisor.__file__).resolve().parent
    expected = [
        root / "_supervisor_cli_parser.py",
        root / "_supervisor_diagnostics.py",
        root / "_supervisor_tick.py",
    ]

    for module_path in expected:
        assert module_path.is_file()

    cli_parser = importlib.import_module("_supervisor_cli_parser")
    diagnostics = importlib.import_module("_supervisor_diagnostics")
    tick = importlib.import_module("_supervisor_tick")

    assert hasattr(cli_parser, "build_parser")
    assert hasattr(diagnostics, "alert")
    assert hasattr(tick, "run_tick")
    assert hasattr(supervisor, "main")
