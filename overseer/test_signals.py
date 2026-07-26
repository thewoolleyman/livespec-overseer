"""Tests for signals.py — pure pane parsing + marker certification.

``import signals`` resolves via conftest.py. The two adversarial-critical
behaviors are tested hard: ``parse_ctx_remaining`` anchoring (design blocker #5)
and the ``ready_marker_valid`` certification (presence + freshness only — the
marker's contents are no longer inspected; markers live under
``<repo>/tmp/overseer/``).

Split at the section banner this file already carried, when it crossed the
200-LLOC soft ceiling: the process-identity helpers moved to
`test_signals_process_identity.py` and the shared track builders to
`test_signals_fakes.py`, leaving this module the pane-text parsers and the marker
certification.
"""

from pathlib import Path

import pytest
import signals
from test_signals_fakes import declare_state, setup_track

__all__: list[str] = []


@pytest.fixture(autouse=True)
def _isolate_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


# --------------------------------------------------------------------------- #
# strip_ansi.
# --------------------------------------------------------------------------- #


def test_strip_ansi_removes_csi_sequences():
    coloured = "\x1b[38;5;244mCtx: 73% left\x1b[0m"
    assert signals.strip_ansi(text=coloured) == "Ctx: 73% left"


# --------------------------------------------------------------------------- #
# parse_ctx_remaining — anchored + fail-closed (blocker #5).
# --------------------------------------------------------------------------- #


def test_parse_ctx_reads_last_status_row():
    capture = "some earlier output\n\n  Ctx: 73% left\n"
    assert signals.parse_ctx_remaining(capture_text=capture) == 73


def test_parse_ctx_takes_last_match_on_the_row():
    # A row with two matches → the LAST wins.
    capture = "Ctx: 90% left   Ctx: 42% left\n"
    assert signals.parse_ctx_remaining(capture_text=capture) == 42


def test_parse_ctx_ignores_body_when_last_line_is_a_normal_prompt():
    """ADVERSARIAL (blocker #5): the BODY contains 'Ctx: 5% left' (e.g. the
    design doc scrolled by) far ABOVE the bottom rows, while the bottom
    statusline carries no Ctx (a fresh session). The bounded last-rows scan must
    NOT reach the stray body match — result None, not a false 5%."""
    capture = (
        "The design doc says the statusline prints Ctx: 5% left near the end.\n"
        "filler A\nfiller B\nfiller C\nfiller D\n"
        + ("─" * 40)
        + "\n❯ \n"
        + ("─" * 40)
        + "\n  Opus 4.8 (1M context) | /x/repo\n"
        + "  ⏵⏵ bypass permissions on (shift+tab to cycle)\n"
    )
    assert signals.parse_ctx_remaining(capture_text=capture) is None


def test_parse_ctx_reads_statusline_above_the_hint_line():
    """REGRESSION (live 2026-07-13): the statusline is the SECOND-to-last row —
    a footer hint renders BELOW it — so reading only the LAST row returns None.
    The bounded last-rows scan must still find the real 73%."""
    assert signals.parse_ctx_remaining(capture_text=_IDLE_CAPTURE) == 73


def test_parse_ctx_reads_status_row_not_body_ctx():
    """ADVERSARIAL: body carries 'Ctx: 5% left', but the actual statusline row
    (last non-empty) says 73% — must return 73, never 5."""
    capture = (
        "quoting the doc: Ctx: 5% left appears in page content\n"
        "\x1b[2m~/repo  main  Ctx: 73% left\x1b[0m\n"
    )
    assert signals.parse_ctx_remaining(capture_text=capture) == 73


def test_parse_ctx_none_when_no_match_anywhere():
    assert signals.parse_ctx_remaining(capture_text="just a normal prompt\n> \n") is None


def test_parse_ctx_none_on_empty_capture():
    assert signals.parse_ctx_remaining(capture_text="") is None
    assert signals.parse_ctx_remaining(capture_text="\n\n   \n") is None


