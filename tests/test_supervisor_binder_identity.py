"""What the supervision offer accepts as a SUPERVISOR BINDER (`overseer-ow7c.4`).

The surface routes on exactly one input — does a durable supervisor prompt already
exist? — and it used to read that input off `plan/<topic>/epic.md`, a migrated WORKER
handoff's ledger anchor that says so in its own text. These are the two directions of
that decision, asserted together because fixing only one of them ships the other.

The tree is synthetic on purpose. The live specimen that filed this
(`plan/model-preserving-restarts`, the one plan of eighteen carrying `epic.md`)
evaporates the day it is archived, and the defect would evaporate with it.
"""

import contextlib
import io as _io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "overseer"))

import _supervisor_offer
import registry
from test_supervisor_builders import (
    idle_capture,
    make_plan,
    make_supervisor,
    mapped_track,
)
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []

_MIGRATED_EPIC_MD = (
    "# Ledger epic anchor\n\n"
    "`overseer-test-epic`\n\n"
    "This migrated research record preserves the legacy handoff's immutable epic\n"
    "anchor. Read live status from the ledger, not from this file.\n"
)


def _offer_conditions(*, sup, track) -> tuple[set[str], str]:
    """Surface the offer once and report the alert conditions plus the emitted text."""
    with contextlib.redirect_stderr(_io.StringIO()) as err:
        _supervisor_offer.surface_supervision_offer(sup=sup, track=track, act=True)
    return {key[2] for key in sup.alerted}, err.getvalue()


def _unsupervised_plan(*, tmp_path):
    """A live, idle, mapped plan whose derived supervisor session does not exist."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=73))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    return repo, topic, sup, mapped_track(repo=repo, topic=topic, session=session)


def test_migrated_epic_without_a_binder_is_offered_supervision(*, tmp_path):
    """(b) `epic.md` is not a binder, so a plan carrying one is told to CREATE one.

    The reproduction. `epic.md` present, no supervisor binder of any kind, no supervisor
    session running — measured live as routing to `supervisor-missing`, whose message
    tells the operator to START a session against a durable prompt that does not exist.
    The correct arm names the operation that would produce one.
    """
    repo, topic, sup, track = _unsupervised_plan(tmp_path=tmp_path)
    (repo / "plan" / topic / "epic.md").write_text(_MIGRATED_EPIC_MD, encoding="utf-8")

    conditions, emitted = _offer_conditions(sup=sup, track=track)

    assert conditions == {"supervision-offer"}
    assert "/livespec-overseer:supervise-plan" in emitted
    assert "start tmux session" not in emitted


def test_a_real_binder_without_a_migrated_epic_is_not_offered_supervision(*, tmp_path):
    """(a) The converse control: a plan holding a binder is not told to author one.

    Asserted beside (b) because a one-way fix — dropping the predicate rather than
    re-pointing it — would pass that test and re-offer supervision to every plan that
    already has it. `epic.md` is deliberately absent, so the only thing that can carry
    this verdict is the artifact whose own subject IS this plan's supervision.
    """
    repo, topic, sup, track = _unsupervised_plan(tmp_path=tmp_path)
    (repo / "plan" / topic / "supervisor-handoff.md").write_text("supervise this\n")
    assert not (repo / "plan" / topic / "epic.md").exists()

    conditions, emitted = _offer_conditions(sup=sup, track=track)

    assert conditions == {"supervisor-missing"}
    assert f"start tmux session '{topic}-supervisor'" in emitted
