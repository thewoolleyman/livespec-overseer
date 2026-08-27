"""Beside-tests for the shared foreman entry gate's live-runtime identity aggregation.

The gate accepted Claude registry evidence ONLY, so a correctly named live Codex
foreman session sitting in the exact repository refused with `runtime registry
mismatch` — the observed failure recorded in
`plan/foreman-codex-pi-runtime-support/research/001-codex-and-pi-entry-gate-baseline.md`.

Every Codex control here is built through `codex_sessions.read_live_codex_sessions`
rather than by hand-rolling a `CodexSession`. That is the point of the controls, not
an incidental style: the unindexed and dead-process refusals are properties of the
established reader, so constructing the evidence directly would assert them of a test
double instead of of the code the gate actually consumes. The reader's own /proc and
`~/.codex` couplings stay injected, so these run with no codex process on the host.
"""

from __future__ import annotations

import inspect
import json
from dataclasses import dataclass

import codex_sessions
import foreman_runtime_identity
from _claude_sessions_registry import ClaudeSession
from test_codex_sessions_fakes import ID_A, ID_B, fake_host, fake_index, fake_rollout

__all__: list[str] = []

FOREMAN_TOPIC = "repo-foreman"
CODEX_PID = 4242


@dataclass(frozen=True, kw_only=True)
class FakeTmux:
    sessions: frozenset[str]

    def session_exists(self, *, session: str) -> bool:
        return session in self.sessions


def make_repo(*, tmp_path, name="repo"):
    repo = tmp_path / name
    (repo / "plan" / "alpha").mkdir(parents=True)
    return repo


def write_watch_set(*, path, repos):
    path.write_text(json.dumps({"repos": [str(repo) for repo in repos]}) + "\n", encoding="utf-8")


def claude_session(*, repo, name=FOREMAN_TOPIC):
    return ClaudeSession(pid=123, name=name, cwd=str(repo), status="idle", proc_start="9")


def codex_evidence(*, tmp_path, records, cwds, fds, comms=None):
    """Codex identity evidence, read through the established live-session reader."""
    home = fake_index(tmp_path=tmp_path, records=records)
    host = fake_host(comms=comms if comms is not None else {CODEX_PID: "codex"}, cwds=cwds, fds=fds)
    return codex_sessions.read_live_codex_sessions(codex_home=home, **host)


def live_codex_evidence(*, tmp_path, repo, name=FOREMAN_TOPIC):
    return codex_evidence(
        tmp_path=tmp_path,
        records=[(ID_A, name)],
        cwds={CODEX_PID: str(repo)},
        fds={CODEX_PID: [fake_rollout(session_id=ID_A)]},
    )


def gate_base(*, repo, tmp_path):
    watch_set = tmp_path / "repos.json"
    write_watch_set(path=watch_set, repos=[repo])
    return {
        "repo": repo,
        "cwd": repo,
        "watch_set_path": watch_set,
        "tmux": FakeTmux(sessions=frozenset({FOREMAN_TOPIC})),
    }


def test_entry_gate_admits_a_live_codex_identity_alongside_the_claude_positive_path(*, tmp_path):
    """Both runtimes satisfy the SAME gate; neither is a special case of the other."""
    assert "codex_sessions" in inspect.signature(foreman_runtime_identity.entry_gate).parameters

    repo = make_repo(tmp_path=tmp_path)
    base = gate_base(repo=repo, tmp_path=tmp_path)
    codex = live_codex_evidence(tmp_path=tmp_path, repo=repo)
    assert [(session.name, session.cwd) for session in codex] == [(FOREMAN_TOPIC, str(repo))]

    claude_only = foreman_runtime_identity.entry_gate(
        **base, sessions=[claude_session(repo=repo)], codex_sessions=[]
    )
    codex_only = foreman_runtime_identity.entry_gate(**base, sessions=[], codex_sessions=codex)
    both = foreman_runtime_identity.entry_gate(
        **base, sessions=[claude_session(repo=repo)], codex_sessions=codex
    )

    assert claude_only.ok is True
    assert codex_only.ok is True
    assert both.ok is True
    assert codex_only.session_name == FOREMAN_TOPIC