def test_parse_ctx_skips_trailing_blank_lines_to_find_status_row():
    capture = "  Ctx: 12% left\n\n\n"  # blank lines after the status row
    assert signals.parse_ctx_remaining(capture_text=capture) == 12


# --------------------------------------------------------------------------- #
# is_busy.
# --------------------------------------------------------------------------- #


def test_is_busy_markers():
    assert signals.is_busy(capture_text="... esc to interrupt ...") is True
    assert signals.is_busy(capture_text="Waiting for 3 background tasks") is True
    # The real active-generation spinner (verified live 2026-07-13): a spinner
    # line carrying a token counter / dot-delimited elapsed / hook phase.
    assert (
        signals.is_busy(capture_text="✻ Galloping… (running stop hooks… 1/3 · 24s · ↓ 1.4k tokens)")
        is True
    )
    # The lingering completed-turn summary is deliberately NOT busy.
    assert signals.is_busy(capture_text="✻ Brewed for 25s") is False
    # A plain idle capture is not busy.
    assert signals.is_busy(capture_text=_IDLE_CAPTURE) is False


def test_is_busy_false_when_idle():
    assert signals.is_busy(capture_text="> \n  ? for shortcuts\n") is False
    # A prose 'background' with no count must not trip the waiting marker.
    assert signals.is_busy(capture_text="thinking about background context") is False


# --------------------------------------------------------------------------- #
# is_structured_gate.
# --------------------------------------------------------------------------- #


def test_is_structured_gate_detects_permission_and_picker():
    permission = "Do you want to proceed?\n❯ 1. Yes\n  2. No\n"
    assert signals.is_structured_gate(capture_text=permission) is True
    picker = "Choose an option\n❯ 1. Alpha\n  2. Beta\n"
    assert signals.is_structured_gate(capture_text=picker) is True


def test_is_structured_gate_false_for_plain_numbered_list():
    # A numbered list in normal output (no cursor, no permission question)
    # must NOT read as a gate.
    plain = "Steps:\n1. do this\n2. do that\n> \n"
    assert signals.is_structured_gate(capture_text=plain) is False


# --------------------------------------------------------------------------- #
# is_idle_input — verified idle (not "just not busy").
# --------------------------------------------------------------------------- #

# The REAL live Claude TUI idle shape (verified 2026-07-13): an empty `❯` prompt
# between two horizontal rule lines, the statusline as the SECOND-to-last row,
# and a footer hint LAST (NOT a `╭─╮` box + `? for shortcuts`).
_IDLE_CAPTURE = (
    "● prior response\n"
    + ("─" * 40)
    + "\n❯ \n"
    + ("─" * 40)
    + "\n  Opus 4.8 (1M context) | /x/repo | Ctx: 73% left\n"
    + "  ⏵⏵ bypass permissions on (shift+tab to cycle) · ← for agents\n"
)


def test_is_idle_input_true_for_verified_idle():
    assert signals.is_idle_input(capture_text=_IDLE_CAPTURE) is True


def test_is_idle_input_false_when_busy():
    busy = "╭──────────╮\n│ > run    │\n╰──────────╯\n  esc to interrupt\n"
    assert signals.is_idle_input(capture_text=busy) is False


def test_is_idle_input_false_when_gate():
    gated = "Do you want to proceed?\n❯ 1. Yes\n  2. No\n  ? for shortcuts\n"
    assert signals.is_idle_input(capture_text=gated) is False


def test_is_idle_input_false_for_blank_pane():
    # 'Not busy' alone is NOT idle-input — a blank pane has no prompt box.
    assert signals.is_idle_input(capture_text="") is False
    assert signals.is_idle_input(capture_text="some stale scrollback with no box\n") is False


# --------------------------------------------------------------------------- #
# ready_marker_valid — the load-bearing three-way certification.
# --------------------------------------------------------------------------- #


