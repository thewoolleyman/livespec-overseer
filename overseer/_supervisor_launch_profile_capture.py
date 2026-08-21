"""Live process launch-profile capture for restart planning."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from _seams import PidToOptionalBytes, PidToOptionalInt

__all__: list[str] = [
    "LaunchProfileProblem",
    "read_launch_profile",
]


@dataclass(frozen=True, kw_only=True)
class LaunchProfileProblem:
    message: str


_SHELL_BASENAMES = frozenset({"sh", "bash", "zsh", "dash", "fish", "ksh", "tcsh", "csh"})
_WRAPPER_ENV_KEY = "LIVESPEC_LOCAL_LLM_WRAPPER"


def _split_nul_bytes(*, data: bytes | None) -> list[str]:
    if data is None:
        return []
    return [part.decode(errors="replace") for part in data.split(b"\0") if part]


def _env_from_bytes(*, data: bytes | None) -> dict[str, str]:
    env: dict[str, str] = {}
    for item in _split_nul_bytes(data=data):
        key, sep, value = item.partition("=")
        if sep:
            env[key] = value
    return env


def _model_from_argv(*, argv: list[str]) -> str | None:
    for index, value in enumerate(argv):
        if value == "--model" and index + 1 < len(argv):
            return argv[index + 1]
        if value == "-m" and index + 1 < len(argv):
            return argv[index + 1]
        if value.startswith("--model="):
            return value.partition("=")[2]
    return None


def _non_anthropic_base_url(*, base_url: str | None) -> bool:
    if not base_url:
        return False
    return "anthropic.com" not in base_url.lower()


def _wrapper_from_parent_chain(
    *,
    pid: int,
    pane_pid: int | None,
    ppid_of: PidToOptionalInt,
    cmdline_of: PidToOptionalBytes,
) -> str | None:
    current = pid
    seen: set[int] = set()
    for _ in range(64):
        parent = ppid_of(pid=current)
        if parent is None or parent <= 0 or parent == pane_pid or parent in seen:
            return None
        seen.add(parent)
        argv = _split_nul_bytes(data=cmdline_of(pid=parent))
        if argv and Path(argv[0]).name not in _SHELL_BASENAMES:
            return argv[0]
        current = parent
    return None


def _wrapper_from_local_router(
    *,
    env: Mapping[str, str],
    pid: int,
    pane_pid: int | None,
    ppid_of: PidToOptionalInt,
    cmdline_of: PidToOptionalBytes,
) -> str | None:
    wrapper = env.get(_WRAPPER_ENV_KEY)
    if wrapper:
        return wrapper
    return _wrapper_from_parent_chain(
        pid=pid,
        pane_pid=pane_pid,
        ppid_of=ppid_of,
        cmdline_of=cmdline_of,
    )


def read_launch_profile(
    *,
    pid: int,
    harness: str,
    pane_pid: int | None,
    cmdline_of: PidToOptionalBytes,
    environ_of: PidToOptionalBytes,
    ppid_of: PidToOptionalInt,
) -> dict[str, str | None] | LaunchProfileProblem:
    """Read a live process's restart launch profile from ``/proc`` seams."""
    argv = _split_nul_bytes(data=cmdline_of(pid=pid))
    env = _env_from_bytes(data=environ_of(pid=pid))
    model = _model_from_argv(argv=argv) or env.get("ANTHROPIC_MODEL")
    if not model:
        return LaunchProfileProblem(message=f"launch profile for pid {pid} has no model token")
    wrapper = (
        _wrapper_from_local_router(
            env=env,
            pid=pid,
            pane_pid=pane_pid,
            ppid_of=ppid_of,
            cmdline_of=cmdline_of,
        )
        if _non_anthropic_base_url(base_url=env.get("ANTHROPIC_BASE_URL"))
        else None
    )
    return {"harness": harness, "model": model, "wrapper": wrapper}
