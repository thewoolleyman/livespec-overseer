"""Beside-tests for supervisor.py — wind-down starvation liveness."""

import contextlib
import io as _io

import _supervisor_config
import _supervisor_snapshot
import pytest
import registry
import signals
import supervisor
from test_supervisor_builders import (
    busy_capture,
    declare,
    idle_capture,
    key_for,
    make_plan,
    make_supervisor,
    mapped_track,
    render_of,
)
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []


@pytest.fixture(autouse=True)
def _isolate_cwd(*, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


def picker_capture(*, ctx: int = 80) -> str:
    return (
        "How do you want to ratify?\n"
        "❯ 1. Yes, run /livespec:revise\n"
        "  2. No, ask the operator\n"
        f"  Opus 4.8 (1M context) | /x/repo | Ctx: {ctx}% left\n"
    )


def test_snapshot_rows_carry_picker_open_and_monotonic_stall_seconds(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=picker_capture())
    clock = {"t": 1000.0}
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: clock["t"])
    track = mapped_track(repo=repo, topic=topic, session=session)

    first = sup.evaluate(track=track, act=True)
    clock["t"] += 42.0
    second = sup.evaluate(track=track, act=True)
    payload = _supervisor_snapshot.row_payload(sup=sup, row=second)

    assert first.status == "blocked:human"
    assert first.picker_open is True
    assert first.stall_seconds == 0
    assert second.picker_open is True
    assert second.stall_seconds == 42
    assert payload["picker_open"] is True
    assert payload["stall_seconds"] == 42


def test_picker_stall_clock_recovers_when_since_is_missing(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=picker_capture())
    clock = {"t": 1000.0}
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: clock["t"])
    track = mapped_track(repo=repo, topic=topic, session=session)

    assert sup.evaluate(track=track, act=True).stall_seconds == 0
    sup.inject[key_for(repo=repo, topic=topic)].blocked_human_stall_since = None
    clock["t"] += 42.0
    recovered = sup.evaluate(track=track, act=True)

    assert recovered.status == "blocked:human"
    assert recovered.stall_seconds == 0


def test_overdue_picker_stall_has_attention_status_distinct_from_fresh_block(
    *, tmp_path, monkeypatch
):
    monkeypatch.setattr(_supervisor_config, "PICKER_STALL_AFTER", 30.0)
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=picker_capture())
    clock = {"t": 1000.0}
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: clock["t"])
    track = mapped_track(repo=repo, topic=topic, session=session)

    fresh = sup.evaluate(track=track, act=True)
    clock["t"] += 31.0
    stalled = sup.evaluate(track=track, act=True)
    needs = render_of(sup=sup, views=[stalled]).split("NEEDS YOU")[1]

    assert fresh.status == "blocked:human"
    assert stalled.status == "picker-stalled"
    assert supervisor.needs_attention(row=stalled) is True
    assert "picker stalled" in (stalled.note or "")
    assert "picker stalled" in needs
    assert not fake.has(method="paste")


def test_overdue_picker_stall_promotes_on_read_only_evaluate_without_acting(
    *, tmp_path, monkeypatch
):
    monkeypatch.setattr(_supervisor_config, "PICKER_STALL_AFTER", 30.0)
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=picker_capture())
    clock = {"t": 1000.0}
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: clock["t"])
    track = mapped_track(repo=repo, topic=topic, session=session)

    assert sup.evaluate(track=track, act=False).status == "blocked:human"
    clock["t"] += 31.0
    stalled = sup.evaluate(track=track, act=False)

    assert stalled.status == "picker-stalled"
    assert "picker stalled" in (stalled.note or "")
    assert not fake.has(method="paste")


def test_charter_authorized_picker_stall_gets_clause_nudge_without_answering_picker(
    *, tmp_path, monkeypatch
):
    monkeypatch.setattr(_supervisor_config, "PICKER_STALL_AFTER", 30.0)
    repo, worker_topic = make_plan(tmp_path=tmp_path)
    topic = signals.supervisor_entity_topic(topic=worker_topic)
    session = topic
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=picker_capture())
    clock = {"t": 1000.0}
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: clock["t"])
    track = mapped_track(repo=repo, topic=topic, session=session)

    with contextlib.redirect_stderr(_io.StringIO()):
        assert sup.evaluate(track=track, act=True).status == "blocked:human"
        clock["t"] += 31.0
        stalled = sup.evaluate(track=track, act=True)
        clock["t"] += 31.0
        still_stalled = sup.evaluate(track=track, act=True)

    assert stalled.status == "picker-stalled"
    assert still_stalled.status == "picker-stalled"
    assert len(fake.paste_texts()) == 1
    pasted = "\n".join(fake.paste_texts())
    assert "If the SUPERVISOR can perform the unblock, PERFORM IT." in pasted
    assert "A wait is not a question. A mechanical unblock is not a question." in pasted
    assert "1. Yes" not in pasted
    assert "2. No" not in pasted
    assert not any(call[0] == "keys" and call[2] in {"Enter", "1", "2"} for call in fake.calls)


