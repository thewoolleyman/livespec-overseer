"""Listener-readiness support for native Herdr test fixtures."""

from __future__ import annotations

import socket
import struct
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

__all__ = [
    "ListenerPoll",
    "ListenerProbe",
    "ListenerReadiness",
    "OwnedChild",
    "await_owned_listener",
    "owned_listener_peer_pid",
]


class OwnedChild(Protocol):
    """The process facts the readiness wait needs from its owned server."""

    pid: int

    def poll(self) -> int | None: ...


ListenerProbe = Callable[..., int]


@dataclass(frozen=True, kw_only=True)
class ListenerPoll:
    """The startup bound and its injectable deterministic clock."""

    seconds: float
    monotonic: Callable[[], float] = time.monotonic
    sleep: Callable[[float], None] = time.sleep


@dataclass(frozen=True, kw_only=True)
class ListenerReadiness:
    """The accepting peer observed for one owned server."""

    attempts: int
    peer_pid: int


def owned_listener_peer_pid(*, socket_path: str, expected_pid: int) -> int:
    """Connect without transmitting and return the accepting AF_UNIX peer pid."""
    del expected_pid
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(0.1)
    try:
        sock.connect(socket_path)
        credentials = sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
    finally:
        sock.close()
    pid, _uid, _gid = struct.unpack("3i", credentials)
    return pid


def await_owned_listener(
    *,
    socket_path: Path,
    session: str,
    child: OwnedChild,
    poll: ListenerPoll,
    probe: ListenerProbe,
) -> ListenerReadiness:
    """Wait until `socket_path` accepts a byte-free connection from `child`."""
    deadline = poll.monotonic() + poll.seconds
    attempts = 0
    last_reason = f"socket path {socket_path} does not exist"
    while poll.monotonic() < deadline:
        status = child.poll()
        if status is not None:
            raise AssertionError(
                f"herdr session {session!r} owned server process {child.pid} exited "
                f"with status {status} before listener readiness after {attempts} "
                f"connect attempts ({last_reason})"
            )
        if socket_path.exists():
            attempts += 1
            try:
                peer_pid = probe(socket_path=str(socket_path), expected_pid=child.pid)
            except OSError as failed:
                last_reason = f"{type(failed).__name__}: {failed}"
            else:
                if peer_pid == child.pid:
                    return ListenerReadiness(attempts=attempts, peer_pid=peer_pid)
                last_reason = f"listener peer pid {peer_pid} is not owned child pid {child.pid}"
        poll.sleep(0.1)
    status = child.poll()
    if status is not None:
        raise AssertionError(
            f"herdr session {session!r} owned server process {child.pid} exited "
            f"with status {status} before listener readiness after {attempts} "
            f"connect attempts ({last_reason})"
        )
    raise AssertionError(
        f"herdr session {session!r} did not expose a connectable owned listener "
        f"at {socket_path} within {poll.seconds}s after {attempts} connect attempts "
        f"({last_reason})"
    )