def test_state_path_is_under_tmp_overseer_never_plan(tmp_path):
    """The ONE indicator file resolves under ``<repo>/tmp/overseer/<topic>/``, not plan/."""
    repo = str(tmp_path / "repo")
    topic = "mytopic"
    expected_dir = Path(repo) / "tmp" / "overseer" / topic
    assert signals.marker_dir(repo, topic) == expected_dir
    assert signals.state_path(repo=repo, topic=topic) == expected_dir / ".overseer-state"
    # The overseer never writes under a session's plan/ tree.
    assert "plan" not in signals.state_path(repo=repo, topic=topic).parts


def test_read_state_parses_token_and_detail(tmp_path):
    """`<token>` or `<token>: <detail>` — the detail carries a blocked reason."""
    repo, topic = setup_track(tmp_path)
    declare_state(repo, topic, "ready\n", mtime=1001.0)
    st = signals.read_state(repo=str(repo), topic=topic)
    assert st is not None and st.token == "ready" and st.detail == ""

    declare_state(repo, topic, "blocked: waiting on the schema call\n", mtime=1002.0)
    st = signals.read_state(repo=str(repo), topic=topic)
    assert st is not None and st.token == "blocked"
    assert st.detail == "waiting on the schema call"

    declare_state(repo, topic, "  WINDING-DOWN  \n", mtime=1003.0)  # tolerant: case + whitespace
    st = signals.read_state(repo=str(repo), topic=topic)
    assert st is not None and st.token == "winding-down"


def test_read_state_none_when_absent_and_token_validity(tmp_path):
    repo, topic = setup_track(tmp_path)
    assert signals.read_state(repo=str(repo), topic=topic) is None  # absent → None (fail-closed)
    for good in signals.STATE_TOKENS:
        assert signals.valid_token(token=good) is True
    assert signals.valid_token(token="redy") is False  # a typo is NOT a state
    # A malformed value is still RETURNED (so the daemon can surface it), just invalid.
    declare_state(repo, topic, "redy\n", mtime=1001.0)
    st = signals.read_state(repo=str(repo), topic=topic)
    assert st is not None and st.token == "redy" and signals.valid_token(token=st.token) is False


def test_ready_valid_only_on_a_fresh_ready_declaration(tmp_path):
    """`ready` is the SOLE restart authorization, and only when it is THIS round's."""
    repo, topic = setup_track(tmp_path)
    declare_state(repo, topic, "ready\n", mtime=1001.0)  # newer than the stamp
    assert signals.ready_valid(repo=str(repo), topic=topic, injection_stamp=1000.0) is True


def test_ready_valid_false_when_absent_stale_unstamped_or_other_value(tmp_path):
    """Fail-closed on every path that is not an unambiguous, this-round `ready`."""
    repo, topic = setup_track(tmp_path)
    # 1. Nothing declared at all — the severe-bug case: idleness is NEVER readiness.
    assert signals.ready_valid(repo=str(repo), topic=topic, injection_stamp=1000.0) is False
    # 2. Declared `ready`, but STALE (older than this round's injection stamp).
    declare_state(repo, topic, "ready\n", mtime=999.0)
    assert signals.ready_valid(repo=str(repo), topic=topic, injection_stamp=1000.0) is False
    # 3. Fresh `ready`, but NO injection this round → nothing to certify.
    declare_state(repo, topic, "ready\n", mtime=1001.0)
    assert signals.ready_valid(repo=str(repo), topic=topic, injection_stamp=None) is False
    # 4. The other two values are NOT readiness — one file, so they REPLACE `ready`.
    for other in ("blocked: needs a human", "winding-down"):
        declare_state(repo, topic, other + "\n", mtime=1001.0)
        assert signals.ready_valid(repo=str(repo), topic=topic, injection_stamp=1000.0) is False
    # 5. A typo'd value is not readiness either.
    declare_state(repo, topic, "redy\n", mtime=1001.0)
    assert signals.ready_valid(repo=str(repo), topic=topic, injection_stamp=1000.0) is False
