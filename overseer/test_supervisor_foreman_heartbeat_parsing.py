"""Fail-closed parsing edges of `read_heartbeat`, the kept foreman-heartbeat reader.

The daemon no longer publishes a foreman seat row, but `read_heartbeat` stays live:
`foreman_heartbeat_fresh` (daemon idle/attention evaluation) and `heartbeat_lapse`
(the foreman skill runtime) both read it. A torn write must never escape into either
caller, so every malformed shape resolves to ``None``. These edges were previously
exercised only through the removed seat-row tests.
"""

from __future__ import annotations

import json
from pathlib import Path

import _supervisor_foreman_heartbeat as heartbeat

__all__: list[str] = []


def _write(*, repo: Path, payload: object) -> None:
    path = heartbeat.heartbeat_path(repo=str(repo))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload if isinstance(payload, str) else json.dumps(payload), encoding="utf-8")


def _valid_payload() -> dict[str, object]:
    return {
        "written_at": "2026-08-23T00:00:00+00:00",
        "pid": 4321,
        "tick_generation": 7,
        "tick_interval_seconds": 600,
    }


def test_read_heartbeat_happy_path_returns_heartbeat(*, tmp_path):
    _write(repo=tmp_path, payload=_valid_payload())

    result = heartbeat.read_heartbeat(repo=str(tmp_path))

    assert result is not None
    assert result.pid == 4321
    assert result.tick_generation == 7
    assert result.tick_interval_seconds == 600


def test_read_heartbeat_naive_written_at_is_coerced_to_utc(*, tmp_path):
    payload = _valid_payload()
    payload["written_at"] = "2026-08-23T00:00:00"  # no timezone -> _parse_timestamp adds UTC

    _write(repo=tmp_path, payload=payload)
    result = heartbeat.read_heartbeat(repo=str(tmp_path))

    assert result is not None
    assert result.written_at.tzinfo is not None


def test_read_heartbeat_non_string_written_at_is_absent(*, tmp_path):
    payload = _valid_payload()
    payload["written_at"] = 1234  # not a str -> None

    _write(repo=tmp_path, payload=payload)

    assert heartbeat.read_heartbeat(repo=str(tmp_path)) is None


def test_read_heartbeat_bool_pid_is_rejected_as_non_int(*, tmp_path):
    payload = _valid_payload()
    payload["pid"] = True  # bool is not an acceptable int -> pid None -> absent

    _write(repo=tmp_path, payload=payload)

    assert heartbeat.read_heartbeat(repo=str(tmp_path)) is None


def test_read_heartbeat_string_tick_generation_is_absent(*, tmp_path):
    payload = _valid_payload()
    payload["tick_generation"] = "7"  # not an int -> None

    _write(repo=tmp_path, payload=payload)

    assert heartbeat.read_heartbeat(repo=str(tmp_path)) is None


def test_read_heartbeat_non_positive_interval_is_absent(*, tmp_path):
    payload = _valid_payload()
    payload["tick_interval_seconds"] = 0  # not > 0 -> final None branch

    _write(repo=tmp_path, payload=payload)

    assert heartbeat.read_heartbeat(repo=str(tmp_path)) is None


def test_read_heartbeat_scalar_json_is_absent(*, tmp_path):
    _write(repo=tmp_path, payload="42")  # valid JSON, wrong shape -> None

    assert heartbeat.read_heartbeat(repo=str(tmp_path)) is None


def test_read_heartbeat_malformed_json_is_absent(*, tmp_path):
    _write(repo=tmp_path, payload="{not valid json")  # parse failure -> None

    assert heartbeat.read_heartbeat(repo=str(tmp_path)) is None
