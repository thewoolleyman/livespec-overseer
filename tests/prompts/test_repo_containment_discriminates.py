"""Defect (b): an empty `pane_cwd` launders into a repo-containment PASS.

`readlink -f ""` is IMPLEMENTATION-DEPENDENT, which makes this an adopter-safety
exhibit rather than a one-platform quirk:

    GNU coreutils   exit 1, empty output   -> HALT, fails safe BY ACCIDENT
    uutils          exit 0, prints $PWD    -> FALSE PASS

The same charter therefore gives OPPOSITE safety verdicts on two adopters, and
`readlink -f -- ""` still returns `$PWD` — `--` does not fix the empty case;
only a non-empty guard on the INPUT does.

THIS MODULE IS DELIBERATELY WRITTEN TO PASS ON BOTH COREUTILS, and that is the
finding rather than a workaround: it PROBES which implementation is present and
asserts the shipped form tracks it. Hardcoding either verdict would make the
suite green on one adopter and red on the other for an environmental reason —
the exact failure mode this thread exists to remove. The developer host runs
uutils; the pinned CI image is Ubuntu-based and runs GNU, so both arms are real.

The remedy, by contrast, is asserted UNCONDITIONALLY: it must halt everywhere.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path

__all__: list[str] = []

_PASS = "PASS"
_HALT = "HALT"


def _readlink(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    # S603/S607: argv is a LIST with no shell and no untrusted input. Resolving
    # `readlink` through PATH is deliberate — WHICH coreutils answers is
    # precisely the adopter-dependence under test.
    return subprocess.run(  # noqa: S603
        ["readlink", *args],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
        cwd=cwd,
    )


def _within(*, resolved: str, repo: Path) -> bool:
    return resolved == str(repo) or resolved.startswith(f"{repo}/")


def containment_shipped(*, pane_cwd: str, repo: Path, cwd: Path) -> str:
    """The shipped form: resolve, then compare. No guard on the input."""
    resolved = _readlink("-f", pane_cwd, cwd=cwd).stdout.strip()
    return _PASS if _within(resolved=resolved, repo=repo) else _HALT


def containment_proposed(*, pane_cwd: str, repo: Path, cwd: Path) -> str:
    """The remedy: refuse an EMPTY pane_cwd before `readlink` ever sees it.

    The guard is on the INPUT, not on the exit code, because the measured
    finding is that `readlink -f -- ""` SUCCEEDS and prints `$PWD` on uutils.
    An empty RESOLUTION needs no separate branch: it cannot match the repo
    prefix, so it already falls through to HALT.
    """
    if not pane_cwd:
        return _HALT
    resolved = _readlink("-f", "--", pane_cwd, cwd=cwd).stdout.strip()
    return _PASS if _within(resolved=resolved, repo=repo) else _HALT


def _empty_resolves_to_cwd(*, cwd: Path) -> bool:
    """Probe THIS host's coreutils: does `readlink -f ""` yield `$PWD`?"""
    return _readlink("-f", "", cwd=cwd).stdout.strip() == str(cwd)


def test_the_shipped_forms_verdict_is_decided_by_the_local_coreutils(*, tmp_path: Path) -> None:
    """THE DEFECT, PINNED — as adopter-dependence, which is what it actually is.

    A supervisor runs this check FROM INSIDE the repo, so on uutils the empty
    `pane_cwd` resolves to a path that IS within the repo and the check reports
    a confident PASS about a worker whose location is unknown.
    """
    repo = tmp_path
    expected = _PASS if _empty_resolves_to_cwd(cwd=repo) else _HALT
    assert containment_shipped(pane_cwd="", repo=repo, cwd=repo) == expected


def test_the_proposed_form_halts_on_an_empty_pane_cwd_on_every_adopter(*, tmp_path: Path) -> None:
    """RED: delete the non-empty guard -> PASS wherever readlink yields $PWD."""
    assert containment_proposed(pane_cwd="", repo=tmp_path, cwd=tmp_path) == _HALT


def test_the_proposed_form_halts_for_a_cwd_outside_the_repo(*, tmp_path: Path) -> None:
    """A real path that is genuinely elsewhere must still halt."""
    repo = tmp_path / "repo"
    repo.mkdir()
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    assert containment_proposed(pane_cwd=str(outside), repo=repo, cwd=repo) == _HALT


