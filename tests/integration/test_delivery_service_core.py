"""Integration coverage for the role holder's credential-delivery core."""

from __future__ import annotations

import importlib
import json
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


def test_issues_a_sanitized_delivery_for_the_confirmed_live_account(*, tmp_path: Path) -> None:
    module_path = Path(__file__).parents[2] / "overseer/caam_delivery_service.py"
    assert module_path.is_file()
    service = importlib.import_module("caam_delivery_service")
    access_token = "access-" + "a"
    _write_live_files(home=tmp_path, token=access_token, account="account-a", user="user-a")

    delivery = service.issue_delivery(
        home=tmp_path,
        now=1_000.0,
        confirm_account=lambda *, access_token: "account-a",
    )

    assert delivery is not None
    assert delivery.sequence == 1
    assert delivery.account_id == "account-a"
    assert delivery.identity == {"oauthAccount": {"accountUuid": "account-a"}, "userID": "user-a"}
    assert delivery.oauth == {"accessToken": "access-a", "expiresAt": 9_999_999_999_000}
    assert "refreshToken" not in json.dumps(delivery.oauth)


def test_refuses_mismatched_or_expired_live_credentials(*, tmp_path: Path) -> None:
    service = importlib.import_module("caam_delivery_service")
    different_token = "access-" + "b"
    _write_live_files(home=tmp_path, token=different_token, account="account-a", user="user-a")
    confirmations: list[str] = []

    refused = service.issue_delivery(
        home=tmp_path,
        now=1_000.0,
        confirm_account=lambda *, access_token: confirmations.append(access_token) and "account-b",
    )

    assert refused is None
    assert confirmations == ["access-b"]
    credentials = tmp_path / ".claude/.credentials.json"
    _ = credentials.write_text(
        json.dumps({"claudeAiOauth": {"accessToken": "access-b", "expiresAt": 1}}),
        encoding="utf-8",
    )
    assert (
        service.issue_delivery(
            home=tmp_path,
            now=1_000.0,
            confirm_account=lambda *, access_token: confirmations.append(access_token)
            and "account-a",
        )
        is None
    )
    assert confirmations == ["access-b"]


def test_live_token_change_gets_a_later_sequence_and_malformed_current_is_ignored(
    *, tmp_path: Path
) -> None:
    service = importlib.import_module("caam_delivery_service")
    first_token = "access-" + "a"
    _write_live_files(home=tmp_path, token=first_token, account="account-a", user="user-a")

    def confirm(*, access_token: str) -> str:
        return "account-a"

    first = service.issue_delivery(home=tmp_path, now=1_000.0, confirm_account=confirm)

    assert first is not None
    assert service.issue_delivery(home=tmp_path, now=1_000.0, confirm_account=confirm) is None
    second_token = "access-" + "b"
    _write_live_files(home=tmp_path, token=second_token, account="account-a", user="user-a")
    second = service.issue_delivery(home=tmp_path, now=1_000.0, confirm_account=confirm)
    assert second is not None
    assert second.sequence > first.sequence
    current = tmp_path / ".local/state/caam-usage-rotate/current-delivery.json"
    _ = current.write_text("{}", encoding="utf-8")
    assert service.load_current_delivery(home=tmp_path) is None


def test_counter_copied_to_a_new_holder_starts_above_its_previous_delivery(
    *, tmp_path: Path
) -> None:
    service = importlib.import_module("caam_delivery_service")
    next_token = "access-" + "next"
    _write_live_files(home=tmp_path, token=next_token, account="account-a", user="user-a")
    counter = tmp_path / ".local/state/caam-usage-rotate/delivery-sequence.json"
    counter.parent.mkdir(parents=True)
    _ = counter.write_text('{"sequence": 40}', encoding="utf-8")

    delivery = service.issue_delivery(
        home=tmp_path,
        now=1_000.0,
        confirm_account=lambda *, access_token: "account-a",
    )

    assert delivery is not None
    assert delivery.sequence == 41
