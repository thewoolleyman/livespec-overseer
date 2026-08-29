"""The daemon-wide idle-nudge switch and its resolution seam (`overseer-4l5iph.1`).

Slice A of the idle-nudge configurability epic: `overseerd --idle-nudge {on,off}`, the
ONE resolution function the later per-track (B) and per-repo (C) slices extend, and the
boundary that keeps all of it away from the low-context path.

Two halves, and the second is the one that matters most:

  * the switch GOVERNS the idle-with-context keep-going nudge — a track idling above the
    wind-down threshold past the 1-hour floor is nudged under `on` and under the unset
    default, and is not nudged under `off`;
  * the switch REACHES NOTHING ELSE — the low-context wrap-up and the cardinal-rule
    restart-on-`ready` path carry no idle-nudge conditional and stay unconditional for
    every actively-driven plan.
"""

import importlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "overseer"))

import _supervisor_config
import registry
import signals
import supervisor
from test_supervisor_builders import (
    idle_capture,
    make_plan,
    make_supervisor,
    mapped_track,
    nudge_count,
    wrapup_count,
)
from test_supervisor_fakes import FakeTmux

from overseer import daemon

__all__: list[str] = []

PACKAGE_DIR = Path(supervisor.__file__).resolve().parent
SEAM_MODULE = "_supervisor_idle_nudge_policy"
# The three modules this slice puts explicitly OUT OF SCOPE: the low-context wrap-up
# and the cardinal-rule restart-on-`ready` get no off-switch, ever, for any track.
UNCONDITIONAL_MODULES = (
    "_supervisor_wrapup_injection.py",
    "_supervisor_ready.py",
    "_supervisor_restart.py",
)


@pytest.fixture(autouse=True)
def _isolate_cwd(*, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


def _idling_past_the_floor(*, tmp_path, **daemon_kwargs):
    """A track idling at an empty prompt well ABOVE the wind-down threshold, ticked once
    to stamp `idle_since` and then advanced past the 1-hour `IDLE_NUDGE_AFTER` floor — so
    the ONLY thing left standing between it and a keep-going nudge is the switch."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=73))
    clock = {"t": 1000.0}
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: clock["t"], **daemon_kwargs)
    sup.claude_status_by_session = {session: "idle"}
    track = mapped_track(repo=repo, topic=topic, session=session)
    sup.evaluate(track=track, act=True)
    clock["t"] += _supervisor_config.IDLE_NUDGE_AFTER + 1
    return sup, fake, track, repo, topic


def test_the_idle_nudge_gate_consults_exactly_one_resolution_function():
    """Slices B and C extend ONE function rather than re-plumbing the call site, so the
    decision gets its own module and `_supervisor_idle` reaches it exactly once."""
    module_path = PACKAGE_DIR / f"{SEAM_MODULE}.py"
    assert module_path.is_file(), (
        f"the idle-nudge decision needs one home ({SEAM_MODULE}.py) so the per-track "
        "and per-repo slices can extend it without touching the gate"
    )
    policy = importlib.import_module(SEAM_MODULE)
    assert policy.__all__ == ["resolve_idle_nudge"]
    idle_source = (PACKAGE_DIR / "_supervisor_idle.py").read_text(encoding="utf-8")
    assert idle_source.count("resolve_idle_nudge(") == 1, (
        "the idle-nudge gate must consult the resolution function at exactly ONE site; "
        "tri-state precedence belongs inside it, never inlined here"
    )


@pytest.mark.parametrize(
    ("daemon_kwargs", "expected_nudges"),
    [
        pytest.param({}, 1, id="flag-unset-preserves-the-nudge"),
        pytest.param({"idle_nudge": True}, 1, id="idle-nudge-on-preserves-the-nudge"),
        pytest.param({"idle_nudge": False}, 0, id="idle-nudge-off-suppresses-the-nudge"),
    ],
)
def test_the_daemon_wide_switch_governs_the_idle_with_context_nudge(
    *, tmp_path, daemon_kwargs, expected_nudges
):
    """One fixture, one variable: the same track idling above threshold past the floor is
    nudged under `on` and under the unset default, and NOT nudged under `off`. The row
    stays descriptive either way — the switch gates the keystroke exactly as the 1-hour
    floor does, it does not reclassify the track."""
    sup, fake, track, repo, topic = _idling_past_the_floor(tmp_path=tmp_path, **daemon_kwargs)
    view = sup.evaluate(track=track, act=True)
    assert view.status == "idle-with-context-left"
    assert nudge_count(fake=fake) == expected_nudges
    assert wrapup_count(fake=fake) == 0
    state = signals.read_state(repo=str(repo), topic=topic)
    if expected_nudges:
        assert state is not None and state.token == signals.STATE_IDLE_WITH_CONTEXT_LEFT
    else:
        # No paste means no daemon-written marker: a suppressed episode is not a
        # "handled" one, so flipping the switch back on re-arms it immediately.
        assert state is None


def test_the_gate_hands_the_seam_the_track_it_is_deciding_about(*, tmp_path, monkeypatch):
    """The call site passes the track, which is what slices B (per-track override) and C
    (per-repo override) need — patching the seam to refuse suppresses the nudge, proving
    the gate reads the resolution rather than re-deriving the decision for itself."""
    policy = importlib.import_module(SEAM_MODULE)
    sup, fake, track, _repo, _topic = _idling_past_the_floor(tmp_path=tmp_path)
    seen: list[tuple[object, object]] = []

    def _refuse(*, sup, track):
        seen.append((sup, track))
        return False

    monkeypatch.setattr(policy, "resolve_idle_nudge", _refuse)
    assert sup.evaluate(track=track, act=True).status == "idle-with-context-left"
    assert nudge_count(fake=fake) == 0
    assert seen == [(sup, track)]


def test_the_low_context_wrapup_and_restart_path_carries_no_idle_nudge_conditional():
    """OUT OF SCOPE by construction: a session that has run its context down must still
    be wound up and restarted on its own `ready`, whatever an operator thinks of being
    poked while idle. No off-switch may reach these three modules."""
    for name in UNCONDITIONAL_MODULES:
        source = (PACKAGE_DIR / name).read_text(encoding="utf-8")
        assert "idle_nudge" not in source, (
            f"{name} must stay unconditional for every actively-driven plan; the "
            "idle-nudge switch governs the keep-going nudge and nothing else"
        )


def test_idle_nudge_off_still_wraps_up_a_track_below_the_threshold(*, tmp_path):
    """The behavioural half of the boundary above: with the switch OFF, a track at 40%
    against the default 50% threshold is still warned and still gets the wrap-up."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=40))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, idle_nudge=False)
    view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)
    assert view.status == "warned"
    assert wrapup_count(fake=fake) == 1
    assert nudge_count(fake=fake) == 0