def test_the_control_both_forms_pass_for_a_genuine_in_repo_cwd(*, tmp_path: Path) -> None:
    """THE CONTROL, AND IT IS NOT OPTIONAL.

    Every halt above is satisfied by a "remedy" that halts unconditionally.
    This is the leg that makes them mean something: a legitimate worker sitting
    inside the repo must still be allowed to proceed, under BOTH forms.
    """
    repo = tmp_path / "repo"
    (repo / "sub").mkdir(parents=True)
    assert containment_proposed(pane_cwd=str(repo / "sub"), repo=repo, cwd=repo) == _PASS
    assert containment_shipped(pane_cwd=str(repo / "sub"), repo=repo, cwd=repo) == _PASS


def test_the_pane_cwd_the_forms_receive_comes_from_a_real_tmux_pane(
    *, tmux: Callable[..., subprocess.CompletedProcess[str]], tmp_path: Path
) -> None:
    """End-to-end on REAL tmux, so the unit legs are not testing a fiction.

    The legs above feed the forms a string. This one proves the string the
    forms actually receive in the field is the one they were tested against —
    and that an ABSENT worker yields the EMPTY value the whole defect turns on.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    tmux("new-session", "-d", "-s", "wk", "-x", "80", "-y", "20", "-c", str(repo))
    live = tmux("display-message", "-p", "-t", "=wk:", "#{pane_current_path}").stdout.strip()
    assert live == str(repo)
    assert containment_proposed(pane_cwd=live, repo=repo, cwd=repo) == _PASS

    absent = tmux("display-message", "-p", "-t", "=nope:", "#{pane_current_path}").stdout.strip()
    assert absent == ""
    assert containment_proposed(pane_cwd=absent, repo=repo, cwd=repo) == _HALT


def _tmux_on(socket: str, *args: str) -> subprocess.CompletedProcess[str]:
    """Address a NAMED private socket, so a rival run can be stood up on purpose.

    The `tmux` fixture deliberately hides its socket; this leg is the one place
    that must name one, because the defect under test IS the name.
    """
    return subprocess.run(  # noqa: S603
        ["tmux", "-L", socket, *args],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )


def test_the_rigs_socket_is_not_shared_with_a_concurrent_run(
    *, tmux: Callable[..., subprocess.CompletedProcess[str]], tmp_path: Path
) -> None:
    """Two runs of this suite at once must not land on the SAME tmux socket.

    MEASURED 2026-07-30, and this is `overseer-jcw`. The rig named its socket
    `legs-{tmp_path.name}`, and `tmp_path.name` is the TEST's identity — byte
    identical across separate pytest invocations (`test_..._re0` both times).
    Unique per test and per xdist worker, as the rig's docstring says; NOT unique
    per RUN. So two concurrent `just check` invocations on one host shared a
    socket, the second `new-session -s wk` failed as a duplicate — silently, since
    the helper passes `check=False` and tmux still exits 0 — and the second run
    then read the FIRST run's pane, failing `assert live == str(repo)` at the line
    above with two different `pytest-NNNN` roots in the diff.

    That is why the symptom presented as a COVERAGE shortfall: the assertion dies
    partway through, so the lines below it never execute, and per-file coverage
    reports them missing rather than pytest reporting a failure people would read.

    Reproduced on demand before this test existed: the leg above passed 2/2 run
    alone and failed when two invocations were run concurrently.

    Sabotage that reddens this: restore `socket = f"legs-{tmp_path.name}"` in
    `conftest.py`. The rival below is then OUR socket, and the fixture reads the
    rival's pane.
    """
    mine = tmp_path / "mine"
    mine.mkdir()
    theirs = tmp_path / "theirs"
    theirs.mkdir()

    # Stand in for a concurrent run of this same test in another checkout: its
    # socket is whatever the rig derives from the test identity ALONE.
    rival = f"legs-{tmp_path.name}"  # rig-socket-rival
    _tmux_on(rival, "new-session", "-d", "-s", "wk", "-x", "80", "-y", "20", "-c", str(theirs))
    try:
        tmux("new-session", "-d", "-s", "wk", "-x", "80", "-y", "20", "-c", str(mine))
        live = tmux("display-message", "-p", "-t", "=wk:", "#{pane_current_path}").stdout.strip()
        assert live == str(mine)
    finally:
        _tmux_on(rival, "kill-server")
