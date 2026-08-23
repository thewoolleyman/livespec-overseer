"""Regression tests for picker detection that ignores quoted markers in scrollback."""

import registry
import signals
from test_supervisor_builders import idle_capture, make_plan, make_supervisor, mapped_track
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []


def live_picker_capture(*, ctx: int = 80) -> str:
    return (
        "How should this session proceed?\n"
        "❯ 1. Continue with the recorded next action\n"
        "  2. Ask the maintainer\n"
        "  Use ↑/↓ to select, Enter to confirm\n"
        f"  Opus 4.8 (1M context) | /x/repo | Ctx: {ctx}% left\n"
    )


def quoted_picker_capture(*, ctx: int = 80) -> str:
    body = (
        "I inspected the peer pane and it quoted these rendered picker markers:\n"
        "☐ waiting on a human\n"
        "❯ 1. Continue with the recorded next action\n"
        "  Use ↑/↓ to select, Enter to confirm\n"
        "Those markers belong to the peer; this pane is now back at a normal prompt."
    )
    return idle_capture(ctx=ctx, body=body)


def test_structured_gate_keys_on_tail_region_not_quoted_scrollback() -> None:
    assert signals.is_structured_gate(capture_text=live_picker_capture()) is True
    assert signals.is_structured_gate(capture_text=quoted_picker_capture()) is False
    assert signals.is_structured_gate(capture_text=idle_capture(ctx=80)) is False


def test_quoted_picker_markers_do_not_raise_picker_open_or_human_wait(*, tmp_path) -> None:
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=quoted_picker_capture())
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    track = mapped_track(repo=repo, topic=topic, session=session)

    row = sup.evaluate(track=track, act=False)

    assert row.picker_open is False
    assert row.human_wait is False
    assert row.status != "blocked:human"


def test_live_tail_picker_still_raises_picker_open_and_human_wait(*, tmp_path) -> None:
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=live_picker_capture())
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    track = mapped_track(repo=repo, topic=topic, session=session)

    row = sup.evaluate(track=track, act=False)

    assert row.status == "blocked:human"
    assert row.picker_open is True
    assert row.human_wait is True
