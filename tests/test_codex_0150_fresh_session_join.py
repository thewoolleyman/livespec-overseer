"""Regression cover for the Codex 0.150 fresh-session live join.

Codex 0.150 moved a session's rollout OWNERSHIP off the TUI process and onto a helper
the TUI spawns. `read_live_codex_sessions` read only the carrier's own fd table, so a
fresh, indexed, correctly-named session in the exact repository produced NO live record
— while established sessions, which still held their own rollout, stayed discoverable.
That is the attended host evidence on `overseer-qmarlj`, modelled here as a process
shape rather than described in prose.

The shape has two halves and both are load-bearing: the carrier (`comm == codex`) holds
the identity and sits in the repository, and the helper holds the rollout while sitting
somewhere else entirely. A join that simply accepted the helper as the session would
find the name and record the WRONG repo, which the fail-closed controls below pin.

Every host coupling is injected, so these run with no codex process and no real
`~/.codex`; no rollout file is written, and one case proves none is opened either.
"""

from __future__ import annotations

import inspect
import json
from dataclasses import dataclass
from pathlib import Path

import codex_sessions
import foreman_runtime_identity

__all__: list[str] = []

CARRIER_PID = 4242  # the TUI: comm == codex, cwd == the repository, in the tmux pane
HELPER_PID = 4243  # what 0.150 spawns to own the rollout; its cwd is NOT the repository
NESTED_PID = 4244  # a `codex resume` started from the carrier's own shell tool
HELPER_CWD = "/"
INDEXED_ID = "019f6a1e-266d-7fc2-8eb2-15ec9d324fb8"
OTHER_ID = "019f548d-6071-7893-9c2e-472cce81da02"
NESTED_ID = "019fc714-beaa-7992-aedf-039091f6d94a"


def rollout(*, session_id: str) -> str:
    """A rollout path of the real shape — the session id lives in the FILENAME."""
    return f"/home/u/.codex/sessions/2026/08/27/rollout-2026-08-27T02-00-00-{session_id}.jsonl"


