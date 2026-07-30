"""Realization-aware checks for generated supervisor prompt fixtures."""

from __future__ import annotations

import re

__all__: list[str] = [
    "banned_requirements",
    "missing_requirements",
    "non_parameterizable_requirements",
]

_ACTING_DAEMON_OVERRIDE = re.compile(
    r"\b(?:may|can|allowed|okay|ok)\b[^\n.]{0,120}\b(?:kill|restart)\b"
    r"[^\n.]{0,120}\bacting overseer daemon\b"
    r"|\bacting overseer daemon\b[^\n.]{0,120}\b(?:may|can|allowed|okay|ok)\b"
    r"[^\n.]{0,120}\b(?:kill|restart)\b",
    re.IGNORECASE,
)
_COMMAND_BLOCKS = re.compile(
    r"^[ \t]*```(?:bash|sh)\n(.*?)\n[ \t]*```",
    re.DOTALL | re.MULTILINE,
)
_ONE_SHOT_SEND_KEYS = re.compile(r"send-keys[^\n]*--\s*'[^']*'\s+Enter")
_NON_PARAMETERIZABLE_REQUIREMENTS = frozenset(
    ("acting-daemon-prohibition", "one-shot-send-keys-enter")
)
_STALL_MODE_2 = "stall-mode-2-armed-re-entry"
_ACTING_DAEMON = "acting-daemon-prohibition"
_ONE_SHOT = "one-shot-send-keys-enter"
_OVERRIDE = "acting-daemon-override"


def _has_stall_mode_2_realization(*, charter: str) -> bool:
    lowered = charter.lower()
    has_literal = "armed re-entry" in lowered
    has_never_end_turn = "never end" in lowered and "turn" in lowered
    has_open_work = "open obligation" in lowered or "work remains" in lowered
    has_wake = "watcher" in lowered or "wake" in lowered or "timer" in lowered
    has_mechanism = "mechanism" in lowered or "armed" in lowered or "start" in lowered
    return has_literal or all((has_never_end_turn, has_open_work, has_wake, has_mechanism))


def _has_acting_daemon_prohibition(*, charter: str) -> bool:
    return "never kill the acting overseer daemon" in charter.lower()


def _command_blocks(*, charter: str) -> list[str]:
    return [match.group(1) for match in _COMMAND_BLOCKS.finditer(charter)]


def non_parameterizable_requirements() -> frozenset[str]:
    return _NON_PARAMETERIZABLE_REQUIREMENTS


def banned_requirements(*, charter: str) -> list[str]:
    banned = [
        _ONE_SHOT for block in _command_blocks(charter=charter) if _ONE_SHOT_SEND_KEYS.search(block)
    ]
    if _ACTING_DAEMON_OVERRIDE.search(charter) is not None:
        banned.append(_OVERRIDE)
    return banned


def missing_requirements(*, charter: str) -> list[str]:
    missing: list[str] = []
    if not _has_stall_mode_2_realization(charter=charter):
        missing.append(_STALL_MODE_2)
    if not _has_acting_daemon_prohibition(charter=charter):
        missing.append(_ACTING_DAEMON)
    missing.extend(banned_requirements(charter=charter))
    return missing
