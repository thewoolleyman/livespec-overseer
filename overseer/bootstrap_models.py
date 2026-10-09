"""Typed evidence, backend protocol and outcomes for two-pane bootstrap."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

import terminal_ownership
from _seams import PidToOptionalInt

__all__: list[str] = [
    "BootstrapBackend",
    "BootstrapOutcome",
    "CallerEvidence",
    "DaemonHostReading",
    "PlacementOutcome",
]


@dataclass(frozen=True, kw_only=True)
class CallerEvidence:
    """Everything needed to prove WHERE the invoking process lives.

    Bundled because the four are never useful apart — a pid with no parent reader
    cannot be placed, and probes with no pid have nothing to be measured against —
    and because the bundle is what makes the public entry point one question rather
    than seven parameters.
    """

    pid: int
    environ: Mapping[str, str]
    probes: Sequence[terminal_ownership.TerminalProbe]
    ppid_of: PidToOptionalInt


@dataclass(frozen=True, kw_only=True)
class DaemonHostReading:
    """Whether a verified live daemon already hosts the top pane.

    Exactly one of three shapes, and the three-way split is the point:

      - `pane_id` set — a LIVE daemon process was proven in a pane above the
        invoking one. A retained shell that outlived its daemon is NOT this case;
        a pane still existing is not a process still running.
      - `unresolved` set — something is up there that can be neither accepted as
        the daemon nor treated as absent. Refuse and name it.
      - `error` set — the reading itself could not be taken, so nothing about the
        layout is known.
    """

    pane_id: str
    unresolved: str
    error: str


@dataclass(frozen=True, kw_only=True)
class PlacementOutcome:
    """One layout mutation's result, naming the pane it created when it got that far.

    `pane_id` is reported even on a FAILED outcome whenever a trustworthy new pane
    was identified, because a partially-applied layout is exactly the state a
    caller has to re-observe. `effect_unknown` separates a mutation refused before
    the write boundary — safe to reconsider — from one whose request was sent and
    went unanswered, which must not be submitted again.
    """

    ok: bool
    pane_id: str
    error: str
    effect_unknown: bool


class BootstrapBackend(Protocol):
    """One backend's whole bootstrap vocabulary over a terminal.

    Three verbs, none destructive. See :mod:`bootstrap` for why the absence of a
    fourth is a guarantee rather than an omission.
    """

    backend: str

    def capability_error(self, *, claim: terminal_ownership.OwnershipClaim) -> str: ...

    def daemon_host(self, *, claim: terminal_ownership.OwnershipClaim) -> DaemonHostReading: ...

    def place_daemon_above(
        self, *, claim: terminal_ownership.OwnershipClaim, cwd: str, command: str
    ) -> PlacementOutcome: ...


@dataclass(frozen=True, kw_only=True)
class BootstrapOutcome:
    """What the bootstrap did, or the precondition it refused on.

    `created` and `reused` are both False on every refusal AND on an uncertain
    placement: a pane whose creation was acknowledged but whose acknowledgement was
    lost has not been established as the daemon's host, and reporting it as created
    would be the claim this whole module exists to avoid making.
    """

    ok: bool
    backend: str
    pane_id: str
    created: bool
    reused: bool
    error: str
    effect_unknown: bool
    probe_errors: tuple[str, ...]
