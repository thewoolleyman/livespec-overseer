"""Every candidate a late fresh-Codex reconciliation must REFUSE.

The recovery in ``test_codex_late_successor_reconciliation`` consumes a ``ready``
declaration — the cardinal rule's sole authorization for a restart — on the strength of
live discovery agreeing with what the daemon recorded launching. That is only safe if
the agreement is total, because a pane whose Codex identity changed OUT-OF-BAND presents
almost the same evidence: a hand-restarted session, an operator ``/rename``, or a
crash-recovered rollout all show a canonical, in-repo, different-rollout session under
this topic. Such a candidate proves a change happened; it does not prove the DAEMON made
it, and spending the declaration on a session the daemon never launched — and never
handed a resume line to — is exactly the failure the fail-closed arm exists to prevent.

So each row below breaks exactly ONE of the facts the record pins, leaving every other
fact intact, and asserts the same two things: the declaration is still the session's own
``ready`` and the round is still open. The last row is the discriminating one — a
perfectly well-formed successor that simply is not the one this restart named.
"""

from __future__ import annotations

import dataclasses

import pytest
import registry
import signals
from test_codex_late_successor_reconciliation import unadopted_fresh_restart
from test_supervisor_builders import FRESH_CODEX_SESSION_ID

__all__: list[str] = []

# A canonical rollout this daemon never launched — the out-of-band identity change.
STRANGER_SESSION_ID = "019f8c40-1111-7aaa-8bbb-2c3d4e5f6071"


