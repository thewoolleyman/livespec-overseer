"""Tests for the deterministic Phase B foreman runtime wrapper."""

from __future__ import annotations

import importlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from _claude_sessions_registry import ClaudeSession

OVERSEER_DIR = Path(__file__).resolve().parents[1] / "overseer"
MODULE_PATH = OVERSEER_DIR / "foreman_runtime.py"
EXECUTABLE_PATH = OVERSEER_DIR / "foreman-runtime"

__all__: list[str] = []


@dataclass(frozen=True, kw_only=True)
class FakeTmux:
    sessions: frozenset[str]

    def session_exists(self, *, session: str) -> bool:
        return session in self.sessions


def foreman_runtime():
    assert MODULE_PATH.is_file()
    if str(OVERSEER_DIR) not in sys.path:
        sys.path.insert(0, str(OVERSEER_DIR))
    return importlib.import_module("foreman_runtime")


def make_repo(*, tmp_path: Path, name: str = "repo") -> Path:
    repo = tmp_path / name
    (repo / "plan" / "alpha").mkdir(parents=True)
    (repo / "tmp" / "overseer").mkdir(parents=True)
    return repo


def write_watch_set(*, path: Path, repos: list[Path]) -> None:
    path.write_text(json.dumps({"repos": [str(repo) for repo in repos]}) + "\n", encoding="utf-8")


def session(*, repo: Path, name: str = "repo-foreman", pid: int = 123, start: str = "9"):
    return ClaudeSession(pid=pid, name=name, cwd=str(repo), status="idle", proc_start=start)


def state_json(*, repo: Path) -> dict[str, object]:
    return json.loads(
        (repo / "tmp" / "overseer" / "foreman" / "runtime.json").read_text(encoding="utf-8")
    )


def test_runtime_module_and_executable_exist():
    assert MODULE_PATH.is_file()
    assert EXECUTABLE_PATH.is_file()
    assert EXECUTABLE_PATH.stat().st_mode & 0o111


def test_entry_and_identity_gates_fail_closed(*, tmp_path):
    module = foreman_runtime()
    repo = make_repo(tmp_path=tmp_path)
    other = make_repo(tmp_path=tmp_path, name="other")
    watch_set = tmp_path / "repos.json"
    write_watch_set(path=watch_set, repos=[repo])

    base = {
        "repo": repo,
        "watch_set_path": watch_set,
        "tmux": FakeTmux(sessions=frozenset({"repo-foreman"})),
        "sessions": [session(repo=repo)],
    }

    assert module.entry_gate(**base, cwd=other).ok is False
    assert module.entry_gate(**base, cwd=repo).ok is True
    missing_watch = module.entry_gate(
        **{**base, "watch_set_path": tmp_path / "missing.json"}, cwd=repo
    )
    assert missing_watch.ok is False
    missing_tmux = module.entry_gate(**{**base, "tmux": FakeTmux(sessions=frozenset())}, cwd=repo)
    assert missing_tmux.ok is False
    wrong_name = module.entry_gate(
        **{**base, "sessions": [session(repo=repo, name="foreman")]}, cwd=repo
    )
    assert wrong_name.ok is False
    assert module.entry_gate(**{**base, "sessions": []}, cwd=repo).ok is False


def test_live_lock_excludes_second_runtime_and_recovers_stale_or_reused_pid(*, tmp_path):
    module = foreman_runtime()
    repo = make_repo(tmp_path=tmp_path)
    lock = module.ForemanLock(path=repo / "tmp" / "overseer" / "foreman" / "runtime.lock")

    first = lock.acquire(pid=111, start_time="alpha", start_time_of=lambda *, pid: "alpha")
    assert first.acquired is True
    second = lock.acquire(pid=222, start_time="beta", start_time_of=lambda *, pid: "alpha")
    assert second.acquired is False
    assert "held by live pid 111" in second.reason

    lock.path.write_text('{"pid":111,"start_time":"old"}\n', encoding="utf-8")
    reused = lock.acquire(pid=222, start_time="beta", start_time_of=lambda *, pid: "new")
    assert reused.acquired is True
    assert json.loads(lock.path.read_text(encoding="utf-8")) == {"pid": 222, "start_time": "beta"}

    lock.path.write_text('{"pid":333,"start_time":"gone"}\n', encoding="utf-8")
    stale = lock.acquire(pid=444, start_time="gamma", start_time_of=lambda *, pid: None)
    assert stale.acquired is True


