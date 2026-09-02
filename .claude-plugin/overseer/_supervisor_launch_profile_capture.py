"""Live process launch-profile capture for restart planning."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from _seams import PidToOptionalBytes, PidToOptionalInt, PidToOptionalStr

__all__: list[str] = [
    "LaunchProfileProblem",
    "apply_runtime_model",
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


def _base_model(*, token: str) -> str:
    """A model token with any trailing bracketed variant suffix (e.g. ``[1m]``) removed.

    The transcript records the base token (``claude-opus-4-8``) where the launch argv
    carries a context-window variant (``claude-opus-4-8[1m]``), so the two are compared
    on their base to tell a genuine model change from the same model named without its
    variant.
    """
    return token.split("[", 1)[0]


def _preferred_model(*, runtime: str | None, launch: str | None) -> str | None:
    """Prefer the transcript token only when it names a DIFFERENT base model.

    Where the transcript names the same base model as the launch source, the launch
    token is retained so a context-window or other launch-token variant is never
    silently dropped by a source that does not carry it.
    """
    if runtime is None:
        return launch
    if launch is None:
        return runtime
    if _base_model(token=runtime) != _base_model(token=launch):
        return runtime
    return launch


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


def _closed_profile(
    *,
    harness: str,
    model: str,
    wrapper: str | None,
) -> dict[str, str | None]:
    return {"harness": harness, "model": model, "wrapper": wrapper}


def apply_runtime_model(
    *,
    profile: dict[str, str | None] | LaunchProfileProblem,
    harness: str,
    pid: int,
    runtime_model_of: PidToOptionalStr,
) -> dict[str, str | None] | LaunchProfileProblem:
    """Prefer the Claude transcript's runtime model over the captured launch model.

    For a Claude-harness track the session's conversation transcript is an additional
    permitted source for the model: its latest top-level assistant-message token is
    preferred over the launch model captured by :func:`read_launch_profile` when it
    names a DIFFERENT base model (a mid-session ``/model`` switch), and ignored when it
    names the same base model so a launch-token variant such as ``[1m]`` is retained.
    The transcript source is fail-soft, and this is a no-op for any other harness (a
    Codex rollout body is never read here) or for an errored profile.
    """
    if isinstance(profile, LaunchProfileProblem) or harness != "claude":
        return profile
    profile["model"] = _preferred_model(runtime=runtime_model_of(pid=pid), launch=profile["model"])
    return profile


def read_launch_profile(
    *,
    pid: int,
    harness: str,
    pane_pid: int | None,
    cmdline_of: PidToOptionalBytes,
    environ_of: PidToOptionalBytes,
    ppid_of: PidToOptionalInt,
) -> dict[str, str | None] | LaunchProfileProblem:
    """Read a live process's restart launch profile from ``/proc`` seams.

    This captures the LAUNCH model (``--model`` in argv, else ``ANTHROPIC_MODEL``). A
    Claude track's runtime model — the model it is actually running after a mid-session
    ``/model`` switch — is layered on by :func:`apply_runtime_model` at the capture
    call sites.
    """
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
    return _closed_profile(harness=harness, model=model, wrapper=wrapper)
