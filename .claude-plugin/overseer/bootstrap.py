"""bootstrap.py — the two-pane bootstrap's order of operations.

`SPECIFICATION/contracts.md` states the preconditions this module enforces: the
bootstrap refuses, BEFORE mutating any window, when ownership of its tmux or herdr
pane cannot be verified, naming the missing precondition; it splits ONLY that
verified invoking window or tab; and it is idempotent, reusing a verified daemon
pane already present in that layout rather than duplicating it.
`SPECIFICATION/constraints.md` adds the capability rule: a selected backend whose
required capabilities are unavailable fails closed before the DEPENDENT ACTION,
naming the failed capability, and never falls back to the other backend.

**Everything here is sequence, and the sequence IS the guarantee.** Each step is a
question that must be answered before the next one may be asked, and each refusal
happens at the earliest point the evidence allows:

  1. WHO owns us — :func:`terminal_ownership.select_owner`, which mutates nothing.
  2. Does the selected backend have a bootstrap at all, and are its capabilities
     present — asked of THAT backend and no other.
  3. Is a verified live daemon already hosting the top pane, or is there something
     up there that cannot be accounted for.
  4. Only then, one split.

Reordering any two of those turns a refusal into a half-applied layout, which is
why the beside-tests grade the call sequence rather than the returned error.

**The backend vocabulary deliberately has no destructive verb.** A bootstrap can
probe a capability, read the layout, and place a pane; it cannot close, kill or
terminate anything. That is the structural form of the rule that a lost or
malformed acknowledgement after a split or a daemon launch must NOT be followed by
cleanup: there is no cleanup to perform, so a possibly-live daemon cannot be
destroyed because its acknowledgement went missing. Nothing is retried either —
`place_daemon_above` is called at most once per bootstrap, because repeating a
mutation past the write boundary would run the daemon command twice or put the
daemon pane back below the session it supervises.

**An UNRESOLVED layout is a third answer, not a missing daemon.** The reading in
step 3 distinguishes three states: a proven live daemon above the invoking pane
(reuse it), nothing above it at all (split), and something above it that cannot be
proven either way (refuse, and name what has to be established). The third is what
a lost acknowledgement leaves behind, and treating it as the second would repeat
the very mutation whose outcome was never settled. `contracts.md` requires further
action to rest on fresh evidence instead, so the refusal says so.
"""

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
    "bootstrap_two_pane",
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

    Three verbs, none destructive. See the module docstring for why the absence of
    a fourth is a guarantee rather than an omission.
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


def _refusal(
    *,
    backend: str,
    error: str,
    probe_errors: tuple[str, ...],
    pane_id: str = "",
    effect_unknown: bool = False,
) -> BootstrapOutcome:
    return BootstrapOutcome(
        ok=False,
        backend=backend,
        pane_id=pane_id,
        created=False,
        reused=False,
        error=error,
        effect_unknown=effect_unknown,
        probe_errors=probe_errors,
    )


def _missing_capability(*, backend: str) -> str:
    return (
        f"the selected {backend} backend has no bootstrap capability in this build; "
        "refusing rather than falling back to another terminal instance"
    )


def _backend_refusal(
    *,
    claim: terminal_ownership.OwnershipClaim,
    backends: Mapping[str, BootstrapBackend],
    probe_errors: tuple[str, ...],
) -> BootstrapOutcome | None:
    """Why the SELECTED backend may not act, or None when it may.

    Step 2 of the sequence, and it asks only the selected backend: a build with no
    bootstrap for it, and a build whose bootstrap reports a missing capability, are
    both refusals naming that backend rather than reasons to try the other one.
    """
    backend = backends.get(claim.backend)
    if backend is None:
        return _refusal(
            backend=claim.backend,
            error=_missing_capability(backend=claim.backend),
            probe_errors=probe_errors,
        )
    capability = backend.capability_error(claim=claim)
    if capability:
        return _refusal(backend=claim.backend, error=capability, probe_errors=probe_errors)
    return None


def _placed(
    *,
    backend: BootstrapBackend,
    claim: terminal_ownership.OwnershipClaim,
    cwd: str,
    command: str,
    probe_errors: tuple[str, ...],
) -> BootstrapOutcome:
    """Steps 3 and 4: read the invoking layout, and split it at most once."""
    host = backend.daemon_host(claim=claim)
    if host.error:
        return _refusal(backend=claim.backend, error=host.error, probe_errors=probe_errors)
    if host.pane_id:
        return BootstrapOutcome(
            ok=True,
            backend=claim.backend,
            pane_id=host.pane_id,
            created=False,
            reused=True,
            error="",
            effect_unknown=False,
            probe_errors=probe_errors,
        )
    if host.unresolved:
        return _refusal(backend=claim.backend, error=host.unresolved, probe_errors=probe_errors)
    placement = backend.place_daemon_above(claim=claim, cwd=cwd, command=command)
    if not placement.ok:
        return _refusal(
            backend=claim.backend,
            error=placement.error,
            probe_errors=probe_errors,
            pane_id=placement.pane_id,
            effect_unknown=placement.effect_unknown,
        )
    return BootstrapOutcome(
        ok=True,
        backend=claim.backend,
        pane_id=placement.pane_id,
        created=True,
        reused=False,
        error="",
        effect_unknown=False,
        probe_errors=probe_errors,
    )


def bootstrap_two_pane(
    *,
    caller: CallerEvidence,
    backends: Mapping[str, BootstrapBackend],
    cwd: str,
    command: str,
) -> BootstrapOutcome:
    """Place `command` in a daemon pane ABOVE the verified invoking pane, once.

    Returns before touching any terminal whenever ownership, the selected backend's
    capabilities, or the invoking layout cannot be established. On a verified reuse
    it performs no mutation at all; on a first bootstrap it performs exactly one.
    """
    selection = terminal_ownership.select_owner(
        pid=caller.pid,
        environ=caller.environ,
        probes=caller.probes,
        ppid_of=caller.ppid_of,
    )
    claim = selection.claim
    if claim is None:
        return _refusal(backend="", error=selection.error, probe_errors=selection.probe_errors)
    refusal = _backend_refusal(claim=claim, backends=backends, probe_errors=selection.probe_errors)
    if refusal is not None:
        return refusal
    return _placed(
        backend=backends[claim.backend],
        claim=claim,
        cwd=cwd,
        command=command,
        probe_errors=selection.probe_errors,
    )
