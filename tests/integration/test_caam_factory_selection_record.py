"""Integration coverage for the factory selection record."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pytest
from caam_anthropic_loop import Flags
from caam_anthropic_pass import run_pass
from caam_decision import UsageRecord

__all__: list[str] = []

pytestmark = pytest.mark.integration

ACTIVE = "anthropic-4"
FACTORY = "anthropic-5"
FACTORY_RECORD_REL = Path(".local/state/caam-usage-rotate/factory-selected-account.json")


@dataclass(frozen=True, kw_only=True)
class _CaamResult:
    returncode: int
    stdout: str
    stderr: str = ""


def _flags() -> Flags:
    return Flags(
        scheduled=True,
        force=False,
        dry_run=False,
        no_models=True,
        no_warm=True,
        session_models=(),
        protected_accounts=(),
    )


def _usage() -> UsageRecord:
    return UsageRecord(
        five_hour_remaining=80.0,
        seven_day_remaining=70.0,
        five_hour_resets_at="2026-11-17T12:00:00Z",
        seven_day_resets_at="2026-11-19T00:00:00Z",
        fable_remaining=90.0,
        fable_resets_at="2026-11-19T00:00:00Z",
    )


def _write_account(*, path: Path, account_uuid: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_text(
        json.dumps({"oauthAccount": {"accountUuid": account_uuid}}), encoding="utf-8"
    )


def _home(*, root: Path) -> Path:
    for profile in (ACTIVE, FACTORY):
        _write_account(
            path=root / ".local/share/caam/vault/claude" / profile / ".claude.json",
            account_uuid=f"uuid-{profile}",
        )
    _write_account(path=root / ".claude.json", account_uuid=f"uuid-{ACTIVE}")
    return root


def _run(*, home: Path) -> int:
    return run_pass(
        flags=_flags(),
        home=home,
        now=1795000000.0,
        stdout=lambda line: None,
        caam_runner=lambda *, args: _CaamResult(
            returncode=0,
            stdout=json.dumps({"tools": [{"tool": "claude", "active_profile": ACTIVE}]}),
        ),
        fetcher=lambda *, creds_path, now=None: (_usage(), None),
        save_state=lambda *, state, state_path: None,
    )


def test_each_interactive_publication_also_writes_the_factory_record(*, tmp_path: Path) -> None:
    home = _home(root=tmp_path)

    assert _run(home=home) == 0

    record_path = home / FACTORY_RECORD_REL
    record = json.loads(record_path.read_text(encoding="utf-8"))
    assert record == {
        "account_uuid": f"uuid-{FACTORY}",
        "profile": FACTORY,
        "reason": None,
        "written_at": "2026-11-18T11:06:40Z",
    }
    assert record_path.stat().st_mode & 0o777 == 0o600
