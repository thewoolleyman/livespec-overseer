"""The recorded model must survive into the PROCESS a Codex wrapper relaunch starts.

The Claude wrapper arm preserves the model through ``ANTHROPIC_MODEL`` because
``claude-local-llm`` DEFERS to an inherited value
(``export ANTHROPIC_MODEL="${ANTHROPIC_MODEL:-$CLAUDE_LOCAL_MODEL}"``) — the
deference IS the mechanism. ``codex-local-llm`` has no such deference: it
``exec``s ``codex -c model_provider=local-llm-fleet "$@"`` and never mentions
``ANTHROPIC_MODEL`` at all, leaving Codex's own model picker in charge. So on
that arm the environment carries the recorded model to a consumer that ignores
it, and the model is silently dropped while the PROVIDER is preserved.

This test is pinned at the level the defect lives at. It EXECUTES the rendered
relaunch command through a wrapper that mirrors the real one's forwarding shape,
into a ``codex`` stub that resolves its model the way Codex does — from ``-m``,
never from the environment — and asserts on the model the stub actually runs
under. Proving only that the rendered command executes passes while the model is
dropped, which is exactly how this went unnoticed: the fabrication had moved out
of the process shape and into the env, where the existing env-delta test could
not see it.
"""

from __future__ import annotations

import os
import shlex
import stat
from pathlib import Path

import pytest
from _supervisor_launch_profile import CodexLaunchPlan
from tmuxio_env import with_env_delta

from overseer import _supervisor_launch, registry

__all__: list[str] = []

_RECORDED_MODEL = "macmini/qwen3-coder-next"
_SESSION_ID = "019f6a1e-266d-7fc2-8eb2-15ec9d324fb8"

# The stub stands in for the REAL consumer, so it must resolve its model the way
# Codex does and no other way: from `-m`, with the environment out of scope. A
# stub that also honoured ANTHROPIC_MODEL would make this test pass against the
# very fabrication it exists to catch.
_CODEX_STUB = """#!/bin/sh
model='<no-model-flag>'
while [ "$#" -gt 0 ]; do
    if [ "$1" = '-m' ]; then
        shift
        model="$1"
    fi
    shift
done
printf '%s\\n' "$model"
"""

# Mirrors `codex-local-llm`: pin the provider, forward everything else through
# `"$@"`, and read nothing from the environment.
_CODEX_WRAPPER = """#!/bin/sh
exec codex -c model_provider=local-llm-fleet "$@"
"""


def _executable(*, path: Path, body: str) -> Path:
    path.write_text(body, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


def _run_and_capture_stdout(*, argv: list[str]) -> tuple[int, str]:
    read_fd, write_fd = os.pipe()
    file_actions = [
        (os.POSIX_SPAWN_DUP2, write_fd, 1),
        (os.POSIX_SPAWN_CLOSE, read_fd),
        (os.POSIX_SPAWN_CLOSE, write_fd),
    ]
    pid = os.posix_spawnp(argv[0], argv, os.environ, file_actions=file_actions)
    os.close(write_fd)
    chunks: list[bytes] = []
    while True:
        chunk = os.read(read_fd, 4096)
        if not chunk:
            break
        chunks.append(chunk)
    os.close(read_fd)
    _, status = os.waitpid(pid, 0)
    stdout = b"".join(chunks).decode(encoding="utf-8")
    if os.WIFEXITED(status):
        return os.WEXITSTATUS(status), stdout
    return 128, stdout


def test_codex_wrapper_relaunch_starts_the_process_under_the_recorded_model(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    stub_dir = tmp_path / "bin"
    stub_dir.mkdir()
    _executable(path=stub_dir / "codex", body=_CODEX_STUB)
    wrapper = _executable(path=tmp_path / "codex-local-llm", body=_CODEX_WRAPPER)
    monkeypatch.setenv("PATH", os.pathsep.join([str(stub_dir), os.environ["PATH"]]))
    track = registry.Track(
        topic="t",
        repo="/data/projects/livespec",
        model_profile={
            "harness": "codex",
            "model": _RECORDED_MODEL,
            "wrapper": str(wrapper),
        },
    )

    plan = _supervisor_launch.codex_launch_plan(
        track=track,
        session_id=_SESSION_ID,
        resume="read first",
    )

    assert isinstance(plan, CodexLaunchPlan)
    rendered = with_env_delta(command=plan.command, env=plan.env)
    returncode, stdout = _run_and_capture_stdout(argv=shlex.split(rendered))

    assert returncode == 0
    assert stdout == f"{_RECORDED_MODEL}\n"
