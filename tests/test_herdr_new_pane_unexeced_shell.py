"""A freshly split pane whose shell has not exec'd yet is read again, not refused.

Measured 2026-10-12 in a pre-push run of
tests/integration/test_overseer_start_public_herdr.py: herdr answered the new
pane's process info while its forked child was still the herdr image, so the
server named the shell 'herdr' and the kernel, read a moment later, ran
/usr/bin/dash. The start refused ("herdr calls shell ... 'herdr' while the kernel
runs '/usr/bin/dash'; one of the two is wrong"), failing overseer-start under load.
"""

from __future__ import annotations

from typing import Any, cast

import _herdr_layout_proofs
import _herdr_shell_identity
import herdr_identity
import herdr_transport

__all__: list[str] = []

_PANE = "w1:p3"
_SHELL_PID = 4100
_DASH = "/usr/bin/dash"
_TARGET = herdr_identity.HerdrPaneTarget(
    socket_path="/run/herdr-test.sock", server_pid=41, server_starttime="777", pane_id="w1:p1"
)


def _reply(*, name: str) -> herdr_transport.RpcOutcome:
    return herdr_transport.RpcOutcome(
        ok=True,
        result={
            "process_info": {
                "pane_id": _PANE,
                "shell_pid": _SHELL_PID,
                "foreground_process_group_id": _SHELL_PID,
                "foreground_processes": [
                    {"pid": _SHELL_PID, "name": name, "cmdline": name, "cwd": "/tmp"}
                ],
            }
        },
        error="",
        peer=None,
        timed_out=False,
        request_sent=True,
    )


class _Requests:
    def __init__(self, *, names: list[str]) -> None:
        self.names = names
        self.reads = 0

    def request(self, **_kwargs: Any) -> herdr_transport.RpcOutcome:
        self.reads += 1
        return _reply(name=self.names.pop(0) if len(self.names) > 1 else self.names[0])


def _proof() -> _herdr_shell_identity.ShellProof:
    def evidence(*, pid: int) -> _herdr_shell_identity.ShellIdentity:
        return _herdr_shell_identity.ShellIdentity(pid=pid, executable=_DASH, starttime="99")

    return _herdr_shell_identity.ShellProof(evidence_of=evidence, login_shells=frozenset({_DASH}))


def _establish(*, requests: _Requests) -> _herdr_shell_identity.RetainedShell:
    return _herdr_layout_proofs.retained_shell(
        requester=cast(_herdr_layout_proofs.BoundedRequests, requests),
        target=_TARGET,
        created=_PANE,
        expected=None,
        proof=_proof(),
    )


def test_a_shell_still_named_for_the_server_is_read_again_until_it_execs() -> None:
    requests = _Requests(names=["herdr", "dash"])

    shell = _establish(requests=requests)

    assert shell.error == ""
    assert shell.identity is not None
    assert requests.reads == 2


def test_a_real_name_mismatch_is_still_refused_at_once() -> None:
    requests = _Requests(names=["bash"])

    shell = _establish(requests=requests)

    assert "one of the two is wrong" in shell.error
    assert requests.reads == 1


def test_a_shell_that_never_execs_is_refused_once_the_bound_is_spent() -> None:
    requests = _Requests(names=["herdr"])

    shell = _establish(requests=requests)

    assert "one of the two is wrong" in shell.error
    assert requests.reads > 1
