"""Beside-tests for supervisor.py — claude registry status.

Split from `test_supervisor.py`, which carried the whole daemon surface at 3010 LLOC
after its shared helpers were extracted — still more than twelve times the 250-LLOC
hard ceiling. The doubles and builders live in `test_supervisor_fakes` /
`test_supervisor_builders`; this module holds only tests.

``import supervisor`` resolves via conftest.py.
"""

import json
import os

import codex_sessions
import pytest
import registry
from test_supervisor_builders import (
    adopt_sup,
    make_plan,
    mapped_track,
    write_session,
)
from test_supervisor_fakes import (
    FakeTmux,
)


@pytest.fixture(autouse=True)
def _isolate_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


def test_refresh_claude_status_populates_the_map_from_registry(tmp_path):
    """`build_rows` recomputes `{tmux: status}` from the registry ⋈ tmux each tick, so
    `evaluate` can read a live session's status without a per-track registry read."""
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    write_session(sessions_dir, 100, name="topic", cwd="/r", status="busy")
    fake = FakeTmux()
    fake.pane_pids[50] = "sA"  # pane PID 50 → tmux session sA
    ppid = {100: 50, 50: 1}  # claude 100 → pane 50
    sup = adopt_sup(tmp_path, fake, sessions_dir, ppid, {100: "pt"})
    sup._refresh_claude_status()
    assert sup._claude_status == {"sA": "busy"}


def test_adopt_sessions_links_by_registry_name(tmp_path):  # noqa: PLR0915 — see below
    """adopt maps each LIVE Claude session (from ~/.claude/sessions) to a plan when
    its registry `cwd` is in a fleet repo AND its `name` is an active plan topic,
    joined to the tmux session by PID. Registry membership proves it is a claude
    process, so there is no worker-command guard. Non-matches, a session outside
    tmux, a dead PID, and an already-mapped (repo, topic) contribute nothing.

    Over the statement limit (PLR0915) deliberately: the seven session rows below
    are seven DIFFERENT adoption outcomes that must be exercised against a single
    `adopt_sessions()` call, because what is under test is how adoption handles a
    MIXED population in one pass. Splitting them into seven tests would test seven
    homogeneous populations instead, and hoisting the fixture to a module-level
    builder would separate each row from the assertion about it.
    """
    repo_a, _ = make_plan(tmp_path, repo_name="repo_a", topic="alpha")
    repo_b, _ = make_plan(tmp_path, repo_name="repo_b", topic="beta")
    (repo_a / "plan" / "gamma").mkdir(parents=True)
    (repo_a / "plan" / "gamma" / "handoff.md").write_bytes(b"h\n")

    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    fake = FakeTmux()
    ppid: dict[int, int] = {}
    starttimes: dict[int, str] = {}

    def live(pid, name, cwd, session, *, in_tmux=True, alive=True):
        write_session(sessions_dir, pid, name=name, cwd=cwd)
        if alive:
            starttimes[pid] = "pt"  # matches procStart → live
        shell = pid + 1  # the claude PID's parent is its pane's shell
        ppid[pid] = shell
        if in_tmux:
            fake.pane_pids[shell] = session

    live(100, "alpha", repo_a, "sesA")  # ADOPT → repo_a::alpha
    live(200, "beta", repo_b, "sesB")  # ADOPT → repo_b::beta
    live(300, "notaplan", repo_a, "sesN")  # skip: name not an active topic
    live(400, "delta", "/somewhere/else", "sesD")  # skip: cwd not in a fleet repo
    live(500, "gamma", repo_a, "sesG")  # RE-POINT: (repo_a, gamma) mapped but its session MOVED
    live(600, "alpha", repo_a, "sesX", in_tmux=False)  # skip: not inside any tmux pane
    live(700, "gamma", repo_a, "sesDead", alive=False)  # skip: dead PID (starttime mismatch)

    sup = adopt_sup(
        tmp_path, fake, sessions_dir, ppid, starttimes, watch_repos=[str(repo_a), str(repo_b)]
    )
    registry.append_mapping(
        mapped_track(repo_a, "gamma", "gamma-existing"), sup.store_path, added_at="pre"
    )

    adopted = sup.adopt_sessions()

    assert sorted((t.repo, t.topic, t.tmux) for t in adopted) == [
        (os.path.normpath(str(repo_a)), "alpha", "sesA"),
        (os.path.normpath(str(repo_b)), "beta", "sesB"),
    ]
    rows = {(r.repo, r.topic): r.tmux for r in registry.read_mapping(sup.store_path)}
    assert rows[(os.path.normpath(str(repo_a)), "alpha")] == "sesA"  # mapped to the SESSION name
    assert rows[(os.path.normpath(str(repo_b)), "beta")] == "sesB"
    # `gamma` was already mapped, but its live named session MOVED (the store recorded
    # `gamma-existing`; the live session now resolves to `sesG`). Adoption RE-POINTS the
    # stale mapping to the current tmux session (R2) rather than freezing it — and it is a
    # re-point, not an adoption, so `gamma` is absent from `adopted` above.
    assert (
        rows[(os.path.normpath(str(repo_a)), "gamma")] == "sesG"
    )  # re-pointed to the live session
    assert (os.path.normpath(str(repo_a)), "notaplan") not in rows  # name not a plan topic
    assert "delta" not in {topic for _repo, topic in rows}  # cwd not in a fleet repo


