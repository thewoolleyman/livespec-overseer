"""Version-keyed Claude idle-shape canary fixtures."""

import contextlib
import hashlib
import importlib.util
import io as _io
import json
import re
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import registry
import signals
from test_supervisor_builders import (
    busy_capture,
    declare,
    idle_capture,
    make_plan,
    make_supervisor,
    mapped_track,
)
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []

_REPO_ROOT = Path(__file__).resolve().parents[1]
_FIXTURE_DIR = _REPO_ROOT / "tests" / "fixtures" / "claude-idle"
_SCRIPT = _REPO_ROOT / "scripts" / "claude-idle-canary.py"
_CAPTURE_SCRIPT = _REPO_ROOT / "scripts" / "capture-claude-idle-canary.py"
_FIXTURE_CTX_RE = re.compile(r"Ctx:\s*(\d+)%\s*left")


def _load_canary() -> ModuleType:
    assert _SCRIPT.is_file()
    spec = importlib.util.spec_from_file_location("claude_idle_canary", _SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_capture_canary() -> ModuleType:
    assert _CAPTURE_SCRIPT.is_file()
    spec = importlib.util.spec_from_file_location("capture_claude_idle_canary", _CAPTURE_SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _idle_capture_without_context() -> str:
    return "\n".join(
        [
            "● prior response",
            "────────────── overseer-idle-canary ──",
            "❯ ",
            "────────────────────────────────────────",
            "  Opus 5 (1M context) | /x/repo | master",
            "  ⏵⏵ bypass permissions on (shift+tab to cycle) · ← for agents",
            "",
        ]
    )


def test_version_keyed_idle_fixtures_cover_the_known_border_shapes() -> None:
    versions = sorted(path.stem for path in _FIXTURE_DIR.glob("*.txt"))
    # A SUPERSET check, not an exact set. This test's purpose is that the
    # registry keeps the DISCRIMINATING PAIR — 2.1.235 renders the topic border
    # with two trailing rule characters and 2.1.237 with one, which is the exact
    # upstream change that blinded supervision and the pair that proves the
    # detector distinguishes them. An exact-equality assertion also declared the
    # registry closed, so every newly captured build broke it and the recipe's
    # "adding a version is one command" could never be true.
    assert {"2.1.235", "2.1.237"} <= set(versions), versions


def _fixture_ctx(*, capture: str) -> int | None:
    """The context percentage a fixture literally carries, or `None` if it carries none.

    Read with this module's OWN regex rather than through
    `signals.parse_ctx_remaining`, so the fixture assertion is an independent
    check of the detector rather than a tautology comparing it to itself.

    This replaces a hard-coded `== 73`, which every registered fixture happened
    to satisfy because both were captured from panes at that percentage. That
    assertion made the registry unextendable: a fixture from a pane at any other
    percentage failed, and a fixture from a FRESH pane — which renders no context
    segment at all, the whole reason the capture no longer requires one — could
    never pass. The rule that replaces it is stricter where it matters and
    permissive only where it must be: a fixture carrying a reading must be parsed
    to exactly that reading, and a fixture carrying none must parse to `None`, so
    a detector that hallucinated a value would still fail.
    """
    match = _FIXTURE_CTX_RE.search(capture)
    return None if match is None else int(match.group(1))


def test_every_registered_idle_fixture_matches_the_detector() -> None:
    for path in sorted(_FIXTURE_DIR.glob("*.txt")):
        capture = path.read_text(encoding="utf-8")
        assert signals.is_idle_input(capture_text=capture) is True, path.name
        assert signals.input_box_ready(capture_text=capture) is True, path.name
        assert signals.parse_ctx_remaining(capture_text=capture) == _fixture_ctx(
            capture=capture
        ), path.name


def test_canary_check_script_reports_unregistered_installed_build() -> None:
    canary = _load_canary()
    # A SYNTHETIC version that no real build will ever carry, asserted absent
    # first. This test previously named a real, then-unregistered build; the day
    # that build was registered — which is the ordinary, intended use of this
    # registry — the test silently inverted and began asserting that a
    # REGISTERED version is refused. A sentinel cannot rot that way, and the
    # precondition below fails loudly rather than inverting if it ever does.
    unregistered = "0.0.0"
    assert unregistered not in {path.stem for path in _FIXTURE_DIR.glob("*.txt")}

    def fake_run(*args, **kwargs):
        del args, kwargs
        return subprocess.CompletedProcess(
            args=["claude", "--version"],
            returncode=0,
            stdout=f"Claude Code {unregistered}\n",
            stderr="",
        )

    assert canary.installed_claude_version(run=fake_run) == unregistered
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


def test_capture_accepts_idle_pane_without_context_percentage() -> None:
    capture_canary = _load_capture_canary()

    assert hasattr(capture_canary, "capture_is_ready")
    assert capture_canary.capture_is_ready(capture=_idle_capture_without_context()) is True


def test_capture_refuses_busy_pane_without_context_percentage() -> None:
    capture_canary = _load_capture_canary()

    assert hasattr(capture_canary, "capture_is_ready")
    assert capture_canary.capture_is_ready(capture=busy_capture(ctx=None)) is False


def test_canary_check_goes_red_when_idle_detection_is_broken(*, tmp_path) -> None:
    canary = _load_canary()
    fixture_dir = tmp_path / "fixtures"
    fixture_dir.mkdir()
    (fixture_dir / "2.1.237.txt").write_text(
        "● prior response\nnot an idle box\n", encoding="utf-8"
    )
    canary._FIXTURE_DIR = fixture_dir

    def fake_run(*args, **kwargs):
        del args, kwargs
        return subprocess.CompletedProcess(
            args=["claude", "--version"],
            returncode=0,
            stdout="Claude Code 2.1.237\n",
            stderr="",
        )

    assert canary.main(argv=["check"], run=fake_run) == 1


def test_capture_script_detects_installed_version() -> None:
    capture_canary = _load_capture_canary()

    def fake_run(*, argv):
        assert argv == ["claude", "--version"]
        return subprocess.CompletedProcess(
            args=argv,
            returncode=0,
            stdout="Claude Code 2.1.238\n",
            stderr="",
        )

    capture_canary._run = fake_run

    assert capture_canary._installed_version() == "2.1.238"


def test_capture_script_treats_unavailable_version_as_none() -> None:
    capture_canary = _load_capture_canary()

    def fake_run(*, argv):
        del argv
        raise OSError

    capture_canary._run = fake_run

    assert capture_canary._installed_version() is None


def test_capture_script_treats_failed_version_command_as_none() -> None:
    capture_canary = _load_capture_canary()

    def fake_run(*, argv):
        return subprocess.CompletedProcess(args=argv, returncode=1, stdout="", stderr="nope")

    capture_canary._run = fake_run

    assert capture_canary._installed_version() is None


def test_capture_script_captures_tmux_pane_text() -> None:
    capture_canary = _load_capture_canary()

    def fake_run(*, argv):
        assert argv == ["tmux", "capture-pane", "-e", "-t", "s", "-p", "-S", "-200"]
        return subprocess.CompletedProcess(args=argv, returncode=0, stdout="pane", stderr="")

    capture_canary._run = fake_run

    assert capture_canary._tmux_capture(session="s") == "pane"


def test_capture_script_empty_capture_on_tmux_failure() -> None:
    capture_canary = _load_capture_canary()

    def fake_run(*, argv):
        return subprocess.CompletedProcess(args=argv, returncode=1, stdout="pane", stderr="")

    capture_canary._run = fake_run

    assert capture_canary._tmux_capture(session="s") == ""


def test_capture_script_starts_canary_session() -> None:
    capture_canary = _load_capture_canary()

    def fake_run(*, argv):
        assert argv == [
            "tmux",
            "new-session",
            "-d",
            "-s",
            "s",
            "claude",
            "--dangerously-skip-permissions",
            "-n",
            "overseer-idle-canary",
        ]
        return subprocess.CompletedProcess(args=argv, returncode=0, stdout="", stderr="")

    capture_canary._run = fake_run

    assert capture_canary._start_canary_session(session="s") is True


def test_capture_script_reports_start_failure() -> None:
    capture_canary = _load_capture_canary()

    def fake_run(*, argv):
        return subprocess.CompletedProcess(args=argv, returncode=1, stdout="", stderr="")

    capture_canary._run = fake_run

    assert capture_canary._start_canary_session(session="s") is False


def test_capture_script_kills_canary_session() -> None:
    capture_canary = _load_capture_canary()
    seen: list[list[str]] = []

    def fake_run(*, argv):
        seen.append(argv)
        return subprocess.CompletedProcess(args=argv, returncode=0, stdout="", stderr="")

    capture_canary._run = fake_run
    capture_canary._kill_canary_session(session="s")

    assert seen == [["tmux", "kill-session", "-t", "s"]]


def test_capture_script_ignores_kill_errors() -> None:
    capture_canary = _load_capture_canary()

    def fake_run(*, argv):
        del argv
        raise subprocess.TimeoutExpired(cmd="tmux", timeout=1)

    capture_canary._run = fake_run

    capture_canary._kill_canary_session(session="s")


def test_capture_script_awaits_ready_capture(*, monkeypatch) -> None:
    capture_canary = _load_capture_canary()

    capture_canary._tmux_capture = lambda *, session: idle_capture(ctx=73).rstrip()
    monkeypatch.setattr(capture_canary.time, "monotonic", lambda: 1.0)

    assert capture_canary._await_idle_capture(session="s") == idle_capture(ctx=73)


def test_capture_script_times_out_waiting_for_idle(*, monkeypatch) -> None:
    capture_canary = _load_capture_canary()
    clock = {"now": 0.0}

    def fake_monotonic():
        clock["now"] += 1.0
        return clock["now"]

    def fake_sleep(seconds):
        assert seconds == 1.0

    capture_canary._CAPTURE_TIMEOUT_SECONDS = 2.0
    capture_canary._tmux_capture = lambda *, session: "busy"
    monkeypatch.setattr(capture_canary.time, "monotonic", fake_monotonic)
    monkeypatch.setattr(capture_canary.time, "sleep", fake_sleep)

    assert capture_canary._await_idle_capture(session="s") is None


def test_capture_script_main_reports_missing_claude_version() -> None:
    capture_canary = _load_capture_canary()
    err = _io.StringIO()
    capture_canary._installed_version = lambda: None

    with contextlib.redirect_stderr(err):
        assert capture_canary.main() == 1

    assert "claude --version unavailable" in err.getvalue()


def test_capture_script_main_reports_start_failure() -> None:
    capture_canary = _load_capture_canary()
    err = _io.StringIO()
    capture_canary._installed_version = lambda: "2.1.238"
    capture_canary._start_canary_session = lambda *, session: False

    with contextlib.redirect_stderr(err):
        assert capture_canary.main() == 1

    assert "tmux canary session did not start" in err.getvalue()


def test_capture_script_main_reports_idle_timeout() -> None:
    capture_canary = _load_capture_canary()
    err = _io.StringIO()
    killed: list[str] = []
    capture_canary._installed_version = lambda: "2.1.238"
    capture_canary._start_canary_session = lambda *, session: True
    capture_canary._await_idle_capture = lambda *, session: None
    capture_canary._kill_canary_session = lambda *, session: killed.append(session)

    with contextlib.redirect_stderr(err):
        assert capture_canary.main() == 1

    assert killed == [f"claude-idle-canary-{capture_canary.os.getpid()}"]
    assert "idle prompt did not render in time" in err.getvalue()


def test_capture_script_main_writes_versioned_fixture(*, tmp_path) -> None:
    capture_canary = _load_capture_canary()
    out = _io.StringIO()
    repo_root = tmp_path / "repo"
    capture_canary._REPO_ROOT = repo_root
    capture_canary._FIXTURE_DIR = repo_root / "fixtures"
    capture_canary._installed_version = lambda: "2.1.238"
    capture_canary._start_canary_session = lambda *, session: True
    capture_canary._await_idle_capture = lambda *, session: "capture\n"
    capture_canary._kill_canary_session = lambda *, session: None

    with contextlib.redirect_stdout(out):
        assert capture_canary.main() == 0

    assert (repo_root / "fixtures" / "2.1.238.txt").read_text(encoding="utf-8") == "capture\n"
    assert "2.1.238.txt" in out.getvalue()


def test_capture_script_run_invokes_subprocess() -> None:
    capture_canary = _load_capture_canary()

    completed = capture_canary._run(argv=[sys.executable, "-c", "print('ok')"])

    assert completed.returncode == 0
    assert completed.stdout == "ok\n"


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

    event = json.loads(err.getvalue())
    assert event["event"] == "claude-build"
    assert event["phase"] == "startup"
    assert event["version"] == "2.1.237"


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

    build = next(
        event
        for line in err.getvalue().splitlines()
        if (event := json.loads(line))["event"] == "claude-build"
    )
    assert build["phase"] == "respawn"
    assert build["version"] == "2.1.237"


# ------------------------------------- the supplied host captures
#
# NEITHER of these is a factory artifact. Both were captured on the operator
# host with `just capture-claude-idle-canary`, in the linked
# `chore/claude-idle-canary-2-1-290` worktree whose cwd is visible in each pane,
# and carried into this repair unchanged rather than recaptured — which is why
# their bytes are pinned by DIGEST. The alternatives a digest forecloses are the
# two that look identical in a diff: an older fixture relabelled as a newer
# release, and a reconstructed rendering standing in for the real ANSI-styled
# pane.
#
# There are TWO because the host build moved while this repair was in flight
# (2.1.290 -> 2.1.292, about eleven hours apart). The older one is kept rather
# than replaced: the registry is append-only by design, a post-merge acceptance
# check still names 2.1.290, and a host that has not updated yet is still a host
# this canary has to recognise. `_CURRENT_HOST_BUILD` names the build the host
# runs NOW, which is the one a post-merge canary will actually be asked about.

_SUPPLIED_CAPTURES = (
    ("2.1.290", "038ee999192893794b849f2306a0be3d2c2a6880ef521b6851f913bca83cd012", 1484),
    ("2.1.292", "e38b57a9d96713cbe6d8f66b3b5df73095d4172ad050c5bc87a77455c89e0521", 1406),
)
_CURRENT_HOST_BUILD = "2.1.292"


def test_each_supplied_host_capture_is_registered_byte_for_byte() -> None:
    """Every supplied capture is present and UNCHANGED, digest and length both."""
    for version, digest, size in _SUPPLIED_CAPTURES:
        fixture = _FIXTURE_DIR / f"{version}.txt"
        assert fixture.is_file(), f"the supplied host capture {version}.txt is missing"

        raw = fixture.read_bytes()

        assert len(raw) == size, (version, len(raw))
        assert hashlib.sha256(raw).hexdigest() == digest, version


def test_the_detector_reads_each_supplied_capture_as_idle_and_input_ready() -> None:
    """The real renderings, evaluated by the shipped predicates rather than retyped.

    Both halves, because the canary script requires both: `is_idle_input` is the
    structural idle shape and `input_box_ready` is what the submit-verify loop
    waits for. The ANSI escapes are left in place deliberately — since 2.1.286
    the detector distinguishes a dim-styled generated placeholder from identical
    user-authored text, and a stripped capture cannot carry that evidence.
    """
    for version, _digest, _size in _SUPPLIED_CAPTURES:
        capture = (_FIXTURE_DIR / f"{version}.txt").read_text(encoding="utf-8")

        assert "\x1b[" in capture, f"{version} must retain its real SGR escapes"
        assert signals.is_idle_input(capture_text=capture) is True, version
        assert signals.input_box_ready(capture_text=capture) is True, version


def test_the_canary_registers_every_supplied_build_including_the_current_host_one() -> None:
    """A host on either supplied build must pass the version-keyed canary.

    The measured host janitor failure was `CLAUDE_IDLE_CANARY_MISSING_FIXTURE`
    for 2.1.290, so the registry — not merely the directory — is what has to
    carry it; 2.1.292 is the build the host runs now and is the one a post-merge
    canary will be asked about.
    """
    canary = _load_canary()
    registered = canary._registered_versions()

    assert _CURRENT_HOST_BUILD in registered
    for version, _digest, _size in _SUPPLIED_CAPTURES:
        assert version in registered, version

        err = _io.StringIO()
        with contextlib.redirect_stderr(err):
            exit_code = canary.main(
                argv=["check"],
                run=lambda *_args, version=version, **_kwargs: subprocess.CompletedProcess(
                    args=["claude", "--version"],
                    returncode=0,
                    stdout=f"{version} (Claude Code)\n",
                ),
            )

        assert exit_code == 0, (version, err.getvalue())
        assert err.getvalue() == "", version


def test_each_supplied_capture_carries_its_host_provenance_row() -> None:
    """The bytes and the account of where they came from travel TOGETHER.

    A registry file with no provenance row is indistinguishable from a
    constructed rendering, which is the whole reason the note beside these
    fixtures exists — and these two need it most, having been captured outside
    the run that registers them.
    """
    note = (_FIXTURE_DIR / "README.md").read_text(encoding="utf-8")

    for version, _digest, _size in _SUPPLIED_CAPTURES:
        row = next(
            (line for line in note.splitlines() if line.startswith(f"| `{version}.txt` |")),
            None,
        )

        assert row is not None, f"no provenance row for {version}.txt"
        assert "just capture-claude-idle-canary" in row, row
        assert "2026-10-06" in row, row
        assert "chore/claude-idle-canary-2-1-290" in row, row
        assert f"Claude Code {version}" in row, row
