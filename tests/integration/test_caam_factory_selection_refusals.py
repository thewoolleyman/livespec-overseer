"""Integration coverage for factory-selection retention and refusal paths."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pytest
from caam_anthropic_loop import Flags
from caam_anthropic_pass import run_pass
from caam_decision import UsageRecord
from caam_factory_selection import factory_selection

__all__: list[str] = []

pytestmark = pytest.mark.integration

ACTIVE = "anthropic-4"
FACTORY = "anthropic-5"
BACKUP = "anthropic-6"
FACTORY_RECORD_REL = Path(".local/state/caam-usage-rotate/factory-selected-account.json")
SELECTION_RECORD_REL = Path(".local/state/caam-usage-rotate/selected-account.json")


@dataclass(frozen=True, kw_only=True)
class _CaamResult:
    returncode: int
    stdout: str
    stderr: str = ""


def _flags(*, protected_accounts: tuple[tuple[str, str], ...] = ()) -> Flags:
    return Flags(
        scheduled=True,
        force=False,
        dry_run=False,
        no_models=True,
        no_warm=True,
        session_models=(),
        protected_accounts=protected_accounts,
    )


def _usage(*, weekly: float = 70.0) -> UsageRecord:
    return UsageRecord(
        five_hour_remaining=80.0,
        seven_day_remaining=weekly,
        five_hour_resets_at="2026-11-17T12:00:00Z",
        seven_day_resets_at="2026-11-19T00:00:00Z",
        fable_remaining=90.0,
        fable_resets_at="2026-11-19T00:00:00Z",
    )


def _write_account(*, path: Path, account_uuid: str | None) -> None:
    account: dict[str, str] = {} if account_uuid is None else {"accountUuid": account_uuid}
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_text(json.dumps({"oauthAccount": account}), encoding="utf-8")


def _home(*, root: Path, active_uuid: str | None = f"uuid-{ACTIVE}") -> Path:
    for profile in (ACTIVE, FACTORY, BACKUP):
        _write_account(
            path=root / ".local/share/caam/vault/claude" / profile / ".claude.json",
            account_uuid=f"uuid-{profile}",
        )
    _write_account(path=root / ".claude.json", account_uuid=active_uuid)
    return root


def _run(
    *,
    home: Path,
    fetcher,
    flags: Flags | None = None,
) -> tuple[int, list[str]]:
    lines: list[str] = []
    code = run_pass(
        flags=_flags() if flags is None else flags,
        home=home,
        now=1795000000.0,
        stdout=lines.append,
        caam_runner=lambda *, args: _CaamResult(
            returncode=0,
            stdout=json.dumps({"tools": [{"tool": "claude", "active_profile": ACTIVE}]}),
        ),
        fetcher=fetcher,
        save_state=lambda *, state, state_path: None,
    )
    return code, lines


def _same_usage(*, creds_path: Path, now: float | None = None) -> tuple[UsageRecord, None]:
    _ = creds_path, now
    return _usage(), None


def _record(*, home: Path) -> dict[str, object]:
    value: object = json.loads((home / FACTORY_RECORD_REL).read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_a_qualifying_factory_account_is_kept_across_passes(*, tmp_path: Path) -> None:
    home = _home(root=tmp_path)

    first, _ = _run(home=home, fetcher=_same_usage)
    second, _ = _run(home=home, fetcher=_same_usage)

    assert first == second == 0
    assert _record(home=home)["profile"] == FACTORY


def test_no_qualifying_account_replaces_a_stale_factory_record(*, tmp_path: Path) -> None:
    home = _home(root=tmp_path)
    record_path = home / FACTORY_RECORD_REL
    record_path.parent.mkdir(parents=True, exist_ok=True)
    _ = record_path.write_text('{"account_uuid": 3}', encoding="utf-8")

    def _no_candidate(*, creds_path: Path, now: float | None = None) -> tuple[UsageRecord, None]:
        _ = now
        return _usage(
            weekly=10.0 if FACTORY in str(creds_path) or BACKUP in str(creds_path) else 70.0
        ), None

    code, _ = _run(home=home, fetcher=_no_candidate)

    assert code == 0
    assert _record(home=home)["profile"] is None
    assert _record(home=home)["account_uuid"] is None
    assert isinstance(_record(home=home)["reason"], str) and _record(home=home)["reason"]


def test_a_malformed_prior_factory_identity_is_not_kept(*, tmp_path: Path) -> None:
    home = _home(root=tmp_path)
    path = home / FACTORY_RECORD_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_text('{"account_uuid": 3}', encoding="utf-8")

    selection = factory_selection(
        home=home,
        profiles=(),
        interactive_name=ACTIVE,
        state={},
        protection_floors={},
        now=1795000000.0,
    )

    assert selection.profile is None


def test_an_unprotected_factory_candidate_wins_over_a_protected_one(*, tmp_path: Path) -> None:
    home = _home(root=tmp_path)

    code, _ = _run(
        home=home,
        fetcher=_same_usage,
        flags=_flags(protected_accounts=((FACTORY, "20"),)),
    )

    assert code == 0
    assert _record(home=home)["profile"] == BACKUP


def test_unresolved_interactive_identity_preserves_both_records(*, tmp_path: Path) -> None:
    home = _home(root=tmp_path, active_uuid=None)
    _write_account(
        path=home / ".local/share/caam/vault/claude" / ACTIVE / ".claude.json", account_uuid=None
    )
    selection_path = home / SELECTION_RECORD_REL
    factory_path = home / FACTORY_RECORD_REL
    selection_path.parent.mkdir(parents=True, exist_ok=True)
    _ = selection_path.write_text('{"prior": "interactive"}', encoding="utf-8")
    _ = factory_path.write_text('{"prior": "factory"}', encoding="utf-8")

    code, _ = _run(home=home, fetcher=_same_usage)

    assert code == 0
    assert selection_path.read_text(encoding="utf-8") == '{"prior": "interactive"}'
    assert factory_path.read_text(encoding="utf-8") == '{"prior": "factory"}'


def test_factory_publication_failure_keeps_interactive_publication(*, tmp_path: Path) -> None:
    home = _home(root=tmp_path)
    (home / FACTORY_RECORD_REL).mkdir(parents=True)

    code, lines = _run(home=home, fetcher=_same_usage)

    assert code == 2
    assert (home / SELECTION_RECORD_REL).is_file()
    assert any("could not publish the factory selection record" in line for line in lines)
