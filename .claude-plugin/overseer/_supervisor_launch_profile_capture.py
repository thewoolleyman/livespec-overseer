"""Live process launch-profile capture for restart planning."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from _seams import PidToOptionalBytes, PidToOptionalInt, PidToOptionalStr
from _supervisor_launch_profile_sources import CodexModelSource

__all__: list[str] = [
    "LaunchProfileProblem",
    "complete_launch_profile",
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
    """Prefer the runtime token only when it names a DIFFERENT base model.

    Where the runtime source names the same base model as the launch source, the launch
    token is retained so a context-window or other launch-token variant is never
    silently dropped by a source that does not carry it. One rule, applied to both
    permitted runtime sources: the Claude transcript and the Codex state database.
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


def _candidate_profile(
    *,
    harness: str,
    model: str | None,
    wrapper: str | None,
) -> dict[str, str | None]:
    """A profile CANDIDATE: the harness and wrapper facts, with a possibly-absent model.

    The model is the only half that can still be supplied by another source, so it is the
    only half allowed to arrive absent. Harness and wrapper are read from the proven live
    process and are final by the time this is built.
    """
    return {"harness": harness, "model": model, "wrapper": wrapper}


def _codex_state_model(*, codex_identity: CodexModelSource | None) -> str | None:
    """The Codex state database's token for an established identity, else ``None``.

    ``None`` for every track with no single established live Codex session identity —
    the specification's unusable case — which is exactly when :func:`codex_model_source`
    declines to build one.
    """
    if codex_identity is None:
        return None
    return codex_identity.read(
        codex_home=codex_identity.codex_home,
        session_id=codex_identity.session_id,
        cwd=codex_identity.cwd,
    )


def _runtime_model(
    *,
    harness: str,
    pid: int,
    runtime_model_of: PidToOptionalStr,
    codex_identity: CodexModelSource | None,
) -> str | None:
    """The ONE additional model source this harness permits, or ``None``."""
    if harness == "claude":
        return runtime_model_of(pid=pid)
    if harness == "codex":
        return _codex_state_model(codex_identity=codex_identity)
    return None


def complete_launch_profile(
    *,
    profile: dict[str, str | None],
    harness: str,
    pid: int,
    runtime_model_of: PidToOptionalStr,
    codex_identity: CodexModelSource | None = None,
) -> dict[str, str | None] | LaunchProfileProblem:
    """Close a candidate against the harness's runtime model, or reject it as unusable.

    Each harness has exactly ONE additional permitted source, and they do not cross. For
    a CLAUDE track it is the session's conversation transcript (its latest top-level
    assistant-message token); for a CODEX track it is ``threads.model`` in the live
    session's own Codex state database, read for the exact established session identity
    — never a rollout body, which is never opened. Either token is preferred over the
    launch model when it names a DIFFERENT base model (a mid-session model change), and
    ignored when it names the same base model so a launch-token variant such as ``[1m]``
    is retained. Both sources are fail-soft, and any other harness has no second source
    at all.

    **The rejection lives HERE, after the second source has spoken, and that placement is
    the whole point (`overseer-phz7te`).** It used to live in :func:`read_launch_profile`,
    which refused the moment argv and the environ carried no model token — so a process
    launched BARE was declared unreadable before the runtime source it was entitled to
    was ever consulted. Measured live 2026-09-12: a bare Codex carrier with a perfectly
    usable exact-identity ``threads.model`` row emitted ``has no model token``, the
    track's stale Claude profile was therefore never replaced, and 95 consecutive restart
    attempts refused because harness ``claude`` cannot relaunch a Codex pane. A candidate
    is only unusable once BOTH sources have failed to name a model.
    """
    model = _preferred_model(
        runtime=_runtime_model(
            harness=harness,
            pid=pid,
            runtime_model_of=runtime_model_of,
            codex_identity=codex_identity,
        ),
        launch=profile["model"],
    )
    if model is None:
        return LaunchProfileProblem(
            message=(
                f"launch profile for pid {pid} has no usable model token: neither the "
                f"{harness} launch argv/environment nor its permitted runtime model "
                "source named one"
            )
        )
    return {**profile, "model": model}


def read_launch_profile(
    *,
    pid: int,
    harness: str,
    pane_pid: int | None,
    cmdline_of: PidToOptionalBytes,
    environ_of: PidToOptionalBytes,
    ppid_of: PidToOptionalInt,
) -> dict[str, str | None]:
    """Assemble a launch-profile CANDIDATE for a live process from ``/proc`` seams.

    This captures the harness and wrapper facts in full, plus the LAUNCH model
    (``--model`` in argv, else ``ANTHROPIC_MODEL``). A process launched BARE names no
    launch model, which is not an error here: the runtime model — the model the session
    is actually running after a mid-session ``/model`` switch, and the only model a bare
    launch ever had — is layered on by :func:`complete_launch_profile`, which is also
    where a candidate neither source could complete is rejected.
    """
    argv = _split_nul_bytes(data=cmdline_of(pid=pid))
    env = _env_from_bytes(data=environ_of(pid=pid))
    model = _model_from_argv(argv=argv) or env.get("ANTHROPIC_MODEL") or None
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
    return _candidate_profile(harness=harness, model=model, wrapper=wrapper)
