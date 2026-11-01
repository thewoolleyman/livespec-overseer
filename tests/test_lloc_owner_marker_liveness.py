"""Exercise the installed owner-liveness gate against this repository's source."""

from __future__ import annotations

from collections.abc import Callable
from inspect import signature
from pathlib import Path
from typing import cast

import pytest
from livespec_dev_tooling.checks import no_lloc_soft_warnings
from returns.io import IOSuccess

__all__: list[str] = []

# The standing owners remain open while their refactors are owed. Each case
# supplies a tracker outcome; the installed gate grades the actual source.
DEBT_OWNERS = frozenset(("overseer-4z97.2", "overseer-yizu3e"))


@pytest.mark.parametrize(("status", "expected"), [("backlog", 0), ("closed", 1), (None, 1)])
def test_the_installed_gate_requires_a_live_owner_for_the_actual_source(
    *,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    status: str | None,
    expected: int,
) -> None:
    root = Path(__file__).resolve().parents[1]
    monkeypatch.chdir(root)
    monkeypatch.setenv("LIVESPEC_FAIL_IF_LLOC_SOFT_WARNINGS_EXIST", "true")
    snapshot = {} if status is None else {owner: status for owner in DEBT_OWNERS}
    observed_repos: list[Path] = []

    def read_ledger(*, repo: Path) -> IOSuccess[dict[str, str]]:
        observed_repos.append(repo)
        return IOSuccess(snapshot)

    previous_logging = no_lloc_soft_warnings.structlog.get_config()
    assert "ledger_reader" in signature(no_lloc_soft_warnings.main).parameters
    run_gate = cast(Callable[..., int], no_lloc_soft_warnings.main)
    try:
        result = run_gate(ledger_reader=read_ledger)
    finally:
        no_lloc_soft_warnings.structlog.configure(**previous_logging)
    assert result == expected
    assert observed_repos == [root]
    diagnostics = capsys.readouterr().err
    assert all(owner in diagnostics for owner in DEBT_OWNERS)
    if expected:
        assert "closed or nonexistent" in diagnostics
    else:
        assert "REFACTOR IS OWED" in diagnostics
