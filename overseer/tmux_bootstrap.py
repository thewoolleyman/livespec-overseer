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
was proven against that server's generation and no other. So the driver is built
from the claim — the default endpoint produces a plain :class:`tmuxio.TmuxIO`,
byte-for-byte the legacy argv, and a named endpoint wraps its runner in
:class:`terminal_probes.SocketScopedRun`, which inserts `-S <socket>` into every
subcommand. Legacy behaviour is preserved by CONSTRUCTION rather than by a flag.

**The capability probed is the pane GEOMETRY read**, for the same reason the herdr
arm probes `pane.layout`: "above" is the requirement, every judgement below is
relative to the claimed pane's own row, and an instance that cannot report that
row cannot have "above" established on it. It is a read, it runs before the split,
and it names what failed.

**Liveness is fresh pane/process evidence, never its title.** The legacy bootstrap
resolved its daemon pane by the `overseer-daemon` pane title; the title is still
SET, because the operator reads it and the legacy layout carries it, but it is not
what is believed. A title is presentation and drifts — live Claude panes drift
theirs to task summaries. `#{pane_current_command}` is the first process reading;
when tmux reports the retained shell, a bounded `/proc` walk must freshly find an
`overseerd` descendant under that exact pane root.  The shell's own command line
does not count because `bash -c '<overseerd command>'` can keep naming a daemon
that has already died.  A pane above the invoking one holding only its login shell
is therefore UNRESOLVED: "the pane is still there" says nothing about the daemon.

**A failed split is a KNOWN failure, not an uncertain one.** `tmuxio` reports a
failed `split-window` as `None` after a bounded, non-zero-exit subprocess call, so
nothing was committed and left unanswered — unlike the herdr socket, there is no
write boundary to be on the far side of. `effect_unknown` is therefore always
False on this arm, and that is a property of the transport rather than an
assumption about tmux.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import bootstrap
import daemon_liveness
import herdr_identity
import terminal_ownership
import terminal_probes
import tmux_daemon_liveness
import tmuxio

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


def socket_scoped_driver(
    *, socket_path: str, run: Callable[..., Any] = subprocess.run
) -> tmuxio.TmuxIO:
    """A tmux driver bound to ONE instance; the default socket needs no wrapper.

    `run` is injected for the same reason `tmuxio`'s own is — so a test can assert
    the argv this produces without a live server — and because that argv is the
    whole claim: the default endpoint must yield the legacy form with no `-S`, and
    a named one must carry `-S <socket>` on every subcommand.
    """
    if socket_path == terminal_probes.DEFAULT_TMUX_ENDPOINT:
        return tmuxio.TmuxIO(run=run)
    return tmuxio.TmuxIO(run=terminal_probes.SocketScopedRun(socket_path=socket_path, run=run))


@dataclass(frozen=True, kw_only=True)
class TmuxBootstrap:
    """Place and verify the daemon pane on ONE positively selected tmux instance.

    `driver_for` is injected so the beside-tests can drive an unreadable geometry,
    a pane above that holds a shell, and a split that fails — none of which can be
    staged against a healthy server — and so a test can assert WHICH instance each
    call was addressed to.
    """

    backend: str = herdr_identity.TMUX_BACKEND
    driver_for: Callable[..., Any] = socket_scoped_driver
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
        driver = self.driver_for(socket_path=claim.socket_path)
        created = driver.split_window_top(pane=claim.pane_id, cwd=cwd, command=command)
        if created is None:
            return bootstrap.PlacementOutcome(
                ok=False,
                pane_id="",
                error=f"tmux refused to split the window holding {claim.pane_id!r}",
                effect_unknown=False,
            )
        _ = driver.set_pane_title(pane=created, title=self.daemon_pane_title)
        if not driver.pane_exists(pane=created):
            return bootstrap.PlacementOutcome(
                ok=False,
                pane_id=created,
                error=(
                    f"the daemon did not stay alive in tmux pane {created!r}; the pane's "
                    "command exited, which closes the pane"
                ),
                effect_unknown=False,
            )
        # Normalize the stack before resizing, exactly as the legacy bootstrap
        # does: an uneven split left behind by a stray third pane would otherwise
        # make the percentage apply to the wrong baseline.
        _ = driver.select_layout_even(pane=claim.pane_id)
        _ = driver.set_pane_height_percent(pane=created, percent=self.height_percent)
        return bootstrap.PlacementOutcome(ok=True, pane_id=created, error="", effect_unknown=False)

    def _tops(
        self, *, claim: terminal_ownership.OwnershipClaim
    ) -> tuple[dict[str, int] | None, str]:
        """Each pane's top row in the claim's window, or why the geometry is unusable."""
        geometries = self.driver_for(socket_path=claim.socket_path).window_pane_geometries(
            pane=claim.pane_id
        )
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
        driver = self.driver_for(socket_path=claim.socket_path)
        command = driver.pane_current_command(session=candidate)
        if command is None:
            return bootstrap.DaemonHostReading(
                pane_id="",
                unresolved="",
                error=(
                    f"the pane above {claim.pane_id!r} ({candidate!r}) has no readable "
                    "foreground command"
                ),
            )
        if daemon_liveness.is_retained_shell(name=command):
            pane_pid_reader = getattr(driver, "pane_pid", None)
            pane_pid = pane_pid_reader(session=candidate) if pane_pid_reader is not None else None
            if pane_pid is not None and tmux_daemon_liveness.daemon_descendant_command(
                root_pid=pane_pid
            ):
                return bootstrap.DaemonHostReading(pane_id=candidate, unresolved="", error="")
            return bootstrap.DaemonHostReading(
                pane_id="",
                unresolved=(
                    f"pane {candidate!r} above {claim.pane_id!r} holds its retained shell "
                    f"({command!r}) rather than a live daemon; a pane that outlived its "
                    "daemon is not daemon liveness, so further action needs fresh "
                    "exact-instance, pane and process evidence"
                ),
                error="",
            )
        if not daemon_liveness.is_daemon_command(text=command):
            return bootstrap.DaemonHostReading(
                pane_id="",
                unresolved=(
                    f"pane {candidate!r} above {claim.pane_id!r} runs {command!r}, not the "
                    "overseer daemon; further action needs fresh exact-instance, pane and "
                    "process evidence"
                ),
                error="",
            )
        return bootstrap.DaemonHostReading(pane_id=candidate, unresolved="", error="")
