"""Repo-level mirror for live Pi identity admission through the foreman entry gate."""

from __future__ import annotations

import json
from dataclasses import dataclass, fields
from pathlib import Path

import foreman_runtime_identity
import pi_sessions

__all__: list[str] = []

FOREMAN_TOPIC = "repo-foreman"
PI_SESSION_ID = "01M10KJ85RX22SN2Z3P5XZVJ1F-pi"
TRANSCRIPT_SENTINEL = "sk-ant-oat0-NEVER-DECODE-ME"


@dataclass(frozen=True, kw_only=True)
class FakeTmux:
    sessions: frozenset[str]

    def session_exists(self, *, session: str) -> bool:
        return session in self.sessions


def pi_evidence(*, tmp_path, cwd, name, session_id=PI_SESSION_ID, markers=True, file_name):
    """Pi evidence read through the established reader, from a real session file.

    The file always carries transcript records around the metadata, so the positive
    control is also a control that a conversation sitting between the header and the
    session_info neither breaks the join nor leaks into it.
    """
    path = tmp_path / file_name
    records = [
        {"type": pi_sessions.SESSION_HEADER_TYPE, "id": PI_SESSION_ID, "cwd": cwd},
        {"type": "message", "role": "assistant", "content": TRANSCRIPT_SENTINEL},
        {"type": "tool_result", "tool_use_id": "t1", "content": TRANSCRIPT_SENTINEL},
        {"type": "compaction", "summary": TRANSCRIPT_SENTINEL},
        {"type": pi_sessions.SESSION_INFO_TYPE, "name": name},
    ]
    path.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")
    env = {
        pi_sessions.PI_SESSION_ID_ENV: session_id,
        pi_sessions.PI_SESSION_FILE_ENV: str(path),
    }
    if markers:
        env[pi_sessions.AI_AGENT_ENV] = pi_sessions.PI_AGENT
        env[pi_sessions.PI_CODING_AGENT_ENV] = pi_sessions.PI_CODING_AGENT_TRUE
    return pi_sessions.read_live_pi_sessions(env=env)


def test_a_live_pi_foreman_identity_enters_the_shared_gate_and_its_controls_refuse(*, tmp_path):
    repo = tmp_path / "repo"
    (repo / "plan" / "alpha").mkdir(parents=True)
    other = tmp_path / "other"
    (other / "plan" / "alpha").mkdir(parents=True)
    watch_set = tmp_path / "repos.json"
    watch_set.write_text(json.dumps({"repos": [str(repo)]}) + "\n", encoding="utf-8")
    base = {
        "repo": repo,
        "cwd": repo,
        "watch_set_path": watch_set,
        "tmux": FakeTmux(sessions=frozenset({FOREMAN_TOPIC})),
    }
    live = pi_evidence(tmp_path=tmp_path, cwd=str(repo), name=FOREMAN_TOPIC, file_name="a.jsonl")
    misnamed = pi_evidence(tmp_path=tmp_path, cwd=str(repo), name="foreman", file_name="b.jsonl")
    elsewhere = pi_evidence(
        tmp_path=tmp_path, cwd=str(other), name=FOREMAN_TOPIC, file_name="c.jsonl"
    )
    unmarked = pi_evidence(
        tmp_path=tmp_path, cwd=str(repo), name=FOREMAN_TOPIC, markers=False, file_name="d.jsonl"
    )
    mismatched_id = pi_evidence(
        tmp_path=tmp_path,
        cwd=str(repo),
        name=FOREMAN_TOPIC,
        session_id="a-different-session",
        file_name="e.jsonl",
    )

    assert [session.name for session in live] == [FOREMAN_TOPIC]
    assert not any(TRANSCRIPT_SENTINEL in repr(session) for session in live)
    assert unmarked == []
    assert mismatched_id == []
    assert "pi_sessions" in {
        field.name for field in fields(foreman_runtime_identity.RuntimeEvidence)
    }

    evidence = foreman_runtime_identity.RuntimeEvidence
    admitted = foreman_runtime_identity.entry_gate(**base, evidence=evidence(pi_sessions=live))

    assert admitted.ok is True
    assert admitted.session_name == FOREMAN_TOPIC
    for found in (misnamed, elsewhere, unmarked, mismatched_id):
        refused = foreman_runtime_identity.entry_gate(**base, evidence=evidence(pi_sessions=found))
        assert refused.ok is False
        assert refused.reason == "runtime registry mismatch"


def test_the_shipped_foreman_runtime_facades_supply_pi_evidence_to_the_gate():
    root = Path(__file__).resolve().parent.parent
    facades = (
        root / "overseer" / "foreman-runtime",
        root / ".claude-plugin" / "bin" / "foreman-runtime",
    )

    for path in facades:
        source = path.read_text(encoding="utf-8")
        assert "pi_sessions.read_live_pi_sessions()" in source, path
        assert "pi_sessions=_real_pi_sessions()" in source, path
