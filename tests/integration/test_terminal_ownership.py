"""Which terminal instance and pane PROVABLY owns the invoking process.

`SPECIFICATION/constraints.md` states the rule this file grades: backend selection
follows the NEAREST positively verified owning terminal in the invoking process's
ancestry, that ancestry must be bound to the exact live backend instance and pane,
and an inherited environment variable, a process name, an active tab or a focused
pane MUST NOT establish ownership. Absent, ambiguous or unreadable ownership
refuses and names the missing evidence rather than guessing or falling back to the
other backend.

The scenarios behind it are `## Scenario: The nearest verified terminal owns the
two-pane overseer` and `## Scenario: Stale environment cannot choose an overseer
pane`.

**Every case here is driven through fake probes, and that is the point rather than
a shortcut.** A probe's job is to ENUMERATE what one terminal instance holds; the
ownership RULE is what this module owns, and the rule has to be gradeable against
ancestries no live host can be asked to produce on demand — a cycle, a procfs read
that fails mid-walk, two servers answering with the same pane id, and a process
reparented to init while its environment still names the pane it came from. The
native counterparts, where a real herdr server enumerates real panes, live in
`tests/test_terminal_probes.py` and `tests/test_bootstrap_live_herdr.py`.
"""

from __future__ import annotations

from dataclasses import dataclass

from overseer import terminal_ownership

__all__: list[str] = []

# One nested ancestry, written once and read by most cases below. The invoking
# process (100) sits under a herdr pane shell (200) whose server is 300, and that
# server sits inside a tmux pane (shell 400) whose server is 500. This is the
# `herdr nested in tmux` shape; reversing which server owns which pane gives the
# `tmux nested in herdr` shape without changing the chain.
NESTED_PARENTS = {100: 200, 200: 300, 300: 400, 400: 500, 500: 1}

HERDR_SOCKET = "/run/user/1000/herdr-inner.sock"
TMUX_SOCKET = "/tmp/tmux-1000/default"


@dataclass(frozen=True, kw_only=True)
class FakeProbe:
    """One terminal backend's enumeration, scripted per endpoint."""

    backend: str
    panes_by_endpoint: dict[str, tuple[terminal_ownership.OwnedPane, ...]]
    errors_by_endpoint: dict[str, str]

    def endpoints(self, *, environ: dict[str, str]) -> tuple[str, ...]:
        del environ
        return tuple(self.panes_by_endpoint) + tuple(self.errors_by_endpoint)

    def owned_panes(self, *, endpoint: str) -> terminal_ownership.ClaimReading:
        error = self.errors_by_endpoint.get(endpoint, "")
        if error:
            return terminal_ownership.ClaimReading(panes=(), error=error)
        return terminal_ownership.ClaimReading(
            panes=self.panes_by_endpoint.get(endpoint, ()), error=""
        )


def _pane(
    *,
    backend: str,
    socket_path: str,
    server_pid: int,
    pane_id: str,
    pane_process_pids: tuple[int, ...],
    server_starttime: str = "gen-1",
) -> terminal_ownership.OwnedPane:
    return terminal_ownership.OwnedPane(
        backend=backend,
        socket_path=socket_path,
        server_pid=server_pid,
        server_starttime=server_starttime,
        pane_id=pane_id,
        pane_process_pids=pane_process_pids,
    )


def _probe(
    *,
    backend: str,
    panes: tuple[terminal_ownership.OwnedPane, ...] = (),
    endpoint: str = "endpoint",
    errors: dict[str, str] | None = None,
) -> FakeProbe:
    return FakeProbe(
        backend=backend,
        panes_by_endpoint={endpoint: panes},
        errors_by_endpoint={} if errors is None else errors,
    )


def _ppid_reader(*, parents: dict[int, int | None]):
    def read(*, pid: int) -> int | None:
        return parents.get(pid, 1)

    return read


def _select(
    *,
    probes: tuple[FakeProbe, ...],
    parents: dict[int, int | None] | None = None,
    environ: dict[str, str] | None = None,
    pid: int = 100,
    max_hops: int = terminal_ownership.MAX_ANCESTRY_HOPS,
) -> terminal_ownership.OwnerSelection:
    return terminal_ownership.select_owner(
        pid=pid,
        environ={} if environ is None else environ,
        probes=probes,
        ppid_of=_ppid_reader(parents=NESTED_PARENTS if parents is None else parents),
        max_hops=max_hops,
    )


def _herdr_inner_pane() -> terminal_ownership.OwnedPane:
    """The herdr pane the invoking process actually sits in."""
    return _pane(
        backend="herdr",
        socket_path=HERDR_SOCKET,
        server_pid=300,
        pane_id="w1:p5",
        pane_process_pids=(200, 100),
    )


def _tmux_outer_pane() -> terminal_ownership.OwnedPane:
    """The tmux pane that hosts the whole herdr server, one hop further out."""
    return _pane(
        backend="tmux",
        socket_path=TMUX_SOCKET,
        server_pid=500,
        pane_id="%7",
        pane_process_pids=(400,),
    )


