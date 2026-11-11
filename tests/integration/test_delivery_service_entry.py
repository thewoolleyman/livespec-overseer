"""Integration coverage for the supervised delivery-service entry point."""

from __future__ import annotations

import importlib
import json
from pathlib import Path

import caam_delivery_runner
import pytest

from tests.integration.test_caam_capacity_reporting import CapacityHarness, usage


class _StopLoopError(Exception):
    """Stop one intentionally unbounded service-loop exercise."""


def _write_live_files(*, home: Path) -> None:
    credentials = home / ".claude/.credentials.json"
    credentials.parent.mkdir(parents=True, exist_ok=True)
    _ = credentials.write_text(
        json.dumps(
            {
                "claudeAiOauth": {
                    "accessToken": "delivery-" + "token",
                    "expiresAt": 9_999_999_999_000,
                }
            }
        ),
        encoding="utf-8",
    )
    _ = (home / ".claude.json").write_text(
        json.dumps({"oauthAccount": {"accountUuid": "account-a"}, "userID": "user-a"}),
        encoding="utf-8",
    )


def test_service_entry_is_supervised_and_never_becomes_a_rotation_dependency(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module_path = Path(__file__).parents[2] / "overseer/caam_delivery_service_entry.py"

    assert module_path.is_file()
    entry = importlib.import_module("caam_delivery_service_entry")
    requests: list[object] = []
    monkeypatch.setattr(
        entry,
        "get_json",
        lambda *, request: requests.append(request) or ({"account_uuid": "account-a"}, None),
    )
    assert entry.confirm_live_account(access_token="delivery-" + "token") == "account-a"
    assert requests[0].url == "https://api.anthropic.com/api/oauth/profile"
    assert "oauth/token" not in requests[0].url
    monkeypatch.setattr(entry, "get_json", lambda *, request: (None, "unavailable"))
    assert entry.confirm_live_account(access_token="delivery-" + "token") is None

    _write_live_files(home=tmp_path)
    service = caam_delivery_runner.DeliveryService(
        home=tmp_path,
        now=lambda: 1_000.0,
        confirm_account=lambda *, access_token: "account-a",
    )
    waits: list[float] = []

    def stop_after_refresh(seconds: float) -> None:
        waits.append(seconds)
        raise _StopLoopError

    with pytest.raises(_StopLoopError):
        entry.run_forever(service=service, wait=stop_after_refresh)
    assert waits == [entry.POLL_INTERVAL_S]

    captured: list[object] = []
    assert entry.main(runner=lambda *, service, wait: captured.append((service, wait))) == 0
    assert captured and captured[0][1] is entry.time.sleep
    unit = Path(__file__).parents[2] / "overseer/caam-delivery-service.service"
    assert unit.read_text(encoding="utf-8").splitlines() == [
        "[Unit]",
        "Description=CAAM enrolled-host credential delivery service",
        "",
        "[Service]",
        "Type=simple",
        "ExecStart=caam-delivery-service",
        "Restart=always",
        "RestartSec=5",
        "",
        "[Install]",
        "WantedBy=default.target",
    ]

    baseline = CapacityHarness(
        home=tmp_path / "baseline",
        active="account-a",
        usages={"account-a": usage(), "account-b": usage()},
    ).run()
    stopped = caam_delivery_runner.DeliveryService(
        home=tmp_path,
        now=lambda: 1_000.0,
        confirm_account=lambda *, access_token: "account-a",
    )
    unreachable = CapacityHarness(
        home=tmp_path / "unreachable",
        active="account-a",
        usages={"account-a": usage(), "account-b": usage()},
    ).run()

    assert stopped is not None
    assert unreachable == baseline