def test_run_daemon_threads_idle_nudge_into_the_supervisor(*, monkeypatch):
    """`run_daemon(idle_nudge=...)` sets the built Supervisor's field; the default is on,
    so an `overseerd` launched without the flag behaves exactly as it always has."""
    seen: list[bool] = []

    class _Sup:
        idle_nudge = True
        warn_percent = registry.DEFAULT_CTX_THRESHOLD

        def run(self, *, interval, once, recover):
            del interval, once, recover
            seen.append(self.idle_nudge)

    monkeypatch.setattr(supervisor, "build_supervisor", lambda: _Sup())
    assert supervisor.run_daemon(idle_nudge=False) == 0
    assert supervisor.run_daemon() == 0
    assert seen == [False, True]


def test_overseerd_parses_idle_nudge_and_threads_it_into_run_daemon(*, tmp_path, monkeypatch):
    """`overseerd --idle-nudge {on,off}` is the daemon-wide switch; an absent flag passes
    the `on` default, so an operator who never types it keeps today's behaviour exactly,
    and anything outside the two-value vocabulary is rejected by argparse rather than
    quietly read as one of them."""
    seen: dict[str, object] = {}

    def _fake_run(*, warn_percent=None, idle_nudge=True):
        del warn_percent
        seen["idle_nudge"] = idle_nudge
        return 0

    monkeypatch.setattr(
        daemon, "_default_daemon_log_path", lambda: tmp_path / "daemon.log", raising=False
    )
    monkeypatch.setattr(daemon.supervisor, "run_daemon", _fake_run)

    assert daemon.main(argv=[]) == 0
    assert seen["idle_nudge"] is True
    assert daemon.main(argv=["--idle-nudge", "on"]) == 0
    assert seen["idle_nudge"] is True
    assert daemon.main(argv=["--idle-nudge", "off"]) == 0
    assert seen["idle_nudge"] is False
    for bad in (["--idle-nudge", "sometimes"], ["--idle-nudge"]):
        with pytest.raises(SystemExit):
            daemon.main(argv=bad)


def test_overseerd_help_documents_the_idle_nudge_switch(*, capsys, tmp_path, monkeypatch):
    """A source-free operator must be able to find the switch AND its boundary: the help
    has to say that the low-context wrap-up is unaffected, or `off` reads as "the daemon
    stops keystroking me", which is not what it does."""
    monkeypatch.setattr(
        daemon, "_default_daemon_log_path", lambda: tmp_path / "daemon.log", raising=False
    )

    with pytest.raises(SystemExit) as exc_info:
        daemon.main(argv=["--help"])

    assert exc_info.value.code == 0
    help_text = capsys.readouterr().out
    assert "--idle-nudge {on,off}" in help_text
    assert "default on" in help_text
    assert "wrap-up" in help_text
