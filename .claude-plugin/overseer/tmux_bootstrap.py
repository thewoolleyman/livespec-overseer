"""tmux_bootstrap.py — the tmux backend of the two-pane bootstrap.

The tmux twin of :mod:`herdr_bootstrap`, answering the same three questions in the
same order against a POSITIVELY SELECTED tmux instance. It exists so that a tmux
ownership claim has a bootstrap of its own: `SPECIFICATION/constraints.md` forbids
falling back to the other backend, so a selected tmux instance with no tmux
bootstrap would be a refusal rather than a split — correct, but useless.

**The instance is RETAINED, which is the part that is new here.** Every existing
tmux call in this package addresses the default server implicitly, and that is
exactly what `SPECIFICATION/constraints.md` requires an unqualified legacy value to
keep meaning. A claim naming a NAMED socket is different: it must keep addressing
THAT server for every later call, because the ownership that authorized the split
was proven against that server's generation and no other. The default endpoint
preserves the legacy no-`-S` meaning, while a named endpoint inserts `-S <socket>`
into every subcommand. Every call then runs a server-side PID/start-time predicate
and its dependent command on the SAME tmux client connection, so a process that
rebinds the socket cannot receive the action.

**The capability probed is the pane GEOMETRY read**, for the same reason the herdr
arm probes `pane.layout`: "above" is the requirement, every judgement below is
relative to the claimed pane's own row, and an instance that cannot report that
row cannot have "above" established on it. It is a read, it runs before the split,
and it names what failed.

**Liveness is fresh pane/process evidence, never its title or reported command.**
The legacy bootstrap resolved its daemon pane by the `overseer-daemon` pane title;
the title is still SET, because the operator reads it and the legacy layout carries
it, but it is not what is believed. A title is presentation and drifts — live
Claude panes drift theirs to task summaries. `#{pane_current_command}` is useful
only for a specific refusal diagnostic. Authorization requires a bounded `/proc`
walk from the exact pane root to a stable PID/start/runtime/argv identity that owns
that pane's terminal foreground group. The shell's own command line does not count
because `bash -c '<overseerd command>'` can keep naming a daemon that has already
died, and a genuine background daemon does not count because it no longer owns the
terminal. A pane above the invoking one holding only its login shell is therefore
UNRESOLVED: "the pane is still there" says nothing about the daemon.

**A failed split is a KNOWN failure, but a post-split proof failure preserves the
known-created pane as unresolved.** `tmuxio` reports a failed `split-window` as
`None` after a bounded, non-zero-exit subprocess call, so nothing was committed
and left unanswered. Once a pane was returned, however, missing server-generation
or exact-process evidence is not permission to repeat or clean up that mutation;
the outcome carries its pane identity with `effect_unknown=True` for fresh
re-observation.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import partial
from pathlib import Path

import bootstrap
import herdr_identity
import terminal_ownership
import tmux_bootstrap_driver
import tmux_bootstrap_launch
import tmux_bootstrap_occupant
import tmux_daemon_liveness
import tmux_generation
import tmuxio_protocols
from tmux_bootstrap_driver import socket_scoped_driver

__all__: list[str] = [
    "DAEMON_PANE_HEIGHT_PERCENT",
    "DAEMON_PANE_TITLE",
    "TmuxBootstrap",
    "socket_scoped_driver",
]

# The identity anchor the operator reads, and the daemon pane's share of the
# window: both carried forward unchanged from the legacy bootstrap, where the
# daemon pane gets the room because it holds the live table AND the NEEDS YOU
# block while the bottom pane is a prompt.
DAEMON_PANE_TITLE = "overseer-daemon"
DAEMON_PANE_HEIGHT_PERCENT = 66
DAEMON_READY_TIMEOUT_SECONDS, DAEMON_READY_POLL_SECONDS = 10.0, 0.05


@dataclass(frozen=True, kw_only=True)
class TmuxBootstrap:
    """Place and verify the daemon pane on ONE positively selected tmux instance.

    `driver_for` is injected so the beside-tests can drive an unreadable geometry,
    a pane above that holds a shell, and a split that fails — none of which can be
    staged against a healthy server — and so a test can assert WHICH instance each
    call was addressed to.
    """

    daemon_executable: Path | None = None
    backend: str = herdr_identity.TMUX_BACKEND
    driver_for: tmuxio_protocols.BootstrapDriverFactory = socket_scoped_driver
    daemon_pane_title: str = DAEMON_PANE_TITLE
    height_percent: int = DAEMON_PANE_HEIGHT_PERCENT

    def capability_error(self, *, claim: terminal_ownership.OwnershipClaim) -> str:
        """Why this instance cannot have a pane placed above the claim, or `""`."""
        _tops, error = self._tops(claim=claim)
        if error:
            return (
                f"tmux pane geometry is unavailable on the selected instance "
                f"{claim.socket_path or 'the default socket'} (server {claim.server_pid}), "
                f"so a pane cannot be placed above {claim.pane_id!r}: {error}"
            )
        return ""

    def daemon_host(
        self, *, claim: terminal_ownership.OwnershipClaim
    ) -> bootstrap.DaemonHostReading:
        """Whether a verified live daemon already sits above the claimed pane."""
        tops, error = self._tops(claim=claim)
        if tops is None:
            return bootstrap.DaemonHostReading(pane_id="", unresolved="", error=error)
        own_top = tops[claim.pane_id]
        above = sorted(pane for pane, top in tops.items() if top < own_top)
        if not above:
            return bootstrap.DaemonHostReading(pane_id="", unresolved="", error="")
        if len(above) != 1:
            return bootstrap.DaemonHostReading(
                pane_id="",
                unresolved=(
                    f"{len(above)} panes sit above {claim.pane_id!r} in this window "
                    f"({above}); this bootstrap owns a two-pane layout and will not "
                    "choose between them"
                ),
                error="",
            )
        return self._occupant(claim=claim, candidate=above[0])

    def place_daemon_above(
        self, *, claim: terminal_ownership.OwnershipClaim, cwd: str, command: str
    ) -> bootstrap.PlacementOutcome:
        """Run `command` in a new TOP pane of the claimed pane's own window."""
        driver = self._driver(claim=claim)
        return tmux_generation.guard(
            driver=driver,
            claim=claim,
            daemon_executable=self.daemon_executable,
            valid=partial(self._split, driver=driver, claim=claim, cwd=cwd, command=command),
            invalid=partial(
                bootstrap.PlacementOutcome,
                ok=False,
                pane_id="",
                effect_unknown=False,
            ),
        )

    def _split(
        self,
        *,
        driver: tmuxio_protocols.BootstrapDriver,
        claim: terminal_ownership.OwnershipClaim,
        cwd: str,
        command: str,
    ) -> bootstrap.PlacementOutcome:
        created = driver.split_window_top(pane=claim.pane_id, cwd=cwd, command=command)
        if created is None:
            return bootstrap.PlacementOutcome(
                ok=False,
                pane_id="",
                error=f"tmux refused to split the window holding {claim.pane_id!r}",
                effect_unknown=False,
            )
        return tmux_generation.guard(
            driver=driver,
            claim=claim,
            daemon_executable=self.daemon_executable,
            valid=partial(self._finish_created_pane, driver=driver, claim=claim, created=created),
            invalid=partial(
                bootstrap.PlacementOutcome,
                ok=False,
                pane_id=created,
                effect_unknown=True,
            ),
        )

    def _finish_created_pane(
        self,
        *,
        driver: tmuxio_protocols.BootstrapDriver,
        claim: terminal_ownership.OwnershipClaim,
        created: str,
    ) -> bootstrap.PlacementOutcome:
        """Prove one known-created pane's daemon after its allocation-scoped split."""
        return tmux_bootstrap_launch.finish_created_pane(
            driver=driver,
            created=created,
            observe=partial(self._observed_occupant, driver=driver, claim=claim, candidate=created),
            policy=tmux_bootstrap_launch.LaunchPolicy(
                title=self.daemon_pane_title,
                timeout_seconds=DAEMON_READY_TIMEOUT_SECONDS,
                poll_seconds=DAEMON_READY_POLL_SECONDS,
            ),
        )

    def _driver(
        self, *, claim: terminal_ownership.OwnershipClaim
    ) -> tmuxio_protocols.BootstrapDriver:
        """Bind real calls to the selected generation; injected fakes stay deterministic."""
        return tmux_bootstrap_driver.bind_server_generation(
            driver=self.driver_for(socket_path=claim.socket_path),
            server_pid=claim.server_pid,
            server_starttime=claim.server_starttime,
            split_height_percent=self.height_percent,
        )

    def _tops(
        self, *, claim: terminal_ownership.OwnershipClaim
    ) -> tuple[dict[str, int] | None, str]:
        """Each pane's top row in the claim's window, or why the geometry is unusable."""
        driver = self._driver(claim=claim)
        geometries = driver.window_pane_geometries(pane=claim.pane_id)
        tops = {geometry.pane: geometry.top for geometry in geometries}
        if not tops:
            return None, "tmux reported no panes for this window"
        if claim.pane_id not in tops:
            return None, f"tmux window geometry does not place pane {claim.pane_id!r}"
        return tops, ""

    def _occupant(
        self, *, claim: terminal_ownership.OwnershipClaim, candidate: str
    ) -> bootstrap.DaemonHostReading:
        """What is running in the single pane above the claim, judged fail-closed."""
        driver = self._driver(claim=claim)
        return self._observed_occupant(driver=driver, claim=claim, candidate=candidate)

    def _observed_occupant(
        self,
        *,
        driver: tmuxio_protocols.BootstrapDriver,
        claim: terminal_ownership.OwnershipClaim,
        candidate: str,
    ) -> bootstrap.DaemonHostReading:
        return tmux_generation.guard(
            driver=driver,
            claim=claim,
            daemon_executable=self.daemon_executable,
            valid=partial(
                tmux_bootstrap_occupant.read_daemon_host,
                driver=driver,
                claim=claim,
                candidate=candidate,
                daemon_executable=self.daemon_executable,
                daemon_process_of=tmux_daemon_liveness.foreground_daemon_process,
            ),
            invalid=partial(bootstrap.DaemonHostReading, pane_id="", unresolved=""),
        )
