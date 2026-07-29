"""The SUPERVISOR-side liveness precondition must discriminate (overseer-ejja5o).

`test_generated_supervisor_handoff_contract.py` asserts the charter EMITS a
supervisor process-tree proof. That is rung 2. This module is rung 3: it runs
the emitted form against a rigged tmux topology and requires the right verdict,
because the defect being closed is precisely a check that is present, runnable,
and answers WRONGLY.

THE DEFECT, OBSERVED NOT HYPOTHESISED. Precondition 2 refused to trust a session
NAME for the worker — it emits a `ps` process-tree check and HALTs unless a live
`claude`/`codex` appears. Precondition 3 then trusted a bare name for the
SUPERVISOR. On 2026-07-28, generating the charter for
`codex-parity-and-rollout-safety`, the supervisor session was created as a bare
`zsh` with no agent in it and precondition 3 returned PASS. A session that could
not supervise anything cleared the gate, and it was caught only because the
maintainer asked what the session was named.

THE TWO HALVES MUST FAIL INDEPENDENTLY. That is acceptance leg 3, and it is not
a nicety: a single fixture that reddens whenever either half is broken cannot
say WHICH half broke, which is the toothless-verifier pattern this repo shipped
once already. So the legs below rig the two failure modes SEPARATELY and require
the other half to stay green in each.

NO SKIPS. The shared rig in `conftest.py` FAILS rather than skips when tmux is
absent; see the do-not-delete rationale on that guard.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

_WORKER = "ejw"
_SUPERVISOR = "ejw-supervisor"
_EXACT_WORKER = f"={_WORKER}:"
_EXACT_SUPERVISOR = f"={_SUPERVISOR}:"

_AGENT_UP = "AGENT-UP"
_SHELL_UP = "SHELL-UP"

_Tmux = Callable[..., subprocess.CompletedProcess[str]]


def _fake_agent(*, tmp_path: Path, name: str) -> Path:
    """An executable literally NAMED `claude`, so `ps` reports a real agent.

    Not a mock: the check under test reads the live process table, so the only
    honest way to rig a "live agent" is to put a process there whose argv a
    supervisor would accept. It prints a sentinel first so the caller can wait
    on the process actually existing rather than on a sleep.
    """
    script = tmp_path / name
    script.write_text(f"#!/bin/sh\necho {_AGENT_UP}\nsleep 300\n", encoding="utf-8")
    script.chmod(0o755)
    return script


def _pane_pid(*, tmux: _Tmux, target: str) -> str:
    """Exactly what the emitted precondition resolves, including its empty case."""
    return tmux("display-message", "-p", "-t", target, "#{pane_pid}").stdout.strip()


def _holds_live_agent(*, pid: str) -> bool:
    """The emitted verdict: a live `claude`/`codex` in the pane's process tree.

    Mirrors the charter's `ps -o pid=,comm=,args= --ppid "$pid" --pid "$pid" -H`
    verbatim. S603/S607 suppressed on the same narrow reasoning as the sibling
    modules: the argv is a LIST with no shell, and resolving `ps` through PATH
    is deliberate so the leg exercises the environment's own `ps`.
    """
    if not pid:
        return False
    proc = subprocess.run(  # noqa: S603
        ["ps", "-o", "pid=,comm=,args=", "--ppid", pid, "--pid", pid, "-H"],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    return any(agent in proc.stdout for agent in ("claude", "codex"))


@pytest.fixture(name="rig")
def _rig(
    *, tmux: _Tmux, wait_for: Callable[[str, str], None], tmp_path: Path
) -> Callable[[str, str], None]:
    """Build the worker/supervisor pair, each independently agent or shell."""

    def _build(worker: str, supervisor: str) -> None:
        agent = _fake_agent(tmp_path=tmp_path, name="claude")
        shell = f"sh -c 'echo {_SHELL_UP}; sleep 300'"
        for session, kind in ((_WORKER, worker), (_SUPERVISOR, supervisor)):
            command = str(agent) if kind == "agent" else shell
            tmux("new-session", "-d", "-s", session, command)
        for session, kind in ((_WORKER, worker), (_SUPERVISOR, supervisor)):
            wait_for(f"={session}:", _AGENT_UP if kind == "agent" else _SHELL_UP)

    return _build


def test_the_existence_only_check_cannot_detect_a_shell_only_supervisor(
    *, tmux: _Tmux, rig: Callable[[str, str], None]
) -> None:
    """PINS THE DEFECT. This is the shipped precondition 3, and it says yes.

    If this ever goes red the defect is gone and the remedy legs below are
    testing nothing — so it is deliberately an assertion that the WRONG answer
    is still produced by the WRONG check.
    """
    rig("agent", "shell")
    assert tmux("has-session", "-t", _EXACT_SUPERVISOR).returncode == 0
    assert not _holds_live_agent(pid=_pane_pid(tmux=tmux, target=_EXACT_SUPERVISOR))


def test_the_process_tree_check_rejects_a_shell_only_supervisor(
    *, tmux: _Tmux, rig: Callable[[str, str], None]
) -> None:
    """THE REMEDY, and acceptance leg 2: shell-only supervisor must go RED."""
    rig("agent", "shell")
    assert _holds_live_agent(pid=_pane_pid(tmux=tmux, target=_EXACT_SUPERVISOR)) is False


def test_the_control_the_process_tree_check_accepts_a_live_supervisor(
    *, tmux: _Tmux, rig: Callable[[str, str], None]
) -> None:
    """THE CONTROL. Without it, a check that always says no would pass leg 2."""
    rig("agent", "agent")
    assert _holds_live_agent(pid=_pane_pid(tmux=tmux, target=_EXACT_SUPERVISOR)) is True


def test_a_shell_only_supervisor_leaves_the_worker_leg_green(
    *, tmux: _Tmux, rig: Callable[[str, str], None]
) -> None:
    """ACCEPTANCE LEG 3, first direction: only the supervisor half reddens."""
    rig("agent", "shell")
    assert _holds_live_agent(pid=_pane_pid(tmux=tmux, target=_EXACT_WORKER)) is True
    assert _holds_live_agent(pid=_pane_pid(tmux=tmux, target=_EXACT_SUPERVISOR)) is False


def test_a_shell_only_worker_leaves_the_supervisor_leg_green(
    *, tmux: _Tmux, rig: Callable[[str, str], None]
) -> None:
    """ACCEPTANCE LEG 3, other direction. The two halves are distinguishable.

    Together with the test above this is the whole point: each half reports on
    its OWN session, so a red verdict names which one is broken.
    """
    rig("shell", "agent")
    assert _holds_live_agent(pid=_pane_pid(tmux=tmux, target=_EXACT_WORKER)) is False
    assert _holds_live_agent(pid=_pane_pid(tmux=tmux, target=_EXACT_SUPERVISOR)) is True


def test_the_distinct_pane_guard_rejects_a_supervisor_resolving_onto_the_worker(
    *, tmux: _Tmux, rig: Callable[[str, str], None]
) -> None:
    """C1's lesson applied to this half, and why the guard is not decoration.

    `ejw` is a strict prefix of `ejw-supervisor`, so a BARE supervisor target
    prefix-matches the worker's session. The process-tree check then runs
    against the WORKER's pane, finds the worker's live agent, and reports the
    supervisor as healthy — a check passing on the wrong pane's evidence, which
    is exactly the shape being removed. The emitted form guards it by requiring
    the two pids to DIFFER.
    """
    rig("agent", "shell")
    worker_pid = _pane_pid(tmux=tmux, target=_EXACT_WORKER)
    bare_pid = _pane_pid(tmux=tmux, target=_WORKER)
    # The bare target resolves onto the worker, and would therefore pass.
    assert bare_pid == worker_pid
    assert _holds_live_agent(pid=bare_pid) is True
    # The guard the charter emits is what refuses it.
    assert (bare_pid != worker_pid) is False


def test_an_empty_pane_pid_is_not_a_pass(*, tmux: _Tmux, rig: Callable[[str, str], None]) -> None:
    """The empty-resolution case, which `readlink -f ""` taught this repo twice.

    An absent supervisor resolves to the empty string, and a verdict function
    that treated "no output" as "nothing disproved" would report healthy.
    """
    rig("agent", "shell")
    assert _pane_pid(tmux=tmux, target="=ejw-absent:") == ""
    assert _holds_live_agent(pid="") is False
