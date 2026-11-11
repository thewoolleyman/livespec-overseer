"""Integration coverage for the role holder's long-running delivery service."""

from __future__ import annotations

import importlib
import json
import threading
from pathlib import Path


def _write_live_files(*, home: Path, token: str, account: str, user: str) -> None:
    credentials = home / ".claude/.credentials.json"
    credentials.parent.mkdir(parents=True, exist_ok=True)
    _ = credentials.write_text(
        json.dumps(
            {
                "claudeAiOauth": {
                    "accessToken": token,
                    "expiresAt": 9_999_999_999_000,
                    "refreshToken": "role-holder-only",
                }
            }
        ),
        encoding="utf-8",
    )
    _ = (home / ".claude.json").write_text(
        json.dumps({"oauthAccount": {"accountUuid": account}, "userID": user}),
        encoding="utf-8",
    )


def test_live_changes_issue_delivery_and_release_a_waiting_client(*, tmp_path: Path) -> None:
    module_path = Path(__file__).parents[2] / "overseer/caam_delivery_runner.py"

    assert module_path.is_file()
    runner_module = importlib.import_module("caam_delivery_runner")
    token_a = "access-" + "a"
    token_b = "access-" + "b"
    _write_live_files(home=tmp_path, token=token_a, account="account-a", user="user-a")
    confirmations: list[str] = []
    service = runner_module.DeliveryService(
        home=tmp_path,
        now=lambda: 1_000.0,
        confirm_account=lambda *, access_token: confirmations.append(access_token) and "account-a",
    )

    first = service.refresh()

    assert first is not None
    delivered: list[object] = []
    waiter = threading.Thread(
        target=lambda: delivered.append(
            service.wait_for_delivery(sequence=first.sequence, timeout=1.0)
        )
    )
    waiter.start()
    _write_live_files(home=tmp_path, token=token_b, account="account-a", user="user-a")
    second = service.refresh()
    waiter.join(timeout=1.0)

    assert second is not None
    assert second.sequence > first.sequence
    assert delivered == [second]
    _write_live_files(home=tmp_path, token=token_b, account="account-a", user="user-b")
    third = service.refresh()

    assert third is not None
    assert third.sequence > second.sequence
    assert confirmations == ["access-a", "access-b", "access-b"]
    assert "oauth/token" not in module_path.read_text(encoding="utf-8")
