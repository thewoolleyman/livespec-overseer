"""The two-pane bootstrap's ORDER of operations, and what it refuses to do.

`SPECIFICATION/contracts.md` states the bootstrap preconditions: it refuses,
before mutating any window, when ownership of its tmux or herdr pane cannot be
verified, naming the missing precondition; it splits ONLY that verified invoking
window or tab; and it is IDEMPOTENT — a verified daemon pane already present in
that layout is reused, not duplicated. `SPECIFICATION/constraints.md` adds that a
selected backend whose required capabilities are unavailable must fail closed
BEFORE the dependent action, naming the failed capability, and must not fall back
to the other backend.

The scenarios behind those are `## Scenario: The nearest verified terminal owns
the two-pane overseer`, `## Scenario: Stale environment cannot choose an overseer
pane` and `## Scenario: A replacement prerequisite failure preserves every live
session`.

**The backend double RECORDS every call, and the recording is the assertion.**
Each case below grades a sequence rather than a return value: that no capability
probe, no layout read and no split happened at all when ownership did not verify;
that the capability refusal preceded the layout read; that a repeat performed zero
splits. A test asserting only on the returned error would pass just as happily
against an implementation that split first and reported the refusal afterwards.

**Nothing here can clean up, and that is structural rather than asserted.** The
backend interface this module drives carries no close, kill or terminate
operation, so an unresolved acknowledgement has no destructive remedy available to
it — which is exactly the requirement: a lost acknowledgement after a split or a
daemon launch must leave the possibly-live process alone and demand fresh
evidence instead. The native half of that, driven against a real herdr server
whose reply is withheld after the real effect landed, is in
`tests/test_bootstrap_live_herdr.py`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from overseer import bootstrap, terminal_ownership

__all__: list[str] = []

CORE_ROOT = "/data/projects/livespec-overseer"
DAEMON_COMMAND = "overseerd 2>> /tmp/overseer/daemon.log"
HERDR_SOCKET = "/run/user/1000/herdr.sock"
TMUX_SOCKET = ""

# Invoking process 100 under a herdr pane shell 200 whose server is 300; that
# server runs inside a tmux pane (shell 400) on a tmux server 500.
NESTED_PARENTS = {100: 200, 200: 300, 300: 400, 400: 500, 500: 1}


@dataclass(frozen=True, kw_only=True)
class StaticProbe:
    """One backend's enumeration, fixed."""

    backend: str
    panes: tuple[terminal_ownership.OwnedPane, ...]
    error: str = ""

    def endpoints(self, *, environ: dict[str, str]) -> tuple[str, ...]:
        del environ
        return ("endpoint",)

    def owned_panes(self, *, endpoint: str) -> terminal_ownership.ClaimReading:
        del endpoint
        if self.error:
            return terminal_ownership.ClaimReading(panes=(), error=self.error)
        return terminal_ownership.ClaimReading(panes=self.panes, error="")


@dataclass(kw_only=True)
class RecordingBackend:
    """A bootstrap backend that records every call it is asked to make."""

    backend: str
    capability: str = ""
    host_pane_id: str = ""
    host_unresolved: str = ""
    host_error: str = ""
    placement: bootstrap.PlacementOutcome | None = None
    calls: list[tuple[str, Any]] = field(default_factory=list)

    def capability_error(self, *, claim: terminal_ownership.OwnershipClaim) -> str:
        self.calls.append(("capability_error", claim.pane_id))
        return self.capability

    def daemon_host(
        self, *, claim: terminal_ownership.OwnershipClaim
    ) -> bootstrap.DaemonHostReading:
        self.calls.append(("daemon_host", claim.pane_id))
        return bootstrap.DaemonHostReading(
            pane_id=self.host_pane_id, unresolved=self.host_unresolved, error=self.host_error
        )

    def place_daemon_above(
        self, *, claim: terminal_ownership.OwnershipClaim, cwd: str, command: str
    ) -> bootstrap.PlacementOutcome:
        self.calls.append(("place_daemon_above", (claim.pane_id, cwd, command)))
        if self.placement is not None:
            return self.placement
        return bootstrap.PlacementOutcome(ok=True, pane_id="w1:p9", error="", effect_unknown=False)

    def verbs(self) -> list[str]:
        return [verb for verb, _ in self.calls]


def _ppid_reader(*, parents: dict[int, int | None]):
    def read(*, pid: int) -> int | None:
        return parents.get(pid, 1)

    return read


