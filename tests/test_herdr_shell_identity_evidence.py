"""What counts as the created pane's retained shell, and what only looks like it.

Unit-level companion to `tests/test_herdr_live_exec_replaced_shell.py`, which
drives the same defect against a real server. That file proves the behaviour;
this one pins the evidence rule, including the shapes a healthy server will not
produce on demand (an unreadable `/proc`, a server whose reported name disagrees
with the kernel's).

**The rule, and an honest account of which half carries which weight.**

  - **Cross-observation identity equality is the airtight half.** The establish
    reading records the whole observed identity — pid, the executable the KERNEL
    reports, and the start time — and the recheck must match it exactly. That
    catches a root replaced between the two readings with no judgement about
    what a shell is: `exec` keeps the pid and the start time, so the executable
    is what moves, and any change at all refuses.
  - **Positive evidence at establish is the narrowing half, and it does not
    certify ownership.** A root replaced BEFORE either reading produces two
    readings that agree perfectly, so equality cannot see it. What refuses it is
    that the executable the kernel reports is not a login shell ACCORDING TO THE
    SYSTEM — `/etc/shells` plus the invoking user's passwd entry, read from the
    host rather than enumerated here. That is the operating system's own answer
    to the question, not an allowlist authored in this repository, and it is
    deliberately not the sole proof of anything: its limit is that one login
    shell `exec`-ing over another is not distinguishable by it, and nothing here
    pretends otherwise.
  - **Neither the server's reported name nor the kernel's executable is trusted
    alone.** They must AGREE. A reported name is a claim by the process's host
    server; an executable is a claim by the kernel; requiring both to describe
    the same program means a single lying source refuses rather than decides.

Start time is carried for a different failure than the one that prompted this:
`exec` preserves it (measured), so it cannot see a replacement — it sees PID
REUSE, a genuinely different process arriving at the same number.

The live readers are exercised against real host facts rather than mocked, but
only facts this test process can assert about ITSELF: its own `/proc` identity,
and that the system login-shell set really reflects `/etc/shells`. Judging a
shell needs a shell, and that belongs in the native file.
"""

from __future__ import annotations

import importlib
import os
from pathlib import Path
from typing import Any

import pytest

__all__: list[str] = []

MODULE_PATH = Path(__file__).resolve().parent.parent / "overseer" / "_herdr_shell_identity.py"

PANE = "w1:p2"
OTHER_PANE = "w1:p1"
SHELL_PID = 4100
CHILD_PID = 4200
BASH = "/usr/bin/bash"
SLEEP = "/usr/bin/sleep"
STARTTIME = "164433575"
LOGIN_SHELLS = frozenset({BASH, "/usr/bin/sh", "/usr/bin/dash"})


def _module() -> Any:
    """The shell-identity collaborator, imported INSIDE the test body.

    A top-level import would make the Red a collection error, which proves only
    that a module is missing rather than that the rule is unimplemented.
    """
    assert MODULE_PATH.is_file(), (
        "the retained-shell proof owes a shell-identity module at "
        f"{MODULE_PATH.relative_to(MODULE_PATH.parent.parent)}"
    )
    return importlib.import_module("_herdr_shell_identity")


def _reply(
    *,
    pane_id: str = PANE,
    shell_pid: int = SHELL_PID,
    group_id: int | None = None,
    name: str = "bash",
) -> dict[str, object]:
    """A measured `pane.process_info` result, idle unless a group id is given."""
    leader = shell_pid if group_id is None else group_id
    return {
        "process_info": {
            "pane_id": pane_id,
            "shell_pid": shell_pid,
            "foreground_process_group_id": leader,
            "foreground_processes": [{"pid": leader, "name": name, "cmdline": name, "cwd": "/tmp"}],
        }
    }


