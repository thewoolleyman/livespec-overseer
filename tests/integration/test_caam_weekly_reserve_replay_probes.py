"""Executable, checkout-local probes for the weekly-reserve proof replay."""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

import pytest

__all__: list[str] = []

pytestmark = pytest.mark.integration

ROOT = Path(__file__).parents[2]
WEEKLY_RESERVE_PROBE = ROOT / "scripts/caam_weekly_reserve_probe.py"
EXPIRING_DRAIN_PROBE = ROOT / "scripts/caam_expiring_drain_probe.py"


def run_probe(
    *,
    program: Path,
    arguments: list[str],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> str:
    """Run one proof probe from paths a clean checkout supplies."""
    monkeypatch.setattr(sys, "argv", [str(program), *arguments])
    runpy.run_path(str(program), run_name="__main__")
    return capsys.readouterr().out


def test_weekly_reserve_probe_replays_from_the_checkout(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The serveability release probe needs no untracked scratch helper."""
    assert WEEKLY_RESERVE_PROBE.is_file()

    output = run_probe(
        program=WEEKLY_RESERVE_PROBE,
        arguments=["unusable"],
        monkeypatch=monkeypatch,
        capsys=capsys,
    )

    assert "scheduled-pass case=unusable exit=0" in output
    assert "weekly reserve was released" in output


def test_expiring_drain_probe_replays_from_the_checkout(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The drain exception probe needs no untracked scratch helper."""
    assert EXPIRING_DRAIN_PROBE.is_file()

    output = run_probe(
        program=EXPIRING_DRAIN_PROBE,
        arguments=[],
        monkeypatch=monkeypatch,
        capsys=capsys,
    )

    assert "scheduled-pass case=expiring-drain exit=0" in output
