"""Beside-tests for supervisor.py — b7: one bad input must NOT kill the whole loop.

Split from `test_supervisor.py`, which carried the whole daemon surface at 3010 LLOC
after its shared helpers were extracted — still more than twelve times the 250-LLOC
hard ceiling. The doubles and builders live in `test_supervisor_fakes` /
`test_supervisor_builders`; this module holds only tests.

``import supervisor`` resolves via conftest.py.
"""

import contextlib
import io as _io
import os

import pytest
import registry
import supervisor
from test_supervisor_builders import (
    isolate_store,
    make_plan,
    make_supervisor,
)
from test_supervisor_fakes import (
    FakeTmux,
)

__all__: list[str] = []


@pytest.fixture(autouse=True)
def _isolate_cwd(*, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


# --------------------------------------------------------------------------- #
# B7: one bad input must NOT kill the whole loop.
# --------------------------------------------------------------------------- #


def test_run_loop_lets_a_tick_exception_propagate(*, tmp_path):
    """A bug in a tick PROPAGATES: the daemon exits and its supervisor restarts it.

    This is the INVERSION of an earlier test that asserted the loop survived a
    raising tick, on the B7 reasoning that a bug evaluating one track must not
    strand the other N-1. That permission was WITHDRAWN by the maintainer ruling of
    2026-07-26 and the narrowing is ratified in livespec `history/v176`: a daemon
    gets no per-iteration broad catch. "Let it crash, systemd restarts" — exactly one
    broad catch per program, in `main()`.

    Inverted rather than DELETED on purpose. A deleted test silently stops proving
    anything, so nothing would notice the catch creeping back; an inverted one pins
    propagation as the contract.

    Why this is SAFE, and why it was unsafe before: the two failure cases the old
    docstring justified the catch with — an unreadable `plan/` dir and a malformed
    store — are boundaried by narrow catches below (`discover_plans` and
    `_read_rows` in `registry.py`), and the six `UnicodeDecodeError` leaks that used
    to escape those handlers were closed first (PR #118). So a bug is now the only
    exception class that can reach here, which is exactly the condition under which
    crashing is correct rather than reckless.
    """
    fake = FakeTmux()
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)

    def boom(*, act):
        raise RuntimeError("a genuine bug in one track's tick")

    sup.tick = boom  # type: ignore[assignment]
    with pytest.raises(RuntimeError, match="a genuine bug"):
        sup.run(once=True)


# --------------------------------------------------------------------------- #
# Startup gate: Linux + tmux is a DECLARED REQUIREMENT (D4) — refuse, don't crash.
# --------------------------------------------------------------------------- #


def test_supported_host_yields_no_reasons(*, tmp_path):
    """The happy path: an existing /proc and a resolvable tmux == zero reasons."""
    sup = make_supervisor(tmp_path=tmp_path, fake=FakeTmux())
    assert sup.unsupported_host_reasons() == []


def test_absent_proc_is_an_unsupported_host(*, tmp_path):
    """macOS has no /proc AT ALL, and both session readers parse /proc/<pid>/ — so a
    missing proc_root is a declared-precondition failure, named as such."""
    sup = make_supervisor(
        tmp_path=tmp_path, fake=FakeTmux(), proc_root=str(tmp_path / "no-such-proc")
    )
    reasons = sup.unsupported_host_reasons()
    assert len(reasons) == 1
    assert "/proc" in reasons[0] and "Linux is required" in reasons[0]


def test_absent_tmux_is_an_unsupported_host(*, tmp_path):
    """Every acting mechanic shells out to a real tmux, so tmux-off-PATH is fatal."""
    sup = make_supervisor(tmp_path=tmp_path, fake=FakeTmux(), which=lambda _name: None)
    reasons = sup.unsupported_host_reasons()
    assert len(reasons) == 1
    assert "tmux is not on PATH" in reasons[0]


