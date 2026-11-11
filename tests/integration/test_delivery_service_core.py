"""Integration coverage for the role holder's credential-delivery core."""

from __future__ import annotations

import importlib
import json
from pathlib import Path


def _write_live_files(*, home: Path, token: str, account: str, user: str) -> None:
    credentials = home / ".claude/.credentials.json"
    credentials.parent.mkdir(parents=True)
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