def _evidence(*, module: Any, executable: str, starttime: str = STARTTIME) -> Any:
    """A live-evidence seam answering for any pid with the given executable."""

    def read(*, pid: int) -> Any:
        return module.ShellIdentity(pid=pid, executable=executable, starttime=starttime)

    return read


def _unreadable(*, pid: int) -> Any:
    """The seam's answer when `/proc` cannot be read for that pid."""
    return None


def _establish(*, module: Any, reply: dict[str, object], evidence_of: Any) -> Any:
    return module.retained_shell(
        result=reply,
        pane_id=PANE,
        expected=None,
        evidence_of=evidence_of,
        login_shells=LOGIN_SHELLS,
    )


def test_an_idle_root_that_the_system_calls_a_login_shell_is_established():
    """The positive control: kernel and server agree, and the system knows the binary."""
    module = _module()

    established = _establish(
        module=module, reply=_reply(), evidence_of=_evidence(module=module, executable=BASH)
    )

    assert established.error == "", established.error
    assert established.identity == module.ShellIdentity(
        pid=SHELL_PID, executable=BASH, starttime=STARTTIME
    )


def test_a_root_the_system_does_not_call_a_login_shell_is_refused():
    """The replaced-before-either-reading case, where equality cannot help.

    Both readings would describe `sleep` and agree with each other, so the only
    thing left to refuse on is what the program IS.
    """
    module = _module()

    established = _establish(
        module=module,
        reply=_reply(name="sleep"),
        evidence_of=_evidence(module=module, executable=SLEEP),
    )

    assert established.identity is None
    assert SLEEP in established.error, established.error


def test_a_reported_name_disagreeing_with_the_kernel_is_refused():
    """One lying source must refuse rather than decide.

    The server says `bash`; the kernel says the executable is `sleep`. Either
    could be the wrong one, which is exactly why neither is allowed to settle it
    alone.
    """
    module = _module()

    established = _establish(
        module=module,
        reply=_reply(name="bash"),
        evidence_of=_evidence(module=module, executable=SLEEP),
    )

    assert established.identity is None, established.error


def test_unreadable_live_evidence_is_refused_rather_than_assumed_idle():
    """No `/proc` answer is not an idle shell; it is no evidence at all."""
    module = _module()

    established = _establish(module=module, reply=_reply(), evidence_of=_unreadable)

    assert established.identity is None
    assert "evidence" in established.error, established.error


def test_an_occupied_or_foreign_or_unreadable_reply_never_reaches_the_evidence():
    """The reply-level refusals are unchanged by the new evidence layer."""
    module = _module()
    readable = _evidence(module=module, executable=BASH)

    occupied = _establish(module=module, reply=_reply(group_id=CHILD_PID), evidence_of=readable)
    foreign = _establish(module=module, reply=_reply(pane_id=OTHER_PANE), evidence_of=readable)
    unreadable = _establish(module=module, reply={"process_info": "nope"}, evidence_of=readable)

    assert occupied.identity is None and "OCCUPIED" in occupied.error, occupied.error
    assert foreign.identity is None, foreign.error
    assert unreadable.identity is None, unreadable.error


def test_a_recheck_refuses_any_change_to_the_established_identity():
    """The airtight half, driven across all three members of the identity.

    The executable case is `exec` at the same pid — the defect that prompted all
    of this. The start-time case is pid reuse, which `exec` does NOT produce and
    which equality catches for free.
    """
    module = _module()
    established = module.ShellIdentity(pid=SHELL_PID, executable=BASH, starttime=STARTTIME)

    def recheck(*, executable: str, starttime: str, shell_pid: int = SHELL_PID) -> Any:
        return module.retained_shell(
            result=_reply(shell_pid=shell_pid),
            pane_id=PANE,
            expected=established,
            evidence_of=_evidence(module=module, executable=executable, starttime=starttime),
            login_shells=LOGIN_SHELLS,
        )

    unchanged = recheck(executable=BASH, starttime=STARTTIME)
    exec_replaced = recheck(executable=SLEEP, starttime=STARTTIME)
    reused_pid = recheck(executable=BASH, starttime="999999999")
    other_pid = recheck(executable=BASH, starttime=STARTTIME, shell_pid=SHELL_PID + 7)

    assert unchanged.error == "", unchanged.error
    assert unchanged.identity == established
    assert exec_replaced.identity is None, "an exec-replaced root must not be rechecked clean"
    assert reused_pid.identity is None, "a different start time at the same pid is not the shell"
    assert other_pid.identity is None, "a different shell pid is a replaced shell"


