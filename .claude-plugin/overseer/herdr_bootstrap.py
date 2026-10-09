"""herdr_bootstrap.py — the herdr backend of the two-pane bootstrap.

Three questions about one herdr instance, in the order :mod:`bootstrap` asks them:
can this instance answer the geometry method at all, is a live daemon already
above the invoking pane, and — only then — place one there.

**The capability probed is the GEOMETRY method, because "above" is the whole
requirement.** `plan/herdr-overseer/research/002-herdr-api-evidence.md` measured
that herdr supports only `right` and `down` splits, so placing a pane above an
existing one is a split FOLLOWED BY a swap, and every step of that sequence is
checked against `pane.layout`. An instance that cannot answer `pane.layout`
therefore cannot have "above" established on it at all. `SPECIFICATION/
constraints.md` requires a selected backend's missing capability to be named
before its DEPENDENT ACTION, and the dependent action here is the split — so the
probe is a read, it runs first, and it names the method.

**The reading is three-way, not two-way.** A pane above the invoking one is
accepted only when the server reports a foreground group that is NOT its own
retained shell AND fresh kernel evidence binds that exact group leader to this
installed command's daemon runtime; anything else up there is UNRESOLVED rather
than absent. The distinction is load-bearing in the direction that costs a
mutation: calling an unaccountable pane "absent" would split again, which is
exactly what must not happen after a lost acknowledgement.

**More than one pane above is unresolved too.** The bootstrap owns a two-pane
layout; a tab carrying several panes above the invoking one is a shape this
bootstrap did not create and cannot reason about, and guessing which of them was
meant to be the daemon is the kind of inference the ownership rules exist to
forbid.

**The placement is :func:`herdr_write.HerdrWriter.split_window_top` unchanged.**
Every proof the sequence needs — that the created pane is new, is in the target's
tab, really ended up above, and is still an idle retained shell at the instant of
the write — already lives in :mod:`herdr_layout`, as does the `effect_unknown`
accounting for a mutation whose answer was lost. This module adapts that outcome
to :class:`bootstrap.PlacementOutcome` and adds nothing: in particular it does not
retry, and it has no way to undo, so a pane created past an unanswered request is
carried out by name for re-observation rather than cleaned up.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import bootstrap
import herdr_adapter
import herdr_identity
import herdr_write
import herdr_write_calls
import terminal_ownership
import tmux_daemon_liveness

__all__: list[str] = ["HerdrBootstrap"]


@dataclass(frozen=True, kw_only=True)
class HerdrBootstrap:
    """Place and verify the daemon pane on ONE exact herdr instance generation.

    `adapter` and `writer` are the observation and mutation surfaces rather than
    sockets, so this module owns no I/O: the deadline, the `SO_PEERCRED` peer
    validation and the pane-echo guards all belong to them and are reused rather
    than restated. Both are injectable so the beside-tests can drive an
    unreadable layout, an occupied pane above, and a lost acknowledgement.
    """

    backend: str = herdr_identity.HERDR_BACKEND
    adapter: Any = field(default_factory=herdr_adapter.HerdrAdapter)
    writer: Any = field(default_factory=herdr_write.HerdrWriter)
    daemon_process_of: Callable[..., tmux_daemon_liveness.DaemonProcessIdentity | None] = field(
        default_factory=lambda: tmux_daemon_liveness.foreground_daemon_process
    )
    ratio: float = herdr_write.DEFAULT_TOP_RATIO

    def capability_error(self, *, claim: terminal_ownership.OwnershipClaim) -> str:
        """Why this instance cannot have a pane placed above the claim, or `""`."""
        _tops, error = self._tops(claim=claim)
        if error:
            return (
                f"herdr {herdr_write_calls.LAYOUT_METHOD} is unavailable on the selected "
                f"instance {claim.socket_path} (server {claim.server_pid}), so a pane "
                f"cannot be placed above {claim.pane_id!r}: {error}"
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
                    f"{len(above)} panes sit above {claim.pane_id!r} on this tab ({above}); "
                    "this bootstrap owns a two-pane layout and will not choose between them"
                ),
                error="",
            )
        return self._occupant(claim=claim, candidate=above[0])

    def place_daemon_above(
        self, *, claim: terminal_ownership.OwnershipClaim, cwd: str, command: str
    ) -> bootstrap.PlacementOutcome:
        """Run `command` in a new retained-shell pane placed ABOVE the claimed pane."""
        outcome = self.writer.split_window_top(
            target=self._target(claim=claim, pane_id=claim.pane_id),
            cwd=cwd,
            command=command,
            ratio=self.ratio,
        )
        return bootstrap.PlacementOutcome(
            ok=outcome.ok,
            pane_id=outcome.pane_id,
            error=outcome.error,
            effect_unknown=outcome.effect_unknown,
        )

    def _target(
        self, *, claim: terminal_ownership.OwnershipClaim, pane_id: str
    ) -> herdr_identity.HerdrPaneTarget:
        """One pane on the EXACT generation the claim verified, never a namesake."""
        return herdr_identity.HerdrPaneTarget(
            socket_path=claim.socket_path,
            server_pid=claim.server_pid,
            server_starttime=claim.server_starttime,
            pane_id=pane_id,
        )

    def _tops(
        self, *, claim: terminal_ownership.OwnershipClaim
    ) -> tuple[dict[str, int] | None, str]:
        """Each pane's top row on the claim's tab, or why the geometry is unusable.

        A layout that does not place the claimed pane itself is refused rather
        than read around: every comparison below is relative to that pane's own
        row, so an answer missing it cannot establish anything about what is above
        it.
        """
        outcome = self.writer.request(
            target=self._target(claim=claim, pane_id=claim.pane_id),
            method=herdr_write_calls.LAYOUT_METHOD,
            params=herdr_write_calls.layout_params(pane_id=claim.pane_id),
            expect=herdr_write_calls.EXPECT_LAYOUT,
        )
        if not outcome.ok:
            return None, outcome.error
        tops = herdr_write_calls.pane_tops(result=outcome.result)
        if tops is None:
            return None, "herdr tab layout is unreadable"
        if claim.pane_id not in tops:
            return None, f"herdr tab layout does not place pane {claim.pane_id!r}"
        return tops, ""

    def _occupant(
        self, *, claim: terminal_ownership.OwnershipClaim, candidate: str
    ) -> bootstrap.DaemonHostReading:
        """What is running in the single pane above the claim, judged fail-closed."""
        reading = self.adapter.foreground(target=self._target(claim=claim, pane_id=candidate))
        if reading.process is None:
            return bootstrap.DaemonHostReading(
                pane_id="",
                unresolved="",
                error=(
                    f"the pane above {claim.pane_id!r} ({candidate!r}) has no readable "
                    f"process: {reading.error}"
                ),
            )
        process = reading.process
        if process.process_group_id == process.shell_pid:
            return bootstrap.DaemonHostReading(
                pane_id="",
                unresolved=(
                    f"pane {candidate!r} above {claim.pane_id!r} holds its retained shell "
                    f"(pid {process.shell_pid}) rather than a live daemon; a pane that "
                    "outlived its daemon is not daemon liveness, so further action needs "
                    "fresh exact-instance, pane and process evidence"
                ),
                error="",
            )
        identity = self.daemon_process_of(root_pid=process.shell_pid)
        if identity is None or identity.pid != process.process_group_id:
            return bootstrap.DaemonHostReading(
                pane_id="",
                unresolved=(
                    f"pane {candidate!r} above {claim.pane_id!r} runs {process.name!r} "
                    f"(group {process.process_group_id}), not the overseer daemon; further "
                    "action needs fresh exact-instance, pane and process evidence"
                ),
                error="",
            )
        return bootstrap.DaemonHostReading(pane_id=candidate, unresolved="", error="")
