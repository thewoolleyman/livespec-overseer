"""Bind and revalidate ready-round authority for a Herdr replacement."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

import _herdr_replacement_process
import herdr_identity
import registry
import signals
from _supervisor_launch_profile import ClaudeLaunchPlan, CodexLaunchPlan

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = [
    "DEFAULT_BINDING",
    "ReplacementBinding",
    "bind_authorization",
    "round_still_authorizes",
]


@dataclass(frozen=True, kw_only=True)
class ReplacementBinding:
    runtime: str = "claude"
    predecessor_identity: str | None = None
    predecessor_rollout: str | None = None
    resume: str | None = None


DEFAULT_BINDING = ReplacementBinding()


def bind_authorization(
    *,
    sup: Supervisor,
    track: registry.Track,
    target: str,
    launch: ClaudeLaunchPlan | CodexLaunchPlan,
    snapshot: _herdr_replacement_process.ReplacementSnapshot,
    binding: ReplacementBinding = DEFAULT_BINDING,
) -> tuple[dict[str, object] | None, str]:
    """Capture the exact round, backend, process identities, and launch profile."""
    decoded = herdr_identity.decode_target(value=target)
    server = cast(herdr_identity.HerdrPaneTarget, decoded.herdr)
    round_record = registry.read_round_record(
        repo=track.repo,
        topic=track.topic,
        stamp_path=sup.stamp_path,
    )
    declared = signals.read_state(repo=track.repo, topic=track.topic)
    identity = binding.predecessor_identity or cast(str, round_record.session_identity)
    predecessor = _herdr_replacement_process.predecessor(snapshot=snapshot, identity=identity)
    if declared is None:
        return None, "ready declaration changed before durable binding"
    if predecessor is None:
        return None, "predecessor process identity was reused or disappeared"
    if snapshot.shell.pid == predecessor.pid:
        return None, "root shell was exec-replaced by the predecessor"
    transaction: dict[str, object] = {
        "version": 1,
        "phase": "before-stop",
        "target": target,
        "server": {
            "socket_path": server.socket_path,
            "pid": server.server_pid,
            "starttime": server.server_starttime,
            "pane_id": server.pane_id,
        },
        "runtime": binding.runtime,
        "predecessor": {
            "pid": predecessor.pid,
            "starttime": predecessor.starttime,
            "process_group": snapshot.foreground_group,
        },
        "shell": _herdr_replacement_process.process_record(process=snapshot.shell),
        "round": {
            "ready_mtime": declared.mtime,
            "round_at": round_record.at,
            "session_identity": identity,
        },
        "launch": {
            "command": launch.command,
            "cwd": track.repo,
            "env": {} if launch.env is None else dict(launch.env),
        },
    }
    if binding.predecessor_rollout is not None:
        transaction["predecessor_rollout"] = binding.predecessor_rollout
    if binding.resume is not None:
        transaction["resume"] = binding.resume
    return transaction, ""


def round_still_authorizes(
    *, sup: Supervisor, track: registry.Track, transaction: dict[str, object]
) -> bool:
    """Compare the live declaration and certified round with the durable binding."""
    declared = signals.read_state(repo=track.repo, topic=track.topic)
    current = registry.read_round_record(
        repo=track.repo,
        topic=track.topic,
        stamp_path=sup.stamp_path,
    )
    recorded = cast(dict[str, object], transaction["round"])
    return all(
        (
            declared is not None,
            None if declared is None else declared.mtime == recorded["ready_mtime"],
            current.at == recorded["round_at"],
            current.session_identity == recorded["session_identity"],
        )
    )
