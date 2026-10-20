"""A picker taller than the gate tail still reads as a live structured gate.

`overseer-xe2mka`. Measured 2026-10-14 on 5.28.3: track `k3s-on-gmktec-for-vps-usage`
sat on a five-option `Continue?` picker whose every option carried a description line,
so the selected `❯ 1.` cursor was ELEVEN non-empty lines above the bottom of the pane.
`signals.is_structured_gate`'s fixed eight-line tail never saw it, and the row published
`settling` with `picker_open: false` for a session that was waiting on a human.
"""

import contextlib
import io as _io

import _supervisor_config
import registry
import signals
from test_picker_tail_gate_detection import quoted_picker_capture
from test_supervisor_builders import make_plan, make_supervisor, mapped_track
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []


def tall_picker_capture(*, ctx: int = 80) -> str:
    """The measured shape: every option carries a description, then the picker footer.

    Eleven non-empty lines sit below the `❯ 1.` cursor — five descriptions, four later
    options, the footer and the statusline — so the cursor is outside any fixed
    eight-line tail.
    """
    return (
        "How should this session proceed?\n"
        "❯ 1. Continue steps 1-4 (Recommended)\n"
        "     Finish the remaining work as planned\n"
        "  2. Stop here and hand off\n"
        "     Leave the rest for the next session\n"
        "  3. Ask the maintainer first\n"
        "     Escalate before touching anything\n"
        "  4. Re-plan the whole batch\n"
        "     Throw the current ordering away\n"
        "  5. Abort the pass\n"
        "     Discard the work in flight\n"
        "  Enter to select · ↑/↓ to navigate · Esc to cancel\n"
        f"  Opus 4.8 (1M context) | /x/repo | Ctx: {ctx}% left\n"
    )


def test_a_picker_taller_than_the_gate_tail_is_still_a_structured_gate() -> None:
    capture = tall_picker_capture()
    below_cursor = [line for line in capture.splitlines() if line.strip()]
    cursor = next(index for index, line in enumerate(below_cursor) if line.startswith("❯ 1."))

    assert len(below_cursor) - 1 - cursor == 11
    assert signals.is_structured_gate(capture_text=capture) is True
    # The `overseer-i6eu2k` control: markers merely QUOTED in prose above a live idle
    # input box must stay out of the gate, however the region is sized.
    assert signals.is_structured_gate(capture_text=quoted_picker_capture()) is False


def test_a_track_on_a_tall_picker_is_blocked_human_then_picker_stalled(
    *,
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(_supervisor_config, "PICKER_STALL_AFTER", 30.0)
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=tall_picker_capture())
    clock = {"t": 1000.0}
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: clock["t"])
    track = mapped_track(repo=repo, topic=topic, session=session)

    with contextlib.redirect_stderr(_io.StringIO()):
        waiting = sup.evaluate(track=track, act=True)
        clock["t"] += 40.0
        stalled = sup.evaluate(track=track, act=True)

    assert waiting.status == "blocked:human"
    assert waiting.picker_open is True
    assert waiting.human_wait is True
    assert stalled.status == "picker-stalled"
    assert stalled.picker_open is True


def test_a_tall_picker_is_never_pasted_into(*, tmp_path) -> None:
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=tall_picker_capture(ctx=80))
    clock = {"t": 1000.0}
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: clock["t"])
    track = mapped_track(repo=repo, topic=topic, session=session)

    with contextlib.redirect_stderr(_io.StringIO()):
        # Above threshold, where the keep-going nudge would otherwise come due once the
        # continuous-idle floor passes; then below it, where the wrap-up would.
        for _ in range(3):
            clock["t"] += _supervisor_config.IDLE_NUDGE_AFTER
            assert sup.evaluate(track=track, act=True).picker_open is True
        fake.panes[session] = tall_picker_capture(ctx=15)
        for _ in range(3):
            clock["t"] += 60.0
            assert sup.evaluate(track=track, act=True).picker_open is True

    assert fake.paste_texts() == []
    assert not any(call[0] == "keys" for call in fake.calls)