def test_adopt_sessions_empty_when_no_registry_match(tmp_path):
    """A live registry session in the repo but whose name is NOT an active topic →
    adopt returns [] and writes nothing."""
    repo, _ = make_plan(tmp_path)  # active topic: "topic"
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    fake = FakeTmux()
    ppid, starttimes = {100: 101}, {100: "pt"}
    fake.pane_pids[101] = "s1"
    write_session(sessions_dir, 100, name="unrelated-name", cwd=repo)
    sup = adopt_sup(tmp_path, fake, sessions_dir, ppid, starttimes, watch_repos=[str(repo)])
    assert sup.adopt_sessions() == []
    assert registry.read_mapping(sup.store_path) == []


def test_adopt_is_continuous_across_ticks(tmp_path):
    """adopt runs every tick via build_rows(act=True): a session not yet named as a
    plan topic at one tick is picked up on a LATER tick once its registry name
    matches — the fix for 'the daemon never re-adopted after the prompt cleared'."""
    repo, topic = make_plan(tmp_path)  # active topic: "topic"
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    fake = FakeTmux()
    ppid, starttimes = {100: 101}, {100: "pt"}
    fake.pane_pids[101] = "s1"

    # Tick 1: session exists (in tmux, in the repo) but is named something else.
    write_session(sessions_dir, 100, name="scratch", cwd=repo)
    sup = adopt_sup(tmp_path, fake, sessions_dir, ppid, starttimes, watch_repos=[str(repo)])
    sup.build_rows(act=True)
    assert registry.read_mapping(sup.store_path) == []  # not adopted yet

    # Tick 2: the maintainer renamed it to the plan topic → adopted this tick.
    write_session(sessions_dir, 100, name=topic, cwd=repo)
    sup.build_rows(act=True)
    rows = {(r.repo, r.topic): r.tmux for r in registry.read_mapping(sup.store_path)}
    assert rows.get((os.path.normpath(str(repo)), topic)) == "s1"


# --------------------------------------------------------------------------- #
# Codex discovery is fully injectable (#6): adopt + refresh route through the
# Supervisor's codex seams, never the real /proc scan or ~/.codex — so the suite
# is hermetic even with a live codex on the host.
# --------------------------------------------------------------------------- #


def test_refresh_and_adopt_route_codex_through_injected_seams(tmp_path):
    """`adopt_sessions` and `_refresh_codex_sessions` must drive Codex discovery through the
    INJECTED seams (`codex_home` / `codex_pids_of_comm` / `codex_fd_targets_of` /
    `codex_cwd_of`), never `codex_sessions`' real `/proc` scan + `~/.codex`. We wire the
    seams to a fully-simulated codex process — pid 9000, holding a rollout whose id the
    injected `~/.codex` index names for our topic — and assert BOTH paths discover it. That
    is impossible unless every reader is the injected one (pid 9000 is not a real process),
    so it proves the threading AND that no real host state is read. Sabotage-verify: drop
    any seam from either supervisor call site and the discovery goes empty."""
    repo, topic = make_plan(tmp_path, topic="cx")
    fake = FakeTmux()
    fake.pane_pids = {7001: "livespec-cx"}  # the codex pid's pane-pid ancestor → this tmux
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()  # no claude registry files → the claude side contributes nothing
    # An injected ~/.codex whose index names our fake session-id for the topic.
    codex_home = tmp_path / "codex-home"
    codex_home.mkdir()
    sid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    (codex_home / "session_index.jsonl").write_text(
        json.dumps({"id": sid, "thread_name": topic}) + "\n", encoding="utf-8"
    )
    # Injected /proc seams describing ONE live codex process (pid 9000) in this repo,
    # each recording its calls so we can assert the injected readers are the ones hit.
    hits = {"pids": [], "fd": [], "cwd": []}

    def _pids(comm):
        hits["pids"].append(comm)
        return [9000] if comm == codex_sessions.CODEX_COMM else []

    def _fd(pid):
        hits["fd"].append(pid)
        return [f"/proc/{pid}/fd/rollout-2026-07-18T00-00-00-{sid}.jsonl"] if pid == 9000 else []

    def _cwd(pid):
        hits["cwd"].append(pid)
        return str(repo) if pid == 9000 else None

    sup = adopt_sup(
        tmp_path,
        fake,
        sessions_dir,
        {9000: 7001},  # ppid_of: pid 9000's parent is the pane pid 7001 (→ resolves to tmux)
        {},
        watch_repos=[str(repo)],
        codex_home=str(codex_home),
        codex_pids_of_comm=_pids,
        codex_fd_targets_of=_fd,
        codex_cwd_of=_cwd,
    )

    adopted = sup.adopt_sessions()
    assert [(t.topic, t.tmux) for t in adopted] == [(topic, "livespec-cx")]
    assert hits["pids"] and hits["fd"] and hits["cwd"]  # the injected readers were the ones hit

    sup._refresh_codex_sessions()
    live = sup._codex.get(("livespec-cx", topic))
    assert live is not None and live.session_id == sid
