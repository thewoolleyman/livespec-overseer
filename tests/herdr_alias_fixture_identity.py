"""Session-path identities owned by the native Herdr alias fixture."""

from __future__ import annotations

import os
import socket
import tempfile
from functools import cache
from hashlib import sha256
from itertools import count
from pathlib import Path

__all__ = [
    "alias_session_name",
    "herdr_api_socket_path",
    "herdr_client_socket_path",
    "unix_socket_path_capacity",
]

_SESSION_PREFIX = "ov-alias-"
_SESSION_DIGEST_CHARACTERS = 32
_SESSION_SEQUENCE = count()


def alias_session_name(*, label: str) -> str:
    """A fixed-width identity derived from unbounded fixture inputs."""
    material = f"{os.getpid()}\0{next(_SESSION_SEQUENCE)}\0{label}".encode()
    digest = sha256(material, usedforsecurity=False).hexdigest()[:_SESSION_DIGEST_CHARACTERS]
    session = f"{_SESSION_PREFIX}{digest}"
    client_socket = herdr_client_socket_path(session=session)
    capacity = unix_socket_path_capacity()
    assert len(os.fsencode(client_socket)) < capacity, (
        f"bounded Herdr fixture identity still exceeds this host's native socket budget: "
        f"{client_socket} is {len(os.fsencode(client_socket))} bytes; sun_path capacity is "
        f"{capacity} bytes including its terminator"
    )
    return session


def herdr_api_socket_path(*, session: str) -> Path:
    """The public API socket Herdr derives for ``session``."""
    return Path.home() / ".config" / "herdr" / "sessions" / session / "herdr.sock"


def herdr_client_socket_path(*, session: str) -> Path:
    """The longer native-client socket Herdr also derives for ``session``."""
    return herdr_api_socket_path(session=session).with_name("herdr-client.sock")


@cache
def unix_socket_path_capacity() -> int:
    """First pathname byte length rejected by this host's real AF_UNIX bind."""
    with tempfile.TemporaryDirectory(prefix="overseer-sun-path-") as scratch:
        root = Path(scratch)
        path_prefix_bytes = len(os.fsencode(root)) + 1
        byte_length = path_prefix_bytes + 1
        while True:
            address = root / ("s" * (byte_length - path_prefix_bytes))
            try:
                with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
                    listener.bind(str(address))
            except OSError:
                return byte_length
            finally:
                address.unlink(missing_ok=True)
            byte_length += 1
