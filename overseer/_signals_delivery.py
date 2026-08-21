"""Queued cross-session delivery parsing for pane captures."""

from __future__ import annotations

import re

from _signals_context import strip_ansi

__all__: list[str] = ["queued_cross_session_delivery_sender"]

# A cross-session delivery queued behind a Claude picker renders as a sender
# header BELOW the picker, then one or more four-space-indented body rows:
#   ``  @ livespec-console-beads-fabro-foreman❯``
#   ``    Console foreman, decision-relevant update ...``
# Verified live 2026-08-19 from tmux session `delivery-path-speed-and-caching`;
# the sender is arbitrary and captured, while the end-anchored trailing `❯` is
# the structural difference from ordinary prompt/picker shapes. No Codex analogue
# has been observed yet, so this detector is Claude-shape only.
_QUEUED_DELIVERY_HEADER_RE = re.compile(r"^  @ (?P<sender>\S.*?)❯$")


def queued_cross_session_delivery_sender(*, capture_text: str) -> str | None:
    """Sender name for a queued cross-session delivery block, if visible."""
    lines = [strip_ansi(text=raw).rstrip() for raw in capture_text.splitlines()]
    for index, line in enumerate(lines[:-1]):
        match = _QUEUED_DELIVERY_HEADER_RE.match(line)
        if match is None:
            continue
        body = lines[index + 1]
        if body.startswith("    ") and body[4:].strip():
            return match.group("sender").strip()
    return None
