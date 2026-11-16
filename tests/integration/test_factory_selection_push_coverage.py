"""Coverage for factory-record delivery branches that do not issue credentials."""

from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest


def _record() -> bytes:
    """Return a valid identity-only factory selection record."""
    return json.dumps(
        {
            "account_uuid": "factory-account",
            "profile": "anthropic-5",
            "reason": None,
            "written_at": "2026-11-16T18:00:00Z",
        },
        sort_keys=True,
    ).encode()


def test_factory_selection_push_handles_absence_and_records_write_errors(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """No source record is a no-op; state-write failures keep the remote result."""
    factory = importlib.import_module("caam_factory_selection_push")
    service = importlib.import_module("caam_delivery_service")

    def unused_run(**_: object) -> tuple[int, str]:
        return 0, "unused"

    assert factory.push_factory_selection(home=tmp_path, run=unused_run) == {}

    hosts = tmp_path / ".local/state/caam-usage-rotate/delivery-hosts"
    hosts.parent.mkdir(parents=True)
    _ = hosts.write_text("h u@h linux\n", encoding="utf-8")

    def refuse(*, path: Path, value: dict[str, object]) -> None:
        del path, value
        raise PermissionError("read-only")

    monkeypatch.setattr(service, "write_private_json", refuse)

    def malformed_reply(**_: object) -> tuple[int, str]:
        return 0, "bad reply"

    outcomes = factory.push_factory_selection(
        home=tmp_path, record_bytes=_record(), now=5.0, run=malformed_reply
    )
    assert outcomes == {"h": "bad reply"}
    assert "FAIL factory push state not written: PermissionError" in capsys.readouterr().err


def test_push_loop_replicates_a_changed_factory_record_without_a_credential_delivery(
    *, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A changed factory record reaches hosts even when no live credential is available."""
    entry = importlib.import_module("caam_delivery_push_entry")
    record_path = tmp_path / ".local/state/caam-usage-rotate/factory-selected-account.json"
    record_path.parent.mkdir(parents=True)
    _ = record_path.write_bytes(_record())
    hosts = tmp_path / ".local/state/caam-usage-rotate/delivery-hosts"
    _ = hosts.write_text("h u@h linux\n", encoding="utf-8")
    loop = entry.PushLoop()

    def applied_reply(**_: object) -> tuple[int, str]:
        return 0, "factory-selection applied 2026-11-16T18:00:00Z"

    entry.run_once(
        home=tmp_path,
        now=5.0,
        loop=loop,
        run=applied_reply,
    )

    assert loop.factory_record == _record()
    expected = "factory selection h: factory-selection applied 2026-11-16T18:00:00Z"
    assert expected in capsys.readouterr().out
