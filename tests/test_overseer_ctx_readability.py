"""Acceptance tests for headroom readability while a picker displaces the statusline.

`overseer-62mgxr`. The daemon reads context headroom from the statusline the pane
renders. An open picker's overlay displaces that statusline out of the capture, so
the live read returns nothing — measured fleet-wide 2026-08-23 as 0 of 8 picker-open
rows carrying a reading, with no exceptions. Headroom is the input to wrap-up safety,
so the instrument fails closed on exactly the sessions that sit longest with the most
unpreserved state.

THESE TESTS KEY ON THE READ FAILING, NEVER ON `picker_open`, and both arms are
exercised because either alone reproduces the defect pointed one way or the other:

  * a track whose live read fails but whose earlier reading this daemon actually
    took reports that reading, MARKED retained and stamped with its age; and
  * a track whose headroom this daemon never read reports UNREADABLE, with no value
    invented for it — no default, no floor, no neighbour's number.

The third case is the load-bearing counter-example the 2026-08-22 re-measurement
found (`factory-host-storage-reclamation`: picker open, ctx 64, statusline intact).
A fix keyed on `picker_open` would DISCARD that row's real reading, which is this
item's own leg 2 pointing the other way, so it is pinned here too.
"""

import contextlib
import importlib
import io as _io
import json
import types
from pathlib import Path

import _supervisor_config
import _supervisor_observe
import _supervisor_records
import _supervisor_snapshot
import _supervisor_view
import registry
from test_supervisor_builders import (
    idle_capture,
    make_plan,
    make_supervisor,
    mapped_track,
    render_of,
    row_line,
)
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []

_FOUR_HOURS = 14400.0


def picker_displacing_the_statusline() -> str:
    """A live picker overlay that has pushed the statusline out of the capture.

    The control the filing recorded: three picker-parked panes carried ZERO
    occurrences of the `Ctx: N% left` statusline while three ordinary panes carried
    one each. This is that pane — a real gate shape with no statusline at all.
    """
    return "How do you want to proceed?\n❯ 1. Yes, ratify it\n  2. No, ask the operator\n"


def picker_keeping_the_statusline(*, ctx: int) -> str:
    """The counter-example: an open picker whose statusline is STILL rendered."""
    return (
        "How do you want to proceed?\n"
        "❯ 1. Yes, ratify it\n"
        "  2. No, ask the operator\n"
        f"  Opus 4.8 (1M context) | /x/repo | Ctx: {ctx}% left\n"
    )


def snapshot_rows(*, sup, views) -> dict[str, dict[str, object]]:
    """Write the daemon status snapshot and return its rows keyed by topic."""
    _supervisor_snapshot.write_status_snapshot(sup=sup, rows=views)
    document = json.loads(Path(sup.status_path).read_text(encoding="utf-8"))
    return {row["topic"]: row for row in document["rows"]}


