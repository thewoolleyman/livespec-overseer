"""Beside-tests for `_codex_proc.carrier_rollout_ids` — the helper-process walk.

These re-home coverage the foreman-test deletion took with it. Codex 0.150 runs a
session's persistence in a helper process the TUI spawns, so the identity carrier may
hold no rollout fd of its own; the walk descends from the carrier to find one while
keeping the identity with the carrier. Two things bound that descent, and both are
tested here because getting either wrong is a live defect rather than a tidiness
issue: a pid already visited is not re-read (so a cyclic or diamond-shaped process
tree still terminates inside one tick), and another live carrier is not descended into
at all (so a `codex resume` launched from a peer session's shell tool cannot have its
rollout attributed to that peer, naming the peer's track after someone else's topic).

The walk is written to a NEW module rather than appended to
`test_codex_sessions_mapping.py`, which sits at 221 LLOC against the 250 ceiling.

``import _codex_proc`` resolves via conftest.py.
"""

from __future__ import annotations

import _codex_proc
from test_codex_sessions_fakes import ID_A, ID_B, fake_rollout

__all__: list[str] = []

_CARRIER = 10
_HELPER = 20
_GRANDCHILD = 30
_PEER_CARRIER = 40


def _readers(*, fds: dict[int, list[str]], children: dict[int, list[int]]):
    return (
        lambda *, pid: list(fds.get(pid, [])),
        lambda *, pid: list(children.get(pid, [])),
    )


def test_the_carriers_own_rollout_comes_before_a_helpers():
    """An established session still holding its own rollout is answered as before."""
    fd_targets_of, children_of = _readers(
        fds={_CARRIER: [fake_rollout(session_id=ID_A)], _HELPER: [fake_rollout(session_id=ID_B)]},
        children={_CARRIER: [_HELPER]},
    )

    ids = _codex_proc.carrier_rollout_ids(
        pid=_CARRIER, fd_targets_of=fd_targets_of, children_of=children_of
    )

    assert ids == [ID_A, ID_B]


def test_a_fresh_session_is_found_through_the_helper_that_holds_its_rollout():
    fd_targets_of, children_of = _readers(
        fds={_HELPER: [fake_rollout(session_id=ID_A)]},
        children={_CARRIER: [_HELPER]},
    )

    ids = _codex_proc.carrier_rollout_ids(
        pid=_CARRIER, fd_targets_of=fd_targets_of, children_of=children_of
    )

    assert ids == [ID_A]


def test_a_pid_reachable_by_two_paths_contributes_its_rollout_once():
    """A diamond: the carrier and its helper both name the same grandchild."""
    fd_targets_of, children_of = _readers(
        fds={_GRANDCHILD: [fake_rollout(session_id=ID_A)]},
        children={_CARRIER: [_HELPER, _GRANDCHILD], _HELPER: [_GRANDCHILD]},
    )

    ids = _codex_proc.carrier_rollout_ids(
        pid=_CARRIER, fd_targets_of=fd_targets_of, children_of=children_of
    )

    assert ids == [ID_A]


def test_a_cyclic_process_tree_terminates_without_re_reading_a_visited_pid():
    """The helper claims the carrier as its own child, so the walk must not loop."""
    reads: list[int] = []
    children = {_CARRIER: [_HELPER], _HELPER: [_CARRIER, _HELPER]}

    def fd_targets_of(*, pid: int) -> list[str]:
        reads.append(pid)
        return [fake_rollout(session_id=ID_A)] if pid == _HELPER else []

    ids = _codex_proc.carrier_rollout_ids(
        pid=_CARRIER,
        fd_targets_of=fd_targets_of,
        children_of=lambda *, pid: list(children.get(pid, [])),
    )

    assert ids == [ID_A]
    assert reads == [_CARRIER, _HELPER]


def test_another_live_carrier_is_not_descended_into_so_its_rollout_stays_its_own():
    """A `codex resume` under a peer session's shell tool keeps its own identity."""
    fd_targets_of, children_of = _readers(
        fds={
            _PEER_CARRIER: [fake_rollout(session_id=ID_B)],
            _GRANDCHILD: [fake_rollout(session_id=ID_B)],
        },
        children={_CARRIER: [_PEER_CARRIER], _PEER_CARRIER: [_GRANDCHILD]},
    )

    ids = _codex_proc.carrier_rollout_ids(
        pid=_CARRIER,
        carrier_pids=frozenset({_PEER_CARRIER}),
        fd_targets_of=fd_targets_of,
        children_of=children_of,
    )

    assert ids == []


def test_the_walk_is_bounded_by_max_nodes_on_a_wide_tree():
    fd_targets_of, children_of = _readers(
        fds={pid: [fake_rollout(session_id=ID_A)] for pid in range(100, 110)},
        children={_CARRIER: list(range(100, 110))},
    )

    ids = _codex_proc.carrier_rollout_ids(
        pid=_CARRIER, fd_targets_of=fd_targets_of, children_of=children_of, max_nodes=3
    )

    assert ids == [ID_A, ID_A, ID_A]
