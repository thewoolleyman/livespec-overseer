"""Production wiring for daemon release-currency and self-reexec seams."""

from __future__ import annotations

from collections.abc import Mapping
from io import StringIO
from pathlib import Path

import registry
import supervisor
from _supervisor_view import RowView

from overseer.test_supervisor_builders import FakeTmux, idle_capture, mapped_track

__all__: list[str] = []


class FakeReleaseRuntimeAdapter:
    def __init__(self, *, target: Path | None = None, blocked: bool = False) -> None:
        self.target = target
        self.blocked = blocked
        self.currency_calls = 0

    def currency_check(self) -> Mapping[str, object] | None:
        self.currency_calls += 1
        return {
            "eligible": self.target is not None,
            "target": str(self.target) if self.target is not None else None,
            "blocked": self.blocked,
            "reason": "release check blocked" if self.blocked else "release check green",
        }

    def reexec_target(self) -> Path | None:
        return self.target


def build_live_supervisor(
    *,
    tmp_path: Path,
    adapter: FakeReleaseRuntimeAdapter,
) -> supervisor.Supervisor:
    sup = supervisor.build_supervisor()
    sup.tmux = FakeTmux()
    repo = tmp_path / "repo"
    (repo / "plan" / "alpha").mkdir(parents=True)
    sup.tmux.serve(session="alpha", repo=repo, capture=idle_capture(ctx=82, topic="alpha"))
    sup.store_path = tmp_path / "store.jsonl"
    sup.stamp_path = tmp_path / "stamps.json"
    sup.watch_repos = [str(repo)]
    sup.watch_set_path = None
    sup.status_path = tmp_path / "status.json"
    sup.out = StringIO()
    sup.proc_root = str(tmp_path)
    sup.which = lambda _name: "/usr/bin/tmux"
    sup.gitignore_check = lambda repo: True
    sup.execv = lambda *, path, argv: None
    registry.upsert_mapping(
        track=mapped_track(repo=str(repo), topic="alpha", session="alpha"),
        store_path=sup.store_path,
    )
    assert sup.currency_check is adapter.currency_check
    assert sup.reexec_target is adapter.reexec_target
    return sup


def test_production_builder_supplies_release_runtime_seams(*, monkeypatch, tmp_path) -> None:
    target = tmp_path / "runtime" / "venv" / "bin" / "overseerd"
    adapter = FakeReleaseRuntimeAdapter(target=target)
    monkeypatch.setattr(
        supervisor,
        "_release_runtime_adapter",
        lambda *, sup: adapter,
        raising=False,
    )

    sup = supervisor.build_supervisor()

    assert sup.currency_check is adapter.currency_check
    assert sup.reexec_target is adapter.reexec_target


def test_acting_tick_runs_the_wired_currency_check(*, monkeypatch, tmp_path) -> None:
    adapter = FakeReleaseRuntimeAdapter()
    monkeypatch.setattr(
        supervisor,
        "_release_runtime_adapter",
        lambda *, sup: adapter,
        raising=False,
    )
    sup = build_live_supervisor(tmp_path=tmp_path, adapter=adapter)

    _ = sup.tick(act=True)

    assert adapter.currency_calls == 1


def test_wired_blocked_verdict_surfaces_and_keeps_ticking(*, monkeypatch, tmp_path) -> None:
    adapter = FakeReleaseRuntimeAdapter(blocked=True)
    monkeypatch.setattr(
        supervisor,
        "_release_runtime_adapter",
        lambda *, sup: adapter,
        raising=False,
    )
    sup = build_live_supervisor(tmp_path=tmp_path, adapter=adapter)

    first = sup.tick(act=True)
    second = sup.tick(act=True)

    currency = next(row for row in first if row.topic == "release-currency")
    assert currency.status == "currency-blocked"
    assert currency.note == "release check blocked"
    assert any(row.topic == "alpha" for row in first)
    assert any(row.topic == "alpha" for row in second)
    assert adapter.currency_calls == 2


def test_wired_reexec_target_reaches_the_tick_safe_point(*, monkeypatch, tmp_path) -> None:
    target = tmp_path / "runtime" / "venv" / "bin" / "overseerd"
    adapter = FakeReleaseRuntimeAdapter(target=target)
    monkeypatch.setattr(
        supervisor,
        "_release_runtime_adapter",
        lambda *, sup: adapter,
        raising=False,
    )
    sup = build_live_supervisor(tmp_path=tmp_path, adapter=adapter)
    executed: list[tuple[str, list[str]]] = []
    sup.execv = lambda *, path, argv: executed.append((path, argv))
    sup.argv = lambda: ["overseerd", "--warn-percent", "40"]
    rows = [
        [RowView(topic="alpha", repo=str(tmp_path), tmux="alpha", ctx=20, status="restarting")],
        [RowView(topic="alpha", repo=str(tmp_path), tmux="alpha", ctx=82, status="idle")],
    ]
    sup.build_rows = lambda *, act: rows.pop(0)

    _ = sup.tick(act=True)
    assert executed == []

    _ = sup.tick(act=True)
    assert executed == [(str(target), [str(target), "--warn-percent", "40"])]
