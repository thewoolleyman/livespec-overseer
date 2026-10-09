"""Public ``overseer-start`` coordination over verified terminal ownership.

This is the shipped path that joins the accepted pure pieces: both ownership
probes, both selected-instance bootstrap backends, the durable uncertainty
journal, and the existing daemon-runtime preparation.  Supervision adoption is
retained for tmux only; Herdr registry/adoption and predecessor replacement are
dependent slices and are deliberately not activated here.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from typing import cast

import bootstrap
import bootstrap_journal
import herdr_bootstrap
import herdr_identity
import streams
import supervisor
import terminal_ownership
import terminal_probes
import tmux_bootstrap
from claude_sessions import proc_ppid

__all__: list[str] = ["run_verified_bootstrap"]


def _report_probe_errors(*, errors: tuple[str, ...]) -> None:
    for error in errors:
        streams.write_stderr(text=f"overseer-start: terminal probe warning: {error}\n")


def _report_refusal(*, outcome: bootstrap.BootstrapOutcome) -> None:
    uncertainty = (
        " The terminal effect is unknown and will not be repeated."
        if outcome.effect_unknown
        else ""
    )
    pane = f" Known created pane: {outcome.pane_id}." if outcome.pane_id else ""
    streams.write_stderr(text=f"overseer-start: {outcome.error}.{uncertainty}{pane}\n")


def _adopt_tmux(*, build_supervisor: Callable[[], supervisor.Supervisor] | None) -> None:
    build = build_supervisor if build_supervisor is not None else supervisor.build_supervisor
    adopted = build().adopt_sessions()
    for track in adopted:
        streams.write_stderr(
            text=f"overseer-start: adopted {track.tmux} → {track.repo}::{track.topic}\n"
        )
    streams.write_stderr(text=f"overseer-start: adopted {len(adopted)} existing session(s).\n")


def run_verified_bootstrap(
    *,
    core: Path,
    command: str,
    build_supervisor: Callable[[], supervisor.Supervisor] | None = None,
    journal: bootstrap_journal.MutationJournal | None = None,
) -> int:
    """Bootstrap the nearest positively verified owning terminal instance."""
    mutation_journal = (
        journal if journal is not None else bootstrap_journal.BootstrapMutationJournal()
    )
    outcome = bootstrap.bootstrap_two_pane(
        caller=bootstrap.CallerEvidence(
            pid=os.getpid(),
            environ=dict(os.environ),
            probes=cast(
                tuple[terminal_ownership.TerminalProbe, ...],
                (
                    terminal_probes.TmuxOwnershipProbe(),
                    terminal_probes.HerdrOwnershipProbe(),
                ),
            ),
            ppid_of=proc_ppid,
        ),
        backends=cast(
            dict[str, bootstrap.BootstrapBackend],
            {
                herdr_identity.TMUX_BACKEND: tmux_bootstrap.TmuxBootstrap(),
                herdr_identity.HERDR_BACKEND: herdr_bootstrap.HerdrBootstrap(),
            },
        ),
        cwd=str(core),
        command=command,
        journal=mutation_journal,
    )
    _report_probe_errors(errors=outcome.probe_errors)
    if not outcome.ok:
        _report_refusal(outcome=outcome)
        return 1
    action = "reused" if outcome.reused else "started"
    streams.write_stderr(
        text=(
            f"overseer-start: {action} overseerd in verified {outcome.backend} "
            f"top pane {outcome.pane_id}.\n"
        )
    )
    if outcome.backend == herdr_identity.TMUX_BACKEND:
        _adopt_tmux(build_supervisor=build_supervisor)
    return 0