def _herdr_pane() -> terminal_ownership.OwnedPane:
    return terminal_ownership.OwnedPane(
        backend="herdr",
        socket_path=HERDR_SOCKET,
        server_pid=300,
        server_starttime="gen-herdr",
        pane_id="w1:p5",
        pane_process_pids=(200,),
    )


def _tmux_pane() -> terminal_ownership.OwnedPane:
    return terminal_ownership.OwnedPane(
        backend="tmux",
        socket_path=TMUX_SOCKET,
        server_pid=500,
        server_starttime="gen-tmux",
        pane_id="%7",
        pane_process_pids=(400,),
    )


def _bootstrap(
    *,
    backends: dict[str, RecordingBackend],
    probes: tuple[StaticProbe, ...] | None = None,
    parents: dict[int, int | None] | None = None,
) -> bootstrap.BootstrapOutcome:
    return bootstrap.bootstrap_two_pane(
        caller=bootstrap.CallerEvidence(
            pid=100,
            environ={},
            probes=(
                (
                    StaticProbe(backend="tmux", panes=(_tmux_pane(),)),
                    StaticProbe(backend="herdr", panes=(_herdr_pane(),)),
                )
                if probes is None
                else probes
            ),
            ppid_of=_ppid_reader(parents=NESTED_PARENTS if parents is None else parents),
        ),
        backends=backends,
        cwd=CORE_ROOT,
        command=DAEMON_COMMAND,
    )


def _pair(
    *, herdr: RecordingBackend | None = None, tmux: RecordingBackend | None = None
) -> dict[str, RecordingBackend]:
    return {
        "herdr": RecordingBackend(backend="herdr") if herdr is None else herdr,
        "tmux": RecordingBackend(backend="tmux") if tmux is None else tmux,
    }


def test_a_verified_owner_gets_one_daemon_pane_above_its_own_invoking_pane() -> None:
    """The nearest verified owner's pane is the one split, with the daemon command."""
    backends = _pair()

    outcome = _bootstrap(backends=backends)

    assert outcome.ok, outcome.error
    assert outcome.backend == "herdr"
    assert outcome.created is True
    assert outcome.reused is False
    assert outcome.pane_id == "w1:p9"
    assert backends["herdr"].calls == [
        ("capability_error", "w1:p5"),
        ("daemon_host", "w1:p5"),
        ("place_daemon_above", ("w1:p5", CORE_ROOT, DAEMON_COMMAND)),
    ]
    # The outer tmux instance is never touched: the invoking tab is the only one
    # the bootstrap may mutate.
    assert backends["tmux"].calls == []


def test_a_repeat_reuses_the_verified_daemon_pane_and_splits_nothing() -> None:
    """Idempotence, asserted on the absence of a second split rather than on a flag."""
    backends = _pair(herdr=RecordingBackend(backend="herdr", host_pane_id="w1:p9"))

    outcome = _bootstrap(backends=backends)

    assert outcome.ok, outcome.error
    assert outcome.reused is True
    assert outcome.created is False
    assert outcome.pane_id == "w1:p9"
    assert "place_daemon_above" not in backends["herdr"].verbs()


def test_unverified_ownership_refuses_before_any_capability_probe_or_split() -> None:
    """Nothing is asked of any backend at all, so nothing can be split or written."""
    backends = _pair()

    outcome = _bootstrap(backends=backends, parents={100: 1})

    assert not outcome.ok
    assert outcome.backend == ""
    assert outcome.pane_id == ""
    assert outcome.effect_unknown is False
    assert "no verified owning terminal" in outcome.error
    assert backends["herdr"].calls == []
    assert backends["tmux"].calls == []


def test_an_unreadable_instance_is_reported_on_the_refusal() -> None:
    """The probe diagnostic survives onto the outcome, so the operator sees it."""
    backends = _pair()

    outcome = _bootstrap(
        backends=backends,
        probes=(StaticProbe(backend="herdr", panes=(), error="socket is unreachable"),),
    )

    assert not outcome.ok
    assert outcome.probe_errors == ("herdr: socket is unreachable",)


def test_a_selected_backend_with_no_bootstrap_capability_never_reaches_the_other_one() -> None:
    """The missing capability is named; the reachable backend does not stand in."""
    backends = {"tmux": RecordingBackend(backend="tmux")}

    outcome = _bootstrap(backends=backends)

    assert not outcome.ok
    assert outcome.backend == "herdr"
    assert "herdr" in outcome.error
    assert "capability" in outcome.error
    assert outcome.effect_unknown is False
    assert backends["tmux"].calls == []


