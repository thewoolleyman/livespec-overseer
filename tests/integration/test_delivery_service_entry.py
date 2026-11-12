"""Integration coverage for the supervised delivery-service entry point."""

from __future__ import annotations

import importlib
import json
import socket
from pathlib import Path

import caam_delivery_enrol
import caam_delivery_registry
import caam_delivery_runner
import pytest
import streams

from overseer._vendor.returns.result import Success
from tests.integration.test_caam_capacity_reporting import NOW, CapacityHarness, usage


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


def test_failed_account_confirmation_emits_a_failure_line_and_continues(
    *, monkeypatch: pytest.MonkeyPatch
) -> None:
    entry = importlib.import_module("caam_delivery_service_entry")
    failure_lines: list[str] = []
    monkeypatch.setattr(streams, "write_stderr", lambda *, text: failure_lines.append(text))
    monkeypatch.setattr(entry, "get_json", lambda *, request: (None, "unavailable"))
    assert entry.confirm_live_account(access_token="delivery-" + "token") is None
    assert failure_lines == ["FAIL delivery account confirmation failed: unavailable\n"]
    failure_lines.clear()
    monkeypatch.setattr(entry, "get_json", lambda *, request: ({"account_uuid": 7}, None))
    assert entry.confirm_live_account(access_token="delivery-" + "token") is None
    assert len(failure_lines) == 1 and failure_lines[0].startswith("FAIL ")
    assert "delivery-" + "token" not in failure_lines[0]


def _run_switching_pass(*, harness: CapacityHarness) -> tuple[int, tuple[str, ...]]:
    """Run one pass and prove it was a pass that switches accounts."""
    outcome = harness.run()
    assert harness.switches == ["account-b"]
    return outcome


def _pass_home(*, home: Path, enrolled: bool) -> CapacityHarness:
    """A rotation-pass vault whose live stores carry a deliverable identity.

    The harness writes the live credential and its account state; the identity
    key a delivery requires is added here, to every arm alike, so the arms differ
    only in whether a host is enrolled.
    """
    harness = CapacityHarness(
        home=home,
        active="account-a",
        usages={"account-a": usage(five_hour_remaining=0.0), "account-b": usage()},
    )
    state_path = home / ".claude.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    _ = state_path.write_text(json.dumps({**state, "userID": "user-a"}), encoding="utf-8")
    if enrolled:
        enrolment = caam_delivery_enrol.issue_enrolment(
            home=home,
            label="laptop",
            network_identity="laptop.example",
            issued_at="2026-11-11T00:00:00Z",
            credential="enrolment-" + "credential",
        )
        assert isinstance(enrolment, Success)
    return harness


_PASS_OWNED = ("selected-account.json",)


def _delivery_files(*, home: Path) -> dict[str, bytes]:
    """Every host-state file the delivery side owns; the pass's own records are not its."""
    state = home / caam_delivery_registry.STATE_DIR_REL
    if not state.is_dir():
        return {}
    return {
        path.name: path.read_bytes()
        for path in sorted(state.iterdir())
        if path.is_file() and path.name not in _PASS_OWNED
    }


def test_stopped_delivery_service_does_not_affect_a_rotation_pass(*, tmp_path: Path) -> None:
    baseline = _run_switching_pass(harness=_pass_home(home=tmp_path / "baseline", enrolled=False))

    enrolled_home = tmp_path / "stopped"
    stopped = _pass_home(home=enrolled_home, enrolled=True)
    before = _delivery_files(home=enrolled_home)

    # The three Givens: an enrolled host exists, the service never ran so nothing
    # was ever delivered or reported, and no report store holds a forwarded refusal.
    assert caam_delivery_registry.registry_path(home=enrolled_home).name in before
    assert not any("report" in name or "current-delivery" in name for name in before)

    assert _run_switching_pass(harness=stopped) == baseline
    assert _delivery_files(home=enrolled_home) == before


def test_unreachable_enrolled_host_does_not_affect_a_rotation_pass(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    baseline = _run_switching_pass(harness=_pass_home(home=tmp_path / "baseline", enrolled=False))

    enrolled_home = tmp_path / "unreachable"
    unreachable = _pass_home(home=enrolled_home, enrolled=True)
    connections: list[object] = []

    def refuse_connection(self: socket.socket, address: object) -> None:
        del self
        connections.append(address)
        raise ConnectionRefusedError

    monkeypatch.setattr(socket.socket, "connect", refuse_connection)
    service = caam_delivery_runner.DeliveryService(
        home=enrolled_home,
        now=lambda: NOW,
        confirm_account=lambda *, access_token: "uuid-account-a",
    )
    # The service is running and has issued a delivery the powered-off host never
    # collects; nothing in that path may open a connection to the host.
    delivery = service.refresh()
    assert delivery is not None and delivery.sequence == 1
    before = _delivery_files(home=enrolled_home)

    assert _run_switching_pass(harness=unreachable) == baseline
    assert _delivery_files(home=enrolled_home) == before
    assert connections == []
