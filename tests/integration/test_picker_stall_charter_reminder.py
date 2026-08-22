"""Integration coverage for stalled-picker charter reminder scenarios.

Tier: `tests.integration` is one of the documented default `scenario_tiers`
prefixes. These tests drive real Supervisor evaluation from a tmux pane capture
through row projection, paste side effects, attention alerts, and snapshot
serialization.
"""

from __future__ import annotations

import contextlib
import io as _io
import json
from pathlib import Path

import _supervisor_config
import _supervisor_snapshot

from overseer import registry, signals, supervisor
from overseer.test_supervisor_builders import (
    make_plan,
    make_supervisor,
    mapped_track,
    write_fresh_supervisor_state,
)
from overseer.test_supervisor_fakes import FakeTmux

__all__: list[str] = []


def picker_capture(*, ctx: int = 80, tail: str = "") -> str:
    return (
        "How do you want to ratify?\n"
        "❯ 1. Yes, run /livespec:revise\n"
        "  2. No, ask the operator\n"
        "Enter to select · ↑/↓ to navigate · Esc to cancel\n"
        f"{tail}"
        f"  Opus 4.8 (1M context) | /x/repo | Ctx: {ctx}% left\n"
    )


def install_picker_paste_echo(*, fake: FakeTmux) -> None:
    fake.on_paste = lambda session, text: echo_picker_paste(fake=fake, session=session, text=text)


def echo_picker_paste(*, fake: FakeTmux, session: str, text: str) -> None:
    val = fake.panes.get(session, "")
    display_text = text.splitlines()[0]
    if isinstance(val, str) and ("\n❯ 1." in val or "\n› 1." in val):
        fake.panes[session] = f"{val}{display_text}\n"


def make_stalled_picker_case(
    *,
    tmp_path: Path,
    monkeypatch,
    topic: str,
    install_echo: bool = False,
):
    monkeypatch.setattr(_supervisor_config, "PICKER_STALL_AFTER", 30.0)
    repo, _plan_topic = make_plan(tmp_path=tmp_path, topic=topic)
    session = topic
    fake = FakeTmux()
    if install_echo:
        install_picker_paste_echo(fake=fake)
    fake.serve(session=session, repo=repo, capture=picker_capture())
    clock = {"t": 1000.0}
    sup = make_supervisor(
        tmp_path=tmp_path,
        fake=fake,
        now=lambda: clock["t"],
        watch_repos=[str(repo)],
    )
    track = mapped_track(repo=repo, topic=topic, session=session)
    write_fresh_supervisor_state(repo=repo, topic=topic)
    return repo, fake, clock, sup, track, session


def advance_to_picker_stall(*, clock: dict[str, float], sup, track):
    assert sup.evaluate(track=track, act=True).status == "blocked:human"
    clock["t"] += 31.0
    return sup.evaluate(track=track, act=True)


def assert_no_picker_answer_or_restart(*, fake: FakeTmux) -> None:
    assert not any(
        call[0] == "keys" and call[2] in {"Enter", "1", "2", "Up", "Down"} for call in fake.calls
    )
    assert not fake.has(method="respawn")
    assert not fake.has(method="new")


def test_scenario_reserved_entity_picker_gets_one_reminder_without_selection_or_restart(
    *, tmp_path, monkeypatch
):
    topic = "picker-charter-supervisor"
    repo, fake, clock, sup, track, _session = make_stalled_picker_case(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        topic=topic,
    )

    with contextlib.redirect_stderr(_io.StringIO()):
        stalled = advance_to_picker_stall(clock=clock, sup=sup, track=track)
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
    assert signals.read_state(repo=str(repo), topic=topic) is None
    assert_no_picker_answer_or_restart(fake=fake)


