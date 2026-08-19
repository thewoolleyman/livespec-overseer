"""Regression tests for picker-stall nudges across the daemon's own paste echo."""

from __future__ import annotations

import contextlib
import io as _io
from pathlib import Path

import _supervisor_config
import signals
from test_supervisor_builders import (
    make_plan,
    make_supervisor,
    mapped_track,
    write_fresh_supervisor_state,
)
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []


def picker_capture(*, ctx: int = 80) -> str:
    return (
        "How do you want to ratify?\n"
        "❯ 1. Yes, run /livespec:revise\n"
        "  2. No, ask the operator\n"
        f"  Opus 4.8 (1M context) | /x/repo | Ctx: {ctx}% left\n"
    )


def install_picker_paste_echo(*, fake: FakeTmux) -> None:
    fake.on_paste = lambda session, text: echo_picker_paste(fake=fake, session=session, text=text)


def echo_picker_paste(*, fake: FakeTmux, session: str, text: str) -> None:
    val = fake.panes.get(session, "")
    display_text = text.splitlines()[0]
    if isinstance(val, str) and ("\n❯ 1." in val or "\n› 1." in val):
        fake.panes[session] = f"{val}{display_text}\n"


def stalled_picker_supervisor(*, tmp_path: Path, monkeypatch):
    monkeypatch.setattr(_supervisor_config, "PICKER_STALL_AFTER", 30.0)
    repo, worker_topic = make_plan(tmp_path=tmp_path)
    topic = signals.supervisor_entity_topic(topic=worker_topic)
    session = topic
    fake = FakeTmux()
    install_picker_paste_echo(fake=fake)
    fake.serve(session=session, repo=repo, capture=picker_capture())
    clock = {"t": 1000.0}
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: clock["t"])
    track = mapped_track(repo=repo, topic=topic, session=session)
    write_fresh_supervisor_state(repo=repo, topic=topic)
    return fake, clock, sup, track, session


def test_picker_stall_nudge_survives_its_own_capture_echo(*, tmp_path, monkeypatch):
    fake, clock, sup, track, _session = stalled_picker_supervisor(
        tmp_path=tmp_path, monkeypatch=monkeypatch
    )

    with contextlib.redirect_stderr(_io.StringIO()):
        assert sup.evaluate(track=track, act=True).status == "blocked:human"
        clock["t"] += 31.0
        stalled = sup.evaluate(track=track, act=True)
        clock["t"] += 31.0
        sup.evaluate(track=track, act=True)
        clock["t"] += 31.0
        still_stalled_after_echo = sup.evaluate(track=track, act=True)

    assert stalled.status == "picker-stalled"
    assert still_stalled_after_echo.status == "picker-stalled"
    assert len(fake.paste_texts()) == 1
    pasted = "\n".join(fake.paste_texts())
    assert "If the SUPERVISOR can perform the unblock, PERFORM IT." in pasted
    assert "A wait is not a question. A mechanical unblock is not a question." in pasted
    assert "1. Yes" not in pasted
    assert "2. No" not in pasted
    assert not any(call[0] == "keys" and call[2] in {"Enter", "1", "2"} for call in fake.calls)


def test_picker_stall_nudge_rearms_after_non_daemon_capture_change(*, tmp_path, monkeypatch):
    fake, clock, sup, track, session = stalled_picker_supervisor(
        tmp_path=tmp_path, monkeypatch=monkeypatch
    )

    with contextlib.redirect_stderr(_io.StringIO()):
        assert sup.evaluate(track=track, act=True).status == "blocked:human"
        clock["t"] += 31.0
        assert sup.evaluate(track=track, act=True).status == "picker-stalled"
        fake.panes[session] = picker_capture(ctx=79)
        assert sup.evaluate(track=track, act=True).status == "blocked:human"
        clock["t"] += 31.0
        assert sup.evaluate(track=track, act=True).status == "picker-stalled"

    assert len(fake.paste_texts()) == 2


def test_foreman_picker_stall_gets_same_reserved_entity_nudge(*, tmp_path, monkeypatch):
    monkeypatch.setattr(_supervisor_config, "PICKER_STALL_AFTER", 30.0)
    repo, _worker_topic = make_plan(tmp_path=tmp_path)
    topic = f"{repo.name}-foreman"
    fake = FakeTmux()
    install_picker_paste_echo(fake=fake)
    fake.serve(session=topic, repo=repo, capture=picker_capture())
    clock = {"t": 1000.0}
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: clock["t"])
    track = mapped_track(repo=repo, topic=topic, session=topic)

    with contextlib.redirect_stderr(_io.StringIO()):
        assert sup.evaluate(track=track, act=True).status == "blocked:human"
        clock["t"] += 31.0
        stalled = sup.evaluate(track=track, act=True)

    assert stalled.status == "picker-stalled"
    assert len(fake.paste_texts()) == 1
    assert not any(call[0] == "keys" and call[2] in {"Enter", "1", "2"} for call in fake.calls)
