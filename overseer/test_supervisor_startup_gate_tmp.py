"""Beside-tests for supervisor.py — startup gate tmp.

Split from `test_supervisor.py`, which carried the whole daemon surface at 3010 LLOC
after its shared helpers were extracted — still more than twelve times the 250-LLOC
hard ceiling. The doubles and builders live in `test_supervisor_fakes` /
`test_supervisor_builders`; this module holds only tests.

``import supervisor`` resolves via conftest.py.
"""

import importlib
import os
from pathlib import Path

import pytest
import registry
import supervisor
from test_supervisor_builders import (
    idle_capture,
    isolate_store,
    make_plan,
)
from test_supervisor_fakes import (
    FakeTmux,
)

__all__: list[str] = []


@pytest.fixture(autouse=True)
def _isolate_cwd(*, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


def test_start_refuses_running_claude_without_force(*, tmp_path, monkeypatch):
    """B8: `start` on a session already running a live Claude must NOT respawn-kill
    it — it upserts the mapping and reports; only --force respawns."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    store = isolate_store(tmp_path=tmp_path, monkeypatch=monkeypatch)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture())

    monkeypatch.setattr(supervisor.tmuxio, "TmuxIO", lambda: fake)
    rc = supervisor.main(argv=["start", "--repo", str(repo), "--topic", topic])
    assert rc == 0
    assert not fake.has(method="respawn")  # the live session was NOT killed
    # but the mapping was upserted
    assert [(r.topic) for r in registry.read_mapping(store_path=store)] == [topic]


def test_start_force_respawns_running_claude(*, tmp_path, monkeypatch):
    """B8: --force DOES respawn a running session (the explicit escape hatch)."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    isolate_store(tmp_path=tmp_path, monkeypatch=monkeypatch)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture())

    monkeypatch.setattr(supervisor.tmuxio, "TmuxIO", lambda: fake)
    rc = supervisor.main(argv=["start", "--force", "--repo", str(repo), "--topic", topic])
    assert rc == 0
    assert fake.has(method="respawn")


def test_cli_surface_has_no_config_knobs(*, tmp_path, monkeypatch):
    """The de-gold-plated track-management CLI: the removed --store/--stamp/--repos/
    --repos-only/--manifest flags and the old positional repo/topic are all
    rejected; --repo/--topic are required keyword flags; and `daemon` is NO LONGER
    a subcommand (it is the dedicated `overseerd` executable)."""
    isolate_store(tmp_path=tmp_path, monkeypatch=monkeypatch)
    repo = str(tmp_path / "repo")
    # Removed store / stamp knobs and the retired `daemon` subcommand are all
    # unrecognized now (argparse exits nonzero).
    rejected = (
        ["add", "--store", str(tmp_path / "x"), "--repo", repo, "--topic", "t"],
        ["add", "--repo", repo, "--topic", "t", "--stamp", str(tmp_path / "x")],
        ["list", "--store", str(tmp_path / "x")],
        ["daemon"],  # retired subcommand: the daemon is now the overseerd executable
        ["daemon", "--repos", repo],
    )
    for argv in rejected:
        with pytest.raises(SystemExit):
            supervisor.main(argv=argv)
    # The old positional form is gone; --repo and --topic are required.
    for argv in (["add", repo, "t"], ["add", "--repo", repo], ["start", "--topic", "t"]):
        with pytest.raises(SystemExit):
            supervisor.main(argv=argv)


def test_run_daemon_uses_fleet_defaults(*, monkeypatch):
    """`run_daemon()` (the overseerd entrypoint) starts the fleet daemon with the
    fixed defaults: the module loop interval, no single-tick, no startup recovery
    (surface-only — the daemon never auto-spawns/revives at startup)."""
    seen: dict[str, object] = {}

    class _RunOnlySup:
        def run(self, *, interval, once, recover):
            seen["args"] = (interval, once, recover)

    monkeypatch.setattr(supervisor, "build_supervisor", lambda: _RunOnlySup())
    assert supervisor.run_daemon() == 0
    assert seen["args"] == (supervisor.LOOP_INTERVAL_SECONDS, False, False)


def test_run_daemon_threads_warn_percent(*, monkeypatch):
    """run_daemon(warn_percent=N) sets the built Supervisor's warn_percent field;
    None falls back to registry.DEFAULT_CTX_THRESHOLD."""
    seen: list[int] = []

    class _Sup:
        warn_percent = registry.DEFAULT_CTX_THRESHOLD

        def run(self, *, interval, once, recover):
            seen.append(self.warn_percent)

    monkeypatch.setattr(supervisor, "build_supervisor", lambda: _Sup())
    assert supervisor.run_daemon(warn_percent=30) == 0
    assert seen == [30]
    assert supervisor.run_daemon() == 0  # None → the built-in default
    assert seen == [30, registry.DEFAULT_CTX_THRESHOLD]


def _load_overseerd():
    return importlib.import_module("overseer.daemon")


def test_overseerd_threads_and_validates_warn_percent(*, monkeypatch):
    """The overseerd executable parses --warn-percent (int in [1, 99]) and threads
    it into run_daemon; a missing flag passes None; out-of-range / non-int argv is
    rejected by argparse (SystemExit)."""
    mod = _load_overseerd()
    seen: dict[str, object] = {}

    def _fake_run(*, warn_percent=None):
        seen["wp"] = warn_percent
        return 0

    monkeypatch.setattr(mod.supervisor, "run_daemon", _fake_run)
    assert mod.main(argv=["--warn-percent", "30"]) == 0
    assert seen["wp"] == 30
    assert mod.main(argv=[]) == 0
    assert seen["wp"] is None
    for bad in (["--warn-percent", "0"], ["--warn-percent", "100"], ["--warn-percent", "x"]):
        with pytest.raises(SystemExit):
            mod.main(argv=bad)


def test_overseerd_console_entry_point_targets_importable_module(*, monkeypatch):
    module_path = Path(supervisor.__file__).resolve().parent / "daemon.py"
    assert module_path.is_file(), "overseerd logic must live in importable overseer.daemon"

    mod = importlib.import_module("overseer.daemon")
    seen: dict[str, object] = {}

    def _fake_run(*, warn_percent=None):
        seen["wp"] = warn_percent
        return 0

    monkeypatch.setattr(mod.supervisor, "run_daemon", _fake_run)
    assert mod.main(argv=["--warn-percent", "30"]) == 0
    assert seen["wp"] == 30

    pyproject = Path(supervisor.__file__).resolve().parent.parent / "pyproject.toml"
    assert 'overseerd = "overseer.daemon:main"' in pyproject.read_text(encoding="utf-8")


def test_overseerd_executable_is_the_daemon_entrypoint():
    """The dedicated `overseerd` executable sits beside supervisor.py, is
    executable, carries the uv self-invoking shebang, and delegates to
    `supervisor.run_daemon` — the daemon is a dedicated executable, NOT a
    subcommand."""
    overseerd = Path(supervisor.__file__).resolve().parent / "overseerd"
    assert overseerd.is_file(), "overseerd must sit beside supervisor.py"
    assert os.access(overseerd, os.X_OK), "overseerd must be executable (chmod +x)"
    body = overseerd.read_text(encoding="utf-8")
    assert body.startswith(
        "#!/usr/bin/env -S uv run --script --no-project\n"
    ), "overseerd must carry the uv self-invoking shebang on line 1"
    assert "from overseer.daemon import main" in body, "overseerd must delegate to overseer.daemon"


def test_wrapup_message_names_the_one_state_file_and_all_three_values():
    """The wrap-up must hand the session the SINGLE state file and all three legal
    values, plus the ledger-held plan state it will be resumed from — named by
    repository path and epic id. Only tmp/ paths — never a state file under plan/, and
    never a plan-tree handoff path as the read-first source."""
    msg = supervisor.wrapup_message(remaining=40, repo="/r", topic="t", epic="overseer-0007")
    assert "40%" in msg
    assert "/r/tmp/overseer/t/.overseer-state" in msg  # the ONE indicator file
    for token in ("winding-down", "ready", "blocked:"):
        assert token in msg
    # The read-first source is named explicitly, by BOTH coordinates.
    assert "overseer-0007" in msg
    assert "/r" in msg
    assert "handoff.md" not in msg
    assert "/r/plan/t/.overseer-state" not in msg  # never under plan/
    # The retired two-file protocol is GONE from the message.
    assert ".overseer-ready" not in msg
    assert ".overseer-blocked" not in msg


def test_wrapup_message_says_so_when_no_plan_epic_is_recorded():
    """A track with no recorded epic gets the truth, not a plausible-looking pointer.

    The restart interlock refuses to respawn such a track, so inventing a source here
    would tell the session to save its state somewhere nothing will ever read from.
    """
    msg = supervisor.wrapup_message(remaining=40, repo="/r", topic="t", epic=None)
    assert "NO plan epic id is recorded" in msg
    assert "handoff.md" not in msg
    # The declaration protocol is unchanged — a missing epic never suppresses the wrap-up.
    for token in ("winding-down", "ready", "blocked:"):
        assert token in msg


def test_wrapup_message_states_no_repo_specific_gate_size():
    """The wrap-up is pasted into sessions across the WHOLE fleet, so it must not
    assert a target COUNT for the doc-only gate — that number is repo-specific and is
    therefore false somewhere no matter which value is chosen.

    Measured 2026-07-26: livespec core's `check-pre-commit-doc-only` runs exactly seven
    targets, but in livespec-overseer (and livespec-dev-tooling, and livespec-runtime)
    the same recipe is an `exit 0` stub whose own echo reads "no repo-metadata checks
    wired yet". Only five of core's seven even have counterparts here. The message
    inherited "seven-target" from core, where the overseer used to live.

    Sabotage that reddens this: restore the word `seven-target` to `_WRAPUP_BODY`.
    """
    msg = supervisor.wrapup_message(remaining=40, repo="/r", topic="t", epic="overseer-0007")
    for count in ("seven-target", "seven target", "five-target", "five target"):
        assert count not in msg
    # The guidance itself must SURVIVE — this is about dropping a false number, not
    # about dropping the instruction to bring the session's own work through the gate.
    assert "--no-verify" in msg
    assert "gate" in msg


def test_wrapup_message_says_only_the_session_authorizes_the_restart():
    """The cardinal rule must be in the message the session actually reads: it is
    restarted only when IT says `ready`, and writing nothing gets it reported — not
    killed. (The old text promised an unconditional force-restart; that was the bug.)"""
    msg = supervisor.wrapup_message(remaining=13, repo="/r", topic="t", epic="overseer-0007")
    assert "ONLY when YOU say so" in msg
    assert "never kills a session" in msg
    assert "not responding" in msg  # writing nothing ⇒ reported to a human


def test_wrapup_message_tells_the_session_to_append_its_resume_state_to_the_ledger():
    """Writing the resume state down locally is NOT saving it
    (plan/archive/plan-thread-integrity/, W4).

    The wrap-up used to say only "UPDATE {handoff}", and the word "commit" appeared
    nowhere in this file — the "persisted is durable" conflation, sitting in the one
    instruction every overseer-managed wind-down receives. A handoff was left dirty on
    2026-07-19 and rescued only by luck.

    The read-first source is now the plan's LEDGER-HELD state, so the same conflation
    wears a new shape: a session that writes its resume state into a local file, or into
    the transcript, has saved nothing the successor can see. The text therefore has to
    name the ACT (append), the ROUTE (the orchestrator's sanctioned plan surface), and
    the two non-routes (a file under plan/, a direct ledger write) — or a low-context
    session strands its successor with an empty read-first source.
    """
    msg = supervisor.wrapup_message(
        remaining=40, repo="/data/projects/livespec", topic="t", epic="overseer-0007"
    )
    assert "APPEND" in msg
    assert "NOT saving it" in msg
    # The route, and the two things that are NOT the route.
    assert "sanctioned plan" in msg
    assert "do NOT write to the ledger directly" in msg
    assert "under plan/" in msg
    # The bypasses it must NOT offer as an escape.
    assert "Never pass --no-verify" in msg
    assert "do not discard the work" in msg
    # And the retired file-shaped ritual is gone from the worker text entirely.
    assert "handoff.md" not in msg
    assert "worktree add" not in msg


def test_wrapup_escalates_from_suggestion_to_insistence():
    """The maintainer's escalation: a SUGGESTION while there is still room (50/40),
    turning INSISTENT at 30/20/10. Re-sending identical text five times is repetition,
    not escalation — and with no force-restart, this escalation IS the lever."""
    for gentle in (50, 40):
        msg = supervisor.wrapup_message(
            remaining=gentle, repo="/r", topic="t", epic="overseer-0007"
        )
        assert "Please start wrapping up" in msg
        assert "STOP AND WIND DOWN NOW" not in msg
    for insistent in (30, 20, 10):
        msg = supervisor.wrapup_message(
            remaining=insistent, repo="/r", topic="t", epic="overseer-0007"
        )
        assert "STOP AND WIND DOWN NOW" in msg
        assert "Please start wrapping up" not in msg
