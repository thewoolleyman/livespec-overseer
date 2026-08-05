"""Tests for signals.py — the process-identity helpers.

Split out of `test_signals.py` at the section banner it already carried, when that
module crossed the 200-LLOC soft ceiling. A file in the 201-250 band passes the
hard gate but hard-fails a RELEASE, via the always-on `check-no-lloc-soft-warnings`
under `LIVESPEC_FAIL_IF_LLOC_SOFT_WARNINGS_EXIST` — which CI sets for the release
context. The pane-text parsers and the marker certification stay in
`test_signals.py`.

``import signals`` resolves via conftest.py.
"""

import pytest
import signals
from test_signals_fakes import declare_state, setup_track

__all__: list[str] = []


@pytest.fixture(autouse=True)
def _isolate_cwd(*, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


# --------------------------------------------------------------------------- #
# Process-identity helpers.
# --------------------------------------------------------------------------- #


def test_pane_is_claude_and_shell():
    assert signals.pane_is_claude(pane_current_command="node") is True
    assert signals.pane_is_claude(pane_current_command="claude") is True
    assert signals.pane_is_claude(pane_current_command="zsh") is False
    assert signals.pane_is_claude(pane_current_command=None) is False
    assert signals.pane_is_shell(pane_current_command="zsh") is True
    assert signals.pane_is_shell(pane_current_command="bash") is True
    assert signals.pane_is_shell(pane_current_command="node") is False


def test_path_in_repo():
    repo = "/data/projects/livespec"
    assert (
        signals.path_in_repo(pane_current_path="/data/projects/livespec", repo=repo) is True
    )  # equal
    assert (
        signals.path_in_repo(pane_current_path="/data/projects/livespec/plan/x", repo=repo) is True
    )  # inside
    # Sibling-prefix trap: '/data/projects/livespec-other' is NOT inside.
    assert (
        signals.path_in_repo(pane_current_path="/data/projects/livespec-other", repo=repo) is False
    )
    assert signals.path_in_repo(pane_current_path="/somewhere/else", repo=repo) is False
    assert signals.path_in_repo(pane_current_path=None, repo=repo) is False


def test_is_idle_input_accepts_renamed_titled_border():
    # B2: `claude -n <topic>` renders the session name INTO the top border
    # (`─── mytopic ──`), which is NOT a pure rule. is_idle_input must still detect
    # the idle box, else every daemon-renamed session becomes unmanageable.
    rule = "─" * 40
    titled = ("─" * 20) + " mytopic ──"
    renamed = f"● prior\n{titled}\n❯ \n{rule}\n  Opus | /r | Ctx: 40% left\n  ? for shortcuts\n"
    assert signals.is_idle_input(capture_text=renamed) is True
    assert signals.input_box_ready(capture_text=renamed) is True


def test_is_idle_input_rejects_prose_around_empty_prompt():
    # Guard: an empty `❯` between ordinary prose lines (no box borders) is NOT idle.
    prose = "● Read 1 file\n❯ \nSome narration line.\n"
    assert signals.is_idle_input(capture_text=prose) is False


def test_parse_ctx_reads_both_runtimes_own_statuslines():
    """Each runtime renders ITS OWN computed context-left; the daemon reads that number
    rather than recomputing occupancy.

    Codex says `Context N% left`, Claude says `Ctx: N% left`. An earlier cut computed
    Codex's ctx from its rollout's `token_count` events and was WRONG by 2-4 points
    against Codex's own display (62 vs 66, 36 vs 38 — verified live 2026-07-17), because
    that reimplements codex-rs's private occupancy formula (a ~12k baseline, reasoning
    tokens excluded). Reading the runtime's own number cannot drift that way.
    """
    claude_pane = "\n".join(["irrelevant", "", "Ctx: 42% left", "? for shortcuts"])
    codex_pane = "\n".join(
        [
            "irrelevant",
            "",
            "\u203a Find and fix a bug in @filename",
            "",
            "  gpt-5.5 high \u00b7 /data/projects/x \u00b7 Context 66% left \u00b7 some-topic",
        ]
    )
    assert signals.parse_ctx_remaining(capture_text=claude_pane) == 42
    assert signals.parse_ctx_remaining(capture_text=codex_pane) == 66


def test_pane_is_codex_is_loose_and_must_never_gate_alone():
    """`bun` is the codex pane's foreground process (the launcher; the codex binary is
    its child) — and it matches ANY bun app, so this predicate is deliberately loose and
    is only ever used PAIRED with an exact live-session-map lookup."""
    assert signals.pane_is_codex(pane_current_command="bun") is True
    assert signals.pane_is_codex(pane_current_command="codex") is True
    assert (
        signals.pane_is_codex(pane_current_command="node") is False
    )  # a Claude pane is never codex
    assert signals.pane_is_codex(pane_current_command="zsh") is False
    assert signals.pane_is_codex(pane_current_command=None) is False


def test_codex_prompt_present_requires_the_codex_statusline_not_just_the_glyph():
    """STRUCTURAL, never glyph-only: a `›` line alone is not a Codex TUI. Claude's own
    statusline says `Ctx: N% left`, Codex's says `Context N% left` — without the Codex
    form this must be False, or a Claude pane that happens to render a `›` (quoted text,
    a prompt char) would be driven through the Codex restart path."""
    claude_pane = "\n".join(
        [
            "● the doc quotes a codex line:",
            "› Find and fix a bug in @filename",
            "  Opus 4.8 | /x/repo | Ctx: 73% left",
            "  ? for shortcuts",
        ]
    )
    assert signals.codex_prompt_present(capture_text=claude_pane) is False
    assert signals.is_codex_idle_input(capture_text=claude_pane) is False


def test_is_codex_idle_input_false_while_the_codex_pane_is_busy():
    """A generating Codex pane still shows its `›` prompt AND its statusline, so the
    prompt check alone would call it idle. Busy must dominate — otherwise the daemon
    pastes the wrap-up into a session mid-generation."""
    busy_codex = "\n".join(
        [
            "✻ Working… (running tests… · 24s · ↓ 1.4k tokens)",
            "› ",
            "  gpt-5.5 high · /data/projects/x · Context 66% left · some-topic",
        ]
    )
    assert signals.codex_prompt_present(capture_text=busy_codex) is True  # the prompt IS present...
    assert signals.is_busy(capture_text=busy_codex) is True
    assert signals.is_codex_idle_input(capture_text=busy_codex) is False  # ...but busy wins


def test_read_state_is_none_when_the_state_file_is_unreadable(*, tmp_path, monkeypatch):
    """Fail-closed: a PRESENT but unreadable indicator reads as "no state", never raises —
    so an unreadable file can never authorize a restart (it is not a `ready`).

    Denial is injected at ``Path.read_text`` rather than via ``chmod``: CI runs its
    container steps as ROOT, where mode bits deny nothing, so a chmod-based version
    of this test passes locally and silently stops exercising the fail-closed branch
    in CI — which is worse than no test, because this branch is a SAFETY guard.
    """
    repo, topic = setup_track(tmp_path=tmp_path)
    declare_state(repo=repo, topic=topic, value="ready\n", mtime=1001.0)

    def _deny(self, *args, **kwargs):
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(signals.Path, "read_text", _deny)
    assert signals.read_state(repo=str(repo), topic=topic) is None
    assert (
        signals.ready_valid(
            repo=str(repo),
            topic=topic,
            certification_floor=1000.0,
            round_session_identity="claude:s:t",
            live_session_identity="claude:s:t",
        )
        is False
    )


def test_read_state_is_none_when_the_state_file_is_not_utf8(*, tmp_path):
    """Fail-closed on a NON-UTF-8 indicator — a different exception class from the
    unreadable case above, and one the sibling test does not reach.

    ``Path.read_text(encoding="utf-8")`` raises ``UnicodeDecodeError`` on undecodable
    bytes. That subclasses ``ValueError``, NOT ``OSError``, so an ``except OSError``
    handler does not catch it and the exception propagates out of ``read_state``.

    This matters beyond tidiness. The daemon's per-iteration broad catch used to
    absorb it — warn, keep supervising — but that catch is being removed under the
    "let it crash, systemd restarts" ruling. Without this boundary the daemon would
    exit on a corrupt indicator, systemd would restart it, the same bytes would be
    read again, and nothing would be supervised until a human intervened. A corrupt
    file is an ENVIRONMENTAL error, not a bug, so it fails soft here.

    Real bytes rather than a monkeypatch: this exercises the actual decode path, so
    it cannot pass by mocking a raise that the production code never performs.
    """
    repo, topic = setup_track(tmp_path=tmp_path)
    path = signals.state_path(repo=str(repo), topic=topic)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\xff\xferead" + b"y\n")

    assert signals.read_state(repo=str(repo), topic=topic) is None
    assert (
        signals.ready_valid(
            repo=str(repo),
            topic=topic,
            certification_floor=1000.0,
            round_session_identity="claude:s:t",
            live_session_identity="claude:s:t",
        )
        is False
    )


def test_only_a_shell_proves_a_pane_is_dead():
    """The rule `start`'s fail-closed guard relies on: proof of DEATH, not "not Claude".
    Enumerating the live runtimes did not scale to a second one — a live codex pane
    (`bun`) failed the Claude test and got respawn-killed."""
    assert signals.pane_is_shell(pane_current_command="zsh") is True
    for live_or_unknown in ("node", "claude", "bun", "codex", "vim", None):
        assert signals.pane_is_shell(pane_current_command=live_or_unknown) is False