def _unrelated_pane(*, backend: str, socket_path: str) -> terminal_ownership.OwnedPane:
    """A pane on a live instance that holds nothing in this process's ancestry."""
    return _pane(
        backend=backend,
        socket_path=socket_path,
        server_pid=500,
        pane_id="%9",
        pane_process_pids=(6060,),
    )


def test_the_nearest_verified_owner_wins_when_both_backends_verify() -> None:
    """A herdr pane inside a tmux pane selects HERDR — the inner, nearer owner."""
    selection = _select(
        probes=(
            _probe(backend="tmux", panes=(_tmux_outer_pane(),)),
            _probe(backend="herdr", panes=(_herdr_inner_pane(),)),
        ),
        environ={"TMUX_PANE": "%7", "HERDR_PANE_ID": "w1:p5"},
    )

    assert selection.ok, selection.error
    assert selection.claim is not None
    assert selection.claim.backend == "herdr"
    assert selection.claim.pane_id == "w1:p5"
    assert selection.claim.socket_path == HERDR_SOCKET
    assert selection.claim.server_pid == 300
    assert selection.claim.server_starttime == "gen-1"
    # The pane process nearest the invoking process, not merely one of the two
    # the probe offered: the distance is what ordered this selection.
    assert selection.claim.pane_process_pid == 100
    assert selection.claim.distance == 0


def test_the_nearest_verified_owner_wins_with_the_nesting_reversed() -> None:
    """The same chain with tmux innermost selects TMUX — order of probes is irrelevant."""
    inner_tmux = _pane(
        backend="tmux",
        socket_path=TMUX_SOCKET,
        server_pid=300,
        pane_id="%2",
        pane_process_pids=(200,),
    )
    outer_herdr = _pane(
        backend="herdr",
        socket_path=HERDR_SOCKET,
        server_pid=500,
        pane_id="w1:p1",
        pane_process_pids=(400,),
    )

    selection = _select(
        probes=(
            _probe(backend="herdr", panes=(outer_herdr,)),
            _probe(backend="tmux", panes=(inner_tmux,)),
        ),
        environ={"HERDR_PANE_ID": "w1:p1"},
    )

    assert selection.ok, selection.error
    assert selection.claim is not None
    assert selection.claim.backend == "tmux"
    assert selection.claim.pane_id == "%2"
    assert selection.claim.distance == 1


def test_a_stale_environment_selector_cannot_establish_ownership() -> None:
    """An inherited pane id whose pane holds no ancestor of ours owns nothing."""
    stale = _pane(
        backend="herdr",
        socket_path=HERDR_SOCKET,
        server_pid=300,
        pane_id="w1:p1",
        pane_process_pids=(9001,),
    )

    selection = _select(
        probes=(_probe(backend="herdr", panes=(stale,)),),
        environ={"HERDR_ENV": "1", "HERDR_PANE_ID": "w1:p1"},
    )

    assert not selection.ok
    assert selection.claim is None
    assert "no verified owning terminal" in selection.error


def test_a_focused_pane_is_not_ownership_evidence() -> None:
    """A probe may say which pane is focused; it still owns nothing without ancestry."""
    focused_elsewhere = _pane(
        backend="herdr",
        socket_path=HERDR_SOCKET,
        server_pid=300,
        pane_id="w1:p9",
        pane_process_pids=(4242,),
    )

    selection = _select(
        probes=(_probe(backend="herdr", panes=(focused_elsewhere,)),),
        environ={"HERDR_PANE_ID": "w1:p9"},
    )

    assert not selection.ok
    assert "no verified owning terminal" in selection.error


def test_a_detached_process_owns_no_terminal_however_its_environment_reads() -> None:
    """A Codex app-server reparented to init has no terminal in its ancestry."""
    selection = _select(
        probes=(_probe(backend="herdr", panes=(_herdr_inner_pane(),)),),
        parents={100: 1},
        environ={"HERDR_PANE_ID": "w1:p5", "HERDR_SOCKET_PATH": HERDR_SOCKET},
    )

    assert not selection.ok
    assert "no verified owning terminal" in selection.error


def test_a_pane_whose_server_is_not_an_ancestor_is_not_an_owner() -> None:
    """Ownership binds the pane AND the instance; a foreign server cannot claim us."""
    foreign_server = _pane(
        backend="herdr",
        socket_path=HERDR_SOCKET,
        server_pid=7777,
        pane_id="w1:p5",
        pane_process_pids=(200,),
    )

    selection = _select(probes=(_probe(backend="herdr", panes=(foreign_server,)),))

    assert not selection.ok
    assert "no verified owning terminal" in selection.error


def test_a_server_nearer_than_its_own_claimed_pane_process_is_not_an_owner() -> None:
    """A pane process further out than its server contradicts itself and is refused."""
    inverted = _pane(
        backend="herdr",
        socket_path=HERDR_SOCKET,
        server_pid=200,
        pane_id="w1:p5",
        pane_process_pids=(400,),
    )

    selection = _select(probes=(_probe(backend="herdr", panes=(inverted,)),))

    assert not selection.ok
    assert "no verified owning terminal" in selection.error


