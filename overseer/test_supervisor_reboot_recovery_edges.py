"""Beside-tests for supervisor.py — reboot recovery edges.

Split from `test_supervisor.py`, which carried the whole daemon surface at 3010 LLOC
after its shared helpers were extracted — still more than twelve times the 250-LLOC
hard ceiling. The doubles and builders live in `test_supervisor_fakes` /
`test_supervisor_builders`; this module holds only tests.

``import supervisor`` resolves via conftest.py.
"""

import contextlib
import io as _io
import json
from pathlib import Path

import _supervisor_config
import pytest
import registry
import supervisor
from test_supervisor_builders import (
    idle_capture,
    make_plan,
    make_supervisor,
    mapped_track,
    on_respawn,
)
from test_supervisor_fakes import (
    FakeTmux,
)

__all__: list[str] = []


@pytest.fixture(autouse=True)
def _isolate_cwd(*, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


def test_do_launch_is_false_when_the_pane_never_becomes_claude(*, tmp_path):
    """B5: a respawn that lands but never yields a live Claude TUI is a FAILED launch —
    False, and the resume line is never pasted into whatever is sitting there instead."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture())
    on_respawn(fake=fake, after=lambda s: fake.cmds.__setitem__(s, "zsh"))  # comes up a shell
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)

    assert (
        sup.do_launch(track=mapped_track(repo=repo, topic=topic, session=session), session=session)
        is False
    )
    assert fake.has(method="respawn")  # it did try...
    assert not fake.has(method="paste")  # ...but never pasted into the un-verified pane


# --------------------------------------------------------------------------- #
# The daemon loop: the per-store singleton lock, startup recovery, the sleep
# between ticks, and a clean exit on Ctrl-C.
# --------------------------------------------------------------------------- #


def test_run_refuses_to_start_when_another_daemon_holds_the_store_lock(*, tmp_path):
    """B6: two daemons on one store double-inject and double-restart — B's
    `respawn-pane -k` can kill the fresh session A just resumed. The second daemon
    surfaces the contended lock path and returns WITHOUT ticking."""
    holder = make_supervisor(tmp_path=tmp_path, fake=FakeTmux())
    handle = holder._acquire_singleton_lock()
    assert handle is not None
    try:
        sup = make_supervisor(tmp_path=tmp_path, fake=FakeTmux())  # same store path → same lock
        ticked = []
        sup.tick = lambda *, act: ticked.append(act)  # type: ignore[assignment]  # spy
        err = _io.StringIO()
        with contextlib.redirect_stderr(err):
            sup.run(once=True)
        assert ticked == []  # NO tick ran
        assert "refusing to start" in err.getvalue()
        assert str(sup._singleton_lock_path()) in err.getvalue()
    finally:
        supervisor.Supervisor._release_singleton_lock(handle=handle)


def test_singleton_lock_is_treated_as_contended_when_the_lockfile_cannot_be_created(*, tmp_path):
    """Fail-soft: any OSError acquiring the lock reads as CONTENDED (None), so a broken
    lock path refuses to start a second daemon rather than assuming it is alone."""
    sup = make_supervisor(tmp_path=tmp_path, fake=FakeTmux())
    blocker = tmp_path / "not-a-dir"
    blocker.write_text("a FILE where the store's parent dir belongs\n", encoding="utf-8")
    sup.store_path = str(blocker / "map.jsonl")  # mkdir of the parent must fail

    assert sup._acquire_singleton_lock() is None


def test_run_with_recover_recreates_missing_sessions_before_the_first_tick(*, tmp_path):
    """`run(recover=True)` performs startup recovery once, BEFORE the loop — so a
    post-reboot daemon has its mapped sessions back by the time the first tick renders."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()  # session absent → recovery recreates it
    fake.panes[session] = idle_capture()  # post-launch empty box so the resume confirms
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    registry.append_mapping(
        track=mapped_track(repo=repo, topic=topic, session=session), store_path=sup.store_path
    )
    ticked = []
    sup.tick = lambda *, act: ticked.append(act)  # type: ignore[assignment]  # spy

    with contextlib.redirect_stderr(_io.StringIO()):
        sup.run(once=True, recover=True)

    assert ("new", session, str(repo)) in fake.calls  # recovery ran...
    assert ticked == [True]  # ...and then exactly one tick


def test_run_sleeps_between_ticks_and_exits_cleanly_on_keyboard_interrupt(*, tmp_path):
    """The loop paces itself with the injected `sleep(interval)` between ticks, and a
    Ctrl-C during a tick exits by RETURNING (logged) rather than propagating — so the
    `finally` releases the singleton lock instead of leaving it held."""
    slept = []
    sup = make_supervisor(tmp_path=tmp_path, fake=FakeTmux(), sleep=slept.append)
    ticks = []

    def tick(*, act):
        ticks.append(act)
        if len(ticks) == 2:  # the operator hits Ctrl-C during the second tick
            raise KeyboardInterrupt

    sup.tick = tick  # type: ignore[assignment]
    err = _io.StringIO()

    with contextlib.redirect_stderr(err):
        sup.run(interval=7.0, once=False)  # must RETURN, not raise

    assert ticks == [True, True]
    assert slept == [7.0]  # slept exactly once, between the two ticks
    assert "interrupted; exiting" in err.getvalue()


# --------------------------------------------------------------------------- #
# The startup gitignore probe. `git check-ignore -q` is the one real subprocess
# in this module; only a ZERO exit may be read as "ignored", and a spawn failure
# fails soft to "not ignored" (which REFUSES to start).
# --------------------------------------------------------------------------- #


def _completed(*, returncode):
    """A `subprocess.CompletedProcess` reached via `_supervisor_config`, so this test
    file needs no `import subprocess` of its own.

    Reaching it through the module that DEFINES `default_gitignore_check` is what makes
    the `monkeypatch.setattr` below land: the checker reads its own module global, so a
    patch applied through the `supervisor` facade would set an attribute nothing reads
    and let this test shell out to the developer's real `git`."""
    return _supervisor_config.subprocess.CompletedProcess(args=[], returncode=returncode)


def test_gitignore_check_is_true_only_on_a_zero_exit(*, monkeypatch):
    """`git check-ignore -q` exits 0 when ignored, 1 when not, 128 on error — so only a
    0 means ignored. Reading 128 as "ignored" would let the daemon start against a repo
    where its markers dirty the tracked tree."""
    codes = [0, 1, 128]
    argvs = []

    def fake_run(argv, **_kwargs):
        argvs.append(argv)
        return _completed(returncode=codes.pop(0))

    monkeypatch.setattr(_supervisor_config.subprocess, "run", fake_run)

    assert supervisor.default_gitignore_check("/x/repo") is True  # 0 → ignored
    assert supervisor.default_gitignore_check("/x/repo") is False  # 1 → NOT ignored
    assert supervisor.default_gitignore_check("/x/repo") is False  # 128 → git errored
    assert argvs[0] == ["git", "-C", "/x/repo", "check-ignore", "-q", "tmp/overseer"]


def test_gitignore_check_fails_soft_to_not_ignored_when_git_cannot_spawn(*, monkeypatch):
    """A spawn failure (no git on PATH) fails soft to False — "not ignored" — which makes
    the daemon REFUSE to start. Failing soft to True would be the unsafe direction."""

    def boom(argv, **_kwargs):
        raise OSError("no git on PATH")

    monkeypatch.setattr(_supervisor_config.subprocess, "run", boom)

    assert supervisor.default_gitignore_check("/x/repo") is False


def test_gitignore_check_passes_a_timeout_and_fails_soft_when_git_hangs(*, monkeypatch):
    """A hung `git` on the START-UP path is worse than a hung one mid-tick.

    This gate runs before any tick, so an unbounded hang wedges the daemon with
    nothing supervised, and under crash-and-restart a restart would re-enter the very
    same hang. Neither the fail-soft handler nor the "let it crash" posture helps: a
    hang raises nothing, so there is nothing to catch and nothing to crash.

    `TimeoutExpired` subclasses `SubprocessError`, so it is caught only because it is
    named explicitly — the prior `except OSError` would have let it escape. It
    resolves to the same `False` as a spawn error, which makes the daemon REFUSE to
    start: an unanswerable check has not proven the path is ignored, and failing soft
    to True would be the unsafe direction.
    """
    seen = {}

    def hang(argv, **kwargs):
        seen.update(kwargs)
        raise _supervisor_config.subprocess.TimeoutExpired(cmd=argv, timeout=kwargs.get("timeout"))

    monkeypatch.setattr(_supervisor_config.subprocess, "run", hang)

    assert supervisor.default_gitignore_check("/x/repo") is False
    assert seen.get("timeout") is not None, "the git call must carry a timeout"
    assert seen["timeout"] > 0


# --------------------------------------------------------------------------- #
# CLI wiring: the fixed fleet manifest, the no-knob Supervisor builder, and the
# `list` / `adopt` / failing-`start` subcommand bodies.
# --------------------------------------------------------------------------- #


def test_watch_set_location_does_not_depend_on_where_this_package_lives(*, tmp_path):
    """The watch-set declaration is an ABSOLUTE `$HOME` path, independent of this module's
    position on disk. This is the property that makes the package relocatable, and it is
    the direct inverse of what the superseded implementation guaranteed.

    That implementation resolved the fleet manifest as `Path(__file__).parents[3]` — "three
    directories up is the repo root" — which is true ONLY while the package sits at
    `<core>/.claude/skills/overseer/`. Moving it anywhere else silently repointed the
    lookup outside the repo, which is why it was the single genuine code blocker on the
    relocation. Asserting the path is under `$HOME` and contains no `..` traversal pins
    that the coupling is gone rather than merely relocated.
    """
    declared = Path(registry.DEFAULT_WATCH_SET_PATH)

    assert declared.is_absolute()
    assert declared.parent == Path.home()
    assert ".." not in declared.parts
    # And it is NOT derived from this module's own location.
    assert Path(supervisor.__file__).resolve().parent not in declared.parents


def test_build_supervisor_has_no_knobs_and_badges_its_own_tmux_pane(*, monkeypatch):
    """The de-gold-plated builder: the watch-set is the `$HOME` declaration and the store /
    stamp paths are the hard-coded registry defaults (None → the module default), with
    `own_pane` read from `$TMUX_PANE` so the window badge works without a flag.

    Asserting the registry constant rather than a recomputed path is deliberate: the whole
    point of the change is that the daemon no longer DERIVES its watch-set location from
    this file's position on disk.
    """
    monkeypatch.setenv("TMUX_PANE", "%42")
    sup = supervisor.build_supervisor()

    assert sup.watch_set_path == registry.DEFAULT_WATCH_SET_PATH
    assert sup.own_pane == "%42"
    assert sup.watch_repos is None  # no --repos knob
    assert sup.store_path is None and sup.stamp_path is None  # no --store / --stamp knobs

    monkeypatch.delenv("TMUX_PANE")
    assert supervisor.build_supervisor().own_pane is None  # not under tmux → no badge


def test_cli_colliding_reads_the_same_watch_set_the_daemon_does(*, tmp_path, monkeypatch):
    """A one-shot `add`/`start` must name its session EXACTLY as the daemon would, so it
    computes collisions over the same `$HOME`-declared watch-set: only a topic present in
    TWO repos is repo-qualified; a topic unique to one repo stays bare.

    Patching the registry CONSTANT rather than a supervisor helper is the point — after the
    relocation change there is no path-deriving function left to patch, which is exactly the
    coupling that had to go.
    """
    make_plan(tmp_path=tmp_path, repo_name="alpha", topic="shared")
    make_plan(tmp_path=tmp_path, repo_name="alpha", topic="only-alpha")
    make_plan(tmp_path=tmp_path, repo_name="beta", topic="shared")
    declaration = tmp_path / "repos.json"
    declaration.write_text(
        json.dumps({"repos": [str(tmp_path / "alpha"), str(tmp_path / "beta")]}),
        encoding="utf-8",
    )
    monkeypatch.setattr(registry, "DEFAULT_WATCH_SET_PATH", declaration)

    assert supervisor._cli_colliding() == frozenset({"shared"})


def test_cli_list_renders_exactly_one_read_only_tick(*, monkeypatch):
    """`overseer list` builds the fleet Supervisor and ticks it ONCE with `act=False` —
    the advertised read-only render: no injection, no restart, no store mutation."""
    ticks = []

    class _TickOnlySup:
        def tick(self, *, act):
            ticks.append(act)
            return []

    monkeypatch.setattr(supervisor, "build_supervisor", lambda: _TickOnlySup())

    assert supervisor.main(["list"]) == 0
    assert ticks == [False]
