"""Every real-tmux rig in this directory must name its socket UNIQUELY PER RUN.

`overseer-jcw`, and the reason this is a gate rather than two fixes: the defect
appeared in `conftest.py` as `legs-{tmp_path.name}` and AGAIN, independently, in
`test_emitted_commands_discriminate.py` as `disc-{tmp_path.name}`. Fixing the
shared conftest left the second one live, and it failed on the very next
concurrent run. A per-module socket scheme is a per-module copy of the bug, so
the third module to grow one would reintroduce it silently.

WHY `tmp_path.name` IS NOT ENOUGH. It is the TEST's identity —
`test_the_pane_cwd_the_forms_re0` — and is byte-identical across separate pytest
invocations (measured: two runs, same string). Unique per test and per xdist
worker; NOT unique per RUN. Two concurrent `just check` invocations on one host
therefore addressed the same `tmux -L` server, the second `new-session` failed as
a duplicate WITHOUT being noticed (the helpers pass `check=False` and tmux still
exits 0), and the second run read the first run's pane.

The symptom is why this was hard to place: the assertion dies partway through the
test, so the lines below it never execute, and the aggregate reports a COVERAGE
shortfall rather than a test failure.

THIS DETECTOR KEYS ON THE PROPERTY — the ABSENCE of a per-process component in a
socket name — not on the presence of either wrong spelling. `legs-` and `disc-`
are not mentioned in the rule.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import cast

import pytest
import test_emitted_commands_discriminate as emitted_commands
import test_repo_containment_discriminates as repo_containment

import conftest

__all__: list[str] = []

_RIG_DIR = Path(__file__).resolve().parent

# An ASSIGNMENT of an f-string interpolating the test's identity. That is the
# ingredient which repeats across runs, so any socket built from it needs
# something that does not.
#
# Keyed on the ASSIGNMENT, not on any occurrence of the substring, and that is
# load-bearing: the first draft matched anywhere on the line and immediately
# flagged its own neighbour's DOCSTRING — the sentence documenting the sabotage
# that reddens this very rule. A detector fooled by prose that MENTIONS the
# defect is the same failure the charter gate carries a dedicated control for.
_TEST_IDENTITY = re.compile(r'^[A-Za-z_]\w*\s*=\s*f"[^"]*\{tmp_path\.name\}')

# A run-unique component. `os.getpid()` is the one in use; the rule accepts any
# spelling that names the process, so a later rig may use `os.getpid` directly.
_RUN_UNIQUE = re.compile(r"getpid")

# A line may build the collision-prone form ON PURPOSE — the leg in
# `test_repo_containment_discriminates.py` stands up a RIVAL run and must
# reproduce exactly the name a concurrent run would compute. Such a line says so.
_DELIBERATE = "rig-socket-rival"


def _tmux_socket_dir() -> Path:
    base = Path(os.environ.get("TMUX_TMPDIR", "/tmp"))
    return base / f"tmux-{os.getuid()}"


def _socket_count(*, name: str) -> int:
    path = _tmux_socket_dir() / name
    return int(path.exists() and path.is_socket())


def _tmux_call(*, socket: str, args: tuple[str, ...]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        ["tmux", "-L", socket, *args],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )


def _offending_lines(*, text: str) -> list[str]:
    """Lines building a socket name from the test identity with nothing run-unique."""
    found: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("#") or _DELIBERATE in line:
            continue
        if _TEST_IDENTITY.search(line) and not _RUN_UNIQUE.search(line):
            found.append(line)
    return found


def _rig_modules() -> list[Path]:
    """Every module in this directory EXCEPT this one.

    This file is excluded because its positive control must contain both
    historical spellings as literal test data, and a rule that scanned its own
    control would flag it forever. The exclusion is safe precisely because this
    module drives no tmux and therefore has no socket to misname — if that ever
    changes, the socket belongs in a rig, not here.
    """
    here = Path(__file__).resolve().name
    return sorted(p for p in _RIG_DIR.glob("*.py") if p.name != here)


def test_there_are_rig_modules_to_scan() -> None:
    """A gate over an empty file set passes vacuously and proves nothing.

    Sabotage that reddens this: point `_RIG_DIR` at a directory with no modules.
    """
    assert len(_rig_modules()) > 1


def test_no_rig_names_its_socket_from_the_test_identity_alone() -> None:
    """THE GATE. A third rig growing its own socket scheme fails here.

    Sabotage that reddens this: restore `f"disc-{tmp_path.name}"` in
    `test_emitted_commands_discriminate.py`.
    """
    offences = {
        path.name: _offending_lines(text=path.read_text(encoding="utf-8"))
        for path in _rig_modules()
    }
    assert {name: lines for name, lines in offences.items() if lines} == {}


def test_the_detector_fires_on_the_shape_it_is_written_for() -> None:
    """POSITIVE CONTROL. A zero from a scan is worthless without one.

    Both historical spellings must be caught by a rule that names neither, and
    the fixed form and the deliberate-rival form must both come back clean.
    """
    assert _offending_lines(text='    name = f"disc-{tmp_path.name}"') != []
    assert _offending_lines(text='    socket = f"legs-{tmp_path.name}"') != []
    assert _offending_lines(text='    s = f"anything-{tmp_path.name}-suffix"') != []

    assert _offending_lines(text='    socket = f"legs-{os.getpid()}-{tmp_path.name}"') == []
    assert _offending_lines(text=f'    rival = f"legs-{{tmp_path.name}}"  # {_DELIBERATE}') == []
    assert _offending_lines(text='    # socket = f"legs-{tmp_path.name}"') == []

    # PROSE MUST NOT COUNT AS CODE. This is not hypothetical: the first draft of
    # this rule flagged exactly this sentence, sitting in a neighbouring
    # docstring, and went red before any defect existed.
    prose = '    Sabotage that reddens this: restore `socket = f"legs-{tmp_path.name}"` in'
    assert _offending_lines(text=prose) == []


def test_the_shared_tmux_fixture_unlinks_only_its_own_socket(*, tmp_path: Path) -> None:
    """A killed rig server must not leave a socket file behind.

    Measured 2026-08-19: 22,715 orphan rig sockets, oldest 2026-07-18. This
    test must not sweep them; it names only the socket created by this fixture
    instance and proves an independently named neighbour survives.
    """
    rig_socket = f"legs-{os.getpid()}-{tmp_path.name}"
    control_socket = f"control-{os.getpid()}-{tmp_path.name}"
    before = _socket_count(name=rig_socket)

    control = _tmux_call(socket=control_socket, args=("new-session", "-d", "-s", "control"))
    try:
        assert control.returncode == 0, control.stderr
        assert _socket_count(name=control_socket) == 1
        wrapped = cast("object", conftest._tmux_fixture).__pytest_wrapped__.obj
        fixture = wrapped(tmp_path=tmp_path)
        tmux = next(fixture)
        tmux("new-session", "-d", "-s", "rig")
        assert _socket_count(name=rig_socket) == before + 1

        with pytest.raises(StopIteration):
            next(fixture)

        assert _socket_count(name=rig_socket) == before
        assert _socket_count(name=control_socket) == 1
    finally:
        _tmux_call(socket=control_socket, args=("kill-server",))
        (_tmux_socket_dir() / control_socket).unlink(missing_ok=True)


def test_the_emitted_commands_fixture_unlinks_its_socket(*, tmp_path: Path) -> None:
    """The module-local `disc-*` rig must not keep leaking after teardown."""
    socket = f"disc-{os.getpid()}-{tmp_path.name}"
    before = _socket_count(name=socket)
    wrapped = cast("object", emitted_commands._socket).__pytest_wrapped__.obj
    fixture = wrapped(tmp_path=tmp_path)
    try:
        next(fixture)
        assert _socket_count(name=socket) == before + 1
    finally:
        with pytest.raises(StopIteration):
            next(fixture)

    assert _socket_count(name=socket) == before


def test_the_repo_containment_rival_socket_is_unlinked(*, tmp_path: Path) -> None:
    """The deliberate rival socket must survive only for the duration of its test."""
    socket = f"legs-{tmp_path.name}"
    before = _socket_count(name=socket)

    try:
        repo_containment._tmux_on(socket, "new-session", "-d", "-s", "wk")
        assert _socket_count(name=socket) == before + 1
    finally:
        repo_containment._tmux_on(socket, "kill-server")
        repo_containment._tmux_socket_path(socket=socket).unlink(missing_ok=True)

    assert _socket_count(name=socket) == before
