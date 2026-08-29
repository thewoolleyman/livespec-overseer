"""The per-track `idle_nudge` override and its `add --idle-nudge` CLI (`overseer-4l5iph.2`).

Slice B of the idle-nudge configurability epic. Slice A gave the daemon ONE resolution
function (`_supervisor_idle_nudge_policy.resolve_idle_nudge`) and a daemon-wide default;
this slice adds the per-track override that wins over it, spelled exactly like the
`ctx_threshold` override it sits beside — a nullable field on every assigned Track
variant, written into the mapping row ONLY when set, and cleared by `inherit`.

Three things this file pins, in the order they matter:

  * PRECEDENCE — a non-None per-track field beats the daemon-wide default in both
    directions, and None inherits it. The headline case is a real-shape control: two
    otherwise-identical tracks idling above threshold past the 1-hour floor under a
    daemon-wide `on`, one nudged and one not, differing only in this field.
  * THE CLI — `add --idle-nudge {on,off}` writes the field and `inherit` clears it back
    to None, matching `--ctx-threshold N|inherit` key for key.
  * THE BOUNDARY — the field lives and dies with the mapping row (no separate
    remove/unassign reset path), and the low-context wrap-up still fires for a track
    whose per-track override is `off`, exactly as it does under the daemon-wide `off`.
"""

import dataclasses
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "overseer"))

import _supervisor_config
import _supervisor_idle_nudge_policy
import registry
import supervisor
from test_supervisor_builders import (
    idle_capture,
    isolate_store,
    make_plan,
    make_supervisor,
    mapped_track,
    nudge_count,
    wrapup_count,
)
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []

# Every ASSIGNED variant carries the override; `UnassignedPlan` answers None through the
# same read-only property it already uses for `ctx_threshold` (it has no row to hold one).
ASSIGNED_VARIANTS = (
    registry.PlanTrack,
    registry.SupervisorSeat,
    registry.ForemanSeat,
    registry.GroomingSeat,
)


@pytest.fixture(autouse=True)
def _isolate_cwd(*, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


def _rows(*, store) -> list[dict[str, object]]:
    return [json.loads(line) for line in store.read_text(encoding="utf-8").splitlines()]


def _idling_past_the_floor(*, tmp_path, per_track, daemon_default=True, name="only"):
    """A track idling at an empty prompt well ABOVE the wind-down threshold, ticked once to
    stamp `idle_since` and then advanced past the 1-hour `IDLE_NUDGE_AFTER` floor — so the
    ONLY thing left standing between it and a keep-going nudge is the override under test.

    `name` gives each fixture its own root, so a test can raise TWO of these side by side
    with genuinely separate repos, stores and stamp sidecars — which is what makes the
    twin control below a control rather than one track observed twice."""
    root = tmp_path / name
    root.mkdir()
    repo, topic = make_plan(tmp_path=root)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=73))
    clock = {"t": 1000.0}
    sup = make_supervisor(
        tmp_path=root, fake=fake, now=lambda: clock["t"], idle_nudge=daemon_default
    )
    sup.claude_status_by_session = {session: "idle"}
    track = dataclasses.replace(
        mapped_track(repo=repo, topic=topic, session=session), idle_nudge=per_track
    )
    sup.evaluate(track=track, act=True)
    clock["t"] += _supervisor_config.IDLE_NUDGE_AFTER + 1
    return sup, fake, track


def test_every_assigned_track_variant_carries_the_per_track_override():
    """The field is a SIBLING of `ctx_threshold` on all four assigned variants, not a
    plan-track special case: a supervisor, foreman or grooming seat is just as capable of
    being an operator's "leave this one alone" as a plan is."""
    for variant in ASSIGNED_VARIANTS:
        fields = {field.name: field for field in dataclasses.fields(variant)}
        assert "idle_nudge" in fields, (
            f"{variant.__name__} must carry the per-track idle_nudge override beside "
            "ctx_threshold; the daemon resolves the two the same way"
        )
        assert fields["idle_nudge"].default is None, (
            f"{variant.__name__}.idle_nudge must default to None — 'no override, inherit "
            "the daemon-wide default' — so an existing row keeps today's behaviour"
        )


def test_an_unassigned_plan_reports_no_override():
    """`UnassignedPlan` has no mapping row, so it can hold no override and answers None
    through the same read-only property shape `ctx_threshold` uses."""
    unassigned = registry.Track(topic="alpha", repo="/repo", assigned=False)
    assert unassigned.idle_nudge is None
    assert unassigned.ctx_threshold is None


