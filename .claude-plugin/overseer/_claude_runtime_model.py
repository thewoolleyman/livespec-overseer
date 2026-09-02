"""Claude conversation-transcript runtime-model reader for launch-profile capture.

The launch profile records the model a track will be RE-ASSERTED with on restart.
Read from launch identity alone (`--model` in argv, else `ANTHROPIC_MODEL` in the
environ), that model reverts a mid-session ``/model`` switch to the LAUNCH model on
the daemon's ready-restart, because neither argv nor the environ is rewritten by the
switch. This module supplies the additional permitted source that closes that gap for
a Claude-harness track: the model TOKEN carried on the latest TOP-LEVEL assistant
message in the session's own conversation transcript.

Three properties of the source are load-bearing and each is pinned by a beside-test:

- **Top-level only.** A session mixes models across its main thread and its
  sub-agents (a real transcript held 190 ``claude-opus-4-8`` main-thread turns beside
  14 ``claude-fable-5-1`` sub-agent turns). A sub-agent message carries
  ``isSidechain: true``; those are EXCLUDED so the latest model is the model the
  operator is actually driving the track under, not whichever sub-agent ran last.
- **A real launch TOKEN, not a display name.** The transcript records
  ``message.model`` as ``claude-fable-5-1`` — the same token ``--model`` takes — so it
  satisfies the spec's prohibition on turning the statusline's rendered display name
  into a launch token. A ``<synthetic>`` (or otherwise empty / non-token) value is not
  a usable token and is skipped.
- **Fail-soft.** Any missing / unreadable / unparseable transcript, or one exposing no
  usable top-level model token, resolves to ``None`` so the caller falls back to the
  launch source exactly as before.

The transcript path is resolved from the session registry the daemon already reads:
``~/.claude/sessions/<pid>.json`` carries the ``sessionId`` and ``cwd``; the transcript
is ``~/.claude/projects/<cwd-with-every-slash-as-dash>/<sessionId>.jsonl``.

This is the CLAUDE reader only. The Codex reader (`codex_sessions.py`) must never read
a rollout body (a hard maintenance invariant), so Codex runtime-model capture is out of
scope here; the launch-profile caller gates this reader on the Claude harness.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import cast

import claude_sessions
import jsonio

__all__: list[str] = [
    "default_projects_dir",
    "latest_top_level_model",
    "read_runtime_model",
    "runtime_model_of",
]

# A model value the transcript records for a synthetic (non-model-call) assistant
# message — an interrupt notice and the like. It is not a launch token, so it never
# expresses the track's runtime model.
_SYNTHETIC_MODEL = "<synthetic>"


def default_projects_dir() -> Path:
    """``~/.claude/projects`` — where Claude Code writes each session's transcript."""
    return Path.home() / ".claude" / "projects"


def latest_top_level_model(*, lines: Iterable[str]) -> str | None:
    """The model token on the LATEST top-level (non-sidechain) assistant message.

    Sidechain / sub-agent messages are excluded, and a synthetic or empty ``model``
    value is not a usable token. Returns ``None`` when no usable token is present.
    Unparseable lines are skipped, so a byte-truncated tail line is harmless.
    """
    latest: str | None = None
    for line in lines:
        try:
            loaded = json.loads(line)
        except ValueError:
            continue
        record = jsonio.as_object(value=cast("object", loaded))
        if record is None:
            continue
        if record.get("type") != "assistant" or record.get("isSidechain"):
            continue
        message = jsonio.as_object(value=record.get("message"))
        if message is None:
            continue
        model = message.get("model")
        if not isinstance(model, str) or not model or model == _SYNTHETIC_MODEL:
            continue
        latest = model
    return latest


def _transcript_path(
    *,
    pid: int,
    sessions_dir: str | Path,
    projects_dir: str | Path,
) -> Path | None:
    session_file = Path(sessions_dir) / f"{pid}.json"
    try:
        raw = session_file.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        loaded = json.loads(raw)
    except ValueError:
        return None
    data = jsonio.as_object(value=cast("object", loaded))
    if data is None:
        return None
    session_id = data.get("sessionId")
    cwd = data.get("cwd")
    if not isinstance(session_id, str) or not session_id:
        return None
    if not isinstance(cwd, str) or not cwd:
        return None
    slug = cwd.replace("/", "-")
    return Path(projects_dir) / slug / f"{session_id}.jsonl"


def read_runtime_model(
    *,
    pid: int,
    sessions_dir: str | Path,
    projects_dir: str | Path,
) -> str | None:
    """Resolve pid → transcript → latest top-level model token, fail-soft to ``None``."""
    path = _transcript_path(pid=pid, sessions_dir=sessions_dir, projects_dir=projects_dir)
    if path is None:
        return None
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    return latest_top_level_model(lines=text.splitlines())


def runtime_model_of(*, pid: int) -> str | None:
    """Production seam binding: read the runtime model from the real host registry."""
    return read_runtime_model(
        pid=pid,
        sessions_dir=claude_sessions.default_sessions_dir(),
        projects_dir=default_projects_dir(),
    )
