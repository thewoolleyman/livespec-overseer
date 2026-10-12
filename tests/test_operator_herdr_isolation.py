"""The suite can never touch the operator's live herdr, even when run from inside it.

Measured 2026-10-12: CLI start tests that mocked tmux selected the REAL herdr driver
through ownership-by-ancestry and left 74 `topic`/`supervisor` workspaces, each
rooted in a deleted pytest directory, in the herdr session the suite ran from.
Scrubbing environment variables alone cannot prevent that, because ownership is
proven by ancestry, so the root conftest refuses the operator's endpoints
themselves. These tests pin that refusal.
"""

from __future__ import annotations

import os
import socket
import subprocess
from pathlib import Path

import pytest
import terminal_probes

__all__: list[str] = []


def _operator_default_socket() -> str:
    # Passing `home` bypasses the per-test repoint and yields the REAL default path.
    return terminal_probes.default_herdr_socket(home=Path.home())


def test_connecting_to_the_operator_herdr_socket_is_refused(
    *, operator_herdr_guard: list[str]
) -> None:
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        with pytest.raises(RuntimeError, match="operator's live herdr socket"):
            sock.connect(_operator_default_socket())
    finally:
        sock.close()
    assert len(operator_herdr_guard) == 1
    operator_herdr_guard.clear()


def test_the_refusal_is_not_an_oserror_that_product_code_would_swallow(
    *, operator_herdr_guard: list[str]
) -> None:
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        with pytest.raises(RuntimeError) as refused:
            sock.connect(_operator_default_socket())
    finally:
        sock.close()
    assert not isinstance(refused.value, OSError)
    operator_herdr_guard.clear()


@pytest.mark.parametrize(
    "args",
    [
        ["workspace", "create", "--label", "topic"],
        ["pane", "list"],
        ["workspace", "list"],
    ],
)
def test_herdr_cli_against_the_default_server_is_refused(
    *, args: list[str], operator_herdr_guard: list[str]
) -> None:
    with pytest.raises(RuntimeError, match="operator's default server"):
        subprocess.run(["herdr", *args], check=False)  # noqa: S603, S607
    assert len(operator_herdr_guard) == 1
    operator_herdr_guard.clear()


def test_isolated_herdr_cli_forms_are_not_refused(
    *, tmp_path: Path, operator_herdr_guard: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    # A stand-in `herdr` that only records, so this runs on hosts without herdr.
    fake = tmp_path / "herdr"
    fake.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    fake.chmod(0o755)
    for args in (["--session", "probe", "server", "stop"], ["session", "delete", "probe"]):
        assert subprocess.run([str(fake), *args], check=False).returncode == 0  # noqa: S603
    assert operator_herdr_guard == []


def test_unrelated_unix_sockets_still_connect(
    *, tmp_path: Path, operator_herdr_guard: list[str]
) -> None:
    address = str(tmp_path / "s.sock")
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        server.bind(address)
        server.listen(1)
        client.connect(address)
    finally:
        client.close()
        server.close()
    assert operator_herdr_guard == []


def test_ambient_herdr_selectors_are_scrubbed_inside_a_test() -> None:
    assert terminal_probes.HERDR_SOCKET_ENV not in os.environ
    assert terminal_probes.default_herdr_socket() != _operator_default_socket()
