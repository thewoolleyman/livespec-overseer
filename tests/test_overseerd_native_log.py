"""Regression tests for overseerd's native daemon log."""

import streams

from overseer import daemon

__all__: list[str] = []


def test_overseerd_opens_native_daemon_log_without_shell_redirect(*, tmp_path, monkeypatch):
    """A manual bare `python -m overseer.daemon` bounce must still preserve daemon
    stderr in tmp/overseer/daemon.log; relying on the caller's shell redirect loses
    the event history."""
    log_path = tmp_path / "tmp" / "overseer" / "daemon.log"

    def _fake_run(*, warn_percent=None):
        del warn_percent
        streams.write_stderr(text="daemon event from bare launch\n")
        return 0

    monkeypatch.setattr(daemon, "_default_daemon_log_path", lambda: log_path, raising=False)
    monkeypatch.setattr(daemon.supervisor, "run_daemon", _fake_run)

    assert daemon.main(argv=[]) == 0
    assert log_path.is_file()
    assert "daemon event from bare launch\n" in log_path.read_text(encoding="utf-8")