def test_charter_authorized_picker_stall_reports_failed_nudge_without_answering(
    *, tmp_path, monkeypatch
):
    monkeypatch.setattr(_supervisor_config, "PICKER_STALL_AFTER", 30.0)
    repo, worker_topic = make_plan(tmp_path=tmp_path)
    topic = signals.supervisor_entity_topic(topic=worker_topic)
    session = topic
    fake = FakeTmux()
    fake.paste_ok = False
    fake.serve(session=session, repo=repo, capture=picker_capture())
    clock = {"t": 1000.0}
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: clock["t"])
    track = mapped_track(repo=repo, topic=topic, session=session)

    with contextlib.redirect_stderr(_io.StringIO()) as err:
        assert sup.evaluate(track=track, act=True).status == "blocked:human"
        clock["t"] += 31.0
        assert sup.evaluate(track=track, act=True).status == "picker-stalled"

    assert "charter-authorized picker-stall nudge FAILED" in err.getvalue()
    assert not any(call[0] == "keys" and call[2] in {"Enter", "1", "2"} for call in fake.calls)


def test_round_starvation_surfaces_after_floor_without_acting(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=40))
    clock = {"t": 1000.0}
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: clock["t"])
    track = mapped_track(repo=repo, topic=topic, session=session)
    declare(repo=repo, topic=topic, value="blocked: need a decision", mtime=900.0)

    with contextlib.redirect_stderr(_io.StringIO()) as err:
        assert sup.evaluate(track=track, act=True).status == "blocked:human"
        fake.panes[session] = busy_capture(ctx=40)
        for _ in range(9):
            clock["t"] += 800.0
            assert sup.evaluate(track=track, act=True).status == "working"
        declare(repo=repo, topic=topic, value="blocked: need a decision", mtime=clock["t"])
        fake.panes[session] = idle_capture(ctx=40)
        sup.claude_status_by_session = {session: "shell"}
        clock["t"] += 800.0
        starved = sup.evaluate(track=track, act=True)

    assert starved.status == "blocked:human"
    assert "winddown starved" in (starved.note or "")
    assert "blocked" in (starved.note or "")
    assert "need a decision" in (starved.note or "")
    assert "background shell" in (starved.note or "")
    assert "visible gate" not in (starved.note or "")
    assert "wind-down starved (2h)" in err.getvalue()
    assert err.getvalue().count("wind-down starved") == 1
    assert not fake.has(method="paste")
    assert not fake.has(method="respawn")
    assert signals.read_state(repo=str(repo), topic=topic) is not None


def test_round_starvation_clears_when_round_opens_or_ctx_recovers(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=busy_capture(ctx=40))
    clock = {"t": 1000.0}
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: clock["t"])
    track = mapped_track(repo=repo, topic=topic, session=session)

    sup.evaluate(track=track, act=True)
    for _ in range(9):
        clock["t"] += 800.0
        generating = sup.evaluate(track=track, act=True)
    with contextlib.redirect_stderr(_io.StringIO()) as err:
        clock["t"] += 800.0
        generating = sup.evaluate(track=track, act=True)
    assert generating.status == "working"
    assert "wind-down starved" not in err.getvalue()

    fake.panes[session] = idle_capture(ctx=40)
    opened = sup.evaluate(track=track, act=True)
    assert opened.status == "warned"
    assert registry.read_injection_stamp(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
    assert sup.inject[key_for(repo=repo, topic=topic)].winddown_starved_episode.since is None

    fake.panes[session] = busy_capture(ctx=40)
    registry.clear_injection_stamp(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
    sup.evaluate(track=track, act=True)
    fake.panes[session] = busy_capture(ctx=73)
    recovered = sup.evaluate(track=track, act=True)
    assert recovered.status == "working"
    assert sup.inject[key_for(repo=repo, topic=topic)].winddown_starved_episode.since is None


def test_round_starvation_unknown_context_never_starts(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=busy_capture(ctx=None))
    clock = {"t": 1000.0}
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: clock["t"])
    track = mapped_track(repo=repo, topic=topic, session=session)

    sup.evaluate(track=track, act=True)
    clock["t"] += _supervisor_config.WINDDOWN_STARVED_AFTER + 1
    with contextlib.redirect_stderr(_io.StringIO()) as err:
        view = sup.evaluate(track=track, act=True)
    assert view.status == "working"
    assert "wind-down starved" not in err.getvalue()
    assert sup.inject[key_for(repo=repo, topic=topic)].winddown_starved_episode.since is None


def test_malformed_state_note_survives_background_shell_ticks(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=73))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    sup.claude_status_by_session = {session: "shell"}
    declare(repo=repo, topic=topic, value="bogus-token")
    track = mapped_track(repo=repo, topic=topic, session=session)

    with contextlib.redirect_stderr(_io.StringIO()) as err:
        first = sup.evaluate(track=track, act=True)
        second = sup.evaluate(track=track, act=True)

    assert first.status == "working"
    assert second.status == "working"
    assert first.note == "BAD state file: 'bogus-token'; background shell"
    assert second.note == "BAD state file: 'bogus-token'; background shell"
    assert err.getvalue().count("MALFORMED state file") == 1