@pytest.fixture(autouse=True)
def _isolate_cwd(*, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


def _rewrite_record(*, stranded, **changes) -> None:
    """Rewrite the restart's recorded provenance, modelling a daemon whose world moved."""
    recorded = registry.read_codex_fresh_restart(
        repo=str(stranded.repo), topic=stranded.topic, stamp_path=stranded.sup.stamp_path
    )
    registry.record_codex_fresh_restart(
        repo=str(stranded.repo),
        topic=stranded.topic,
        record=dataclasses.replace(recorded, **changes),
        stamp_path=stranded.sup.stamp_path,
    )


def _assert_untouched(*, stranded) -> None:
    assert stranded.state_token() == signals.STATE_READY
    assert stranded.round_record().at is not None
    assert "restarted (codex)" not in stranded.log.getvalue()
    assert "consumed ready declaration" not in stranded.log.getvalue()


def test_a_successor_that_is_not_discoverable_at_all_reconciles_nothing(*, tmp_path):
    """The state the restart itself gave up in: still no fd evidence, still nothing to do."""
    stranded = unadopted_fresh_restart(tmp_path=tmp_path)
    stranded.sup.live_codex = {}

    _ = stranded.tick()

    _assert_untouched(stranded=stranded)


def test_the_predecessor_reappearing_is_not_a_successor(*, tmp_path):
    """The same rollout means the respawn did NOT take: the window never reset."""
    stranded = unadopted_fresh_restart(tmp_path=tmp_path)
    stranded.surfaces(session_id=stranded.predecessor)

    _ = stranded.tick()

    _assert_untouched(stranded=stranded)


def test_a_rollout_id_that_is_not_a_canonical_uuid_is_refused(*, tmp_path):
    """An id that cannot be compared cannot discriminate a successor from anything."""
    stranded = unadopted_fresh_restart(tmp_path=tmp_path)
    stranded.surfaces(session_id="not-a-canonical-uuid")

    _ = stranded.tick()

    _assert_untouched(stranded=stranded)


def test_a_live_session_named_for_another_topic_is_refused(*, tmp_path):
    """The indexed thread name is part of the identity, not decoration."""
    stranded = unadopted_fresh_restart(tmp_path=tmp_path)
    stranded.surfaces(session_id=FRESH_CODEX_SESSION_ID, name="some-other-topic")

    _ = stranded.tick()

    _assert_untouched(stranded=stranded)


def test_a_successor_in_another_pane_is_refused(*, tmp_path):
    """The restart happened in one pane; a successor in another is someone else's."""
    stranded = unadopted_fresh_restart(tmp_path=tmp_path)
    stranded.surfaces(session_id=FRESH_CODEX_SESSION_ID)
    _rewrite_record(stranded=stranded, pane="%99")

    _ = stranded.tick()

    _assert_untouched(stranded=stranded)


def test_a_successor_in_another_tmux_session_is_refused(*, tmp_path):
    """A re-pointed mapping row is not evidence about the round this daemon opened."""
    stranded = unadopted_fresh_restart(tmp_path=tmp_path)
    stranded.surfaces(session_id=FRESH_CODEX_SESSION_ID)
    _rewrite_record(stranded=stranded, tmux="some-other-tmux-session")

    _ = stranded.tick()

    _assert_untouched(stranded=stranded)


def test_a_record_bound_to_another_repository_is_refused(*, tmp_path):
    """Rows are repo-scoped; a record naming a different checkout proves nothing here."""
    stranded = unadopted_fresh_restart(tmp_path=tmp_path)
    stranded.surfaces(session_id=FRESH_CODEX_SESSION_ID)
    _rewrite_record(stranded=stranded, repo=str(tmp_path / "some-other-repo"))

    _ = stranded.tick()

    _assert_untouched(stranded=stranded)


def test_a_successor_running_outside_the_repository_never_reaches_the_pane(*, tmp_path):
    """A Codex pane whose cwd left the repository is not this track's pane at all.

    The refusal here is EARLIER than the reconciliation — `pane_is_managed` proves
    process identity plus cwd before any act, and a Codex session outside the repo
    fails it — so the row reads `session-gone` and nothing downstream is consulted.
    Recorded because it is the shape an operator will reach for first, and because the
    NEXT test is the one that actually exercises the reconciliation's own cwd gate.
    """
    stranded = unadopted_fresh_restart(tmp_path=tmp_path)
    stranded.surfaces(session_id=FRESH_CODEX_SESSION_ID, cwd=tmp_path / "elsewhere")

    view = stranded.tick()

    assert view.status == "session-gone"
    _assert_untouched(stranded=stranded)


def test_a_surviving_successor_in_another_checkout_is_refused(*, tmp_path):
    """The pane was taken over out-of-band; the successor survives somewhere else.

    This is how the reconciliation's own cwd gate is reachable, and why it is not
    redundant with the pane-identity gate above: the PANE can satisfy that gate as a
    live Claude TUI in this repository while live Codex discovery still reports this
    topic on a process running in a different checkout. The record's successor id
    matches, so every other fact agrees — and consuming the declaration would spend it
    on a session that is neither in this pane nor in this repository.
    """
    stranded = unadopted_fresh_restart(tmp_path=tmp_path)
    stranded.surfaces(session_id=FRESH_CODEX_SESSION_ID, cwd=tmp_path / "another-checkout")
    stranded.fake.cmds[stranded.session] = "node"  # a Claude TUI now holds the pane
    stranded.fake.paths[stranded.session] = str(stranded.repo)

    _ = stranded.tick()

    _assert_untouched(stranded=stranded)


def test_an_unproven_out_of_band_identity_change_is_refused(*, tmp_path):
    """The discriminating row: everything agrees EXCEPT that the daemon launched it.

    Canonical, different from the predecessor, named for this topic, in this pane, in
    this repository — and not the rollout the ``/rename`` proved. Without the recorded
    successor id this candidate is indistinguishable from a real recovery, which is
    precisely why a bare "the identity changed" test would not have been safe.
    """
    stranded = unadopted_fresh_restart(tmp_path=tmp_path)
    stranded.surfaces(session_id=STRANGER_SESSION_ID)

    _ = stranded.tick()

    _assert_untouched(stranded=stranded)
