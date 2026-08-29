"""Regression tests for overseerd's native daemon log."""

import json
from pathlib import Path

import pytest
import streams

from overseer import daemon, start

__all__: list[str] = []


def test_overseerd_opens_native_daemon_log_without_shell_redirect(*, tmp_path, monkeypatch):
    """A manual bare `python -m overseer.daemon` bounce must still preserve daemon
    stderr in tmp/overseer/daemon.log; relying on the caller's shell redirect loses
    the event history."""
    log_path = tmp_path / "tmp" / "overseer" / "daemon.log"

    def _fake_run(*, warn_percent=None, idle_nudge=True):
        del warn_percent, idle_nudge
        streams.write_stderr(text="daemon event from bare launch\n")
        return 0

    monkeypatch.setattr(daemon, "_default_daemon_log_path", lambda: log_path, raising=False)
    monkeypatch.setattr(daemon.supervisor, "run_daemon", _fake_run)

    assert daemon.main(argv=[]) == 0
    assert log_path.is_file()
    assert "daemon event from bare launch\n" in log_path.read_text(encoding="utf-8")


def test_overseerd_open_event_is_structured(*, tmp_path, monkeypatch):
    """The first daemon-log line is part of the event stream, not a prose preamble."""
    log_path = tmp_path / "tmp" / "overseer" / "daemon.log"

    def _fake_run(*, warn_percent=None, idle_nudge=True):
        del warn_percent, idle_nudge
        return 0

    monkeypatch.setattr(daemon, "_default_daemon_log_path", lambda: log_path, raising=False)
    monkeypatch.setattr(daemon.supervisor, "run_daemon", _fake_run)

    assert daemon.main(argv=[]) == 0
    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    event = json.loads(lines[0])
    assert event["event"] == "daemon-log-opened"
    assert event["message"] == "daemon log opened"
    assert event["daemon_instance_id"] == "unknown"
    assert event["tick_generation"] == 0


def test_overseerd_native_log_prefers_checkout_when_installed_elsewhere(
    *, tmp_path: Path, monkeypatch
) -> None:
    """The daemon's own log resolver must match overseer-start's checkout rule."""
    prefix = tmp_path / "runtime" / "venv" / "lib" / "python3.10" / "site-packages"
    checkout = tmp_path / "operator-checkout"
    (prefix / "overseer").mkdir(parents=True)
    (checkout / "overseer").mkdir(parents=True)
    (checkout / "overseer" / "start.py").write_text("# checkout marker\n", encoding="utf-8")
    monkeypatch.setattr(start, "__file__", str(prefix / "overseer" / "start.py"))
    monkeypatch.chdir(checkout)

    assert daemon._default_daemon_log_path() == checkout / "tmp" / "overseer" / "daemon.log"
    assert not (prefix / "tmp").exists()


def test_overseerd_help_documents_log_export_and_warn_percent(
    *, capsys: pytest.CaptureFixture[str], tmp_path: Path, monkeypatch
) -> None:
    """A source-free operator must be able to find logs and configure export."""
    log_path = tmp_path / "tmp" / "overseer" / "daemon.log"
    monkeypatch.setattr(daemon, "_default_daemon_log_path", lambda: log_path, raising=False)

    with pytest.raises(SystemExit) as exc_info:
        daemon.main(argv=["--help"])

    assert exc_info.value.code == 0
    help_text = capsys.readouterr().out
    assert "--warn-percent N" in help_text
    assert "default 50" in help_text
    assert str(log_path) in help_text
    assert "checkout tmp/overseer/daemon.log" in help_text
    assert "daemon_package.package_dir" in help_text
    assert "OTEL_EXPORTER_OTLP_ENDPOINT" in help_text
    assert "OTEL_SERVICE_NAME" in help_text
    assert "HONEYCOMB_INGEST_KEY_LIVESPEC" in help_text
    assert "livespec-overseer" in help_text
    assert "livespec-family" in help_text
    assert "no endpoint" in help_text
    assert "local only" in help_text
    assert "host-local OTLP receiver" in help_text
    assert "x-honeycomb-team" in help_text
    assert "children inherit its environment" in help_text
