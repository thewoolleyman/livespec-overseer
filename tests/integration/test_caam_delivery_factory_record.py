"""Factory selection propagation remains identity-only and never moves backward."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from caam_delivery_apply_script import apply_program
from caam_delivery_push_state import Host

pytestmark = pytest.mark.integration


def _record(*, written_at: object = "2026-11-18T12:00:00Z", **changes: object) -> dict[str, object]:
    return {
        "profile": "factory-profile",
        "account_uuid": "factory-account",
        "written_at": written_at,
        "reason": None,
        **changes,
    }


@pytest.mark.parametrize(
    "record",
    [
        {},
        _record(account_uuid=None),
        _record(profile=1),
        _record(profile=None, account_uuid=None, reason=None),
        _record(written_at=1),
        _record(written_at="not-a-time"),
    ],
)
def test_only_a_complete_identity_only_factory_record_can_be_sent(
    *, tmp_path: Path, record: dict[str, object]
) -> None:
    factory = __import__("caam_delivery_factory_record")
    path = tmp_path / ".local/state/caam-usage-rotate/factory-selected-account.json"
    path.parent.mkdir(parents=True)
    _ = path.write_text(json.dumps(record), encoding="utf-8")

    assert factory.factory_record(home=tmp_path) is None


def test_factory_targets_and_push_state_follow_the_record_time_not_delivery_sequence() -> None:
    factory = __import__("caam_delivery_factory_record")
    first = Host(label="first", target="u@first", platform="linux")
    second = Host(label="second", target="u@second", platform="linux")
    record = (b'{"profile":"p"}', "2026-11-18T12:00:00Z")
    state = {"first": {"factory_written_at": record[1]}, "second": {}}

    assert factory.factory_targets(
        hosts=[first, second], behind=[], state=state, factory_record=record
    ) == [second]
    assert factory.factory_targets(
        hosts=[first, second], behind=[first], state=state, factory_record=None
    ) == [first]

    factory.record_factory_result(
        entry=state["second"], line="failed timeout", factory_record=record
    )
    assert "factory_written_at" not in state["second"]
    factory.record_factory_result(
        entry=state["second"], line="stale-sequence 3 host-applied 3", factory_record=record
    )
    assert state["second"]["factory_written_at"] == record[1]
    factory.record_factory_result(
        entry=state["first"], line="failed 3 JSONDecodeError", factory_record=record
    )
    assert state["first"]["factory_written_at"] == record[1]


def test_receiver_writes_the_exact_newer_record_but_rejects_a_delayed_one(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    home = tmp_path / "receiver"
    newest = json.dumps(_record(written_at="2026-11-18T12:00:00Z"), separators=(",", ":"))
    delayed = json.dumps(_record(written_at="2026-11-18T11:59:59Z"), separators=(",", ":"))

    def apply(*, sequence: int, record: str) -> str:
        monkeypatch.setenv("HOME", str(home))
        payload = json.dumps(
            {
                "sequence": sequence,
                "oauth": {"accessToken": "token", "expiresAt": 1},
                "identity": {},
                "factory_record": record,
            }
        )
        with pytest.raises(SystemExit) as stopped:
            exec(  # noqa: S102
                compile(apply_program(payload=payload), "<receiver>", "exec"),
                {"__name__": "__main__"},
            )
        assert stopped.value.code == 0
        return capsys.readouterr().out.strip()

    assert apply(sequence=1, record=newest) == "applied 1"
    path = home / ".local/state/caam-usage-rotate/factory-selected-account.json"
    assert path.read_bytes() == newest.encode()
    assert path.stat().st_mode & 0o777 == 0o600
    assert apply(sequence=2, record=delayed) == "applied 2"
    assert path.read_bytes() == newest.encode()
