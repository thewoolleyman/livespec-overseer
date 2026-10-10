"""Malformed tmux rectangles refuse before public bootstrap can split."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

import pytest
import tmuxio

from overseer import bootstrap, terminal_ownership, tmux_bootstrap

__all__: list[str] = []


@dataclass(frozen=True, kw_only=True)
class _Completed:
    returncode: int
    stdout: str = ""
    stderr: str = ""


@dataclass(kw_only=True)
class _MalformedRectangleRun:
    rectangle: tuple[int, int, int, int]
    calls: list[tuple[str, ...]] = field(default_factory=list)

    def __call__(
        self,
        argv: Sequence[str],
        *,
        input: str | None = None,
        capture_output: bool | None = None,
        text: bool | None = None,
        check: bool | None = None,
        timeout: float | None = None,
    ) -> _Completed:
        del input, capture_output, text, check, timeout
        call = tuple(argv)
        self.calls.append(call)
        rendered = " ".join(call)
        if "pane_left" in rendered:
            left, top, width, height = self.rectangle
            return _Completed(
                returncode=0,
                stdout=(f"%daemon\t{left}\t{top}\t{width}\t{height}\n" "%caller\t0\t20\t60\t20\n"),
            )
        return _Completed(returncode=1)


@dataclass(frozen=True, kw_only=True)
class _TmuxProbe:
    backend: str = "tmux"

    def endpoints(self, *, environ: Mapping[str, str]) -> tuple[str, ...]:
        del environ
        return ("",)

    def owned_panes(self, *, endpoint: str) -> terminal_ownership.ClaimReading:
        return terminal_ownership.ClaimReading(
            panes=(
                terminal_ownership.OwnedPane(
                    backend=self.backend,
                    socket_path=endpoint,
                    server_pid=300,
                    server_starttime="gen-1",
                    pane_id="%caller",
                    pane_process_pids=(200,),
                ),
            ),
            error="",
        )


@pytest.mark.parametrize(
    "rectangle",
    [
        (-1, 0, 60, 20),
        (0, -1, 60, 20),
        (0, 0, 0, 20),
        (0, 0, -1, 20),
        (0, 0, 60, 0),
        (0, 0, 60, -1),
    ],
)
def test_invalid_tmux_rectangle_refuses_before_any_split(
    *, rectangle: tuple[int, int, int, int]
) -> None:
    run = _MalformedRectangleRun(rectangle=rectangle)
    backend = tmux_bootstrap.TmuxBootstrap(
        daemon_executable=None,
        driver_for=lambda *, socket_path: tmuxio.TmuxIO(run=run),
    )
    backends: dict[str, bootstrap.BootstrapBackend] = {"tmux": backend}
    probes: tuple[terminal_ownership.TerminalProbe, ...] = (_TmuxProbe(),)

    outcome = bootstrap.bootstrap_two_pane(
        caller=bootstrap.CallerEvidence(
            pid=100,
            environ={},
            probes=probes,
            ppid_of=lambda *, pid: {100: 200, 200: 300, 300: 1}.get(pid),
        ),
        backends=backends,
        cwd="/candidate",
        command="overseerd",
    )

    assert not outcome.ok
    assert "pane geometry is unavailable" in outcome.error
    assert not any("split-window" in " ".join(call) for call in run.calls)