@pytest.mark.parametrize(
    ("daemon_default", "per_track", "expected"),
    [
        pytest.param(True, None, True, id="none-inherits-daemon-on"),
        pytest.param(False, None, False, id="none-inherits-daemon-off"),
        pytest.param(True, False, False, id="per-track-off-beats-daemon-on"),
        pytest.param(False, True, True, id="per-track-on-beats-daemon-off"),
        pytest.param(True, True, True, id="per-track-on-agrees-with-daemon-on"),
        pytest.param(False, False, False, id="per-track-off-agrees-with-daemon-off"),
    ],
)
def test_a_non_none_per_track_field_wins_over_the_daemon_wide_default(
    *, tmp_path, daemon_default, per_track, expected
):
    """The whole precedence chain slice B is responsible for, resolved in the ONE seam:
    a set field decides, in BOTH directions, and None defers to the daemon-wide switch."""
    repo, topic = make_plan(tmp_path=tmp_path)
    fake = FakeTmux()
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, idle_nudge=daemon_default)
    track = dataclasses.replace(
        mapped_track(repo=repo, topic=topic, session="s"), idle_nudge=per_track
    )
    assert _supervisor_idle_nudge_policy.resolve_idle_nudge(sup=sup, track=track) is expected


def test_a_per_track_off_track_is_not_nudged_while_its_twin_still_is(*, tmp_path):
    """The real-shape control the acceptance criterion asks for: the SAME fixture, the same
    daemon-wide `on` default, the same idle-past-the-floor pane — and the only difference
    between the track that gets the single-shot nudge and the track that gets none is the
    per-track field. The row stays descriptive either way; this gates the keystroke."""
    nudged_sup, nudged_fake, nudged = _idling_past_the_floor(
        tmp_path=tmp_path, per_track=True, name="loud"
    )
    assert nudged_sup.evaluate(track=nudged, act=True).status == "idle-with-context-left"
    assert nudge_count(fake=nudged_fake) == 1

    quiet_sup, quiet_fake, quiet = _idling_past_the_floor(
        tmp_path=tmp_path, per_track=False, name="quiet"
    )
    assert quiet_sup.evaluate(track=quiet, act=True).status == "idle-with-context-left"
    assert nudge_count(fake=quiet_fake) == 0
    assert wrapup_count(fake=quiet_fake) == 0


def test_a_per_track_on_track_is_still_nudged_under_a_daemon_wide_off(*, tmp_path):
    """The inverse control, end to end: an operator who switched the nudge off fleet-wide
    can still opt ONE track back in, and it gets the ordinary single-shot-per-episode nudge."""
    sup, fake, track = _idling_past_the_floor(
        tmp_path=tmp_path, per_track=True, daemon_default=False
    )
    assert sup.evaluate(track=track, act=True).status == "idle-with-context-left"
    assert nudge_count(fake=fake) == 1


def test_idle_nudge_none_is_omitted_from_the_row_and_an_explicit_bool_roundtrips(*, tmp_path):
    """Key for key with `ctx_threshold`: a track with no override serializes a row WITHOUT
    the key, so a bare row stays distinguishable from one that pinned the current default,
    and an explicit `False` survives the round trip as `False` rather than as "absent"."""
    store = tmp_path / "map.jsonl"
    for topic, idle_nudge in (("nooverride", None), ("quiet", False), ("loud", True)):
        registry.append_mapping(
            track=registry.Track(topic=topic, repo="/r", tmux=f"r--{topic}", idle_nudge=idle_nudge),
            store_path=store,
        )

    rows = _rows(store=store)
    assert "idle_nudge" not in rows[0]  # None → key omitted
    assert rows[1]["idle_nudge"] is False  # explicit False → key present and False
    assert rows[2]["idle_nudge"] is True

    by_topic = {entry.track.topic: entry.track for entry in registry.read_mapping(store_path=store)}
    assert by_topic["nooverride"].idle_nudge is None
    assert by_topic["quiet"].idle_nudge is False
    assert by_topic["loud"].idle_nudge is True