def test_unindexed_codex_evidence_refuses_fail_closed(*, tmp_path):
    """An unnamed session carries no topic anywhere, so the reader never yields it."""
    repo = make_repo(tmp_path=tmp_path)
    base = gate_base(repo=repo, tmp_path=tmp_path)
    unindexed = codex_evidence(
        tmp_path=tmp_path,
        records=[(ID_B, FOREMAN_TOPIC)],
        cwds={CODEX_PID: str(repo)},
        fds={CODEX_PID: [fake_rollout(session_id=ID_A)]},
    )

    assert unindexed == []
    result = foreman_runtime_identity.entry_gate(**base, sessions=[], codex_sessions=unindexed)
    assert result.ok is False
    assert result.reason == "runtime registry mismatch"


def test_wrong_name_codex_evidence_refuses_fail_closed(*, tmp_path):
    """The exact canonical name check is preserved — a near-miss topic is not a foreman."""
    repo = make_repo(tmp_path=tmp_path)
    base = gate_base(repo=repo, tmp_path=tmp_path)
    misnamed = live_codex_evidence(tmp_path=tmp_path, repo=repo, name="foreman")

    assert [session.name for session in misnamed] == ["foreman"]
    result = foreman_runtime_identity.entry_gate(**base, sessions=[], codex_sessions=misnamed)
    assert result.ok is False
    assert result.reason == "runtime registry mismatch"


def test_wrong_cwd_codex_evidence_refuses_fail_closed(*, tmp_path):
    """The exact repository check is preserved — a correctly named session elsewhere refuses."""
    repo = make_repo(tmp_path=tmp_path)
    other = make_repo(tmp_path=tmp_path, name="other")
    base = gate_base(repo=repo, tmp_path=tmp_path)
    elsewhere = live_codex_evidence(tmp_path=tmp_path, repo=other)

    assert [session.cwd for session in elsewhere] == [str(other)]
    result = foreman_runtime_identity.entry_gate(**base, sessions=[], codex_sessions=elsewhere)
    assert result.ok is False
    assert result.reason == "runtime registry mismatch"


def test_absent_and_dead_codex_evidence_refuse_fail_closed(*, tmp_path):
    """No codex process at all, and a pid that vanished mid-read, both yield no evidence."""
    repo = make_repo(tmp_path=tmp_path)
    base = gate_base(repo=repo, tmp_path=tmp_path)
    absent = codex_evidence(
        tmp_path=tmp_path, records=[(ID_A, FOREMAN_TOPIC)], cwds={}, fds={}, comms={}
    )
    dead = codex_evidence(
        tmp_path=tmp_path,
        records=[(ID_A, FOREMAN_TOPIC)],
        cwds={},
        fds={CODEX_PID: [fake_rollout(session_id=ID_A)]},
    )

    assert absent == []
    assert dead == []
    for evidence in (absent, dead):
        result = foreman_runtime_identity.entry_gate(**base, sessions=[], codex_sessions=evidence)
        assert result.ok is False
        assert result.reason == "runtime registry mismatch"


def test_claude_behaviour_is_unchanged_when_no_codex_evidence_is_supplied(*, tmp_path):
    """The Codex evidence parameter defaults to empty, so every Claude leg is untouched."""
    repo = make_repo(tmp_path=tmp_path)
    other = make_repo(tmp_path=tmp_path, name="other")
    base = gate_base(repo=repo, tmp_path=tmp_path)
    claude = [claude_session(repo=repo)]

    assert foreman_runtime_identity.entry_gate(**base, sessions=claude).ok is True
    assert (
        foreman_runtime_identity.entry_gate(**{**base, "cwd": other}, sessions=claude).ok is False
    )
    unwatched = foreman_runtime_identity.entry_gate(
        **{**base, "watch_set_path": tmp_path / "missing.json"}, sessions=claude
    )
    assert unwatched.ok is False
    no_tmux = foreman_runtime_identity.entry_gate(
        **{**base, "tmux": FakeTmux(sessions=frozenset())}, sessions=claude
    )
    assert no_tmux.ok is False
    misnamed = foreman_runtime_identity.entry_gate(
        **base, sessions=[claude_session(repo=repo, name="foreman")]
    )
    assert misnamed.reason == "runtime registry mismatch"
    assert foreman_runtime_identity.entry_gate(**base, sessions=[]).ok is False
