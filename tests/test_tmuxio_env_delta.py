from __future__ import annotations

import os
import shlex
import stat
from pathlib import Path

from _supervisor_launch_profile import ClaudeLaunchPlan, CodexLaunchPlan
from test_tmuxio_fakes import io as _io

from overseer import _supervisor_launch, registry

__all__: list[str] = []


def _executable_wrapper(*, tmp_path: Path, name: str, target: str) -> Path:
    wrapper = tmp_path / name
    wrapper.write_text(f'#!/bin/sh\nexec {target} "$@"\n', encoding="utf-8")
    wrapper.chmod(wrapper.stat().st_mode | stat.S_IXUSR)
    return wrapper


def _rendered_respawn_command(*, command: str, env: registry.ModelProfile) -> str:
    io, fake = _io()
    assert io.respawn_pane(
        session="livespec:t",
        cwd="/data/projects/livespec",
        command=command,
        env=env,
    )
    return fake.calls[0]["argv"][-1]


def _assert_unsets_precede_assignments(*, command: str) -> None:
    words = shlex.split(command)
    assignment_index = next(index for index, word in enumerate(words) if "=" in word)
    unset_indexes = [index for index, word in enumerate(words) if word == "-u"]

    assert unset_indexes
    assert all(index < assignment_index for index in unset_indexes)


def _assert_rendered_env_executes(*, command: str) -> None:
    returncode, stdout = _exec_and_capture_stdout(argv=shlex.split(command))

    assert returncode == 0
    assert stdout == "overseer-env-ok\n"


def _exec_and_capture_stdout(*, argv: list[str]) -> tuple[int, str]:
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


def test_claude_wrapper_plan_env_delta_is_valid_for_gnu_env(*, tmp_path: Path) -> None:
    wrapper = _executable_wrapper(tmp_path=tmp_path, name="claude-local-llm", target="claude")
    track = registry.Track(
        topic="t",
        repo="/data/projects/livespec",
        model_profile={
            "harness": "claude",
            "model": "macmini/qwen3-coder-next",
            "wrapper": str(wrapper),
        },
    )
    plan = _supervisor_launch.claude_launch_plan(track=track)

    assert isinstance(plan, ClaudeLaunchPlan)
    command = _rendered_respawn_command(command="/bin/echo overseer-env-ok", env=plan.env)

    _assert_unsets_precede_assignments(command=command)
    _assert_rendered_env_executes(command=command)


def test_codex_wrapper_plan_env_delta_is_valid_for_gnu_env(*, tmp_path: Path) -> None:
    wrapper = _executable_wrapper(tmp_path=tmp_path, name="codex-local-llm", target="codex")
    track = registry.Track(
        topic="t",
        repo="/data/projects/livespec",
        model_profile={
            "harness": "codex",
            "model": "macmini/qwen3-coder-next",
            "wrapper": str(wrapper),
        },
    )
    plan = _supervisor_launch.codex_launch_plan(
        track=track,
        session_id="019f6a1e-266d-7fc2-8eb2-15ec9d324fb8",
        resume="read first",
    )

    assert isinstance(plan, CodexLaunchPlan)
    assert plan.env is not None
    command = _rendered_respawn_command(command="/bin/echo overseer-env-ok", env=plan.env)

    _assert_unsets_precede_assignments(command=command)
    _assert_rendered_env_executes(command=command)


def test_claude_cloud_plan_env_delta_remains_all_unset(*, tmp_path: Path) -> None:
    track = registry.Track(
        topic="t",
        repo="/data/projects/livespec",
        model_profile={
            "harness": "claude",
            "model": "claude-opus-4-1-20250805",
            "wrapper": None,
        },
    )
    plan = _supervisor_launch.claude_launch_plan(track=track)

    assert isinstance(plan, ClaudeLaunchPlan)
    command = _rendered_respawn_command(command="claude -n t", env=plan.env)

    assert command == (
        "env -u ANTHROPIC_MODEL -u ANTHROPIC_SMALL_FAST_MODEL "
        "-u CLAUDE_CODE_DISABLE_1M_CONTEXT -u CLAUDE_CODE_MAX_CONTEXT_TOKENS claude -n t"
    )
