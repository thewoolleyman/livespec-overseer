"""The daemon's installed artifact identity must remain its process identity.

Linux presentation names are descriptive and can be changed independently of the
executable or command.  Bootstrap and proof therefore identify ``overseerd`` by its
PID/start tuple, executable and installed command; starting the daemon must not add a
``prctl(PR_SET_NAME)`` side effect merely to make a presentation-name observer pass.
"""

from __future__ import annotations

import ctypes
from pathlib import Path

import pytest

from overseer import daemon

__all__: list[str] = []


def test_daemon_start_does_not_replace_its_kernel_presentation_name(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple[object, ...]] = []

    class _Libc:
        def prctl(self, *args: object) -> int:
            calls.append(args)
            return 0

    monkeypatch.setattr(ctypes, "CDLL", lambda *_args, **_kwargs: _Libc())
    monkeypatch.setattr(daemon, "_default_daemon_log_path", lambda: tmp_path / "daemon.log")
    monkeypatch.setattr(daemon.supervisor, "run_daemon", lambda **_kwargs: 0)

    assert daemon.main(argv=[]) == 0
    assert calls == []