def index(*, tmp_path: Path, records: list[dict[str, object]]) -> Path:
    """A `~/.codex` whose `session_index.jsonl` holds `records`, verbatim, in order."""
    home = tmp_path / "codex"
    home.mkdir(exist_ok=True)
    lines = [json.dumps(record) for record in records]
    (home / "session_index.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return home


def named(*, session_id: str, thread_name: str) -> dict[str, object]:
    return {"id": session_id, "thread_name": thread_name, "updated_at": "2026-08-27T02:00:00Z"}


def host(*, comms=None, cwds=None, fds=None, children=None) -> dict[str, object]:
    """Injected readers for one host: pid→comm, pid→cwd, pid→open fds, pid→children.

    The seam assertion is deliberate. Without a process-tree reader the join cannot see
    a helper-owned rollout AT ALL, and every case below would fail with a TypeError on
    an unexpected keyword rather than on the behaviour it is about — so the gap is
    stated here once, as the behavioural claim it is.
    """
    assert "children_of" in inspect.signature(codex_sessions.read_live_codex_sessions).parameters, (
        "read_live_codex_sessions takes no process-tree seam, so it cannot reach a rollout "
        "held by the helper process a Codex 0.150 session spawns"
    )
    comms, cwds, fds, children = comms or {}, cwds or {}, fds or {}, children or {}
    return {
        "pids_of_comm": lambda *, comm: sorted(p for p, c in comms.items() if c == comm),
        "cwd_of": lambda *, pid: cwds.get(pid),
        "fd_targets_of": lambda *, pid: fds.get(pid, []),
        "children_of": lambda *, pid: list(children.get(pid, [])),
    }


def fresh_0150_host(*, carrier_cwd, helper_fds, carrier_comm=None) -> dict[str, object]:
    """The measured 0.150 shape: the carrier holds NO rollout, its helper holds one."""
    return host(
        comms={
            CARRIER_PID: carrier_comm or codex_sessions.CODEX_COMM,
            HELPER_PID: "codex-app-server",
        },
        cwds={CARRIER_PID: carrier_cwd, HELPER_PID: HELPER_CWD},
        fds={CARRIER_PID: ["/dev/null", "socket:[1]"], HELPER_PID: list(helper_fds)},
        children={CARRIER_PID: [HELPER_PID]},
    )


@dataclass(frozen=True, kw_only=True)
class FakeTmux:
    sessions: frozenset[str]

    def session_exists(self, *, session: str) -> bool:
        return session in self.sessions


def watched_repo(*, tmp_path: Path) -> tuple[Path, Path, str]:
    """A watched repo, its watch-set file, and the canonical foreman session name."""
    repo = tmp_path / "repo"
    (repo / "plan" / "alpha").mkdir(parents=True)
    watch_set = tmp_path / "repos.json"
    watch_set.write_text(json.dumps({"repos": [str(repo)]}) + "\n", encoding="utf-8")
    return repo, watch_set, foreman_runtime_identity.canonical_session_name(repo=repo)


def gate(*, repo: Path, watch_set: Path, session_name: str, live) -> object:
    """The shared foreman entry gate, fed exactly the evidence this reader produced."""
    return foreman_runtime_identity.entry_gate(
        repo=repo,
        cwd=repo,
        watch_set_path=watch_set,
        tmux=FakeTmux(sessions=frozenset({session_name})),
        evidence=foreman_runtime_identity.RuntimeEvidence(codex_sessions=live),
    )


def test_a_fresh_codex_0150_session_joins_through_the_helper_holding_its_rollout(*, tmp_path):
    """The regression. The carrier holds no rollout fd of its own, so the pre-0.150 join
    saw nothing; the helper it spawned holds the indexed rollout. The record must carry
    the CARRIER's pid and cwd — the helper's cwd is `/`, and reporting that would name
    the session in the wrong repository — and it must enter the foreman gate."""
    repo, watch_set, session_name = watched_repo(tmp_path=tmp_path)
    home = index(
        tmp_path=tmp_path, records=[named(session_id=INDEXED_ID, thread_name=session_name)]
    )

    live = codex_sessions.read_live_codex_sessions(
        codex_home=home,
        **fresh_0150_host(carrier_cwd=str(repo), helper_fds=[rollout(session_id=INDEXED_ID)]),
    )

    assert [(s.pid, s.name, s.cwd, s.session_id) for s in live] == [
        (CARRIER_PID, session_name, str(repo), INDEXED_ID)
    ]
    admitted = gate(repo=repo, watch_set=watch_set, session_name=session_name, live=live)
    assert admitted.ok is True
    assert admitted.session_name == session_name


def test_an_established_session_holding_its_own_rollout_is_still_discovered(*, tmp_path):
    """The pre-0.150 shape — one codex process, its own rollout fd, no helper anywhere —
    must keep joining exactly as it did. Those sessions stayed discoverable through the
    upgrade, and the repair must not trade one shape for the other."""
    repo, watch_set, session_name = watched_repo(tmp_path=tmp_path)
    home = index(
        tmp_path=tmp_path, records=[named(session_id=INDEXED_ID, thread_name=session_name)]
    )

    live = codex_sessions.read_live_codex_sessions(
        codex_home=home,
        **host(
            comms={CARRIER_PID: codex_sessions.CODEX_COMM},
            cwds={CARRIER_PID: str(repo)},
            fds={CARRIER_PID: ["/dev/null", rollout(session_id=INDEXED_ID)]},
        ),
    )

    assert [(s.pid, s.name, s.cwd, s.session_id) for s in live] == [
        (CARRIER_PID, session_name, str(repo), INDEXED_ID)
    ]
    assert gate(repo=repo, watch_set=watch_set, session_name=session_name, live=live).ok is True


def test_a_nested_codex_session_keeps_its_own_identity_instead_of_its_parents(*, tmp_path):
    """A `codex resume` launched from another session's shell tool is a DESCENDANT of
    that session and is its own identity. The walk must stop at it: attributing its
    rollout to the parent would name the parent's track after someone else's topic, and
    the daemon restarts a track by that name."""
    repo, _watch_set, session_name = watched_repo(tmp_path=tmp_path)
    home = index(
        tmp_path=tmp_path,
        records=[
            named(session_id=INDEXED_ID, thread_name=session_name),
            named(session_id=NESTED_ID, thread_name="a-different-topic"),
        ],
    )

    live = codex_sessions.read_live_codex_sessions(
        codex_home=home,
        **host(
            comms={
                CARRIER_PID: codex_sessions.CODEX_COMM,
                NESTED_PID: codex_sessions.CODEX_COMM,
                HELPER_PID: "codex-app-server",
            },
            cwds={
                CARRIER_PID: str(repo),
                NESTED_PID: str(repo),
                HELPER_PID: HELPER_CWD,
            },
            fds={
                CARRIER_PID: [rollout(session_id=INDEXED_ID)],
                NESTED_PID: [],
                HELPER_PID: [rollout(session_id=NESTED_ID)],
            },
            children={CARRIER_PID: [NESTED_PID], NESTED_PID: [HELPER_PID]},
        ),
    )

    assert [(s.pid, s.name) for s in live] == [
        (CARRIER_PID, session_name),
        (NESTED_PID, "a-different-topic"),
    ]


def test_every_unsound_0150_shape_stays_fail_closed_through_the_foreman_gate(*, tmp_path):
    """The controls. Each is a live 0.150 process tree missing exactly one thing the
    identity proof needs, and every one must be REFUSED — the widened rollout lookup
    must not have widened what counts as an identity.

    The third field says whether the READER is silent, and the split is the design, not
    an inconsistency: the reader is a dumb join that reports whatever live session it can
    name, so a session with no id, no name, no cwd or no carrier is dropped THERE, while a
    real Codex session that is simply not this repo's foreman is reported and refused at
    the gate. Wrong-name and wrong-cwd are exactly that case, and asserting silence for
    them would pin policy into the wrong module.
    """
    repo, watch_set, session_name = watched_repo(tmp_path=tmp_path)
    indexed = [named(session_id=INDEXED_ID, thread_name=session_name)]
    dead_process = fresh_0150_host(
        carrier_cwd=str(repo), helper_fds=[rollout(session_id=INDEXED_ID)]
    )
    dead_process["cwd_of"] = lambda *, pid: None  # the carrier vanished mid-read
    cases = {
        "unindexed": (
            [named(session_id=OTHER_ID, thread_name=session_name)],
            fresh_0150_host(carrier_cwd=str(repo), helper_fds=[rollout(session_id=INDEXED_ID)]),
            True,
        ),
        "wrong name": (
            [named(session_id=INDEXED_ID, thread_name="some-other-topic")],
            fresh_0150_host(carrier_cwd=str(repo), helper_fds=[rollout(session_id=INDEXED_ID)]),
            False,
        ),
        "wrong cwd": (
            indexed,
            fresh_0150_host(
                carrier_cwd="/data/projects/elsewhere",
                helper_fds=[rollout(session_id=INDEXED_ID)],
            ),
            False,
        ),
        "dead process": (indexed, dead_process, True),
        "missing rollout": (
            indexed,
            fresh_0150_host(carrier_cwd=str(repo), helper_fds=["/dev/null", "socket:[2]"]),
            True,
        ),
        "malformed rollout name": (
            indexed,
            fresh_0150_host(
                carrier_cwd=str(repo),
                helper_fds=["/home/u/.codex/sessions/2026/08/27/rollout-no-uuid-here.jsonl"],
            ),
            True,
        ),
        "malformed index record": (
            [{"id": 17, "thread_name": session_name}, {"thread_name": session_name}],
            fresh_0150_host(carrier_cwd=str(repo), helper_fds=[rollout(session_id=INDEXED_ID)]),
            True,
        ),
        "not a codex carrier": (
            indexed,
            fresh_0150_host(
                carrier_cwd=str(repo),
                helper_fds=[rollout(session_id=INDEXED_ID)],
                carrier_comm="bun",
            ),
            True,
        ),
    }

    for label, (records, live_host, reader_is_silent) in cases.items():
        live = codex_sessions.read_live_codex_sessions(
            codex_home=index(tmp_path=tmp_path, records=records), **live_host
        )
        refused = gate(repo=repo, watch_set=watch_set, session_name=session_name, live=live)
        assert (live == []) is reader_is_silent, label
        assert refused.ok is False, label
        assert refused.reason == "runtime registry mismatch", label


def test_the_walk_is_bounded_and_survives_a_cycle_in_the_process_tree(*, tmp_path):
    """A `/proc` tree read pid-by-pid is not guaranteed acyclic or small, and this runs
    once per carrier per tick. The visited set makes a cycle terminate; `max_nodes`
    stops a deep chain, and stopping means the ids beyond the bound are simply not
    found — never a partial identity, since a session with no id is dropped."""
    _repo, _watch_set, _session_name = watched_repo(tmp_path=tmp_path)
    cyclic = host(
        fds={HELPER_PID: [rollout(session_id=INDEXED_ID)]},
        children={CARRIER_PID: [HELPER_PID], HELPER_PID: [CARRIER_PID, HELPER_PID]},
    )
    chain = host(
        fds={
            HELPER_PID: [rollout(session_id=INDEXED_ID)],
            NESTED_PID: [rollout(session_id=OTHER_ID)],
        },
        children={CARRIER_PID: [HELPER_PID], HELPER_PID: [NESTED_PID]},
    )

    assert codex_sessions.carrier_rollout_ids(
        pid=CARRIER_PID,
        fd_targets_of=cyclic["fd_targets_of"],
        children_of=cyclic["children_of"],
    ) == [INDEXED_ID]
    assert codex_sessions.carrier_rollout_ids(
        pid=CARRIER_PID,
        fd_targets_of=chain["fd_targets_of"],
        children_of=chain["children_of"],
        max_nodes=1,
    ) == [INDEXED_ID]


def test_the_helper_join_opens_the_index_and_never_a_rollout_body(*, tmp_path, monkeypatch):
    """A rollout is a full session transcript. The join needs the FILENAME and `/proc`,
    so it must open none of them — and the index read recorded alongside is the control
    proving the recorder was live rather than the absence being an artefact."""
    repo, _watch_set, session_name = watched_repo(tmp_path=tmp_path)
    home = index(
        tmp_path=tmp_path, records=[named(session_id=INDEXED_ID, thread_name=session_name)]
    )
    opened: list[str] = []
    real_open = Path.open

    def recording_open(self, *args, **kwargs):
        opened.append(str(self))
        return real_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", recording_open)
    live = codex_sessions.read_live_codex_sessions(
        codex_home=home,
        **fresh_0150_host(carrier_cwd=str(repo), helper_fds=[rollout(session_id=INDEXED_ID)]),
    )

    assert [s.session_id for s in live] == [INDEXED_ID]
    assert [path for path in opened if path.endswith("session_index.jsonl")] != []
    assert [path for path in opened if "rollout-" in path] == []