def test_a_picker_that_displaces_the_statusline_still_reports_marked_headroom(*, tmp_path):
    """Leg 1: the row reports a value, and says plainly that the value is retained."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=62))
    clock = {"t": 1000.0}
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: clock["t"])
    track = mapped_track(repo=repo, topic=topic, session=session)

    with contextlib.redirect_stderr(_io.StringIO()):
        live = sup.evaluate(track=track, act=True)
        fake.panes[session] = picker_displacing_the_statusline()
        clock["t"] += _FOUR_HOURS
        parked = sup.evaluate(track=track, act=True)
        rows = snapshot_rows(sup=sup, views=[parked])

    assert rows[topic]["ctx"] == 62
    assert rows[topic]["ctx_source"] == "retained"
    assert rows[topic]["ctx_age_seconds"] == int(_FOUR_HOURS)
    assert live.ctx == 62
    assert live.ctx_source == "live"
    assert live.ctx_age_seconds is None
    # The picker really did blind the LIVE read; the reading is carried, not re-read.
    assert parked.picker_open is True


def test_a_retained_reading_survives_the_fail_closed_decision_window(*, tmp_path):
    """Four hours is well past `CTX_STALE_AFTER`, which is where the old dash came from."""
    assert _supervisor_config.CTX_STALE_AFTER < _FOUR_HOURS
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=71))
    clock = {"t": 1000.0}
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: clock["t"])
    track = mapped_track(repo=repo, topic=topic, session=session)

    with contextlib.redirect_stderr(_io.StringIO()):
        sup.evaluate(track=track, act=True)
        fake.panes[session] = picker_displacing_the_statusline()
        clock["t"] += _FOUR_HOURS
        parked = sup.evaluate(track=track, act=True)

    assert parked.ctx == 71
    assert parked.ctx_source == "retained"


def test_a_track_whose_headroom_was_never_read_reports_unreadable(*, tmp_path):
    """Leg 2's second arm: no value is invented where none was ever obtained."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=picker_displacing_the_statusline())
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    track = mapped_track(repo=repo, topic=topic, session=session)

    with contextlib.redirect_stderr(_io.StringIO()):
        row = sup.evaluate(track=track, act=True)
        rows = snapshot_rows(sup=sup, views=[row])

    assert rows[topic].get("ctx_source") == "unreadable"
    assert rows[topic]["ctx"] is None
    assert rows[topic].get("ctx_age_seconds") is None
    assert row.picker_open is True


def test_an_open_picker_with_a_visible_statusline_keeps_its_live_reading(*, tmp_path):
    """The counter-example is not rounded off: a real reading is never discarded."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=picker_keeping_the_statusline(ctx=64))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    track = mapped_track(repo=repo, topic=topic, session=session)

    with contextlib.redirect_stderr(_io.StringIO()):
        row = sup.evaluate(track=track, act=True)
        rows = snapshot_rows(sup=sup, views=[row])

    assert rows[topic].get("ctx_source") == "live"
    assert rows[topic]["ctx"] == 64
    assert row.picker_open is True


def test_the_table_marks_a_retained_reading_and_still_dashes_an_unreadable_one(*, tmp_path):
    """A retained number must never render as though the pane had just produced it."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=55))
    clock = {"t": 1000.0}
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: clock["t"])
    track = mapped_track(repo=repo, topic=topic, session=session)

    with contextlib.redirect_stderr(_io.StringIO()):
        sup.evaluate(track=track, act=True)
        fake.panes[session] = picker_displacing_the_statusline()
        clock["t"] += _FOUR_HOURS
        parked = sup.evaluate(track=track, act=True)

    unread = _supervisor_view.RowView(
        topic="never-read", repo=str(repo), tmux=None, ctx=None, status="session-gone"
    )
    out = render_of(sup=sup, views=[parked, unread])

    assert "55%~4h" in row_line(out=out, topic=topic)
    assert "—" in row_line(out=out, topic="never-read")


def test_the_reporting_projection_never_relaxes_the_fail_closed_decision_input(*, tmp_path):
    """The retained value reaches the OPERATOR, never the cascade that acts on it.

    `Observation.eff_ctx` keeps its one-hour window, so a four-hour-old reading still
    cannot cross a threshold, open a round, or authorize anything. Reporting an old
    number while saying it is old is safe; ACTING on one is the failure the window
    exists to prevent, and this pins the two apart at the seam.
    """
    package_dir = Path(__file__).resolve().parent.parent / "overseer"
    module_path = package_dir / "_supervisor_ctx_reading.py"
    assert module_path.is_file()
    module = importlib.import_module("_supervisor_ctx_reading")

    state = _supervisor_records.InjectState()
    state.last_ctx = 44
    state.last_ctx_seen = 1000.0
    now = 1000.0 + _FOUR_HOURS

    reported = module.ctx_reading(state=state, current=None, now=now)
    decided = _supervisor_observe.effective_ctx(
        sup=types.SimpleNamespace(inject={("repo", "topic"): state}),
        key=("repo", "topic"),
        current=None,
        now=now,
    )

    assert reported.value == 44
    assert reported.source == "retained"
    assert reported.age_seconds == _FOUR_HOURS
    assert decided is None


