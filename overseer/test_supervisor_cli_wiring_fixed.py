"""Beside-tests for supervisor.py — cli wiring fixed.

Split from `test_supervisor.py`, which carried the whole daemon surface at 3010 LLOC
after its shared helpers were extracted — still more than twelve times the 250-LLOC
hard ceiling. The doubles and builders live in `test_supervisor_fakes` /
`test_supervisor_builders`; this module holds only tests.

``import supervisor`` resolves via conftest.py.
"""

import contextlib
import io as _io

import pytest
import registry
import signals
import supervisor
from test_supervisor_builders import (
    adopt_sup,
    arm_ready_marker,
    declare,
    idle_capture,
    isolate_store,
    make_plan,
    make_supervisor,
    mapped_track,
    wrapup_count,
    write_session,
)
from test_supervisor_fakes import (
    FakeTmux,
)


@pytest.fixture(autouse=True)
def _isolate_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


def test_cli_adopt_reports_every_adopted_session_and_the_total(monkeypatch, capsys):
    """`overseer adopt` names each newly-adopted session with its (repo, topic) and then
    reports the count — the operator's confirmation that a hand-started session is now
    supervised."""
    adopted = [
        registry.Track(topic="alpha", repo="/x/repo_a", tmux="sesA"),
        registry.Track(topic="beta", repo="/x/repo_b", tmux="sesB"),
    ]

    class _AdoptOnlySup:
        def adopt_sessions(self):
            return adopted

    monkeypatch.setattr(supervisor, "build_supervisor", lambda: _AdoptOnlySup())

    assert supervisor.main(["adopt"]) == 0

    out = capsys.readouterr().out
    assert "adopted sesA → /x/repo_a::alpha" in out
    assert "adopted sesB → /x/repo_b::beta" in out
    assert "adopted 2 existing session(s)" in out


def test_cli_start_fails_when_the_tmux_session_cannot_be_created(tmp_path, monkeypatch, capsys):
    """Codex re-review #3: `new-session` failing must abort `start` with a nonzero exit —
    proceeding to `_do_launch` would respawn whatever the bare name prefix-matched. And a
    start that never launched must leave NO mapping row claiming it did."""
    repo, topic = make_plan(tmp_path)
    session = registry.tmux_id(str(repo), topic)
    store = isolate_store(tmp_path, monkeypatch)
    fake = FakeTmux()  # session absent
    fake.new_session_ok = False
    monkeypatch.setattr(supervisor.tmuxio, "TmuxIO", lambda: fake)

    assert supervisor.main(["start", "--repo", str(repo), "--topic", topic]) == 1
    assert ("new", session, str(repo)) in fake.calls
    assert not fake.has("respawn")  # never respawned a prefix-matched sibling
    assert "could not create tmux session" in capsys.readouterr().err
    assert registry.read_mapping(store) == []  # nothing mapped


def test_cli_start_fails_when_the_launch_does_not_land(tmp_path, monkeypatch, capsys):
    """B5 at the CLI: `_do_launch` returning False exits nonzero and reports, rather than
    printing `started …` for a session that never came up — and again maps nothing."""
    repo, topic = make_plan(tmp_path)
    session = registry.tmux_id(str(repo), topic)
    store = isolate_store(tmp_path, monkeypatch)
    fake = FakeTmux()  # session absent → created, then the respawn fails
    fake.respawn_ok = False
    monkeypatch.setattr(supervisor.tmuxio, "TmuxIO", lambda: fake)

    assert supervisor.main(["start", "--repo", str(repo), "--topic", topic]) == 1
    assert ("new", session, str(repo)) in fake.calls
    assert fake.has("respawn")

    err = capsys.readouterr().err
    assert "start FAILED to launch" in err and session in err
    assert registry.read_mapping(store) == []  # nothing mapped


# --------------------------------------------------------------------------- #
# The read-only render (`/overseer list` → `tick(act=False)`) must DERIVE every
# status the daemon would while performing NO side effect: no paste, no respawn,
# no alert, no injection stamp, and no marker written or retired. Each test below
# picks a branch whose act=True twin is already covered and pins the act=False
# side. `list` runs against a LIVE daemon's store, so a side effect leaking into
# it is exactly the bug these close.
# --------------------------------------------------------------------------- #


def test_read_only_list_reports_a_malformed_state_file_without_alerting(tmp_path):
    """A typo'd declaration still shows in the row's note under `list`, but the operator
    ALERT is an event-history line the DAEMON owns — emitting it from the read-only render
    would re-spam the log on every `list`."""
    repo, topic = make_plan(tmp_path)
    session = registry.tmux_id(str(repo), topic)
    fake = FakeTmux()
    fake.serve(session, repo, capture=idle_capture(ctx=30))
    sup = make_supervisor(tmp_path, fake)
    registry.write_injection_stamp(str(repo), topic, 1000.0, sup.stamp_path)
    declare(repo, topic, "redy", mtime=1001.0)  # typo
    err = _io.StringIO()

    with contextlib.redirect_stderr(err):
        view = sup.evaluate(mapped_track(repo, topic, session), act=False)

    assert view.note is not None and "redy" in view.note  # the operator still sees it
    assert "MALFORMED state file" not in err.getvalue()  # but no alert was emitted
    assert not fake.has("paste")
    assert not fake.has("respawn")


