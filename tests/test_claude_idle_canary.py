"""Version-keyed Claude idle-shape canary fixtures."""

import contextlib
import importlib.util
import io as _io
import subprocess
from pathlib import Path
from types import ModuleType

import registry
import signals
from test_supervisor_builders import declare, idle_capture, make_plan, make_supervisor, mapped_track
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []

_REPO_ROOT = Path(__file__).resolve().parents[1]
_FIXTURE_DIR = _REPO_ROOT / "tests" / "fixtures" / "claude-idle"
_SCRIPT = _REPO_ROOT / "scripts" / "claude-idle-canary.py"


def _load_canary() -> ModuleType:
    assert _SCRIPT.is_file()
    spec = importlib.util.spec_from_file_location("claude_idle_canary", _SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_version_keyed_idle_fixtures_cover_the_known_border_shapes() -> None:
    versions = sorted(path.stem for path in _FIXTURE_DIR.glob("*.txt"))
    assert versions == ["2.1.235", "2.1.237", "2.1.238"]


def test_every_registered_idle_fixture_matches_the_detector() -> None:
    for path in sorted(_FIXTURE_DIR.glob("*.txt")):
        capture = path.read_text(encoding="utf-8")
        assert signals.is_idle_input(capture_text=capture) is True, path.name
        assert signals.input_box_ready(capture_text=capture) is True, path.name
        assert signals.parse_ctx_remaining(capture_text=capture) == 73, path.name


def test_canary_check_script_reports_unregistered_installed_build() -> None:
    canary = _load_canary()

    def fake_run(*args, **kwargs):
        del args, kwargs
        return subprocess.CompletedProcess(
            args=["claude", "--version"],
            returncode=0,
            stdout="Claude Code 2.1.999\n",
            stderr="",
        )

    assert canary.installed_claude_version(run=fake_run) == "2.1.999"
    assert canary.main(argv=["check"], run=fake_run) == 1


def test_canary_check_script_accepts_registered_installed_build() -> None:
    canary = _load_canary()

    def fake_run(*args, **kwargs):
        del args, kwargs
        return subprocess.CompletedProcess(
            args=["claude", "--version"],
            returncode=0,
            stdout="Claude Code 2.1.237\n",
            stderr="",
        )

    assert canary.main(argv=["check"], run=fake_run) == 0


def test_canary_check_is_wired_into_just_check() -> None:
    justfile = (_REPO_ROOT / "justfile").read_text(encoding="utf-8")
    assert "check-claude-idle-canary" in justfile
    assert "capture-claude-idle-canary" in justfile


def test_run_logs_the_installed_claude_build_at_startup(*, tmp_path) -> None:
    fake = FakeTmux()
    sup = make_supervisor(
        tmp_path=tmp_path,
        fake=fake,
        watch_repos=[],
        watch_set_path=None,
        claude_version_of=lambda: "2.1.237",
    )

    err = _io.StringIO()
    with contextlib.redirect_stderr(err):
        sup.run(once=True)

    assert "overseer: claude build at startup: 2.1.237" in err.getvalue()


def test_claude_restart_logs_the_installed_claude_build(*, tmp_path) -> None:
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=14))
    sup = make_supervisor(
        tmp_path=tmp_path,
        fake=fake,
        claude_version_of=lambda: "2.1.237",
    )
    registry.write_injection_stamp(
        repo=str(repo), topic=topic, ts=1000.0, stamp_path=sup.stamp_path
    )
    declare(repo=repo, topic=topic, value="ready")
    track = mapped_track(repo=repo, topic=topic, session=session)

    err = _io.StringIO()
    with contextlib.redirect_stderr(err):
        assert sup.evaluate(track=track, act=True).status == "restarting"

    assert "overseer: claude build at respawn: 2.1.237" in err.getvalue()
