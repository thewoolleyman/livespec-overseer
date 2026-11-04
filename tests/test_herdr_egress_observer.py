"""Controls for the fixture server's procfs-based egress observer."""

from __future__ import annotations

import socket
from pathlib import Path

import herdr_live_server
import pytest

__all__: list[str] = []

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_the_observer_follows_descendants_and_socket_inodes(
    *, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A non-local peer is discovered from the owning process's open descriptor."""

    class _ProcPath:
        def __init__(self, value: str) -> None:
            self.value = value

        @property
        def name(self) -> str:
            return self.value.rsplit("/", maxsplit=1)[-1]

        def __truediv__(self, child: str) -> _ProcPath:
            return _ProcPath(f"{self.value}/{child}")

        def iterdir(self) -> list[_ProcPath]:
            entries = {
                "/proc": ["10", "11", "12", "bad", "13"],
                "/proc/10/fd": ["3", "4"],
                "/proc/11/fd": PermissionError("hidden descendant descriptors"),
                "/proc/12/fd": ["3"],
            }
            result = entries.get(self.value, [])
            if isinstance(result, OSError):
                raise result
            return [_ProcPath(f"{self.value}/{entry}") for entry in result]

        def read_text(self, *, encoding: str) -> str:
            del encoding
            contents = {
                "/proc/10/stat": "10 (server) S 12 0",
                "/proc/11/stat": "11 (child) S 10 0",
                "/proc/12/stat": "12 (grandchild) S 11 0",
                "/proc/net/tcp": "\n".join(
                    (
                        "sl local_address rem_address st tx_queue rx_queue tr tm->when "
                        "retrnsmt uid timeout inode",
                        "0: 0100007F:0000 08080808:01BB 01 00000000:00000000 "
                        "00:00000000 00000000 1000 0 123",
                        "1: 0100007F:0000 0200007F:01BB 01 00000000:00000000 "
                        "00:00000000 00000000 1000 0 124",
                    )
                ),
            }
            if self.value == "/proc/13/stat":
                raise OSError("transient process exit")
            if self.value == "/proc/net/tcp6":
                raise OSError("no IPv6 table")
            return contents[self.value]

        def readlink(self) -> str:
            links = {
                "/proc/10/fd/3": "socket:[123]",
                "/proc/10/fd/4": "/dev/null",
                "/proc/12/fd/3": "socket:[124]",
            }
            return links[self.value]

    assert hasattr(herdr_live_server, "outbound_internet_connections")
    monkeypatch.setattr(herdr_live_server, "Path", _ProcPath)

    assert herdr_live_server._process_descendants(root_pid=10) == {10, 11, 12}
    assert herdr_live_server._socket_inodes(pids={10, 11, 12}) == {"123", "124"}
    assert herdr_live_server._external_tcp_sockets(inodes={"123", "124"}) == ("8.8.8.8:443",)
    assert herdr_live_server.outbound_internet_connections(server_pid=10) == ("8.8.8.8:443",)


def test_the_observer_recognizes_local_peers_and_both_ip_families() -> None:
    """Loopback is not egress, while procfs TCP encodings remain readable."""
    assert hasattr(herdr_live_server, "_is_local_or_unspecified")
    assert herdr_live_server._is_local_or_unspecified(address="127.0.0.2")
    assert herdr_live_server._remote_address(encoded="08080808", family=socket.AF_INET) == "8.8.8.8"
    assert (
        herdr_live_server._remote_address(
            encoded="00000000000000000000000001000000", family=socket.AF_INET6
        )
        == "::1"
    )


def test_fixture_config_requires_each_disabled_update_check(*, tmp_path: Path) -> None:
    """A custom fixture config is rejected unless both startup checks are off."""
    assert hasattr(herdr_live_server, "_require_disabled_update_checks")
    config = tmp_path / "fixture.toml"
    _ = config.write_text("[update]\nversion_check = false\n", encoding="utf-8")

    with pytest.raises(AssertionError, match="manifest_check"):
        herdr_live_server._require_disabled_update_checks(path=config)


def test_the_codex_herdr_exercise_writes_its_hermetic_config_before_starting() -> None:
    """The process that starts the exercise server owns its no-egress config."""
    controller = (REPO_ROOT / "scripts" / "overseer-live-exercise-inside.sh").read_text(
        encoding="utf-8"
    )
    config = "[update]\nversion_check = false\nmanifest_check = false"
    backend_start = 'herdr --session "$instance" server'

    assert config in controller
    assert controller.index(config) < controller.index(backend_start)