def test_tick_rotation_hourly_default_budget_and_heartbeat(*, tmp_path):
    module = foreman_runtime()
    repo = make_repo(tmp_path=tmp_path)
    calls: list[int] = []
    runtime = module.ForemanRuntime(
        repo=repo,
        now=lambda: 1000.0,
        llm_tick=lambda *, document: calls.append(len(document.monitored_entities)) or True,
    )

    assert runtime.config.llm_tick_interval_seconds == 3600
    first = runtime.step(document={"snapshot": {"rows": [{"topic": "alpha", "status": "idle"}]}})
    assert first.llm_tick is True
    assert first.exit_reason is None
    assert state_json(repo=repo)["next_llm_tick_at"] == 4600.0
    heartbeat = json.loads(
        (repo / "tmp" / "overseer" / "foreman" / "heartbeat.json").read_text(encoding="utf-8")
    )
    assert heartbeat["tick_generation"] == 1
    assert heartbeat["tick_interval_seconds"] == 3600
    assert calls == [1]

    runtime = module.ForemanRuntime(
        repo=repo,
        now=lambda: 4600.0,
        config=module.ForemanConfig(hard_tick_budget=2),
        llm_tick=lambda *, document: calls.append(len(document.monitored_entities)) or False,
    )
    second = runtime.step(document={"snapshot": {"rows": [{"topic": "alpha", "status": "idle"}]}})
    assert second.exit_reason == "hard-tick-budget"


def test_early_carrier_ticks_do_not_push_llm_deadline_past_due_tick(*, tmp_path):
    module = foreman_runtime()
    repo = make_repo(tmp_path=tmp_path)
    clock = {"now": 1000.0}
    calls: list[float] = []
    runtime = module.ForemanRuntime(
        repo=repo,
        now=lambda: clock["now"],
        llm_tick=lambda *, document: calls.append(clock["now"]) or False,
    )
    document = {"snapshot": {"rows": [{"topic": "alpha", "status": "idle"}]}}

    first = runtime.step(document=document)
    assert first.llm_tick is True
    assert state_json(repo=repo)["next_llm_tick_at"] == 4600.0

    clock["now"] = 4590.0
    early = runtime.step(document=document)
    assert early.llm_tick is False
    assert state_json(repo=repo)["next_llm_tick_at"] == 4600.0

    clock["now"] = 4605.0
    due_after_jitter = runtime.step(document=document)
    assert due_after_jitter.llm_tick is True
    assert state_json(repo=repo)["next_llm_tick_at"] == 8205.0

    for expected_call in (8210.0, 11815.0, 15420.0):
        clock["now"] = expected_call
        result = runtime.step(document=document)
        assert result.llm_tick is True

    assert calls == [1000.0, 4605.0, 8210.0, 11815.0, 15420.0]


def test_loop_lapsed_is_false_on_the_first_ever_tick(*, tmp_path):
    module = foreman_runtime()
    repo = make_repo(tmp_path=tmp_path)
    runtime = module.ForemanRuntime(repo=repo, now=lambda: 1000.0)

    first = runtime.step(document={"snapshot": {"rows": [{"topic": "alpha", "status": "idle"}]}})

    assert first.loop_lapsed is False
    assert first.heartbeat_age_seconds is None


def test_loop_lapsed_is_false_when_the_recurring_loop_ticked_on_schedule(*, tmp_path):
    module = foreman_runtime()
    repo = make_repo(tmp_path=tmp_path)
    clock = {"now": 1000.0}
    runtime = module.ForemanRuntime(repo=repo, now=lambda: clock["now"])
    document = {"snapshot": {"rows": [{"topic": "alpha", "status": "idle"}]}}

    runtime.step(document=document)
    clock["now"] += 3600.0  # exactly one default hourly interval later
    second = runtime.step(document=document)

    assert second.loop_lapsed is False
    assert second.heartbeat_age_seconds == 3600.0