def test_two_servers_sharing_a_pane_id_resolve_to_the_one_holding_our_ancestor() -> None:
    """Opaque pane ids repeat across instances; the chain is what disambiguates."""
    namesake = _pane(
        backend="herdr",
        socket_path="/run/user/1000/herdr-other.sock",
        server_pid=8888,
        pane_id="w1:p5",
        pane_process_pids=(5555,),
        server_starttime="gen-9",
    )
    probe = FakeProbe(
        backend="herdr",
        panes_by_endpoint={
            HERDR_SOCKET: (_herdr_inner_pane(),),
            "/run/user/1000/herdr-other.sock": (namesake,),
        },
        errors_by_endpoint={},
    )

    selection = _select(probes=(probe,))

    assert selection.ok, selection.error
    assert selection.claim is not None
    assert selection.claim.socket_path == HERDR_SOCKET
    assert selection.claim.server_pid == 300


def test_two_distinct_verified_owners_at_the_same_distance_are_ambiguous() -> None:
    """Contradictory evidence refuses; it never picks a side."""
    one = _pane(
        backend="herdr",
        socket_path=HERDR_SOCKET,
        server_pid=300,
        pane_id="w1:p5",
        pane_process_pids=(200,),
    )
    other = _pane(
        backend="herdr",
        socket_path=HERDR_SOCKET,
        server_pid=300,
        pane_id="w1:p6",
        pane_process_pids=(200,),
    )

    selection = _select(probes=(_probe(backend="herdr", panes=(one, other)),))

    assert not selection.ok
    assert selection.claim is None
    assert "ambiguous" in selection.error
    assert "w1:p5" in selection.error
    assert "w1:p6" in selection.error


def test_an_identical_claim_reached_through_two_endpoints_is_not_ambiguous() -> None:
    """The same instance named twice is one owner, not two."""
    probe = FakeProbe(
        backend="herdr",
        panes_by_endpoint={
            HERDR_SOCKET: (_herdr_inner_pane(),),
            "duplicate": (_herdr_inner_pane(),),
        },
        errors_by_endpoint={},
    )

    selection = _select(probes=(probe,))

    assert selection.ok, selection.error
    assert selection.claim is not None
    assert selection.claim.pane_id == "w1:p5"


def test_a_cyclic_ancestry_refuses_and_names_the_revisited_process() -> None:
    selection = _select(
        probes=(_probe(backend="herdr", panes=(_herdr_inner_pane(),)),),
        parents={100: 200, 200: 100},
    )

    assert not selection.ok
    assert selection.claim is None
    assert "cyclic" in selection.error
    assert "100" in selection.error


def test_an_unreadable_ancestry_refuses_and_names_where_the_walk_stopped() -> None:
    selection = _select(
        probes=(_probe(backend="herdr", panes=(_herdr_inner_pane(),)),),
        parents={100: 200, 200: None},
    )

    assert not selection.ok
    assert "unreadable" in selection.error
    assert "200" in selection.error


def test_an_ancestry_longer_than_the_bound_refuses_rather_than_walking_on() -> None:
    selection = _select(
        probes=(_probe(backend="herdr", panes=(_herdr_inner_pane(),)),),
        max_hops=2,
    )

    assert not selection.ok
    assert "bounded" in selection.error
    assert "2" in selection.error


def test_an_unreadable_backend_is_never_resolved_by_the_other_one() -> None:
    """A probe failure beside a non-owning instance refuses, naming both facts.

    This is the no-silent-fallback rule in its load-bearing direction: the tmux
    instance here is perfectly readable and simply does not own us, so the only
    way a selection could succeed is by treating the unreadable herdr instance as
    settled — which is precisely what must not happen.
    """
    selection = _select(
        probes=(
            _probe(backend="herdr", errors={HERDR_SOCKET: "socket is unreachable"}),
            _probe(
                backend="tmux",
                panes=(_unrelated_pane(backend="tmux", socket_path=TMUX_SOCKET),),
            ),
        ),
    )

    assert not selection.ok
    assert selection.claim is None
    assert "no verified owning terminal" in selection.error
    assert selection.probe_errors == ("herdr: socket is unreachable",)


def test_a_probe_failure_beside_a_verified_owner_rides_along_on_the_selection() -> None:
    """The unreadable instance stays visible even when another one does verify."""
    selection = _select(
        probes=(
            _probe(backend="tmux", errors={TMUX_SOCKET: "server not running"}),
            _probe(backend="herdr", panes=(_herdr_inner_pane(),)),
        ),
    )

    assert selection.ok, selection.error
    assert selection.probe_errors == ("tmux: server not running",)


def test_the_ancestry_chain_is_ordered_from_the_invoking_process_outward() -> None:
    reading = terminal_ownership.ancestry_chain(
        pid=100, ppid_of=_ppid_reader(parents=NESTED_PARENTS)
    )

    assert reading.error == ""
    assert reading.chain == (100, 200, 300, 400, 500)


def test_the_ancestry_chain_stops_at_the_init_process_without_including_it() -> None:
    reading = terminal_ownership.ancestry_chain(
        pid=100, ppid_of=_ppid_reader(parents={100: 200, 200: 0})
    )

    assert reading.error == ""
    assert reading.chain == (100, 200)