def test_cli_add_idle_nudge_is_explicitly_written_and_clearable(*, tmp_path, monkeypatch):
    """`add --idle-nudge {on,off}` writes the per-track field and `inherit` clears it back to
    None, mirroring `--ctx-threshold N|inherit` — including the part that matters most: the
    clear REMOVES the key rather than writing a false-y one, so the track genuinely reverts
    to the daemon-wide default instead of pinning today's value of it."""
    repo = tmp_path / "repo"
    (repo / "plan" / "alpha").mkdir(parents=True)
    store = isolate_store(tmp_path=tmp_path, monkeypatch=monkeypatch)
    registry.append_mapping(
        track=registry.Track(
            topic="alpha",
            repo=str(repo),
            tmux="old-session",
            epic="overseer-old",
            ctx_threshold=45,
            added_at="2026-08-19T07:42:57Z",
        ),
        store_path=store,
    )

    def _add(*flag: str) -> int:
        return supervisor.main(argv=["add", "--repo", str(repo), "--topic", "alpha", *flag])

    assert _add("--idle-nudge", "off") == 0
    rows = _rows(store=store)
    assert rows[0]["idle_nudge"] is False
    # An unsupplied field is never touched: the same preservation `--ctx-threshold` gets.
    assert rows[0]["ctx_threshold"] == 45
    assert rows[0]["epic"] == "overseer-old"
    assert rows[0]["added_at"] == "2026-08-19T07:42:57Z"

    assert _add("--idle-nudge", "on") == 0
    assert _rows(store=store)[0]["idle_nudge"] is True

    # An `add` that names neither flag leaves BOTH overrides standing.
    assert _add() == 0
    assert _rows(store=store)[0]["idle_nudge"] is True
    assert _rows(store=store)[0]["ctx_threshold"] == 45

    assert _add("--idle-nudge", "inherit") == 0
    rows = _rows(store=store)
    assert "idle_nudge" not in rows[0]
    assert rows[0]["ctx_threshold"] == 45
    assert rows[0]["epic"] == "overseer-old"
    assert rows[0]["added_at"] == "2026-08-19T07:42:57Z"


def test_a_track_reverts_to_the_daemon_wide_default_after_inherit(*, tmp_path, monkeypatch):
    """The behavioural half of `inherit`: read the row back through the ordinary mapping
    reader and resolve it. Before the clear the track refuses the nudge against a daemon-wide
    `on`; after it, the same track takes the daemon's answer again."""
    repo = tmp_path / "repo"
    (repo / "plan" / "alpha").mkdir(parents=True)
    store = isolate_store(tmp_path=tmp_path, monkeypatch=monkeypatch)
    sup = make_supervisor(tmp_path=tmp_path, fake=FakeTmux(), idle_nudge=True)

    def _only_track():
        entries = registry.read_mapping(store_path=store)
        assert len(entries) == 1
        return entries[0].track

    assert (
        supervisor.main(
            argv=["add", "--repo", str(repo), "--topic", "alpha", "--idle-nudge", "off"]
        )
        == 0
    )
    pinned = _only_track()
    assert pinned.idle_nudge is False
    assert _supervisor_idle_nudge_policy.resolve_idle_nudge(sup=sup, track=pinned) is False

    assert (
        supervisor.main(
            argv=["add", "--repo", str(repo), "--topic", "alpha", "--idle-nudge", "inherit"]
        )
        == 0
    )
    cleared = _only_track()
    assert cleared.idle_nudge is None
    assert _supervisor_idle_nudge_policy.resolve_idle_nudge(sup=sup, track=cleared) is True


def test_the_override_lives_and_dies_with_the_mapping_row(*, tmp_path, monkeypatch):
    """No remove/unassign-time reset path is added, and none is needed: `remove` drops the
    WHOLE row, so the override goes with it and a fresh `add` starts with no override at
    all. Deferred per the plan's scope event — this test is what makes the deferral safe."""
    repo = tmp_path / "repo"
    (repo / "plan" / "alpha").mkdir(parents=True)
    store = isolate_store(tmp_path=tmp_path, monkeypatch=monkeypatch)

    assert (
        supervisor.main(
            argv=["add", "--repo", str(repo), "--topic", "alpha", "--idle-nudge", "off"]
        )
        == 0
    )
    assert _rows(store=store)[0]["idle_nudge"] is False

    assert supervisor.main(argv=["remove", "--repo", str(repo), "--topic", "alpha"]) == 0
    assert _rows(store=store) == []

    assert supervisor.main(argv=["add", "--repo", str(repo), "--topic", "alpha"]) == 0
    assert "idle_nudge" not in _rows(store=store)[0]


def test_a_per_track_off_still_wraps_up_a_track_below_the_threshold(*, tmp_path):
    """OUT OF SCOPE stays out of scope one tier down: the per-track override reaches the
    keep-going nudge and nothing else. A track at 40% against the default 50% threshold is
    warned and wound up even though its own field says "never nudge me" — the low-context
    path has no off-switch at ANY tier, which is the promise slice A made daemon-wide."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=40))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, idle_nudge=True)
    track = dataclasses.replace(
        mapped_track(repo=repo, topic=topic, session=session), idle_nudge=False
    )
    view = sup.evaluate(track=track, act=True)
    assert view.status == "warned"
    assert wrapup_count(fake=fake) == 1
    assert nudge_count(fake=fake) == 0