def test_a_missing_backend_capability_is_reported_before_its_dependent_action() -> None:
    """The layout is never read and nothing is split once a capability is missing."""
    backends = _pair(
        herdr=RecordingBackend(
            backend="herdr", capability="herdr pane.swap is unavailable on protocol 21"
        )
    )

    outcome = _bootstrap(backends=backends)

    assert not outcome.ok
    assert outcome.backend == "herdr"
    assert "pane.swap is unavailable" in outcome.error
    assert backends["herdr"].verbs() == ["capability_error"]
    assert backends["tmux"].calls == []


def test_an_unreadable_layout_refuses_without_splitting() -> None:
    backends = _pair(
        herdr=RecordingBackend(backend="herdr", host_error="pane listing is unreadable")
    )

    outcome = _bootstrap(backends=backends)

    assert not outcome.ok
    assert "pane listing is unreadable" in outcome.error
    assert outcome.effect_unknown is False
    assert backends["herdr"].verbs() == ["capability_error", "daemon_host"]


def test_an_unresolved_layout_refuses_rather_than_repeating_the_split() -> None:
    """The repeat-after-a-lost-acknowledgement path: re-observe, never re-mutate.

    A pane sits above the invoking pane that cannot be proven to host a live
    daemon. Splitting again would repeat a mutation whose outcome was never
    settled, so the bootstrap refuses and names what has to be established first.
    """
    backends = _pair(
        herdr=RecordingBackend(
            backend="herdr",
            host_unresolved=(
                "pane 'w1:p2' sits above 'w1:p5' holding a retained shell rather than a "
                "live daemon; fresh instance, pane and process evidence is required"
            ),
        )
    )

    outcome = _bootstrap(backends=backends)

    assert not outcome.ok
    assert outcome.reused is False
    assert outcome.created is False
    assert "fresh instance, pane and process evidence" in outcome.error
    assert "place_daemon_above" not in backends["herdr"].verbs()


def test_a_lost_acknowledgement_leaves_the_created_pane_named_and_unresolved() -> None:
    """A mutation whose answer was lost reports the pane it made and stays uncertain."""
    backends = _pair(
        herdr=RecordingBackend(
            backend="herdr",
            placement=bootstrap.PlacementOutcome(
                ok=False,
                pane_id="w1:p2",
                error="herdr request deadline expired before a complete reply arrived",
                effect_unknown=True,
            ),
        )
    )

    outcome = _bootstrap(backends=backends)

    assert not outcome.ok
    assert outcome.effect_unknown is True
    assert outcome.pane_id == "w1:p2"
    assert outcome.created is False
    assert "deadline expired" in outcome.error
    # Exactly one attempt. Repeating it would run the daemon command twice or put
    # the daemon pane back below the session it supervises.
    assert backends["herdr"].verbs().count("place_daemon_above") == 1


def test_a_refused_split_reports_a_known_failure_with_nothing_created() -> None:
    backends = _pair(
        herdr=RecordingBackend(
            backend="herdr",
            placement=bootstrap.PlacementOutcome(
                ok=False,
                pane_id="",
                error="herdr server does not own pane 'w1:p5'",
                effect_unknown=False,
            ),
        )
    )

    outcome = _bootstrap(backends=backends)

    assert not outcome.ok
    assert outcome.effect_unknown is False
    assert outcome.pane_id == ""
    assert "does not own pane" in outcome.error


def test_the_bootstrap_interface_offers_no_way_to_destroy_anything() -> None:
    """Failure cleanup cannot terminate a possibly-live process, by construction.

    The protocol is the whole vocabulary a bootstrap has over a terminal: three
    operations and one identifying attribute. If a close/kill/terminate operation
    ever appears on it, the structural guarantee above becomes an ordinary promise
    that has to be tested case by case.
    """
    operations = {name for name in dir(bootstrap.BootstrapBackend) if not name.startswith("_")}
    attributes = set(bootstrap.BootstrapBackend.__annotations__)

    assert operations == {"capability_error", "daemon_host", "place_daemon_above"}
    assert attributes == {"backend"}


def test_a_probe_failure_beside_a_verified_owner_rides_along_on_a_successful_bootstrap() -> None:
    backends = _pair()

    outcome = _bootstrap(
        backends=backends,
        probes=(
            StaticProbe(backend="tmux", panes=(), error="server not running"),
            StaticProbe(backend="herdr", panes=(_herdr_pane(),)),
        ),
    )

    assert outcome.ok, outcome.error
    assert outcome.probe_errors == ("tmux: server not running",)
