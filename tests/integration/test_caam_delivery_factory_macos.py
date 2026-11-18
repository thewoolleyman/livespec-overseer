"""A macOS listed host receives the factory selection record, and nothing else."""

from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

FACTORY_RECORD_REL = Path(".local/state/caam-usage-rotate/factory-selected-account.json")


def _holder(*, tmp_path: Path, with_record: bool) -> Path:
    push = importlib.import_module("caam_delivery_push")
    holder = tmp_path / "holder"
    (holder / push.HOSTS_FILE).parent.mkdir(parents=True, exist_ok=True)
    _ = (holder / push.HOSTS_FILE).write_text(
        "mac user@mac macos\nlin user@lin linux\n", encoding="utf-8"
    )
    if with_record:
        (holder / FACTORY_RECORD_REL).parent.mkdir(parents=True, exist_ok=True)
        _ = (holder / FACTORY_RECORD_REL).write_text(
            json.dumps(
                {
                    "account_uuid": "factory-account",
                    "profile": "anthropic-5",
                    "reason": None,
                    "written_at": "2026-11-18T12:00:00Z",
                }
            ),
            encoding="utf-8",
        )
    return holder


def _delivery() -> object:
    service = importlib.import_module("caam_delivery_service")
    return service.Delivery(
        sequence=1,
        account_id="interactive-account",
        identity={"oauthAccount": {"accountUuid": "interactive-account"}},
        oauth={"accessToken": "tok-secret", "expiresAt": 9},
    )


def test_a_macos_host_receives_the_factory_record_but_no_credential(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    push = importlib.import_module("caam_delivery_push")
    holder = _holder(tmp_path=tmp_path, with_record=True)
    receivers = {"user@mac": tmp_path / "mac", "user@lin": tmp_path / "lin"}
    programs: dict[str, str] = {}

    def run(*, target: str, program: str, **_: object) -> tuple[int, str]:
        programs[target] = program
        monkeypatch.setenv("HOME", str(receivers[target]))
        code = 0
        try:
            exec(compile(program, "<push>", "exec"), {"__name__": "__main__"})  # noqa: S102
        except SystemExit as stop:
            code = int(stop.code or 0)
        return code, capsys.readouterr().out.strip()

    outcomes = push.push_due(home=holder, delivery=_delivery(), now=1.0, run=run)

    assert outcomes["mac"] == push.UNSUPPORTED_MACOS
    assert outcomes["lin"] == "applied 1"
    expected = (holder / FACTORY_RECORD_REL).read_bytes()
    record = receivers["user@mac"] / FACTORY_RECORD_REL
    assert record.read_bytes() == expected
    assert record.stat().st_mode & 0o777 == 0o600
    assert not (receivers["user@mac"] / ".claude").exists()
    assert "tok-secret" not in programs["user@mac"]
    state = json.loads((holder / push.PUSH_STATE).read_text(encoding="utf-8"))
    assert state["mac"]["factory_written_at"] == "2026-11-18T12:00:00Z"
    assert state["mac"].get("sequence") is None


def test_a_macos_host_gets_no_ssh_call_when_there_is_no_factory_record(*, tmp_path: Path) -> None:
    push = importlib.import_module("caam_delivery_push")
    holder = _holder(tmp_path=tmp_path, with_record=False)
    targets: list[str] = []

    def run(*, target: str, **_: object) -> tuple[int, str]:
        targets.append(target)
        return 0, "applied 1"

    outcomes = push.push_due(home=holder, delivery=_delivery(), now=1.0, run=run)

    assert targets == ["user@lin"]
    assert outcomes["mac"] == push.UNSUPPORTED_MACOS
