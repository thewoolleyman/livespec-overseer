"""Deterministic checkout-side coverage for public bootstrap coordination.

The native companion test proves real installed-candidate effects.  These cases
keep the orchestration and durable journal visible to checkout coverage without
replacing that native proof with doubles.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path

import pytest

from overseer import (
    bootstrap,
    bootstrap_journal,
    public_bootstrap,
    start,
    terminal_ownership,
    terminal_probes,
)

__all__: list[str] = []


def _outcome(
    *,
    ok: bool,
    backend: str,
    pane_id: str,
    reused: bool = False,
    error: str = "",
    effect_unknown: bool = False,
) -> bootstrap.BootstrapOutcome:
    return bootstrap.BootstrapOutcome(
        ok=ok,
        backend=backend,
        pane_id=pane_id,
        created=ok and not reused,
        reused=reused,
        error=error,
        effect_unknown=effect_unknown,
        probe_errors=(),
    )


@dataclass(frozen=True, kw_only=True)
class _Track:
    tmux: str
    repo: str
    topic: str


@dataclass(frozen=True, kw_only=True)
class _Supervisor:
    adopted: tuple[_Track, ...] = ()

    def adopt_sessions(self) -> list[_Track]:
        return list(self.adopted)


def test_public_coordinator_reports_refusals_successes_and_tmux_adoption(
    *, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    outcomes = [
        replace(
            _outcome(
                ok=False,
                backend="herdr",
                pane_id="tab:p2",
                error="reply was lost",
                effect_unknown=True,
            ),
            probe_errors=("tmux endpoint stale",),
        ),
        _outcome(ok=False, backend="herdr", pane_id="", error="ownership is ambiguous"),
        _outcome(ok=True, backend="tmux", pane_id="%2", reused=True),
        _outcome(ok=True, backend="tmux", pane_id="%3"),
        _outcome(ok=True, backend="herdr", pane_id="tab:p4"),
    ]
    calls: list[dict[str, object]] = []

    def coordinate(**kwargs: object) -> bootstrap.BootstrapOutcome:
        calls.append(kwargs)
        return outcomes.pop(0)

    monkeypatch.setattr(public_bootstrap.bootstrap, "bootstrap_two_pane", coordinate)
    explicit_journal = bootstrap_journal.NoMutationJournal()

    assert (
        public_bootstrap.run_verified_bootstrap(
            core=tmp_path, command="overseerd", journal=explicit_journal
        )
        == 1
    )
    assert public_bootstrap.run_verified_bootstrap(core=tmp_path, command="overseerd") == 1
    assert (
        public_bootstrap.run_verified_bootstrap(
            core=tmp_path,
            command="overseerd",
            build_supervisor=lambda: _Supervisor(
                adopted=(_Track(tmux="work", repo="/repo", topic="plan"),)
            ),
        )
        == 0
    )
    monkeypatch.setattr(public_bootstrap.supervisor, "build_supervisor", lambda: _Supervisor())
    assert public_bootstrap.run_verified_bootstrap(core=tmp_path, command="overseerd") == 0
    assert public_bootstrap.run_verified_bootstrap(core=tmp_path, command="overseerd") == 0

    first = calls[0]
    assert first["journal"] is explicit_journal
    assert {probe.backend for probe in first["caller"].probes} == {"tmux", "herdr"}
    assert set(first["backends"]) == {"tmux", "herdr"}
    err = capsys.readouterr().err
    assert "terminal probe warning: tmux endpoint stale" in err
    assert "effect is unknown" in err
    assert "Known created pane: tab:p2" in err
    assert "ownership is ambiguous" in err
    assert "reused overseerd in verified tmux top pane %2" in err
    assert "adopted work → /repo::plan" in err
    assert "started overseerd in verified herdr top pane tab:p4" in err


def _claim(*, generation: str = "901") -> terminal_ownership.OwnershipClaim:
    return terminal_ownership.OwnershipClaim(
        backend="herdr",
        socket_path="/run/user/1000/herdr.sock",
        server_pid=901,
        server_starttime=generation,
        pane_id="tab:p7",
        pane_process_pid=77,
        distance=2,
    )


def test_journal_retains_exact_identity_until_fresh_evidence_resolves_it(*, tmp_path: Path) -> None:
    assert bootstrap_journal.default_journal_root(home=tmp_path).is_relative_to(tmp_path)
    assert bootstrap_journal.default_journal_root().is_absolute()
    journal = bootstrap_journal.BootstrapMutationJournal(root=tmp_path / "journal")
    claim = _claim()

    assert journal.pending_error(claim=claim) == ""
    journal.prepare(claim=claim)
    records = list(journal.root.glob("*.json"))
    assert len(records) == 1
    prepared = json.loads(records[0].read_text(encoding="utf-8"))
    assert prepared == {
        "backend": "herdr",
        "invoking_pane_id": "tab:p7",
        "known_created_pane_id": "",
        "server_pid": 901,
        "server_starttime": "901",
        "socket_path": "/run/user/1000/herdr.sock",
    }
    assert "fresh exact-instance, pane and process evidence" in journal.pending_error(claim=claim)
    assert journal.pending_error(claim=_claim(generation="902")) == ""
    with pytest.raises(FileExistsError):
        journal.prepare(claim=claim)

    journal.retain(claim=claim, pane_id="tab:p2")
    retained = json.loads(records[0].read_text(encoding="utf-8"))
    assert retained["known_created_pane_id"] == "tab:p2"
    journal.resolve(claim=claim)
    journal.resolve(claim=claim)
    assert journal.pending_error(claim=claim) == ""


@dataclass(kw_only=True)
class _NeverPlaceBackend:
    backend: str = "herdr"

    def capability_error(self, *, claim: terminal_ownership.OwnershipClaim) -> str:
        _ = claim
        return ""

    def daemon_host(
        self, *, claim: terminal_ownership.OwnershipClaim
    ) -> bootstrap.DaemonHostReading:
        _ = claim
        return bootstrap.DaemonHostReading(pane_id="", unresolved="", error="")

    def place_daemon_above(
        self, *, claim: terminal_ownership.OwnershipClaim, cwd: str, command: str
    ) -> bootstrap.PlacementOutcome:
        raise AssertionError(f"mutation replayed for {claim.pane_id} in {cwd}: {command}")


@dataclass(frozen=True, kw_only=True)
class _PendingJournal(bootstrap_journal.NoMutationJournal):
    def pending_error(self, *, claim: terminal_ownership.OwnershipClaim) -> str:
        return f"{claim.pane_id} still has unresolved exact-instance evidence"


def test_an_existing_journal_refuses_before_replaying_the_mutation(
    *, monkeypatch: pytest.MonkeyPatch
) -> None:
    claim = _claim()
    monkeypatch.setattr(
        bootstrap.terminal_ownership,
        "select_owner",
        lambda **_kwargs: terminal_ownership.OwnerSelection(
            ok=True, claim=claim, error="", probe_errors=()
        ),
    )

    outcome = bootstrap.bootstrap_two_pane(
        caller=bootstrap.CallerEvidence(pid=1, environ={}, probes=(), ppid_of=lambda *, pid: pid),
        backends={"herdr": _NeverPlaceBackend()},
        cwd="/repo",
        command="overseerd",
        journal=_PendingJournal(),
    )

    assert not outcome.ok
    assert "unresolved exact-instance evidence" in outcome.error


def test_verified_start_prepares_runtime_and_preserves_operator_home(
    *, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    executable = tmp_path / "candidate" / "bin" / "overseerd"
    calls: list[tuple[Path, str]] = []
    monkeypatch.setattr(start, "_running_under_supported_agent", lambda: True)
    monkeypatch.setenv(terminal_probes.HERDR_SOCKET_ENV, "/run/user/1000/herdr.sock")
    monkeypatch.setenv("HOME", str(tmp_path / "operator-home"))
    monkeypatch.setattr(
        start.public_bootstrap,
        "run_verified_bootstrap",
        lambda *, core, command, build_supervisor: calls.append((core, command)) or 0,
    )

    assert (
        start.main(
            argv=["--warn-percent", "37"],
            core_root=tmp_path,
            ensure_daemon_runtime=lambda: executable,
        )
        == 0
    )
    assert calls[0][0] == tmp_path
    assert calls[0][1].startswith(f"HOME={tmp_path / 'operator-home'} ")
    assert str(executable) in calls[0][1]
    assert "--warn-percent 37" in calls[0][1]


def test_verified_start_covers_runtime_refusal_defaults_and_legacy_pane_guard(
    *, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(start, "_running_under_supported_agent", lambda: True)
    monkeypatch.setenv(terminal_probes.HERDR_SOCKET_ENV, "/run/user/1000/herdr.sock")
    assert start.main(argv=[], core_root=tmp_path, ensure_daemon_runtime=lambda: None) == 1
    assert "failed to prepare" in capsys.readouterr().err

    executable = tmp_path / "candidate" / "overseerd"
    monkeypatch.setattr(start, "_default_core_root", lambda: tmp_path)
    monkeypatch.setattr(start.runtime_prefix, "ensure_current_runtime", lambda: executable)
    monkeypatch.delenv("HOME", raising=False)
    commands: list[str] = []
    monkeypatch.setattr(
        start.public_bootstrap,
        "run_verified_bootstrap",
        lambda *, core, command, build_supervisor: commands.append(command) or 0,
    )
    assert start.main(argv=[]) == 0
    assert commands == [f"{executable} 2>> {tmp_path / 'tmp/overseer/daemon.log'}"]

    monkeypatch.delenv("TMUX_PANE", raising=False)
    assert start.main(argv=[], io=object()) == 1
    assert "$TMUX_PANE unset" in capsys.readouterr().err