def test_read_only_list_reports_working_without_retiring_a_stale_block(tmp_path):
    """A `blocked:` a generating session has outlived is retired by the DAEMON (it deletes
    the marker). `list` must render the same `working` row carrying that reason and leave
    the marker on disk — retiring it is a filesystem mutation, and the teeth here are that
    the identical act=True tick DOES void it."""
    repo, topic = make_plan(tmp_path)
    session = registry.tmux_id(str(repo), topic)
    fake = FakeTmux()
    fake.serve(session, repo, capture="esc to interrupt\n  Ctx: 40% left\n")  # generating
    sup = make_supervisor(tmp_path, fake)
    declare(repo, topic, "blocked: waiting on a human", mtime=1.0)  # far past the grace
    track = mapped_track(repo, topic, session)

    view = sup.evaluate(track, act=False)

    assert view.status == "working"
    assert view.note is not None and "waiting on a human" in view.note  # reason still shown
    state = signals.read_state(str(repo), topic)
    assert state is not None and state.token == signals.STATE_BLOCKED  # marker untouched

    # Teeth: the SAME tick with act=True is the one allowed to retire it.
    with contextlib.redirect_stderr(_io.StringIO()):
        assert sup.evaluate(track, act=True).note is None
    assert signals.read_state(str(repo), topic) is None


def test_read_only_list_reports_restarting_without_respawning(tmp_path):
    """`restarting` is a DERIVED status — the row shows what the daemon would do next. Under
    `list` no respawn may fire and the `ready` declaration + round must survive intact, or a
    read-only render would have consumed the session's one restart authorization."""
    repo, topic = make_plan(tmp_path)
    session = registry.tmux_id(str(repo), topic)
    fake = FakeTmux()
    fake.serve(session, repo, capture=idle_capture(ctx=30))
    sup = make_supervisor(tmp_path, fake)
    registry.write_injection_stamp(str(repo), topic, 1000.0, sup.stamp_path)
    marker = arm_ready_marker(repo, topic, mtime=1001.0)

    view = sup.evaluate(mapped_track(repo, topic, session), act=False)

    assert view.status == "restarting"
    assert not fake.has("respawn")  # the session was NOT killed by a `list`
    assert not fake.has("paste")
    assert marker.exists()  # the authorization survives for the daemon's own tick
    assert registry.read_injection_stamp(str(repo), topic, sup.stamp_path) == 1000.0


def test_read_only_list_reports_danger_without_injecting_or_alerting(tmp_path):
    """At/below the danger line the daemon injects a wrap-up and alerts that the track is
    NOT RESPONDING. `list` shows the same `danger` row and does neither — and above all
    opens no injection round, which would move the certification anchor a later `ready`
    is compared against."""
    repo, topic = make_plan(tmp_path)
    session = registry.tmux_id(str(repo), topic)
    fake = FakeTmux()
    fake.serve(session, repo, capture=idle_capture(ctx=15))  # <= DANGER_CTX_REMAINING
    sup = make_supervisor(tmp_path, fake)
    err = _io.StringIO()

    with contextlib.redirect_stderr(err):
        view = sup.evaluate(mapped_track(repo, topic, session), act=False)

    assert view.status == "danger"
    assert err.getvalue() == ""  # no NOT RESPONDING alert from a read-only render
    assert wrapup_count(fake) == 0  # and nothing keystroked
    assert registry.read_injection_stamp(str(repo), topic, sup.stamp_path) is None


# --------------------------------------------------------------------------- #
# Remaining single-branch edges: an unreported self-status, a failed paste in an
# ALREADY-open round, a failed window rename, and `start` on a proven-dead pane.
# --------------------------------------------------------------------------- #


def test_live_outside_tmux_note_omits_the_suffix_when_no_status_is_reported(tmp_path):
    """The live-outside-tmux note appends Claude's own self-reported status only when the
    registry actually carries one. With none reported the note stops at the pid — never a
    dangling `self-reported status ` with nothing after it."""
    repo, topic = make_plan(tmp_path)
    session = registry.tmux_id(str(repo), topic)
    fake = FakeTmux()  # mapped tmux session absent → routes to the no-managed-pane row
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    write_session(sessions_dir, 100, name=topic, cwd=str(repo), status="")  # no self-report
    sup = adopt_sup(tmp_path, fake, sessions_dir, {}, {100: "pt"})

    view = sup.evaluate(mapped_track(repo, topic, session), act=True)

    assert view.status == "live-outside-tmux"
    assert view.note == (
        "live Claude session (pid 100) running OUTSIDE tmux — daemon cannot manage it"
    )
    assert "self-reported status" not in view.note


def test_failed_paste_in_an_already_open_round_keeps_the_rounds_stamp(tmp_path):
    """The rollback on a failed wrap-up paste applies ONLY to a round this tick just
    OPENED. A re-warn at a lower band runs inside a round opened earlier, and clearing that
    round's `at` would reset the anchor `ready_valid` compares a declaration against — so
    the stamp is left alone and only the alert fires."""
    repo, topic = make_plan(tmp_path)
    session = registry.tmux_id(str(repo), topic)
    fake = FakeTmux()
    fake.serve(session, repo, capture=idle_capture(ctx=40))  # a LOWER band than 50
    fake.paste_ok = False  # the re-warn paste does not land
    sup = make_supervisor(tmp_path, fake, warn_percent=50)
    registry.write_injection_stamp(str(repo), topic, 1000.0, sup.stamp_path)  # round ALREADY open
    registry.add_notified_band(str(repo), topic, 50, sup.stamp_path)  # the 50 band already sent
    err = _io.StringIO()

    with contextlib.redirect_stderr(err):
        sup.evaluate(mapped_track(repo, topic, session), act=True)

    assert "wrap-up injection FAILED" in err.getvalue()
    assert registry.read_injection_stamp(str(repo), topic, sup.stamp_path) == 1000.0  # kept
    # The undelivered band is NOT marked notified, so the next tick re-tries it.
    assert 40 not in set(registry.read_notified_bands(str(repo), topic, sup.stamp_path))