def test_loop_lapsed_is_true_after_the_recurring_loop_stopped_ticking(*, tmp_path):
    module = foreman_runtime()
    repo = make_repo(tmp_path=tmp_path)
    clock = {"now": 1000.0}
    runtime = module.ForemanRuntime(repo=repo, now=lambda: clock["now"])
    document = {"snapshot": {"rows": [{"topic": "alpha", "status": "idle"}]}}

    runtime.step(document=document)
    # No further ticks land for well over 2x the hourly interval — the same
    # threshold the daemon's own `foreman_row` uses to raise a stale-heartbeat
    # NEEDS YOU alert (`_supervisor_foreman._stale_after`). A manually-invoked
    # tick that lands after that gap must see the lapse immediately, not only
    # after the daemon's next poll of the heartbeat file this call is about to
    # overwrite.
    clock["now"] += 3.0 * 3600.0
    resumed = runtime.step(document=document)

    assert resumed.loop_lapsed is True
    assert resumed.heartbeat_age_seconds == 3.0 * 3600.0


def test_convergence_requires_non_empty_set_no_change_and_no_action(*, tmp_path):
    module = foreman_runtime()
    repo = make_repo(tmp_path=tmp_path)
    config = module.ForemanConfig(converged_ticks=2)
    actions = [False, False, True, False, False]
    clock = {"now": 10.0}
    runtime = module.ForemanRuntime(
        repo=repo,
        now=lambda: clock["now"],
        config=config,
        llm_tick=lambda *, document: actions.pop(0),
    )

    empty = runtime.step(document={"snapshot": {"rows": []}})
    assert empty.exit_reason is None
    clock["now"] = 3610.0
    first = runtime.step(document={"snapshot": {"rows": [{"topic": "a", "status": "idle"}]}})
    assert first.exit_reason is None
    clock["now"] = 7210.0
    action = runtime.step(document={"snapshot": {"rows": [{"topic": "a", "status": "idle"}]}})
    assert action.action_taken is True
    assert action.exit_reason is None
    clock["now"] = 10810.0
    no_change = runtime.step(document={"snapshot": {"rows": [{"topic": "a", "status": "idle"}]}})
    assert no_change.exit_reason is None
    clock["now"] = 14410.0
    converged = runtime.step(document={"snapshot": {"rows": [{"topic": "a", "status": "idle"}]}})
    assert converged.exit_reason == "converged"


def test_unchanged_token_free_observation_preserves_stable_tick_without_converging(*, tmp_path):
    module = foreman_runtime()
    repo = make_repo(tmp_path=tmp_path)
    clock = {"now": 10.0}
    runtime = module.ForemanRuntime(repo=repo, now=lambda: clock["now"])
    document = {"snapshot": {"rows": [{"topic": "a", "status": "idle"}]}}

    first = runtime.step(document=document)
    immediate = runtime.step(document=document)

    assert first.llm_tick is True
    assert immediate.llm_tick is False
    assert immediate.exit_reason is None
    assert state_json(repo=repo)["stable_ticks"] == 1


def test_token_free_generation_watcher_reenters_after_llm_loop_exit(*, tmp_path):
    module = foreman_runtime()
    repo = make_repo(tmp_path=tmp_path)
    runtime = module.ForemanRuntime(
        repo=repo, now=lambda: 0.0, config=module.ForemanConfig(converged_ticks=1)
    )

    result = runtime.step(document={"snapshot": {"rows": [{"topic": "a", "status": "idle"}]}})
    assert result.exit_reason == "converged"
    snapshot_one = {"snapshot": {"tick_generation": 1, "rows": []}}
    assert runtime.token_free_watch(document=snapshot_one) is True
    assert runtime.token_free_watch(document=snapshot_one) is False
    assert (
        runtime.token_free_watch(document={"snapshot": {"tick_generation": 2, "rows": []}}) is True
    )
    attention = {"needs_attention": {"items": [{"id": "overseer-a"}]}}
    assert runtime.token_free_watch(document=attention) is True
