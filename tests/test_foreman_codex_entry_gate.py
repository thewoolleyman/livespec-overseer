"""Repo-level mirror for live Codex identity admission through the foreman entry gate."""

from __future__ import annotations

import inspect
import json
from dataclasses import dataclass
from pathlib import Path

import codex_sessions
import foreman_runtime_identity

__all__: list[str] = []

FOREMAN_TOPIC = "repo-foreman"
CODEX_PID = 4242
OPEN_ROLLOUT_ID = "019f6a1e-266d-7fc2-8eb2-15ec9d324fb8"
OTHER_ID = "019f548d-6071-7893-9c2e-472cce81da02"


@dataclass(frozen=True, kw_only=True)
class FakeTmux:
    sessions: frozenset[str]

    def session_exists(self, *, session: str) -> bool:
        return session in self.sessions


def codex_evidence(*, tmp_path, named_id, cwd):
    """Codex evidence read through the established reader; the pid always holds
    OPEN_ROLLOUT_ID open, so naming a DIFFERENT id in the index makes it unindexed."""
    home = tmp_path / "codex"
    home.mkdir(exist_ok=True)
    record = {"id": named_id, "thread_name": FOREMAN_TOPIC, "updated_at": "2026-08-27T02:00:00Z"}
    (home / "session_index.jsonl").write_text(json.dumps(record) + "\n", encoding="utf-8")
    rollout = (
        f"/home/u/.codex/sessions/2026/08/27/rollout-2026-08-27T02-00-00-{OPEN_ROLLOUT_ID}.jsonl"
    )
    return codex_sessions.read_live_codex_sessions(
        codex_home=home,
        pids_of_comm=lambda *, comm: [CODEX_PID] if comm == "codex" else [],
        cwd_of=lambda *, pid: cwd if pid == CODEX_PID else None,
        fd_targets_of=lambda *, pid: [rollout] if pid == CODEX_PID else [],
    )


def test_a_live_codex_foreman_identity_enters_the_shared_gate_and_an_unindexed_one_refuses(
    *, tmp_path
):
    assert "codex_sessions" in inspect.signature(foreman_runtime_identity.entry_gate).parameters

    repo = tmp_path / "repo"
    (repo / "plan" / "alpha").mkdir(parents=True)
    watch_set = tmp_path / "repos.json"
    watch_set.write_text(json.dumps({"repos": [str(repo)]}) + "\n", encoding="utf-8")
    base = {
        "repo": repo,
        "cwd": repo,
        "watch_set_path": watch_set,
        "tmux": FakeTmux(sessions=frozenset({FOREMAN_TOPIC})),
        "sessions": [],
    }
    live = codex_evidence(tmp_path=tmp_path, named_id=OPEN_ROLLOUT_ID, cwd=str(repo))
    unindexed = codex_evidence(tmp_path=tmp_path, named_id=OTHER_ID, cwd=str(repo))

    admitted = foreman_runtime_identity.entry_gate(**base, codex_sessions=live)
    refused = foreman_runtime_identity.entry_gate(**base, codex_sessions=unindexed)

    assert [session.name for session in live] == [FOREMAN_TOPIC]
    assert unindexed == []
    assert admitted.ok is True
    assert admitted.session_name == FOREMAN_TOPIC
    assert refused.ok is False
    assert refused.reason == "runtime registry mismatch"


def test_the_shipped_foreman_runtime_facades_supply_codex_evidence_to_the_gate():
    root = Path(__file__).resolve().parent.parent
    facades = (
        root / "overseer" / "foreman-runtime",
        root / ".claude-plugin" / "bin" / "foreman-runtime",
    )

    for path in facades:
        source = path.read_text(encoding="utf-8")
        assert "codex_sessions.read_live_codex_sessions()" in source, path
        assert "codex_sessions=_real_codex_sessions()" in source, path
