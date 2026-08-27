"""Shared builders for the Pi active-session reader's beside-tests.

The twin of :mod:`test_codex_sessions_fakes`, and it exists for the same reason:
both Pi test modules need the same session-file and environment shapes, and a
second copy of them would be a second thing to keep true.

:class:`RecordingParse` is the load-bearing one. The reader's transcript-safety
promise is about what it READS, and a returned identity can only ever show what
came OUT — so every control drives the reader through a decoder that remembers
the lines it was handed, and asserts on those.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import jsonio
import pi_sessions

__all__: list[str] = []

SESSION_ID = "01M0PP1ZF673-pi-session"
FOREMAN_TOPIC = "repo-foreman"
REPO = "/data/projects/repo"
SECRET = "sk-ant-oat0-NEVER-DECODE-ME"


@dataclass(kw_only=True)
class RecordingParse:
    """The injected JSON decode, remembering every line it was asked to decode."""

    lines: list[str] = field(default_factory=list)

    def __call__(self, *, line: str) -> jsonio.JsonObjectParse:
        self.lines.append(line)
        return jsonio.parse_object_line(line=line)


def pi_env(*, session_file, session_id=SESSION_ID, **overrides):
    """The environment a Pi built-in tool injects; an override of None drops the key."""
    env = {
        pi_sessions.AI_AGENT_ENV: pi_sessions.PI_AGENT,
        pi_sessions.PI_CODING_AGENT_ENV: pi_sessions.PI_CODING_AGENT_TRUE,
        pi_sessions.PI_SESSION_ID_ENV: session_id,
        pi_sessions.PI_SESSION_FILE_ENV: str(session_file),
    }
    env.update(overrides)
    return {key: value for key, value in env.items() if value is not None}


def header(*, session_id=SESSION_ID, cwd=REPO):
    return {"type": pi_sessions.SESSION_HEADER_TYPE, "id": session_id, "cwd": cwd}


def session_info(*, name=FOREMAN_TOPIC):
    return {"type": pi_sessions.SESSION_INFO_TYPE, "name": name}


def transcript_records():
    """The record shapes that carry conversation content, with a sentinel inside."""
    return [
        {"type": "message", "role": "assistant", "content": SECRET},
        {"type": "tool_result", "tool_use_id": "t1", "content": SECRET},
        {"type": "compaction", "summary": SECRET},
        {"type": "reasoning", "text": SECRET},
    ]


def write_session_file(*, tmp_path, records, name="session.jsonl"):
    path = tmp_path / name
    path.write_text(
        "".join(json.dumps(record) + "\n" for record in records),
        encoding="utf-8",
    )
    return path


def read(*, env, **overrides):
    """Drive the reader with a recording decoder; returns ``(sessions, parse)``."""
    parse = RecordingParse()
    sessions = pi_sessions.read_live_pi_sessions(env=env, parse=parse, **overrides)
    return sessions, parse


def valid_records():
    """A well-formed session file: header, a conversation, then the current name."""
    return [header(), *transcript_records(), session_info()]