def test_the_gate_asks_about_tmux_by_its_real_name(*, tmp_path):
    """The gate must ask `which` about the literal 'tmux', NOT a caller's injected
    tmux_bin: it answers 'is this host supported at all?', and the beside-tests' fake
    tmux must never be able to satisfy it."""
    asked: list[str] = []
    sup = make_supervisor(
        tmp_path=tmp_path, fake=FakeTmux(), which=lambda name: asked.append(name) or "/usr/bin/tmux"
    )
    _ = sup.unsupported_host_reasons()
    assert asked == ["tmux"]


def test_run_refuses_on_an_unsupported_host_before_ticking(*, tmp_path):
    """The refusal mirrors the gitignore gate: surface an actionable reason and return
    from run() BEFORE any tick — an obscure FileNotFoundError several ticks deep is
    exactly what declaring the precondition exists to prevent."""
    repo, _topic = make_plan(tmp_path=tmp_path)
    err = _io.StringIO()
    sup = make_supervisor(
        tmp_path=tmp_path,
        fake=FakeTmux(),
        watch_repos=[str(repo)],
        gitignore_check=lambda _r: True,
        which=lambda _name: None,
    )
    ticked: list[bool] = []
    sup.tick = lambda *, act: ticked.append(act)  # type: ignore[assignment]  # spy
    with contextlib.redirect_stderr(err):
        sup.run(once=True)
    assert ticked == []  # NO tick ran
    assert "refusing to start: unsupported host" in err.getvalue()


def test_the_host_gate_precedes_the_gitignore_gate(*, tmp_path):
    """Ordering matters: an unsupported host is the more fundamental failure, so it is
    reported even when a watched repo ALSO has an ungitignored tmp/overseer/. Reporting
    the gitignore offence first would send the operator to fix the wrong thing."""
    repo, _topic = make_plan(tmp_path=tmp_path)
    err = _io.StringIO()
    sup = make_supervisor(
        tmp_path=tmp_path,
        fake=FakeTmux(),
        watch_repos=[str(repo)],
        gitignore_check=lambda _r: False,  # ALSO an offender
        which=lambda _name: None,
    )
    with contextlib.redirect_stderr(err):
        sup.run(once=True)
    assert "unsupported host" in err.getvalue()
    assert "NOT gitignored" not in err.getvalue()


# --------------------------------------------------------------------------- #
# Startup gate: tmp/overseer/ MUST be gitignored, else the daemon refuses to start.
# --------------------------------------------------------------------------- #


def test_run_refuses_when_tmp_not_gitignored(*, tmp_path):
    """New startup gate: if a watched repo's tmp/overseer/ is NOT gitignored, the
    daemon surfaces 'refusing to start' and returns from run() BEFORE ticking — the
    overseer writes markers there and must never dirty a tracked tree."""
    repo, _topic = make_plan(tmp_path=tmp_path)
    fake = FakeTmux()
    sup = make_supervisor(
        tmp_path=tmp_path, fake=fake, watch_repos=[str(repo)], gitignore_check=lambda _r: False
    )
    assert sup.unignored_tmp_repos() == [os.path.normpath(str(repo))]
    ticked: list[bool] = []
    sup.tick = lambda *, act: ticked.append(act)  # type: ignore[assignment]  # spy
    sup.run(once=True)  # refuses before acquiring the lock or ticking
    assert ticked == []  # NO tick ran


def test_run_proceeds_when_tmp_gitignored(*, tmp_path):
    """Counterpart: when every watched repo's tmp/overseer/ IS gitignored the gate
    passes and run(once=True) performs a single normal act=True tick."""
    repo, _topic = make_plan(tmp_path=tmp_path)
    fake = FakeTmux()
    sup = make_supervisor(
        tmp_path=tmp_path, fake=fake, watch_repos=[str(repo)], gitignore_check=lambda _r: True
    )
    assert sup.unignored_tmp_repos() == []
    ticked: list[bool] = []
    sup.tick = lambda *, act: ticked.append(act)  # type: ignore[assignment]  # spy
    sup.run(once=True)
    assert ticked == [True]  # proceeded to exactly one act=True tick