def test_scenario_ordinary_worker_picker_is_promoted_and_alerted_but_not_pasted(
    *, tmp_path, monkeypatch
):
    cases = {}
    for topic in ("picker-charter-supervisor", "picker-charter-worker"):
        repo, fake, clock, sup, track, _session = make_stalled_picker_case(
            tmp_path=tmp_path,
            monkeypatch=monkeypatch,
            topic=topic,
        )
        with contextlib.redirect_stderr(_io.StringIO()) as err:
            stalled = advance_to_picker_stall(clock=clock, sup=sup, track=track)
        cases[topic] = repo, fake, stalled, err.getvalue()

    reserved_repo, reserved_fake, reserved_row, reserved_err = cases["picker-charter-supervisor"]
    ordinary_repo, ordinary_fake, ordinary_row, ordinary_err = cases["picker-charter-worker"]

    assert reserved_repo == ordinary_repo
    assert reserved_row.status == "picker-stalled"
    assert ordinary_row.status == "picker-stalled"
    assert ordinary_row.picker_open is True
    assert supervisor.needs_attention(row=ordinary_row) is True
    assert "picker stalled" in ordinary_err
    assert "picker stalled" in (ordinary_row.note or "")
    assert len(reserved_fake.paste_texts()) == 1
    assert ordinary_fake.paste_texts() == []
    assert reserved_err.count("picker stalled") == 1
    assert_no_picker_answer_or_restart(fake=ordinary_fake)


def test_scenario_charter_reminder_stays_single_shot_across_external_redraw(
    *, tmp_path, monkeypatch
):
    topic = "picker-charter-supervisor"
    _repo, fake, clock, sup, track, session = make_stalled_picker_case(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        topic=topic,
        install_echo=True,
    )

    with contextlib.redirect_stderr(_io.StringIO()):
        stalled = advance_to_picker_stall(clock=clock, sup=sup, track=track)
        echoed_capture = fake.panes[session]
        clock["t"] += 31.0
        still_stalled_after_echo = sup.evaluate(track=track, act=True)
        fake.panes[session] = picker_capture(ctx=79)
        still_stalled_after_redraw = sup.evaluate(track=track, act=True)
        clock["t"] += 31.0
        still_stalled_later = sup.evaluate(track=track, act=True)

    assert stalled.status == "picker-stalled"
    assert "Your supervisor charter already says:" in echoed_capture
    assert still_stalled_after_echo.status == "picker-stalled"
    assert still_stalled_after_redraw.status == "picker-stalled"
    assert still_stalled_later.status == "picker-stalled"
    assert len(fake.paste_texts()) == 1
    assert_no_picker_answer_or_restart(fake=fake)


def test_scenario_stalled_picker_publishes_promoted_status_with_human_wait_evidence(
    *, tmp_path, monkeypatch
):
    topic = "picker-charter-worker"
    status_path = tmp_path / "status.json"
    _repo, fake, clock, sup, track, _session = make_stalled_picker_case(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        topic=topic,
    )
    sup.status_path = str(status_path)
    registry.append_mapping(track=track, store_path=sup.store_path, added_at="t")

    with contextlib.redirect_stderr(_io.StringIO()):
        rows = sup.tick(act=True)
        clock["t"] += 31.0
        rows = sup.tick(act=True)

    row = next(item for item in rows if item.topic == topic)
    payload = _supervisor_snapshot.row_payload(sup=sup, row=row)
    document = json.loads(status_path.read_text(encoding="utf-8"))
    published = next(item for item in document["rows"] if item["topic"] == topic)

    assert row.status == "picker-stalled"
    assert row.human_wait is True
    assert row.picker_open is True
    assert row.stall_seconds >= 30
    assert payload["status"] == "picker-stalled"
    assert payload["human_wait"] is True
    assert payload["picker_open"] is True
    assert published["status"] == "picker-stalled"
    assert published["human_wait"] is True
    assert published["picker_open"] is True
    assert [item for item in rows if item.status == "blocked:human"] == []
    assert [item for item in rows if item.picker_open] == [row]
    assert supervisor.needs_attention(row=row) is True
    assert fake.paste_texts() == []
    assert_no_picker_answer_or_restart(fake=fake)
