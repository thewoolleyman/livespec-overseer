"""Proceed-path tests for overseer-start."""

from pathlib import Path

import pytest
from test_overseer_start import _FakeSupervisor, _in_claude_tmux, _kinds, _load

__all__: list[str] = []


@pytest.fixture(autouse=True)
def _isolate_cwd(*, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


class FakeLayout:
    """A tmux window that records what the bootstrap did to it.

    Satisfies `tmuxio.WindowLayoutDriver` structurally, which is the whole point
    of that Protocol: a launcher double never has to pretend it can paste.
    """

    def __init__(self, *, titles=None, split_result="%77", resolves_title=True):
        self.titles = list(titles or [])
        self.split_result = split_result
        # False models a pane whose title tmux cannot read back — the fail-soft
        # path where the daemon pane exists but never gets its height.
        self.resolves_title = resolves_title
        self.calls = []

    def window_pane_titles(self, *, pane):
        self.calls.append(("window_pane_titles", pane))
        return list(self.titles)

    def split_window_top(self, *, pane, cwd, command):
        self.calls.append(("split_window_top", pane, cwd, command))
        return self.split_result

    def pane_exists(self, *, pane):
        self.calls.append(("pane_exists", pane))
        return True

    def set_pane_title(self, *, pane, title):
        self.calls.append(("set_pane_title", pane, title))
        self.titles.append(title)
        return True

    def select_layout_even(self, *, pane):
        self.calls.append(("select_layout_even", pane))
        return True

    def pane_by_title(self, *, pane, title):
        self.calls.append(("pane_by_title", pane, title))
        if not self.resolves_title:
            return None
        return "%77" if title in self.titles else None

    def set_pane_height_percent(self, *, pane, percent):
        self.calls.append(("set_pane_height_percent", pane, percent))
        return True


def test_splits_a_daemon_pane_and_gives_it_its_height(*, monkeypatch, tmp_path):
    """The normal first run: split, title the new pane, even the stack, then resize."""
    mod = _load()
    _in_claude_tmux(monkeypatch=monkeypatch)
    layout = FakeLayout()

    rc = mod.main(argv=[], io=layout, build_supervisor=_FakeSupervisor, core_root=tmp_path)

    assert rc == 0
    assert _kinds(layout=layout) == [
        "window_pane_titles",
        "split_window_top",
        "set_pane_title",
        "pane_exists",
        "select_layout_even",
        "pane_by_title",
        "set_pane_height_percent",
    ]
    # The split runs in the core repo root, and the daemon pane gets the title the
    # idempotency check looks for on a re-run.
    assert layout.calls[1][2] == str(tmp_path)
    assert layout.calls[2][2] == mod._DAEMON_PANE_TITLE
    assert layout.calls[6][2] == mod._DAEMON_PANE_HEIGHT_PERCENT


def test_creates_the_daemon_marker_directory_under_the_core_root(*, monkeypatch, tmp_path):
    mod = _load()
    _in_claude_tmux(monkeypatch=monkeypatch)

    assert (
        mod.main(argv=[], io=FakeLayout(), build_supervisor=_FakeSupervisor, core_root=tmp_path)
        == 0
    )

    assert (tmp_path / "tmp" / "overseer").is_dir()


def test_default_core_root_is_this_checkout_for_split_and_scratch(*, monkeypatch):
    mod = _load()
    _in_claude_tmux(monkeypatch=monkeypatch)
    layout = FakeLayout()
    made_dirs = []

    def fake_mkdir(self, *, parents=False, exist_ok=False):
        made_dirs.append((self, parents, exist_ok))

    monkeypatch.setattr(mod.Path, "mkdir", fake_mkdir)

    assert mod.main(argv=[], io=layout, build_supervisor=_FakeSupervisor) == 0

    repo_root = Path(mod.__file__).resolve().parent.parent
    assert layout.calls[1][2] == str(repo_root)
    assert made_dirs == [(repo_root / "tmp" / "overseer", True, True)]


def test_is_idempotent_when_the_daemon_pane_already_exists(*, monkeypatch, tmp_path, capsys):
    """A re-run must NOT split a second daemon pane — but must still resize.

    The resize is deliberately kept on this path: the pane is resolved BY TITLE
    rather than from the split's return value, so a re-run repairs a stack that
    was left uneven.
    """
    mod = _load()
    _in_claude_tmux(monkeypatch=monkeypatch)
    layout = FakeLayout(titles=[mod._DAEMON_PANE_TITLE])

    rc = mod.main(argv=[], io=layout, build_supervisor=_FakeSupervisor, core_root=tmp_path)

    assert rc == 0
    assert "split_window_top" not in _kinds(layout=layout)
    assert "set_pane_height_percent" in _kinds(layout=layout)
    assert "already present" in capsys.readouterr().err


def test_fails_when_the_split_fails(*, monkeypatch, tmp_path, capsys):
    """A failed split exits non-zero BEFORE any resize, leaving no half-set-up layout."""
    mod = _load()
    _in_claude_tmux(monkeypatch=monkeypatch)
    layout = FakeLayout(split_result=None)

    rc = mod.main(argv=[], io=layout, build_supervisor=_FakeSupervisor, core_root=tmp_path)

    assert rc == 1
    assert "FAILED to split" in capsys.readouterr().err
    assert "select_layout_even" not in _kinds(layout=layout)
    assert "set_pane_height_percent" not in _kinds(layout=layout)


def test_skips_the_resize_when_the_daemon_pane_cannot_be_resolved(*, monkeypatch, tmp_path):
    """`pane_by_title` returning None is fail-soft: no resize, still exit 0.

    The bootstrap's job is done once the daemon pane exists; an unreadable title
    costs the operator some screen height, not the daemon.
    """
    mod = _load()
    _in_claude_tmux(monkeypatch=monkeypatch)
    layout = FakeLayout(resolves_title=False)

    rc = mod.main(argv=[], io=layout, build_supervisor=_FakeSupervisor, core_root=tmp_path)

    assert rc == 0
    assert "set_pane_height_percent" not in _kinds(layout=layout)


def test_reports_each_adopted_session_and_the_total(*, monkeypatch, tmp_path, capsys):
    mod = _load()
    _in_claude_tmux(monkeypatch=monkeypatch)

    class _Track:
        def __init__(self, tmux, repo, topic):
            self.tmux, self.repo, self.topic = tmux, repo, topic

    adopted = [_Track("sesA", "/repo/a", "alpha"), _Track("sesB", "/repo/b", "beta")]
    rc = mod.main(
        argv=[],
        io=FakeLayout(),
        build_supervisor=lambda: _FakeSupervisor(adopted),
        core_root=tmp_path,
    )

    assert rc == 0
    err = capsys.readouterr().err
    assert "sesA" in err and "/repo/a::alpha" in err
    assert "sesB" in err and "/repo/b::beta" in err
    assert "adopted 2 existing session(s)" in err


def test_warn_percent_is_threaded_into_the_daemon_command(*, monkeypatch, tmp_path):
    """The flag must reach `overseerd`, or the operator's threshold is silently lost."""
    mod = _load()
    _in_claude_tmux(monkeypatch=monkeypatch)
    layout = FakeLayout()

    rc = mod.main(
        argv=["--warn-percent", "35"],
        io=layout,
        build_supervisor=_FakeSupervisor,
        core_root=tmp_path,
    )

    assert rc == 0
    command = layout.calls[1][3]
    assert "--warn-percent 35" in command


def test_no_warn_percent_flag_leaves_the_daemon_on_its_default(*, monkeypatch, tmp_path):
    mod = _load()
    _in_claude_tmux(monkeypatch=monkeypatch)
    layout = FakeLayout()

    assert mod.main(argv=[], io=layout, build_supervisor=_FakeSupervisor, core_root=tmp_path) == 0

    assert "--warn-percent" not in layout.calls[1][3]
