"""Daemon-side controls for release-currency check failures."""

from __future__ import annotations

from collections.abc import Iterator
from io import StringIO

import pytest
import registry
import supervisor

from overseer.test_supervisor_builders import FakeTmux, idle_capture, mapped_track

__all__: list[str] = []


def _sup(*, tmp_path, currency_check):
    repo = tmp_path / "repo"
    (repo / "plan" / "alpha").mkdir(parents=True)
    tmux = FakeTmux()
    tmux.serve(session="alpha", repo=repo, capture=idle_capture(ctx=82, topic="alpha"))
    return supervisor.Supervisor(
        tmux=tmux,
        store_path=tmp_path / "store.jsonl",
        stamp_path=tmp_path / "stamps.json",
        watch_repos=[str(repo)],
        status_path=tmp_path / "status.json",
        out=StringIO(),
        proc_root=str(tmp_path),
        which=lambda _name: "/usr/bin/tmux",
        gitignore_check=lambda repo: True,
        currency_check=currency_check,
    )


def _blocked_verdict(*, reason: str) -> dict[str, object]:
    return {"eligible": False, "target": None, "blocked": True, "reason": reason}


def _map_alpha(*, sup: supervisor.Supervisor) -> None:
    registry.upsert_mapping(
        track=mapped_track(repo=next(iter(sup.watch_repos or [])), topic="alpha", session="alpha"),
        store_path=sup.store_path,
    )


def _assert_alpha_is_still_supervised(*, rows: list[supervisor.RowView]) -> None:
    alpha = next(row for row in rows if row.topic == "alpha")
    assert alpha.tmux == "alpha"
    assert alpha.ctx == 82


@pytest.mark.parametrize(
    ("currency_check", "reason"),
    [
        (lambda: _blocked_verdict(reason="forge unreachable"), "forge unreachable"),
        (lambda: _blocked_verdict(reason="forge rate-limited"), "forge rate-limited"),
        (
            lambda: _blocked_verdict(reason="release ref did not resolve"),
            "release ref did not resolve",
        ),
    ],
)
def test_currency_check_failure_keeps_supervising_and_surfaces_a_blocked_value(
    *,
    tmp_path,
    capsys,
    currency_check,
    reason: str,
) -> None:
    """Currency failures are attention rows, not daemon-stopping exceptions."""
    sup = _sup(tmp_path=tmp_path, currency_check=currency_check)
    _map_alpha(sup=sup)

    rows = sup.tick(act=True)

    _assert_alpha_is_still_supervised(rows=rows)
    currency = next(row for row in rows if row.topic == "release-currency")
    assert currency.status == "currency-blocked"
    assert currency.note == reason
    assert supervisor.needs_attention(row=currency) is True
    assert reason in capsys.readouterr().err


def test_currency_check_exception_degrades_to_blocked_value_and_keeps_ticking(
    *,
    tmp_path,
    capsys,
) -> None:
    """A thrown forge read is the same disposition as a blocked verdict."""

    def currency_check() -> dict[str, object]:
        raise OSError("network is unreachable")

    sup = _sup(tmp_path=tmp_path, currency_check=currency_check)
    _map_alpha(sup=sup)

    rows = sup.tick(act=True)

    _assert_alpha_is_still_supervised(rows=rows)
    currency = next(row for row in rows if row.topic == "release-currency")
    assert currency.status == "currency-blocked"
    assert currency.note == "currency check failed: network is unreachable"
    assert "network is unreachable" in capsys.readouterr().err


def test_currency_check_reports_on_entry_not_every_tick(*, tmp_path, capsys) -> None:
    """The live row remains current, but daemon log noise is edge-triggered."""
    sup = _sup(
        tmp_path=tmp_path,
        currency_check=lambda: _blocked_verdict(reason="forge rate-limited"),
    )
    _map_alpha(sup=sup)

    first = sup.tick(act=True)
    first_err = capsys.readouterr().err
    second = sup.tick(act=True)
    second_err = capsys.readouterr().err

    assert any(row.status == "currency-blocked" for row in first)
    assert any(row.status == "currency-blocked" for row in second)
    assert "forge rate-limited" in first_err
    assert second_err == ""


def test_currency_check_rearms_after_a_normal_tick(*, tmp_path, capsys) -> None:
    verdicts: Iterator[dict[str, object]] = iter(
        [
            _blocked_verdict(reason="forge unreachable"),
            {"eligible": False, "target": None, "blocked": False, "reason": "already current"},
            _blocked_verdict(reason="forge unreachable"),
        ]
    )
    sup = _sup(tmp_path=tmp_path, currency_check=lambda: next(verdicts))
    _map_alpha(sup=sup)

    _ = sup.tick(act=True)
    first_err = capsys.readouterr().err
    normal_rows = sup.tick(act=True)
    normal_err = capsys.readouterr().err
    _ = sup.tick(act=True)
    rearmed_err = capsys.readouterr().err

    assert "forge unreachable" in first_err
    assert not any(row.status == "currency-blocked" for row in normal_rows)
    assert normal_err == ""
    assert "forge unreachable" in rearmed_err