def test_cli_add_remove_roundtrip(*, tmp_path, monkeypatch):
    store = isolate_store(tmp_path=tmp_path, monkeypatch=monkeypatch)
    repo = str(tmp_path / "repo")
    assert supervisor.main(["add", "--repo", repo, "--topic", "alpha"]) == 0
    rows = registry.read_mapping(store_path=store)
    assert [(r.topic, r.tmux) for r in rows] == [
        ("alpha", registry.tmux_id(repo=repo, topic="alpha"))
    ]

    assert supervisor.main(["add", "--repo", repo, "--topic", "alpha"]) == 0
    assert len(registry.read_mapping(store_path=store)) == 1

    assert supervisor.main(["remove", "--repo", repo, "--topic", "alpha"]) == 0
    assert registry.read_mapping(store_path=store) == []


def test_cli_add_names_a_bare_topic_by_default(*, tmp_path, monkeypatch):
    # With no cross-repo collision, `add` maps the session to the BARE topic name.
    store = isolate_store(tmp_path=tmp_path, monkeypatch=monkeypatch)
    repo = str(tmp_path / "livespec")
    assert supervisor.main(["add", "--repo", repo, "--topic", "autonomous-mode"]) == 0
    rows = registry.read_mapping(store_path=store)
    assert [(r.topic, r.tmux) for r in rows] == [("autonomous-mode", "autonomous-mode")]


def test_cli_add_single_dash_prefixes_a_cross_repo_collision(*, tmp_path, monkeypatch):
    # When the topic collides across repos, `add` repo-qualifies it as `<slug>-<topic>`
    # with a SINGLE dash (the daemon derives the identical name).
    store = isolate_store(tmp_path=tmp_path, monkeypatch=monkeypatch)
    monkeypatch.setattr(supervisor, "_cli_colliding", lambda: frozenset({"shared"}))
    repo = str(tmp_path / "livespec")
    assert supervisor.main(["add", "--repo", repo, "--topic", "shared"]) == 0
    assert supervisor.main(["add", "--repo", repo, "--topic", "solo"]) == 0
    rows = {r.topic: r.tmux for r in registry.read_mapping(store_path=store)}
    assert rows["shared"] == "livespec-shared"  # colliding -> repo-qualified
    assert rows["solo"] == "solo"  # non-colliding -> bare


def test_build_rows_caches_the_cross_repo_collision_set(*, tmp_path):
    # Two watched repos share topic "shared"; each also carries a unique topic. After a
    # tick's build_rows, the daemon caches exactly the cross-repo topic, and `_session_of`
    # repo-qualifies ONLY that one — per repo, single dash — leaving the unique ones bare.
    r1, _ = make_plan(tmp_path=tmp_path, repo_name="livespec", topic="shared")
    make_plan(tmp_path=tmp_path, repo_name="livespec", topic="solo-a")
    r2, _ = make_plan(tmp_path=tmp_path, repo_name="other", topic="shared")
    make_plan(tmp_path=tmp_path, repo_name="other", topic="solo-b")
    sessions = tmp_path / "sess"
    sessions.mkdir()
    sup = make_supervisor(
        tmp_path=tmp_path,
        fake=FakeTmux(),
        watch_repos=[str(r1), str(r2)],
        sessions_dir=str(sessions),
    )
    rows = sup.build_rows(act=False)
    assert sup.colliding_topics == frozenset({"shared"})
    derived = {(r.repo, r.topic): sup._session_of(track=r) for r in rows}
    assert derived[(str(r1), "shared")] == "livespec-shared"
    assert derived[(str(r2), "shared")] == "other-shared"
    assert derived[(str(r1), "solo-a")] == "solo-a"
    assert derived[(str(r2), "solo-b")] == "solo-b"


def test_cli_unassign_is_remove(*, tmp_path, monkeypatch):
    store = isolate_store(tmp_path=tmp_path, monkeypatch=monkeypatch)
    repo = str(tmp_path / "repo")
    supervisor.main(["add", "--repo", repo, "--topic", "beta"])
    assert supervisor.main(["unassign", "--repo", repo, "--topic", "beta"]) == 0
    assert registry.read_mapping(store_path=store) == []
