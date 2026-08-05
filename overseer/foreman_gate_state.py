"""Gate-state persistence and runtime-specific restoration adapters."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol

import registry

__all__: list[str] = [
    "GateState",
    "gate_state_path",
    "persist_gate_state",
    "restore_gate_state",
    "restore_navigation_keys",
]

STATE_FILE = ".foreman-gate-state.json"


class GateTmux(Protocol):
    def send_keys(self, *, session: str, keys: str) -> bool: ...

    def bracketed_paste(self, *, session: str, text: str) -> bool: ...


@dataclass(frozen=True, kw_only=True)
class GateState:
    runtime: str
    pane: str
    capture: str
    question_text: str
    question_fingerprint: str


def gate_state_path(*, repo: str | Path, topic: str) -> Path:
    return Path(repo) / "tmp" / "overseer" / topic / STATE_FILE


def persist_gate_state(*, repo: str | Path, topic: str, state: GateState) -> None:
    registry.atomic_write(
        path=gate_state_path(repo=repo, topic=topic),
        body=json.dumps(asdict(state), indent=2, sort_keys=True) + "\n",
    )


def restore_navigation_keys(*, runtime: str) -> tuple[str, ...]:
    if runtime == "codex":
        return ("Escape", "Escape")
    if runtime == "claude":
        return ("Escape",)
    return ()  # pragma: no cover


def restore_gate_state(*, tmux: GateTmux, target: str, state: GateState) -> bool:
    if state.runtime not in {"claude", "codex"}:  # pragma: no cover
        return False
    for key in restore_navigation_keys(runtime=state.runtime):
        if not tmux.send_keys(session=target, keys=key):  # pragma: no cover
            return False
    return tmux.bracketed_paste(session=target, text=state.question_text)
