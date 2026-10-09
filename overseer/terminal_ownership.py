"""terminal_ownership.py — which terminal instance and pane PROVABLY owns a process.

`SPECIFICATION/constraints.md` requires backend selection to follow the NEAREST
positively verified owning terminal in the invoking process's ancestry, to bind
that ancestry to the exact live backend INSTANCE and PANE, and to refuse — naming
the missing evidence — when ownership is absent, ambiguous or unreadable. It also
states, in the negative, what may NOT establish ownership: an inherited
environment variable, a process name on its own, the active tab, or the focused
pane. This module is that rule and nothing else. It opens no socket, spawns no
process, and reads nothing but the one `/proc` seam it is handed.

**The division of labour with a probe is the whole design.** A
:class:`TerminalProbe` ENUMERATES: it turns environment hints into candidate
endpoints and asks one live instance which panes it holds and what runs in them.
It is never asked to decide ownership, because the evidence that decides it — the
invoking process's own ancestry — is not a fact about any terminal. So a probe
cannot accidentally admit a pane by looking at a label, a title or a focus flag:
those fields never reach this module.

**Environment selectors locate; ancestry proves.** `HERDR_PANE_ID`, `TMUX_PANE`
and their siblings survive `exec`, survive reparenting to init, and survive the
terminal that set them, so they are useful only for finding an endpoint worth
probing. The research measurement behind that
(`plan/herdr-overseer/research/002-herdr-api-evidence.md`) is a Codex tool
subprocess carrying `HERDR_PANE_ID=w1:p1` while its conversation was displayed in
`w1:p5`, detached from both through a managed app-server reparented to pid 1. Such
a process reaches this module with a two-element chain and is REFUSED, however
confidently its environment reads.

**Ownership is a CONJUNCTION, and each half closes a different hole.** A claim
survives only when a pane process the instance reports is in the chain AND the
instance's own server process is in the chain, strictly FURTHER OUT than that pane
process. The pane half is what binds the exact pane; without it any pane on a
server we happen to sit under would do. The server half is what binds the exact
instance; without it a pane id that merely repeats across two servers — measured:
`w1:p1` exists on both the default and a named herdr instance — could be matched
on the wrong one. The ORDERING is what rejects a self-contradictory answer: a
server cannot be nearer to us than the pane it is hosting.

**`distance` is the pane process's index in that chain, and it is the only
ordering input.** Nesting is therefore answered structurally rather than by
preferring a backend: whichever instance's pane holds the ancestor NEAREST the
invoking process is the owner, so herdr-inside-tmux selects herdr and
tmux-inside-herdr selects tmux with no rule naming either.

**A tie is a refusal, not a tiebreak.** Two distinct verified owners at the same
distance mean the evidence contradicts itself, and the constraint forbids a guess.
Claims for the same backend, live server generation and pane are deduplicated
first, because an ambient client route and an explicit socket can reach the same
owner.  The explicit socket wins only as the retained coordinate for later calls;
it is not additional ownership evidence.  A different generation or pane remains
a distinct owner and therefore still refuses on an equal-distance tie.

**A probe failure NEVER becomes a selection.** Its diagnostic rides along on
`probe_errors` whether or not another instance verified, so an unreachable backend
stays visible to the caller; what it must not do is let the reachable backend stand
in for it, which is the silent fallback the constraint forbids.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

from _seams import PidToOptionalInt

__all__: list[str] = [
    "MAX_ANCESTRY_HOPS",
    "AncestryReading",
    "ClaimReading",
    "OwnedPane",
    "OwnerSelection",
    "OwnershipClaim",
    "TerminalProbe",
    "ancestry_chain",
    "select_owner",
]

# The walk is bounded for the same reason every other loop here is: a `/proc`
# reader that answers plausibly but endlessly must not hold the caller. Sixty-four
# hops is far past any real agent-under-shell-under-terminal depth, so exceeding it
# means the ancestry is not describable rather than merely deep.
MAX_ANCESTRY_HOPS = 64

# Pid 1 is init and pid 0 is the kernel's placeholder for "no parent". Neither is a
# terminal and neither has a readable terminal ancestry, so both END the walk
# rather than continuing into it.
_ROOT_PARENT_CEILING = 1

_NO_OWNER = (
    "no verified owning terminal in this process's ancestry: no probed instance "
    "reported a pane whose process and server are both ancestors of this process"
)


@dataclass(frozen=True, kw_only=True)
class AncestryReading:
    """The invoking process's bounded ancestry, or why it could not be walked.

    `chain` is ordered NEAREST FIRST and is empty on every refusal rather than
    carrying a partial walk, so a caller cannot mistake the prefix it managed to
    read for the whole ancestry — a partial chain would under-report distance and
    could select an outer terminal as the nearest one.
    """

    chain: tuple[int, ...]
    error: str


@dataclass(frozen=True, kw_only=True)
class OwnedPane:
    """One pane a probed terminal instance holds — a candidate, not yet a claim.

    `pane_process_pids` is every process the instance reports FOR THAT PANE: a
    herdr reading supplies the pane's retained shell and its foreground group
    leader, a tmux reading supplies the pane's root process. More than one is
    offered because the instance cannot know which of them this caller descends
    from; selecting among them is this module's job.
    """

    backend: str
    socket_path: str
    server_pid: int
    server_starttime: str
    pane_id: str
    pane_process_pids: tuple[int, ...]


@dataclass(frozen=True, kw_only=True)
class ClaimReading:
    """One terminal instance's enumeration, or a named refusal and no panes.

    The pairing matters for the same reason it does on a pane capture: an instance
    holding no panes and an instance that could not be read both produce an empty
    tuple, and only the first is an answer.
    """

    panes: tuple[OwnedPane, ...]
    error: str


@dataclass(frozen=True, kw_only=True)
class OwnershipClaim:
    """One pane on one live instance, positively bound to the invoking ancestry.

    `server_pid` plus `server_starttime` ARE the instance generation: the pid alone
    is reused after a restart, and the research measurement is that a restart may
    reuse the socket path and the pane ids too.
    """

    backend: str
    socket_path: str
    server_pid: int
    server_starttime: str
    pane_id: str
    pane_process_pid: int
    distance: int


@dataclass(frozen=True, kw_only=True)
class OwnerSelection:
    """The selected owner, or a refusal naming the missing or conflicting evidence.

    `probe_errors` is populated on SUCCESS as well as failure. An instance that
    could not be read is a fact the caller should surface even when another one
    verified, and suppressing it on success is how an unreachable backend becomes
    invisible.
    """

    ok: bool
    claim: OwnershipClaim | None
    error: str
    probe_errors: tuple[str, ...]


class TerminalProbe(Protocol):
    """One backend's endpoint discovery plus its pane enumeration.

    `endpoints` is handed the environment because that is the ONLY thing
    environment selectors are good for here; it returns socket paths to probe, in
    the backend's own spelling, and makes no claim that any of them owns anything.
    """

    backend: str

    def endpoints(self, *, environ: Mapping[str, str]) -> tuple[str, ...]: ...

    def owned_panes(self, *, endpoint: str) -> ClaimReading: ...


def ancestry_chain(
    *,
    pid: int,
    ppid_of: PidToOptionalInt,
    max_hops: int = MAX_ANCESTRY_HOPS,
) -> AncestryReading:
    """`pid`'s ancestry, nearest first, bounded and cycle-checked.

    Three distinct refusals, kept distinct because they call for different
    remedies: a REVISITED pid means the readings contradict each other, an
    unreadable parent means `/proc` stopped answering mid-walk (the process may
    have exited under us), and exhausting the bound means the chain is not
    describable. None of the three is reported as "no terminal found", because an
    ancestry that could not be read is not evidence of absence.
    """
    chain: list[int] = []
    seen: set[int] = set()
    current = pid
    for _ in range(max_hops):
        if current in seen:
            return AncestryReading(
                chain=(), error=f"process ancestry is cyclic: pid {current} is revisited"
            )
        seen.add(current)
        chain.append(current)
        parent = ppid_of(pid=current)
        if parent is None:
            return AncestryReading(
                chain=(), error=f"process ancestry is unreadable at pid {current}"
            )
        if parent <= _ROOT_PARENT_CEILING:
            return AncestryReading(chain=tuple(chain), error="")
        current = parent
    return AncestryReading(
        chain=(),
        error=f"process ancestry is longer than the bounded walk of {max_hops} hops",
    )


def _claim_for(*, pane: OwnedPane, index_of: Mapping[int, int]) -> OwnershipClaim | None:
    """`pane`'s ownership claim over this ancestry, or None when it has none.

    Private, and returning None deliberately: "this pane does not own us" is an
    ANSWER about the pane rather than a failure to obtain one, and the caller's
    whole job is to collect the panes that do.
    """
    server_index = index_of.get(pane.server_pid)
    if server_index is None:
        return None
    nearer = [
        index_of[process]
        for process in pane.pane_process_pids
        if process in index_of and index_of[process] < server_index
    ]
    if not nearer:
        return None
    distance = min(nearer)
    return OwnershipClaim(
        backend=pane.backend,
        socket_path=pane.socket_path,
        server_pid=pane.server_pid,
        server_starttime=pane.server_starttime,
        pane_id=pane.pane_id,
        pane_process_pid=next(
            process for process in pane.pane_process_pids if index_of.get(process) == distance
        ),
        distance=distance,
    )


def _gathered(
    *,
    environ: Mapping[str, str],
    probes: Sequence[TerminalProbe],
    index_of: Mapping[int, int],
) -> tuple[list[OwnershipClaim], list[str]]:
    """Every distinct verified owner across all endpoints, plus each read failure.

    Socket spelling is a route to an owner rather than part of its identity.  When
    both the ambient tmux route and its explicit named socket prove the same live
    generation and pane, retain the explicit coordinate so dependent actions stay
    bound even after they leave the probing call.
    """
    claims: dict[tuple[str, int, str, str], OwnershipClaim] = {}
    errors: list[str] = []
    for probe in probes:
        for endpoint in probe.endpoints(environ=environ):
            reading = probe.owned_panes(endpoint=endpoint)
            if reading.error:
                errors.append(f"{probe.backend}: {reading.error}")
                continue
            for pane in reading.panes:
                claim = _claim_for(pane=pane, index_of=index_of)
                if claim is not None:
                    identity = (
                        claim.backend,
                        claim.server_pid,
                        claim.server_starttime,
                        claim.pane_id,
                    )
                    retained = claims.get(identity)
                    if retained is None or (not retained.socket_path and claim.socket_path):
                        claims[identity] = claim
    return list(claims.values()), errors


def _ambiguity(*, contenders: set[OwnershipClaim]) -> str:
    """The refusal naming every owner that tied, in a stable order."""
    named = ", ".join(
        sorted(f"{claim.backend} {claim.socket_path} pane {claim.pane_id}" for claim in contenders)
    )
    return (
        f"terminal ownership is ambiguous: {len(contenders)} distinct verified owners "
        f"are equally near this process ({named})"
    )


def select_owner(
    *,
    pid: int,
    environ: Mapping[str, str],
    probes: Sequence[TerminalProbe],
    ppid_of: PidToOptionalInt,
    max_hops: int = MAX_ANCESTRY_HOPS,
) -> OwnerSelection:
    """The nearest positively verified owning terminal instance and pane, or why not.

    Nothing here mutates anything, and that is a precondition rather than a
    property: a caller is expected to run this BEFORE any terminal mutation, so
    that an absent, stale, detached, cyclic or ambiguous answer costs nothing to
    act on.
    """
    reading = ancestry_chain(pid=pid, ppid_of=ppid_of, max_hops=max_hops)
    if reading.error:
        return OwnerSelection(ok=False, claim=None, error=reading.error, probe_errors=())
    index_of = {process: index for index, process in enumerate(reading.chain)}
    claims, errors = _gathered(environ=environ, probes=probes, index_of=index_of)
    if not claims:
        return OwnerSelection(ok=False, claim=None, error=_NO_OWNER, probe_errors=tuple(errors))
    nearest = min(claim.distance for claim in claims)
    contenders = {claim for claim in claims if claim.distance == nearest}
    if len(contenders) != 1:
        return OwnerSelection(
            ok=False,
            claim=None,
            error=_ambiguity(contenders=contenders),
            probe_errors=tuple(errors),
        )
    return OwnerSelection(
        ok=True, claim=next(iter(contenders)), error="", probe_errors=tuple(errors)
    )
