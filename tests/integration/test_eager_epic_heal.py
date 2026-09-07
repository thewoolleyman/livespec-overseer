"""`overseer-fdau` — a derivable-but-null plan epic is healed EAGERLY, not at a boundary.

THE DEFECT. A plan mapping row can be persisted with an unresolved epic even when
``registry.epic_from_plan_anchor(repo, topic)`` WOULD resolve a real one (adopted
before its anchor was readable, or adopted epic-less by design). Such a row renders
``mapping-unusable`` ("mapping row has unresolved epic; restart resume cannot be
built"), lands in ``NEEDS YOU``, and pesters the operator to register an epic the
daemon can name itself. The only heal that existed (overseer-vbmq's
``rederive_epic_if_stale``) runs ONLY at the restart-interlock boundary — after a
``ready`` declaration, under ``act``. A SESSION-GONE track (or one that is simply
idle-and-fine) never reaches that boundary, so its derivable null sat unusable
INDEFINITELY.

THE FIX. The acting tick heals it eagerly, before evaluation, and persists it — so
the very case the restart-boundary heal misses is cured on the first tick that
observes the derivable null.

WHY THE CONTROLS ARE THE POINT.
  - A genuinely-unresolvable epic (the anchor returns None) must STILL surface to a
    human unchanged, and the track must NOT be dropped from supervision
    (cite overseer-y3xhlh.11).
  - The heal must be BOUNDED: one anchor read per null row, never a per-tick ledger
    subprocess.
  - The read-only ``list`` tick must never heal — it must not read a `plan/` anchor.
"""

from __future__ import annotations

import contextlib
import io as _io
from pathlib import Path

import registry
from test_supervisor_builders import TEST_EPIC, make_plan, make_supervisor
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []


def _null_epic_row(*, repo: Path, topic: str, session: str) -> registry.Track:
    """A mapping row whose epic was persisted null — the derivable-but-null shape."""
    return registry.Track(
        topic=topic, repo=str(repo), tmux=session, epic=None, added_at="2026-09-06T00:00:00Z"
    )


def _stored_epic(*, store_path: str, topic: str) -> str | None:
    for track in registry.read_valid_mapping(store_path=store_path):
        if track.topic == topic:
            return track.epic
    raise AssertionError(f"no stored row for {topic}")


def test_session_gone_null_epic_row_heals_from_the_derivable_anchor(*, tmp_path):
    """THE RED. A SESSION-GONE track — the case vbmq's restart-boundary heal misses.

    Its stored epic is null while the plan's handoff anchor resolves to TEST_EPIC.
    One acting tick must persist the derived epic AND keep supervising the track.
    """
    repo, topic = make_plan(tmp_path=tmp_path)  # handoff.md anchors to TEST_EPIC
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()  # no serve() — the session is GONE
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, watch_repos=[str(repo)], out=_io.StringIO())
    registry.append_mapping(
        track=_null_epic_row(repo=repo, topic=topic, session=session),
        store_path=sup.store_path,
        added_at="2026-09-06T00:00:00Z",
    )

    with contextlib.redirect_stderr(_io.StringIO()):
        views = sup.tick(act=True)

    # Persisted — a LATER tick (and the read-only `list` projection) sees the real epic.
    assert _stored_epic(store_path=sup.store_path, topic=topic) == TEST_EPIC
    # Not dropped: the track is still supervised, and — being session-gone — still red.
    row = next(view for view in views if view.topic == topic)
    assert row.status == "session-gone"


def test_the_healed_row_no_longer_renders_mapping_unusable(*, tmp_path):
    """After the acting tick heals it, the read-only projection is clean."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    sup = make_supervisor(
        tmp_path=tmp_path, fake=FakeTmux(), watch_repos=[str(repo)], out=_io.StringIO()
    )
    registry.append_mapping(
        track=_null_epic_row(repo=repo, topic=topic, session=session),
        store_path=sup.store_path,
        added_at="2026-09-06T00:00:00Z",
    )

    with contextlib.redirect_stderr(_io.StringIO()):
        _ = sup.tick(act=True)
        readonly = sup.tick(act=False)

    row = next(view for view in readonly if view.topic == topic)
    assert row.status != "mapping-unusable"


def test_a_genuinely_unresolvable_epic_still_surfaces_and_is_not_dropped(*, tmp_path):
    """CONTROL. Anchor returns None → the row stays unresolved, still surfaces to a
    human as mapping-unusable on the read-only projection, and is NOT dropped."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    sup = make_supervisor(
        tmp_path=tmp_path,
        fake=FakeTmux(),
        watch_repos=[str(repo)],
        out=_io.StringIO(),
        epic_lookup=lambda *, repo, topic: None,
    )
    registry.append_mapping(
        track=_null_epic_row(repo=repo, topic=topic, session=session),
        store_path=sup.store_path,
        added_at="2026-09-06T00:00:00Z",
    )

    with contextlib.redirect_stderr(_io.StringIO()):
        acting = sup.tick(act=True)
        readonly = sup.tick(act=False)

    assert not registry.epic_is_resolved(epic=_stored_epic(store_path=sup.store_path, topic=topic))
    assert next(view for view in acting if view.topic == topic).status == "session-gone"
    assert next(view for view in readonly if view.topic == topic).status == "mapping-unusable"


def test_the_heal_is_bounded_to_one_anchor_read_per_null_row(*, tmp_path):
    """CONTROL. No per-tick ledger subprocess: an unresolvable null row is probed
    ONCE across many acting ticks, not once per tick."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    calls: list[str] = []

    def counting_lookup(*, repo, topic):
        calls.append(topic)  # unresolvable: falls through to an implicit None

    sup = make_supervisor(
        tmp_path=tmp_path,
        fake=FakeTmux(),
        watch_repos=[str(repo)],
        out=_io.StringIO(),
        epic_lookup=counting_lookup,
    )
    registry.append_mapping(
        track=_null_epic_row(repo=repo, topic=topic, session=session),
        store_path=sup.store_path,
        added_at="2026-09-06T00:00:00Z",
    )

    with contextlib.redirect_stderr(_io.StringIO()):
        for _ in range(5):
            _ = sup.tick(act=True)

    assert calls == [topic]


def test_a_read_only_tick_never_heals_and_never_reads_the_anchor(*, tmp_path):
    """CONTROL. The `list` path (act=False) must not read a `plan/` anchor: the heal
    is act-only, so a read-only tick leaves the store untouched and reads nothing."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    calls: list[str] = []

    def counting_lookup(*, repo, topic):
        calls.append(topic)
        return TEST_EPIC

    sup = make_supervisor(
        tmp_path=tmp_path,
        fake=FakeTmux(),
        watch_repos=[str(repo)],
        out=_io.StringIO(),
        epic_lookup=counting_lookup,
    )
    registry.append_mapping(
        track=_null_epic_row(repo=repo, topic=topic, session=session),
        store_path=sup.store_path,
        added_at="2026-09-06T00:00:00Z",
    )

    with contextlib.redirect_stderr(_io.StringIO()):
        _ = sup.tick(act=False)

    assert calls == []
    assert not registry.epic_is_resolved(epic=_stored_epic(store_path=sup.store_path, topic=topic))