def test_the_system_login_shell_set_comes_from_the_host_not_from_this_repo():
    """`/etc/shells` and the passwd entry are the source, read rather than listed.

    Asserted against the host's own files so a hand-authored set substituted
    later would not satisfy it. Skipped rather than faked where the host carries
    no `/etc/shells`, because inventing one here would defeat the point.
    """
    module = _module()
    registry = Path("/etc/shells")
    if not registry.is_file():
        pytest.skip("this host carries no /etc/shells to read")

    resolved = module.system_login_shells()

    declared = {
        os.path.realpath(line.strip())
        for line in registry.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    }
    assert declared, "fixture precondition: /etc/shells names at least one shell"
    assert declared <= resolved, f"{declared - resolved} declared in /etc/shells but not resolved"


def test_the_live_reader_reports_this_test_process_s_own_kernel_identity():
    """The `/proc` reader is exercised against a process this test can vouch for.

    Its own. The executable must be the running interpreter and the start time
    must match `/proc` field 22 read independently, so the reader is measured
    rather than assumed; a pid that cannot exist reads as no evidence.
    """
    module = _module()

    mine = module.proc_shell_identity(pid=os.getpid())

    assert mine is not None, "this process must have a readable /proc identity"
    assert mine.pid == os.getpid()
    assert mine.executable == os.path.realpath(f"/proc/{os.getpid()}/exe")
    stat = Path(f"/proc/{os.getpid()}/stat").read_text(encoding="utf-8")
    assert mine.starttime == stat[stat.rindex(")") + 1 :].split()[19]
    assert module.proc_shell_identity(pid=-1) is None, "an impossible pid is no evidence"


def test_every_reader_fails_closed_when_the_host_will_not_answer(
    *, monkeypatch: pytest.MonkeyPatch
):
    """The four ways the host can decline, each yielding no evidence rather than a guess.

    POST-IMPLEMENTATION coverage, stated rather than implied: the behaviour these
    four assert was written for the exec-replacement pair above, and these cases
    were authored afterwards to pin its fail-closed edges. They are not original
    Red-first evidence for it.

    Each matters for a different real condition. A process that dies between the
    two `/proc` reads yields an executable and no start time. A host with no
    `/etc/shells` and an account with no passwd shell both leave the registry
    unable to corroborate anything — and an EMPTY registry is deliberately not
    special-cased: it refuses every establish, which for a write is the safe
    direction.
    """
    module = _module()

    monkeypatch.setattr(module.claude_sessions, "proc_starttime", lambda *, pid: None)
    assert (
        module.proc_shell_identity(pid=os.getpid()) is None
    ), "a readable executable with no start time is not an identity"

    monkeypatch.setattr(module, "LOGIN_SHELL_REGISTRY", "/nonexistent/etc/shells")

    class _NoShell:
        pw_shell = ""

    monkeypatch.setattr(module.pwd, "getpwuid", lambda _uid: _NoShell())
    assert module.system_login_shells() == frozenset(), "an empty passwd shell registers nothing"

    def _absent(_uid: int) -> object:
        raise KeyError(_uid)

    monkeypatch.setattr(module.pwd, "getpwuid", _absent)
    assert (
        module.system_login_shells() == frozenset()
    ), "an uid with no passwd entry and no /etc/shells corroborates nothing"