def test_the_population_table_shows_readings_without_collapsing_the_categories(*, tmp_path):
    """Leg 3, stated WITH ITS SCOPE, as the 2026-08-22 correction requires.

    SCOPE: the four TRACKED tracks below, after four hours parked. Untracked rows are
    excluded — a discovered plan with no session reads None because nothing is
    tracked, not because a read failed, and counting those as failures is what made
    the original fleet-wide picture look three times worse than it was.

    The tabulation this produces, `ctx` against `status`:

        status                  picker   ctx READ   ctx NONE
        picker-stalled            yes        1          0    parked-long (retained 4h)
        picker-stalled            yes        1          0    parked-visible (live)
        picker-stalled            yes        0          1    parked-never-read
        idle-with-context-left    no         1          0    ordinary-idle (live)

    Read it in both directions, because one direction alone is satisfiable by a
    defect. Picker rows now carry readings — that is the fix. And one picker row
    still carries NONE — that is what proves the first half was not achieved by
    defaulting, carrying a neighbour's value, or inventing a floor, which would have
    made this table look healthy while reproducing the defect.

    Note also what the three picker rows have in common and what they do not: an
    IDENTICAL status, and three different reading provenances. The categories were
    not collapsed to produce the readings, and the readings are not collapsed into
    each other — `retained`, `live` and `unreadable` stay distinguishable at the same
    status, which is exactly the discrimination leg 2 requires.
    """
    repo, _ = make_plan(tmp_path=tmp_path, topic="parked-long")
    fake = FakeTmux()
    clock = {"t": 1000.0}
    panes = {
        "parked-long": idle_capture(ctx=62),
        "parked-visible": picker_keeping_the_statusline(ctx=64),
        "parked-never-read": picker_displacing_the_statusline(),
        "ordinary-idle": idle_capture(ctx=80),
    }
    for topic, capture in panes.items():
        fake.serve(session=topic, repo=repo, capture=capture)
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: clock["t"])
    tracks = {topic: mapped_track(repo=repo, topic=topic, session=topic) for topic in panes}

    with contextlib.redirect_stderr(_io.StringIO()):
        # Tick one reads every statusline that is visible; `parked-long`'s picker then
        # opens on tick two, so its own reading predates the picker exactly as a real
        # parked track's does.
        for track in tracks.values():
            sup.evaluate(track=track, act=True)
        fake.panes["parked-long"] = picker_displacing_the_statusline()
        for track in tracks.values():
            sup.evaluate(track=track, act=True)
        clock["t"] += _FOUR_HOURS
        views = [sup.evaluate(track=track, act=True) for track in tracks.values()]
        rows = snapshot_rows(sup=sup, views=views)

    tracked = {topic: row for topic, row in rows.items() if row["status"] != "unassigned"}
    assert len(tracked) == len(panes)
    read = {topic for topic, row in tracked.items() if row["ctx"] is not None}
    assert read == {"parked-long", "parked-visible", "ordinary-idle"}
    stalled = {topic for topic, row in tracked.items() if row["status"] == "picker-stalled"}
    assert stalled == {"parked-long", "parked-visible", "parked-never-read"}
    assert tracked["parked-long"]["ctx_source"] == "retained"
    assert tracked["parked-long"]["ctx_age_seconds"] == int(_FOUR_HOURS)
    assert tracked["parked-visible"]["ctx_source"] == "live"
    assert tracked["parked-never-read"]["ctx_source"] == "unreadable"
    assert tracked["ordinary-idle"]["status"] == "idle-with-context-left"
    assert tracked["ordinary-idle"]["picker_open"] is False
    assert tracked["ordinary-idle"]["ctx_source"] == "live"
